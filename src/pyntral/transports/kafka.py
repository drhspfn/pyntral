"""Kafka event transport, with manual offsets and ordered partition retries."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..events import AdminEvent, DeliveryReport
from .base import BrokerEventBus, EventDecodeError, decode_event, encode_event


class KafkaEventBus(BrokerEventBus):
    def __init__(self, bootstrap_servers: str | list[str], *,
                 topic: str = "pyntral.events", group_id: str = "pyntral",
                 consume: bool = True, retry_delay: float = 1.0,
                 auto_offset_reset: str = "latest") -> None:
        super().__init__()
        if not topic or not group_id or retry_delay <= 0:
            raise ValueError("topic/group_id must be nonempty and retry_delay positive")
        if auto_offset_reset not in ("earliest", "latest"):
            raise ValueError("auto_offset_reset must be 'earliest' or 'latest'")
        self.bootstrap_servers = bootstrap_servers
        self.topic, self.group_id = topic, group_id
        self.consume, self.retry_delay = consume, retry_delay
        self.auto_offset_reset = auto_offset_reset
        self._producer: Any = None
        self._consumer: Any = None
        self._task: asyncio.Task[None] | None = None
        self._logger = logging.getLogger("pyntral.events")

    async def start(self) -> None:
        if self._started:
            return
        try:
            from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
        except ImportError as exc:
            raise RuntimeError("Kafka requires: uv add 'pyntral[kafka]'") from exc
        producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers,
                                     acks="all", enable_idempotence=True)
        await producer.start()
        consumer = None
        try:
            if self.consume:
                consumer = AIOKafkaConsumer(
                    self.topic, bootstrap_servers=self.bootstrap_servers,
                    group_id=self.group_id, enable_auto_commit=False,
                    auto_offset_reset=self.auto_offset_reset,
                )
                await consumer.start()
            self._producer, self._consumer = producer, consumer
            self._started = True
            if consumer is not None:
                self._task = asyncio.create_task(self._run(), name="pyntral-kafka")
        except BaseException:
            if consumer is not None:
                await consumer.stop()
            await producer.stop()
            self._started = False
            raise

    async def _run(self) -> None:
        # One sequential loop: committing a later offset must never skip a failed
        # earlier record from the same partition. A poison event blocks progress
        # until an operator fixes it (invalid envelopes are logged and skipped).
        assert self._consumer is not None
        try:
            from aiokafka import TopicPartition
            async for message in self._consumer:
                try:
                    event = decode_event(message.value)
                except EventDecodeError:
                    self._logger.exception("events.invalid_payload transport=kafka")
                    await self._consumer.commit({TopicPartition(message.topic, message.partition): message.offset + 1})
                    continue
                while True:
                    try:
                        report = await self._deliver(event)
                        if report.failed:
                            raise RuntimeError(f"{report.failed} subscribers failed")
                        await self._consumer.commit({TopicPartition(message.topic, message.partition): message.offset + 1})
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self._logger.exception("events.consumer_failed transport=kafka event_id=%s", event.event_id)
                        await asyncio.sleep(self.retry_delay)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._logger.exception("events.consumer_loop_failed transport=kafka")
            raise

    async def publish(self, event: AdminEvent) -> DeliveryReport:
        self._require_started()
        assert self._producer is not None
        await self._producer.send_and_wait(self.topic, encode_event(event),
                                            key=(event.resource or event.type).encode("utf-8"))
        return DeliveryReport(delivered=0, failed=0)

    async def close(self) -> None:
        self._started = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        try:
            if self._consumer is not None:
                await self._consumer.stop()
        finally:
            if self._producer is not None:
                await self._producer.stop()
            self._producer = self._consumer = None
