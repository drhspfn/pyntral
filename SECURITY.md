# Security policy

Pyntral is a **public beta**, not a certified security product. Do not expose it to the public Internet without a reviewed authentication, authorization, HTTPS and deployment configuration.

## Reporting vulnerabilities

If a private maintainer contact is available on the eventual repository, use that confidential channel. Until a private reporting address is published, **do not post exploit details or credentials in a public issue**; contact the maintainer privately through an existing trusted channel. This repository does not yet claim a dedicated security response SLA.

## Deployment expectations

- Require HTTPS and `secure_cookie=True` outside localhost.
- Use a strong, stable secret key stored outside the source tree and rotate it as part of an incident response plan.
- Configure real user authentication and server-side resource/row/field permissions.
- Do not return passwords, secrets or sensitive media URLs through resource fields, bridges, custom callbacks or logs.
- Use CSRF-aware API clients for mutations; restrict CORS and embedding appropriately at the proxy/host layer.
- Rate-limit login endpoints via host infrastructure if exposed to untrusted networks.
- Restrict RabbitMQ/Kafka credentials and topics/queues to trusted services. Broker payloads contain IDs and metadata but no application-level ACL filtering.
- Run dependency scanning and a security review before a stable production release.

## Supported versions

| Version | Security support |
| --- | --- |
| `1.0.0b2` | Best-effort beta maintenance with no guaranteed SLA |

See [authentication](docs/authentication.md), [authorization](docs/authorization.md) and [deployment](docs/deployment.md).
