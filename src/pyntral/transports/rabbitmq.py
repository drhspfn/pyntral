"""RabbitMQ event transport. Requires pyntral[rabbitmq].

Queue semantics: workers sharing a queue compete; different queue names receive
independent copies. Configure a dead-letter exchange for rejected poison events.
"""
from __future__ import annotations

import logging
from typing import Any

from ..events import AdminEvent, DeliveryReport
from .base import BrokerEventBus, EventDecodeError, encode_event


class RabbitMQEventBus(BrokerEventBus):
    def __init__(self, url: str, *, exchange: str = "pyntral.events",
                 queue: str = "pyntral.default", prefetch: int = 20,
                 consume: bool = True, queue_arguments: dict[str, Any] | None = None) -> None:
        super().__init__()
        if not exchange or not queue or prefetch < 1:
            raise ValueError("exchange/queue must be nonempty and prefetch positive")
        self.url, self.exchange_name, self.queue_name = url, exchange, queue
        self.prefetch, self.consume = prefetch, consume
        self.queue_arguments = dict(queue_arguments or {})
        self._connection: Any = None
        self._channel: Any = None
        self._exchange: Any = None
        self._consumer: Any = None
        self._consumer_tag: str | None = None
        self._logger = logging.getLogger("pyntral.events")

    async def start(self) -> None:
        if self._started:
            return
        try:
            import aio_pika
        except ImportError as exc:
            raise RuntimeError("RabbitMQ requires: uv add 'pyntral[rabbitmq]'") from exc
        connection = await aio_pika.connect_robust(self.url)
        try:
            channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
            await channel.set_qos(prefetch_count=self.prefetch)
            exchange = await channel.declare_exchange(
                self.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True,
            )
            # Declare the durable queue even in publisher-only mode, so messages
            # survive while consumers are disconnected.
            queue = await channel.declare_queue(self.queue_name, durable=True,
                                                arguments=self.queue_arguments or None)
            await queue.bind(exchange, routing_key="events")
            tag = None
            if self.consume:
                tag = await queue.consume(self._on_message, no_ack=False)
            self._connection, self._channel, self._exchange = connection, channel, exchange
            self._consumer, self._consumer_tag = queue, tag
            self._started = True
        except BaseException:
            await connection.close()
            raise

    async def _on_message(self, message: Any) -> None:
        # Invalid payloads are poison messages: reject, never retry indefinitely.
        try:
            from .base import decode_event
            event = decode_event(message.body)
        except EventDecodeError:
            self._logger.exception("events.invalid_payload transport=rabbitmq")
            await message.reject(requeue=False)
            return
        try:
            report = await self._deliver(event)
            if report.failed:
                raise RuntimeError(f"{report.failed} subscribers failed")
        except Exception:
            self._logger.exception("events.consumer_failed transport=rabbitmq event_id=%s", event.event_id)
            # Requeue is intentionally off to prevent a hot poison-message loop.
            # Configure DLX/DLQ on the queue for retry processing if needed.
            await message.reject(requeue=False)
        else:
            await message.ack()

    async def publish(self, event: AdminEvent) -> DeliveryReport:
        self._require_started()
        import aio_pika
        assert self._exchange is not None
        await self._exchange.publish(
            aio_pika.Message(body=encode_event(event), message_id=event.event_id,
                             content_type="application/json", delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key="events", mandatory=True,
        )
        # 'delivered' counts local callbacks only, not broker consumer deliveries.
        return DeliveryReport(delivered=0, failed=0)

    async def close(self) -> None:
        self._started = False
        try:
            if self._consumer is not None and self._consumer_tag is not None:
                await self._consumer.cancel(self._consumer_tag)
        finally:
            try:
                if self._connection is not None:
                    await self._connection.close()
            finally:
                self._consumer = self._consumer_tag = None
                self._connection = self._channel = self._exchange = None
