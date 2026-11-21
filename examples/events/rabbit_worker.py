"""Run separately after installing pyntral[rabbitmq] and starting RabbitMQ.

    uv run python examples/events/rabbit_worker.py

Workers sharing a queue compete; use distinct queue names for independent subscribers.
"""
import asyncio
import os

from pyntral import RabbitMQEventBus, ResourceCreated, ResourceUpdated


async def main() -> None:
    bus = RabbitMQEventBus(
        os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/"),
        queue="pyntral.example_worker",
    )

    @bus.on("resource.*", resource="agents")
    async def changed(event: ResourceCreated | ResourceUpdated) -> None:
        print(event.event_id, event.type, event.record_id,
              [(field.name, field.kind) for field in event.fields])

    async with bus:
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
