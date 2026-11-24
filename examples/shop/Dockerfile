# Production smoke-test for the shop demo. Build from the REPOSITORY ROOT context:
# docker compose -f examples/shop/compose.yaml build
FROM ghcr.io/astral-sh/uv:0.9-python3.13-bookworm AS build
WORKDIR /app
# Node.js is only needed to compile the admin SPA; no Node in runtime.
COPY --from=node:22-bookworm /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
COPY . /app
RUN uv sync --locked --no-dev
# Runtime credentials are NOT embedded into the image. Only temporary credentials
# are provided for importing the demo during Pydantic/TypeScript generation.
RUN ADMIN_USERNAME=build-only \
    ADMIN_PASSWORD_HASH="$(uv run python -c 'from pyntral.auth import hash_password; print(hash_password("build-only"))')" \
    APP_SECRET_KEY='temporary-build-only-secret-not-used-at-runtime' \
    uv run --locked pyntral build --app examples.shop.app:app --force
RUN uv run --locked pyntral export-ui /app/admin-dist

FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYNTRAL_DIST=/app/admin-dist \
    DATABASE_URL=sqlite:////app/data/shop.db \
    SHOP_UPLOAD_ROOT=/app/data/uploads
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY --from=build /app/examples /app/examples
COPY --from=build /app/admin-dist /app/admin-dist
RUN useradd -m -u 10001 pyntral && mkdir -p /app/data && chown pyntral:pyntral /app/data
USER pyntral
EXPOSE 8000
CMD ["uvicorn", "examples.shop.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "warning"]
