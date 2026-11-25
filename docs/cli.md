# CLI, build cache, and developer workflow

[Documentation index](README.md) · [Getting started](getting-started.md)

`pyntral` is a Python console command installed with the package. Run it through `uv run` from the repository root while developing Pyntral.

## Commands

| Command | Function |
| --- | --- |
| `pyntral init-env [--username NAME]` | Prompt for a password, write local `.env` credentials (gitignored). |
| `pyntral hash-password [--password VALUE]` | Generate a scrypt password hash. Omit the flag to avoid recording a password in shell history. |
| `pyntral doctor` | Check toolchain paths and whether a built SPA is present. |
| `pyntral init-ui` | Scaffold `pyntral.components.json` and a sample TSX field component. |
| `pyntral types MODULE:app [--out PATH] [--editor]` | Generate bridges without building the SPA, optionally copy types and configure VS Code. |
| `pyntral types MODULE:app --watch` | Regenerate types in a fresh Python subprocess as source files change. |
| `pyntral dev MODULE:app` | Run Uvicorn and Vite in development. |
| `pyntral build [--force] [--app MODULE:app]` | Typecheck and bundle the SPA using a content-based build cache. |
| `pyntral export-ui DESTINATION` | Copy a compiled SPA to an absent/empty runtime directory. |
| `pyntral schema MODULE:app [--out PATH] [--format markdown\|json]` | Generate resource documentation without building the SPA. |

All commands accept `--project PATH` **before the subcommand** to point at another project directory.

## Dev flags

```bash
uv run pyntral dev examples.shop.app:app \
  --backend-port 8000 --frontend-port 5173 --base /admin/ \
  --uvicorn-log-level WARNING --log-level INFO \
  --log-http errors --slow-request-ms 750
```

Additional flags: `--access-log`, `--log-format compact|json`, `--log-channel NAME=LEVEL` (repeatable), `--log-event EVENT=ON|OFF` (repeatable), `--log-file PATH`, and `--log-channel-file CHANNEL=PATH` (repeatable). By default the CLI suppresses Uvicorn per-request access logging, not errors or admin event logs.

## Local workspace

```text
.pyntral/
├── ui/                     # Staged React/Vite sources, npm dependencies and lockfile
├── generated/bridges.ts    # Generated TS bridge bindings
├── tsconfig.editor.json    # Generated VS Code TypeScript config
├── npm-cache/              # npm download cache
├── dist/                   # Production HTML/JS/CSS bundle
└── build.json               # Last successful build fingerprint
```

`pyntral dev` copies packaged UI sources only when their hash changes; npm dependencies are reinstalled when the manifest changes. The build fingerprint includes UI sources, extension configuration/files, generated types and public base path. Running `pyntral build` again may be a cache hit; `--force` always rebuilds.

Do not commit `.pyntral/`. Remove its generated UI files to force a clean
rebuild. If the application also uses a subdirectory for file storage, preserve
that directory. Keep `.env` and the application database separate.

## External TSX components

Use `pyntral.components.json` at the project root. The CLI checks that extension paths resolve inside the project. The build imports them into the Vite virtual module registry. Run `pyntral types` or pass `--app` if you use bridges; the component config may also specify an `app` import string.

## Production bundles

**Standard installation:** `uv add pyntral` or `pip install pyntral` includes an already-built generic SPA. FastAPI serves it automatically at `/admin/`; there is no need to run this CLI command or install Node.js.

**Customized application:** when adding your own TSX fields, pages or dialogs, run:

```bash
uv run pyntral build --force --app examples.shop.app:app
```

The backend serves `.pyntral/dist/` automatically from the current working directory when built. You can override it with `Admin(dist_dir=...)` or `PYNTRAL_DIST=/absolute/path`. Both production bundles resolve the configured `Admin.path` and ASGI `root_path` at runtime. Use `pyntral dev --base /console/` for Vite development against `Admin(path="/console")`.

**Maintainers:** the PyPI workflow runs `uv run python scripts/build_release.py`, which compiles a generic SPA in an empty temporary host project and then bundles it into Python wheel/sdist. This release script is not part of a consuming application's installation process.

## Windows

The CLI resolves `npm.cmd` on Windows and `npm` elsewhere for dependency installation and builds. Development launches the actual Vite JavaScript entry point with Node and keeps it running while a separate Uvicorn process is restarted on Python changes. Child processes have isolated process groups; reloads do not send Ctrl+C to the shared console. A failed Python import leaves Vite and the watcher running, and saving corrected Python code retries the backend. Ctrl+C stops both servers. Run the same `uv run pyntral ...` commands in PowerShell. If Node is missing, install Node 22.12+ and ensure npm is on `PATH` before retrying.

## Reproducibility

Python dependencies are specified in `pyproject.toml`; create and commit `uv.lock` as part of the maintainer's release process. The frontend dependency manifest lives in `src/pyntral/ui/package.json`; generated npm lock state is currently in `.pyntral/ui/`. For fully reproducible frontend builds, a reviewed lockfile and `npm ci` workflow should be committed before a stable release.

## Fast bridge generation and editor support

```bash
uv run pyntral types examples.shop.app:app --editor
uv run pyntral types examples.shop.app:app --out admin/generated/bridges.ts
uv run pyntral types examples.shop.app:app --watch
```

These commands do **not** run npm, ESLint, TypeScript or Vite. Generated types are always maintained in `.pyntral/generated/bridges.ts` and may also be copied to `--out`; the extra output must stay inside the project. `--editor` creates `.pyntral/tsconfig.editor.json` and, if the root lacks one, a small `tsconfig.json` extending it. Existing root TS configs are **never overwritten**: merge the generated path mappings yourself or extend the generated config.

`--watch` watches Python source and the component manifest; it reruns generation in a new interpreter so that changed modules are imported fresh. Its errors are reported and watching continues. Use Ctrl+C to stop. VS Code needs React type packages installed in `.pyntral/ui/node_modules` (start `pyntral dev` once or run a normal build).

## Export a prebuilt custom UI

`pyntral export-ui DESTINATION` copies the compiled `.pyntral/dist` directory
to an absent or empty directory, excluding the development workspace and npm
dependencies. Run `pyntral build --app MODULE:app` first. Set
`PYNTRAL_DIST` to the exported directory in the Python-only runtime.
See [multi-stage deployment](deployment.md#custom-ui-in-a-python-only-runtime).

### Dashboard extensions and editor setup

The dashboards manifest category is included in extension source fingerprints,
Vite registration, linting and generated editor includes. After adding a TSX
dashboard, run `pyntral types MODULE:app --editor` for editor support and
`pyntral build --app MODULE:app` for deployment. See [dashboard configuration](extensions.md#home-and-category-dashboards).
