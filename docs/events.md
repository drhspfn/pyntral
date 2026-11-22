# Typed events and broker transports

[Documentation index](README.md) · [Logging](logging.md) · [Authorization](authorization.md)

Pyntral provides metadata-only events. Event messages contain IDs and affected field **names/types**; they deliberately do not carry old/new values, ORM model instances, query payloads, or tokens. A consumer that needs record data must perform a separately authorized read.

## Built-in event types

- `ResourceCreated`, `ResourceUpdated`, `ResourceDeleted` (`resource.created`, `resource.updated`, `resource.deleted`)
- `ActionExecuted` (`action.executed`)
- `LoginSucceeded`, `LoginFailed`, `LogoutSucceeded`
- `CustomEvent` for a named application signal

The immutable Pydantic envelope contains `event_id`, `occurred_at`, `correlation_id`, `resource`, `record_id`, `actor_id`, and `fields`. Each `FieldRef` has `name` and `kind`, never a value.

```python
from pyntral import ResourceUpdated

@admin.events.on(ResourceUpdated, resource="agents")
async def agent_changed(event: ResourceUpdated):
    print(event.resource, event.record_id)
    print([(field.name, field.kind) for field in event.fields])
```

You can subscribe with `admin.events.subscribe(ResourceUpdated, handler, resource="agents")` and use event type strings/wildcard patterns for matching. `InMemoryEventBus(on_error="log" | "raise")` supports sync and async subscribers. Subscription callbacks are local to the process.

## Permission-checked data retrieval

```python
record = await admin.read_event_record(event, service_principal)
```

The principal must be a verified `Principal`; Pyntral resolves it through the configured backend and checks `show`, field thresholds, and row-level scopes. An unauthorized consumer gets 403 or 401; a deleted row returns 404. Do not treat `actor_id` as a service principal.

## Event transport interface

`EventTransport` defines `subscribe(...)`, `on(...)`, `publish(event) -> DeliveryReport`, `start()`, and `close()`. A `DeliveryReport` contains `delivered` and `failed` counts for local dispatch; broker publish acknowledgements do **not** imply that application subscribers have consumed messages.

| Bus | Delivery properties | Multi-worker semantics |
| --- | --- | --- |
| `InMemoryEventBus` | In-process, volatile, no durable queue | Each process sees its own events only |
| `RabbitMQEventBus` | Persistent messages, publisher confirms, manual ACK/Reject | Shared queue consumers compete for messages |
| `KafkaEventBus` | Producer acks, consumer group, manual offset commit | Partition distribution within a consumer group |

### RabbitMQ

```bash
# Inside this repository
uv sync --extra rabbitmq
# In another project after publication
uv add 'pyntral[rabbitmq]'
```

```python
from pyntral import RabbitMQEventBus

bus = RabbitMQEventBus(
    "amqp://guest:guest@localhost/", exchange="myapp.admin.events",
    queue="myapp.admin.workers", prefetch=20,
)
admin = Admin(app, session_factory=SessionLocal, auth=auth,
              secret_key=secret, event_bus=bus)
```

The bus creates a durable topic exchange and durable queue, publishes persistent messages with confirms, and ACKs successful handlers. Invalid payloads or failed handlers are rejected **without requeue**; configure a RabbitMQ dead-letter exchange and queue yourself to retain rejected messages. Multiple processes using the same queue are competing consumers, **not** independent copies of each message. For fan-out, give independent subscriber groups distinct queues.

### Kafka

```bash
uv sync --extra kafka
```

```python
from pyntral import KafkaEventBus

bus = KafkaEventBus(
    "localhost:9092", topic="myapp.admin.events", group_id="myapp.admin-workers",
)
admin = Admin(app, session_factory=SessionLocal, auth=auth,
              secret_key=secret, event_bus=bus)
```

Kafka uses `acks="all"`, an idempotent producer, and manual consumer group offset commits after successful handler processing. The consumer processes messages sequentially to avoid committing later offsets past failures; a failed event can block its processing loop until repaired. No dead-letter integration is built in.

### Lifecycle

With default `auto_start_events=True`, Pyntral composes the **parent FastAPI lifespan** and starts/stops the bus with the host application. For a separately managed worker, set `auto_start_events=False` and use `async with bus:` or explicit `await bus.start()`/`await bus.close()` as appropriate. See the runnable worker patterns in [`examples/events/`](../examples/events/).

## Important delivery limitations

- Events for built-in CRUD are emitted **after successful SQLAlchemy commit**, but there is still a crash window between commit and broker publication. This is **not** transactional outbox delivery.
- RabbitMQ and Kafka subscribers must be **idempotent**, since retries/redelivery can occur. There is no exactly-once business-operation guarantee.
- Subscriber code is trusted server code; broker credentials restrict network access, not per-resource permissions. A record is never embedded in the event.
- Custom action handlers may manage their own transactions; their success event cannot attest to a commit performed (or not performed) inside arbitrary user code.
- Live RabbitMQ/Kafka infrastructure validation is required before production use.

See [deployment and readiness](deployment.md#release-readiness).

## Browser cache invalidation (opt-in)

Set `Admin(realtime_updates=True)` to expose an authenticated
`GET /admin/api/realtime` Server-Sent Events stream. Browsers subscribe only
after login and invalidate visible TanStack Query caches when they receive an
`invalidate` event. **No resource name, record ID, actor or changed values are
sent over the stream**, and each subsequent API request still enforces normal
permissions. Signals are bounded and coalesced in memory, and not guaranteed
across processes or restarts. Shared RabbitMQ queues use competing consumers:
configure independent broadcast delivery for each web worker before relying on
multi-worker realtime updates.



`Admin(event_publish_timeout=2.0)` limits how long a request waits for
publication. A timeout is logged and the committed HTTP operation can still
succeed. A broker may have accepted the message before the timeout, so consumers
must be idempotent. Request-path subscribers should be asynchronous and
cooperate with cancellation. SSE connections are limited to five minutes and
recheck session validity before emitting an invalidation or heartbeat.
