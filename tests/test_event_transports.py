"""Transport contract, safety, acknowledgement and lifecycle without brokers."""
import asyncio
import io
import json
import logging
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from pyntral import LoggingConfig, ResourceUpdated
from pyntral.events import FieldRef
from pyntral.logging import configure_logging, emit, stop_logging
from pyntral.transports.base import EventDecodeError, decode_event, encode_event
from pyntral.transports.kafka import KafkaEventBus
from pyntral.transports.rabbitmq import RabbitMQEventBus


def event():
    return ResourceUpdated(resource="users", record_id="123", actor_id="admin",
                           fields=(FieldRef(name="email", kind="string"),))


def test_codec_version_roundtrip_and_redaction():
    wire = encode_event(event())
    decoded = decode_event(wire)
    assert decoded.type == "resource.updated"
    assert decoded.record_id == "123"
    assert decoded.fields[0].kind == "string"
    assert b"old_value" not in wire and b"new_value" not in wire
    with pytest.raises(EventDecodeError):
        decode_event(b'{"version":2,"event":{}}')
    with pytest.raises(EventDecodeError):
        decode_event(b'{"version":1,"event":{"type":"unknown.thing"}}')
    modified = json.loads(wire)
    modified["event"]["password"] = "secret"
    with pytest.raises(EventDecodeError):
        decode_event(json.dumps(modified).encode())
    with pytest.raises(ValueError):
        encode_event(ResourceUpdated(resource="users", record_id="1",
                                     fields=tuple(FieldRef(name="x" * 1000, kind="string") for _ in range(80))))


def test_events_are_separate_configurable_logger():
    stream = io.StringIO()
    configure_logging(stream=stream)
    try:
        policy = LoggingConfig(channels={"lifecycle": "OFF", "events": "DEBUG"})
        emit(policy, "lifecycle", "events.hidden")
        emit(policy, "events", "events.published", level="DEBUG", field_names=["name"])
        assert "events.hidden" not in stream.getvalue()
        assert "events.published" in stream.getvalue()
        assert "field_names" in stream.getvalue()
    finally:
        stop_logging()


def test_broker_missing_dependency_error(monkeypatch):
    # Simulates the optional extra being unavailable even on a full dev install.
    import builtins
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name in ("aio_pika", "aiokafka"):
            raise ImportError(name)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing)
    async def run():
        with pytest.raises(RuntimeError, match=r"pyntral\[rabbitmq\]"):
            await RabbitMQEventBus("amqp://unused").start()
        with pytest.raises(RuntimeError, match=r"pyntral\[kafka\]"):
            await KafkaEventBus("unused").start()
    asyncio.run(run())


def test_rabbit_consumer_ack_and_reject():
    class Message:
        def __init__(self, raw):
            self.body = raw
            self.acked = self.rejected = False
        async def ack(self): self.acked = True
        async def reject(self, requeue):
            assert requeue is False
            self.rejected = True

    async def run():
        bus = RabbitMQEventBus("amqp://unused")
        seen = []
        bus.subscribe(ResourceUpdated, seen.append)
        good = Message(encode_event(event()))
        await bus._on_message(good)
        assert good.acked and not good.rejected and len(seen) == 1
        invalid = Message(b"not json")
        await bus._on_message(invalid)
        assert invalid.rejected and not invalid.acked
        def fail(_): raise RuntimeError("subscriber failed")
        bus.subscribe(ResourceUpdated, fail)
        failed = Message(encode_event(event()))
        await bus._on_message(failed)
        assert failed.rejected and not failed.acked
    asyncio.run(run())


