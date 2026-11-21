# Typed Python ↔ React bridges

[Documentation index](README.md) · [Extensions](extensions.md) · [Authorization](authorization.md)

Bridges expose **explicit, authenticated HTTP operations**, not arbitrary Python execution from React. They validate input and output with Pydantic models; the build tools generate a TypeScript client for registered bridge methods.

## Python definition

```python
from pydantic import BaseModel
from pyntral import Bridge

class AssetInput(BaseModel):
    asset_id: int

class AssetOutput(BaseModel):
    url: str
    filename: str

def resolve_asset(payload: AssetInput, ctx) -> AssetOutput:
    asset = ctx.session.get(FileAsset, payload.asset_id)
    if asset is None:
        from pyntral.orm import AdminError
        raise AdminError(404, "Asset not found", "not_found")
    # Apply authorization to asset access in production code.
    return AssetOutput(url=asset.public_url, filename=asset.filename)

admin.add_bridge(Bridge(
    name="resolve-asset", input_model=AssetInput, output_model=AssetOutput,
    handler=resolve_asset, description="Resolve a public asset URL",
    min_role=None,
))
```

A bridge handler accepts the validated input model and a `BridgeContext` with `principal` and `session`. It may be synchronous or asynchronous. If the operation returns user-specific data, enforce an explicit check for the current principal (for example with role thresholds and a scoped database query). `min_role` is an optional coarse threshold, **not row-level authorization**.

## Generate the client

```bash
uv run pyntral types examples.shop.app:app
# Or during the normal build:
uv run pyntral build --app examples.shop.app:app
```

Generation writes `.pyntral/generated/bridges.ts` **without a Vite build**. For VS Code autocomplete in this monorepo, run:

```bash
uv run pyntral types examples.shop.app:app --editor
uv run pyntral types examples.shop.app:app --watch
```

The first command creates/updates the editor TypeScript configuration without replacing any existing root `tsconfig.json`. The second watches Python changes and automatically refreshes the bridge declarations. You can also copy the generated client with `--out admin/generated/bridges.ts`. An already running React dev server may need to reload to pick up changed contracts; production builds still need a rebuild.

In a registered custom component:

```tsx
import { resolveAsset } from "@pyntral/generated";
import { useQuery } from "@tanstack/react-query";

export function AssetPreview({ assetId }: { assetId: number }) {
  const result = useQuery({
    queryKey: ["asset", assetId],
    queryFn: () => resolveAsset({ asset_id: assetId }),
  });
  if (!result.data) return <span>Loading…</span>;
  return <img src={result.data.url} alt={result.data.filename} />;
}
```

The request is sent to `POST /admin/api/bridge/resolve-asset` with the normal admin session and CSRF header. The server returns `{ "result": ... }` according to the declared output schema. A client function is generated from the Pydantic model definitions, not from the database model itself.

## Limits and security

- The API is available only to authenticated sessions; it does not bypass the admin's security model.
- The bridge is independent of ORM resource permissions; **a bridge can accidentally leak data** if its handler fails to check access.
- Use primitive Pydantic DTOs, not SQLAlchemy objects, as boundary types.
- Treat image and CDN URLs as sensitive if private: generate scoped, expiring URLs when necessary.
- The automatic client is compiled from imports and must be regenerated when Python bridge definitions change.

For a complete example, see [`examples/shop/app.py`](../examples/shop/app.py) and [`admin/AssetImage.tsx`](../admin/AssetImage.tsx).
