"""Run after installing pyntral[kafka] and provisioning Kafka topic.

    uv run python examples/events/kafka_worker.py
"""
import asyncio
import os

from pyntral import KafkaEventBus, ResourceUpdated


async def main() -> None:
    bus = KafkaEventBus(
        os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        topic=os.getenv("KAFKA_TOPIC", "pyntral.events"),
        group_id="pyntral.example_worker",
    )

    @bus.on(ResourceUpdated, resource="agents")
    async def changed(event: ResourceUpdated) -> None:
        print(event.event_id, event.record_id,
              [(field.name, field.kind) for field in event.fields])

    async with bus:
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