def test_kafka_commit_exact_offset_and_retry(monkeypatch):
    fake = types.ModuleType("aiokafka")
    class TP:
        def __init__(self, topic, partition):
            self.topic, self.partition = topic, partition
        def __hash__(self): return hash((self.topic, self.partition))
        def __eq__(self, other): return isinstance(other, TP) and vars(other) == vars(self)
    fake.TopicPartition = TP
    monkeypatch.setitem(sys.modules, "aiokafka", fake)
    commits = []
    class Consumer:
        def __aiter__(self):
            self.iter = iter([SimpleNamespace(value=encode_event(event()), topic="events",
                                              partition=2, offset=17)])
            return self
        async def __anext__(self):
            try: return next(self.iter)
            except StopIteration: raise StopAsyncIteration
        async def commit(self, offsets): commits.append(offsets)
    async def run():
        bus = KafkaEventBus("unused")
        bus._consumer = Consumer()
        received = []
        attempts = 0
        def handler(evt):
            nonlocal attempts
            attempts += 1
            if attempts == 1: raise RuntimeError("transient")
            received.append(evt.record_id)
        bus.subscribe(ResourceUpdated, handler)
        await bus._run()
        assert attempts == 2 and received == ["123"]
        assert commits == [{TP("events", 2): 18}]
    asyncio.run(run())


def test_parent_lifecycle_starts_broker():
    class Bus:
        def __init__(self): self.started = self.closed = False
        async def start(self): self.started = True
        async def close(self): self.closed = True
    from pyntral import Admin, LocalAuth, hash_password
    bus = Bus()
    app = FastAPI()
    Admin(app, session_factory=lambda: None, auth=LocalAuth("admin", hash_password("password123")),
          secret_key="x" * 64, event_bus=bus, secure_cookie=False)
    with TestClient(app):
        assert bus.started and not bus.closed
    assert bus.closed


def test_rabbit_publisher_confirm_lifecycle(monkeypatch):
    from enum import Enum
    fake = types.ModuleType("aio_pika")
    fake.ExchangeType = SimpleNamespace(TOPIC="topic")
    fake.DeliveryMode = SimpleNamespace(PERSISTENT="persistent")
    fake.Message = lambda **kw: SimpleNamespace(**kw)
    calls = []
    class Exchange:
        async def publish(self, message, routing_key, mandatory):
            calls.append(("publish", message, routing_key, mandatory))
    class Queue:
        async def bind(self, exchange, routing_key):
            calls.append(("bind", routing_key))
        async def consume(self, callback, no_ack):
            assert no_ack is False
            return "consumer-id"
        async def cancel(self, tag):
            calls.append(("cancel", tag))
    class Channel:
        async def set_qos(self, prefetch_count):
            calls.append(("qos", prefetch_count))
        async def declare_exchange(self, name, type, durable):
            assert durable and type == "topic"
            return Exchange()
        async def declare_queue(self, name, durable, arguments):
            calls.append(("queue", name, durable, arguments))
            return Queue()
    class Connection:
        async def channel(self, publisher_confirms, on_return_raises):
            assert publisher_confirms and on_return_raises
            return Channel()
        async def close(self):
            calls.append(("close",))
    async def connect(url):
        return Connection()
    fake.connect_robust = connect
    monkeypatch.setitem(sys.modules, "aio_pika", fake)

    async def run():
        bus = RabbitMQEventBus("amqp://unused", queue="my-queue", prefetch=4,
                               queue_arguments={"x-dead-letter-exchange": "dlx"})
        async with bus:
            await bus.start()  # idempotent
            report = await bus.publish(event())
            assert report.delivered == 0 and report.failed == 0
        assert calls.count(("close",)) == 1
        assert calls.count(("cancel", "consumer-id")) == 1
        assert any(item[0] == "publish" and item[2:] == ("events", True)
                   and decode_event(item[1].body).record_id == "123" for item in calls)
        assert ("queue", "my-queue", True, {"x-dead-letter-exchange": "dlx"}) in calls
    asyncio.run(run())


