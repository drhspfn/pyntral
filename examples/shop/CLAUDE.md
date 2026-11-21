# Shop example instructions

These rules extend [the root CLAUDE.md](../../CLAUDE.md).

`examples/shop/` is the **required runnable showcase** for new Pyntral features; it is not just a smoke-test fixture.

- Every new user-facing capability must be reachable in the Shop UI in the same PR as the implementation. Describe exactly where to click and what to expect in this directory's `README.md`.
- Exercise the real Python API/ORM/actions/bridges. Never fake backend functionality with local TSX-only behavior.
- Ensure seed scripts are idempotent, including when a developer already has `shop.db`. Add seed data for new tables without deleting or resetting existing customers, orders or products.
- Keep credentials in `.env` and documented setup commands; do not embed secrets or unsafe auth bypasses.
- Register custom TSX in `pyntral.components.json`. Verify the custom Shop build and avoid changes that break the prebuilt generic SPA.
- Test successful workflows, invalid input, authorization and relevant database constraints. Add an integration test when introducing new demo models or actions.
- Avoid isolated or inaccessible demo fragments: the feature should be discoverable from the sidebar or a documented resource detail.
