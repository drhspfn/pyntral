# Publishing Pyntral to PyPI

[Documentation index](README.md) · [Installation](getting-started.md) · [Deployment](deployment.md)

**Pyntral is distributed only as a Python package** (`pyntral`). The React SPA is an internal implementation detail. There is no npm registry publication and no separate frontend installation for ordinary consumers.

## Two supported installation modes

| Use case | Install | Build required in consumer app? | Node.js required? |
| --- | --- | --- | --- |
| Standard model-driven admin | `uv add pyntral` / `pip install pyntral` | No | No |
| Admin with custom TSX fields, pages or dialogs | Same `uv add pyntral` | Yes, run `pyntral build --app your.module:app` | Yes, **only at build/development time** |

The official wheel contains a **generic production SPA** at `pyntral/web_dist/`. FastAPI serves this bundle by default. Custom React components cannot be precompiled into a reusable wheel because they belong to the consuming application; compile them into the application's `.pyntral/dist/`, or pass `Admin(dist_dir=...)` explicitly. This does not change the Python package being installed.

## Release pipeline

`.github/workflows/publish-pypi.yml` runs when a Git tag `v*` is pushed. It:

1. Verifies `v<version>` matches `pyproject.toml` (for example `v1.0.0b3`).
2. Runs Python and JavaScript logic tests.
3. Compiles the **generic** frontend using a temporary project without application-specific components or bridge contracts. This build runs ESLint, TypeScript and Vite.
4. Copies its production bundle to `src/pyntral/web_dist/` and builds the Python wheel and sdist with `uv build`.
5. Rejects distributions that do not contain the HTML, JS and CSS assets.
6. Installs the generated wheel in a clean Python environment and verifies bundled files are available.
7. Uploads verified distributions as a GitHub artifact; a separate permission-restricted job publishes them to PyPI via **Trusted Publishing (OIDC)**.

`web_dist` is generated and gitignored, but is included in the built wheel and sdist. Generic builds must not import the shop demo or bake local credentials, data, TSX extensions or bridge definitions into the public package.

## One-time PyPI setup

1. Own the `pyntral` project name on PyPI (or register a *pending publisher* if this is a first publication).
2. Add a GitHub Actions Trusted Publisher for the **actual GitHub owner/repository**, workflow file **`publish-pypi.yml`**, and environment **`pypi`**. These values must match your GitHub repository and workflow.
3. Create and protect the GitHub environment `pypi` (prefer a required approval).
4. Add the repository's actual project URLs to `[project.urls]` in `pyproject.toml` after the GitHub destination exists.

No PyPI API token is stored in GitHub Secrets. The publish job has `id-token: write`; build jobs do not. The workflow does **not** create or reserve the PyPI project on your behalf.

## Local release validation

With Node.js and uv available:

```bash
uv sync --extra dev
uv run python scripts/build_release.py
```

The release script builds the generic SPA and verifies both `dist/pyntral-*.whl` and `dist/pyntral-*.tar.gz`. You may supply `--from-dist /path/to/generic/build` only if that directory was compiled from a blank Pyntral project. Do not pass an application's customized SPA.

Check the wheel in an isolated environment:

```bash
uv venv /tmp/pyntral-check
uv pip install --python /tmp/pyntral-check/bin/python dist/*.whl httpx
/tmp/pyntral-check/bin/python scripts/smoke_installed.py
```

On Windows, use `Scripts\python.exe` under the environment directory.

After confirming all checks, create and push the release tag:

```bash
git tag v1.0.0b3
git push origin v1.0.0b3
```

Check the workflow outcome and PyPI package files before announcing availability. **No PyPI publication is performed by creating this repository.**

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/) and [uv publishing guidance](https://docs.astral.sh/uv/guides/publish/).

## Version consistency before tagging

Update pyproject.toml and uv.lock with uv version / uv lock, and set
src/pyntral/ui/package.json to the corresponding SemVer version (Python
1.0.0b3 = frontend 1.0.0-beta.3). No npm install is needed for a version-only
change. Update README, CHANGELOG, and tests/test_public_release.py.
Run `uv run --locked --extra dev pytest -q` and wait for PR checks before tagging.