def test_kafka_producer_configuration_lifecycle(monkeypatch):
    fake = types.ModuleType("aiokafka")
    configs = []
    class Producer:
        def __init__(self, **kwargs):
            configs.append(kwargs)
        async def start(self): pass
        async def stop(self): configs.append("stopped")
        async def send_and_wait(self, topic, payload, key):
            configs.append((topic, decode_event(payload).record_id, key))
    fake.AIOKafkaProducer = Producer
    fake.AIOKafkaConsumer = object  # consume=False avoids a consumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake)
    async def run():
        bus = KafkaEventBus("localhost:9092", topic="audit", consume=False)
        await bus.start()
        report = await bus.publish(event())
        assert report.delivered == 0
        await bus.close()
    asyncio.run(run())
    assert configs[0]["acks"] == "all" and configs[0]["enable_idempotence"] is True
    assert ("audit", "123", b"users") in configs
    assert "stopped" in configs


def test_parent_custom_lifespan_is_preserved():
    from contextlib import asynccontextmanager
    from pyntral import Admin, LocalAuth, hash_password

    timeline = []

    @asynccontextmanager
    async def host_lifespan(app):
        timeline.append('host.start')
        try:
            yield {"host_ready": True}
        finally:
            timeline.append('host.close')

    class Bus:
        async def start(self): timeline.append('bus.start')
        async def close(self): timeline.append('bus.close')

    app = FastAPI(lifespan=host_lifespan)
    @app.get("/host")
    async def host(request: Request):
        return {"ready": request.state.host_ready}

    Admin(app, session_factory=lambda: None,
          auth=LocalAuth('admin', hash_password('password123')),
          secret_key='x' * 64, event_bus=Bus(), secure_cookie=False)
    with TestClient(app) as client:
        assert client.get("/host").json() == {"ready": True}
        assert timeline == ['host.start', 'bus.start']
    assert timeline == ['host.start', 'bus.start', 'bus.close', 'host.close']


def test_parent_custom_lifespan_without_autostart():
    from contextlib import asynccontextmanager
    from pyntral import Admin, LocalAuth, hash_password

    timeline = []

    @asynccontextmanager
    async def host_lifespan(app):
        timeline.append('host.start')
        yield
        timeline.append('host.close')

    class Bus:
        async def start(self): timeline.append('bus.start')
        async def close(self): timeline.append('bus.close')

    app = FastAPI(lifespan=host_lifespan)
    Admin(app, session_factory=lambda: None,
          auth=LocalAuth('admin', hash_password('password123')),
          secret_key='x' * 64, event_bus=Bus(),
          auto_start_events=False, secure_cookie=False)
    with TestClient(app):
        assert timeline == ['host.start']
    assert timeline == ['host.start', 'host.close']


def test_event_transport_start_failure_still_closes_host_lifespan():
    from contextlib import asynccontextmanager
    from pyntral import Admin, LocalAuth, hash_password

    timeline = []

    @asynccontextmanager
    async def host_lifespan(app):
        timeline.append('host.start')
        try:
            yield
        finally:
            timeline.append('host.close')

    class Bus:
        async def start(self):
            timeline.append('bus.start')
            raise RuntimeError('broker unavailable')
        async def close(self): timeline.append('bus.close')

    app = FastAPI(lifespan=host_lifespan)
    Admin(app, session_factory=lambda: None,
          auth=LocalAuth('admin', hash_password('password123')),
          secret_key='x' * 64, event_bus=Bus(), secure_cookie=False)
    with pytest.raises(RuntimeError, match='broker unavailable'):
        with TestClient(app):
            pass
    assert timeline == ['host.start', 'bus.start', 'host.close']


def test_kafka_close_releases_clients_after_task_failure():
    from unittest.mock import AsyncMock

    async def check():
        bus = KafkaEventBus("fixture")
        consumer = bus._consumer = SimpleNamespace(stop=AsyncMock())
        producer = bus._producer = SimpleNamespace(stop=AsyncMock())
        async def failed():
            raise RuntimeError("simulated consumer failure")
        bus._task = asyncio.create_task(failed())
        await asyncio.sleep(0)
        await bus.close()
        consumer.stop.assert_awaited_once()
        producer.stop.assert_awaited_once()

    asyncio.run(check())
