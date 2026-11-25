"""Managed Vite workspace and content-addressed build cache in .pyntral/."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from contextlib import closing

from watchfiles import DefaultFilter, watch

from .auth import hash_password
from .typegen import generate_types, configure_editor
from .logging import LoggingConfig

CACHE_NAME = ".pyntral"
IGNORED_DIRS = {"node_modules", "dist", ".git", ".vite"}
WATCH_EXCLUDED_DIRS = IGNORED_DIRS | {".venv", ".pyntral", "__pycache__", "build", "venv"}


def _source_ui() -> Path:
    return Path(__file__).parent / "ui"


def _cache(project: Path) -> Path:
    return project / CACHE_NAME


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    if not path.exists():
        return "missing"
    for entry in sorted(path.rglob("*")):
        if not entry.is_file() or any(part in IGNORED_DIRS for part in entry.relative_to(path).parts):
            continue
        hasher.update(str(entry.relative_to(path)).encode())
        hasher.update(entry.read_bytes())
    return hasher.hexdigest()


def _component_fingerprint(project: Path) -> str:
    config_path = project / "pyntral.components.json"
    if not config_path.exists():
        return "no-components"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    files = {
        f"{category}:{name}": relative
        for category in ("fields", "pages", "actions", "dialogs", "crud", "themes", "profile", "access", "auth", "sidebarHeaders", "sidebarFooters", "sidebarItems", "dashboards")
        for name, relative in config.get(category, {}).items()
    }
    hasher = hashlib.sha256(config_path.read_bytes())
    for name, relative in sorted(files.items()):
        path = (project / relative).resolve()
        if not path.is_relative_to(project.resolve()):
            raise ValueError(f"Extension must be under project directory: {name}")
        if not path.is_file() or path.suffix not in (".tsx", ".ts", ".jsx", ".js"):
            raise ValueError(f"Missing or unsupported extension file: {relative}")
        hasher.update(name.encode())
        hasher.update(path.read_bytes())
        # Imports in sibling files may change; hash entire containing directory.
        hasher.update(_digest(path.parent).encode())
    return hasher.hexdigest()


def sync_ui(project: Path) -> Path:
    source = _source_ui()
    if not (source / "package.json").exists():
        raise RuntimeError("UI sources were not packaged. Install from this project's source tree.")
    dest = _cache(project) / "ui"
    fingerprint = _digest(source)
    marker = dest / ".source.sha256"
    if not marker.is_file() or marker.read_text() != fingerprint:
        dest.mkdir(parents=True, exist_ok=True)
        # Keep node_modules and lockfile across source updates.
        # Prune removed templates without descending into the npm cache.
        visited: list[Path] = []
        for root, directories, files in os.walk(dest, topdown=True):
            directories[:] = [d for d in directories if d not in IGNORED_DIRS]
            current = Path(root)
            visited.append(current)
            for filename in files:
                if filename in (".source.sha256", ".dependencies.sha256", "package-lock.json"):
                    continue
                existing = current / filename
                if not (source / existing.relative_to(dest)).exists():
                    existing.unlink()
        for directory in reversed(visited):
            if directory != dest and not (source / directory.relative_to(dest)).exists() and not any(directory.iterdir()):
                directory.rmdir()
        for entry in source.rglob("*"):
            relative = entry.relative_to(source)
            if any(p in IGNORED_DIRS for p in relative.parts):
                continue
            target = dest / relative
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif entry.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry, target)
        marker.write_text(fingerprint)
    generated = project / CACHE_NAME / "generated" / "bridges.ts"
    generated.parent.mkdir(parents=True, exist_ok=True)
    if not generated.exists():
        generated.write_text("export {}; // Register a Bridge and run pyntral types\n", encoding="utf-8")
    return dest


def _npm_executable() -> str:
    """Resolve the real npm launcher (npm.cmd on Windows, npm elsewhere).

    subprocess with shell=False cannot reliably launch the extensionless npm shim
    on Windows. Resolve an executable once and reuse it for install/dev/build.
    """
    executable = "npm.cmd" if sys.platform == "win32" else "npm"
    resolved = shutil.which(executable)
    if resolved is None:
        raise RuntimeError("Node.js/npm not found. Install Node.js >=22.12")
    return resolved


def install_frontend(project: Path, ui: Path) -> None:
    modules = ui / "node_modules"
    # npm install is skipped only if the toolchain corresponds to this package.json.
    manifest = (ui / "package.json").read_bytes()
    fingerprint = hashlib.sha256(manifest).hexdigest()
    marker = ui / ".dependencies.sha256"
    # A partial npm installation can contain Vite but miss TypeScript declarations.
    # Never trust the fingerprint if mandatory build-time packages are absent.
    ready = all((modules / module).is_dir() for module in (
        "vite", "typescript", "@types/react", "@types/react-dom", "lucide-react",
    ))
    if ready and marker.is_file() and marker.read_text() == fingerprint:
        return
    npm = _npm_executable()
    # An old lock may disagree with a changed manifest. Update it via install first.
    use_ci = False
    if (ui / "package-lock.json").exists() and not ready:
        try:
            lock = json.loads((ui / "package-lock.json").read_text(encoding="utf-8"))
            root = lock.get("packages", {}).get("", {})
            declared = json.loads(manifest)
            use_ci = all(root.get(group, {}) == declared.get(group, {}) for group in (
                "dependencies", "devDependencies"
            ))
        except (OSError, ValueError, TypeError):
            pass
    cmd = [npm, "ci" if use_ci else "install"]
    print("[pyntral] Installing frontend dependencies…", flush=True)
    subprocess.run(cmd + ["--include=dev", "--no-audit", "--no-fund"], cwd=ui, check=True,
                   env={**os.environ, "npm_config_cache": str(_cache(project) / "npm-cache"), "NODE_ENV": "development"})
    marker.write_text(fingerprint, encoding="utf-8")


def frontend_env(project: Path, *, api_port: int = 8000, base: str = "/admin/") -> dict[str, str]:
    if not base.startswith("/") or not base.endswith("/"):
        raise ValueError("base must start and end with /")
    return {**os.environ, "PYNTRAL_PROJECT": str(project),
            "PYNTRAL_BASE": base,
            "PYNTRAL_BACKEND": f"http://127.0.0.1:{api_port}"}


def build(project: Path, *, force: bool = False, base: str = "/admin/", app: str | None = None) -> Path:
    project = project.resolve()
    if not app and (project / "pyntral.components.json").is_file():
        app = json.loads((project / "pyntral.components.json").read_text(encoding="utf-8")).get("app")
    if app:
        generate_types(project, app)
    configure_editor(project)
    ui = sync_ui(project)
    dist = (_cache(project) / "dist").resolve()
    fingerprint = hashlib.sha256(
        (str(_digest(_source_ui())) + _component_fingerprint(project) +
         _digest(_cache(project) / "generated") + base).encode()
    ).hexdigest()
    state = _cache(project) / "build.json"
    if not force and state.is_file() and (dist / "index.html").is_file():
        try:
            if json.loads(state.read_text())["fingerprint"] == fingerprint:
                print("[pyntral] Cache hit: bundle is current")
                return dist
        except (ValueError, KeyError):
            pass
    install_frontend(project, ui)
    print("[pyntral] Building React SPA…", flush=True)
    env = frontend_env(project, base=base)
    subprocess.run([_npm_executable(), "run", "build", "--", "--outDir", str(dist)],
                   cwd=ui, env=env, check=True)
    if not (dist / "index.html").is_file():
        raise RuntimeError("Vite did not produce an index.html")
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"fingerprint": fingerprint, "base": base}, indent=2))
    print(f"[pyntral] Built: {dist}")
    return dist


def export_ui(project: Path, destination: Path) -> Path:
    """Copy a previously compiled custom SPA to a runtime-only directory."""
    source = (_cache(project.resolve()) / "dist").resolve()
    destination = destination.resolve()
    if not (source / "index.html").is_file() or not (source / "assets").is_dir() or not any((source / "assets").glob("*.js")):
        raise RuntimeError("Custom SPA is missing; run pyntral build first")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Export destination must be separate from the build cache")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Export destination must be absent or empty")
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination


def dev(project: Path, app: str, *, backend_port: int, frontend_port: int, base: str,
        access_log: bool = False, log_level: str = "INFO",
        uvicorn_log_level: str = "WARNING",
        log_format: str = "compact", log_http: str = "errors",
        log_channels: tuple[str, ...] = (), log_file: str | None = None,
        slow_request_ms: float = 750.0, log_events: tuple[str, ...] = (),
        channel_files: tuple[str, ...] = ()) -> int:
    project = project.resolve()
    generate_types(project, app)
    ui = sync_ui(project)
    _component_fingerprint(project)  # validate before starting processes
    install_frontend(project, ui)
    env = frontend_env(project, api_port=backend_port, base=base)
    channel_settings: dict[str, str] = {}
    for override in log_channels:
        name, separator, level = override.partition("=")
        if not separator:
            raise ValueError(f"Invalid --log-channel {override!r}; expected name=LEVEL")
        channel_settings[name.strip()] = level.strip().upper()
    if log_format not in ("compact", "json"):
        raise ValueError("log_format must be compact or json")
    event_settings: dict[str, bool] = {}
    for override in log_events:
        name, separator, state = override.partition("=")
        if not separator or state.strip().upper() not in ("ON", "OFF") or not name.strip():
            raise ValueError(f"Invalid --log-event {override!r}; expected EVENT=ON|OFF")
        event_settings[name.strip()] = state.strip().upper() == "ON"
    file_settings: dict[str, str] = {}
    for override in channel_files:
        name, separator, path = override.partition("=")
        if not separator or not name.strip() or not path.strip():
            raise ValueError(f"Invalid --log-channel-file {override!r}; expected CHANNEL=PATH")
        file_settings[name.strip()] = path.strip()
    # Validate eagerly before starting either subprocess.
    if uvicorn_log_level.upper() not in ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        raise ValueError("Invalid Uvicorn log level")
    LoggingConfig(level=log_level, channels=channel_settings, events=event_settings,
                  http=log_http, slow_request_ms=slow_request_ms)
    from .logging import CHANNELS
    for channel in file_settings:
        if channel not in CHANNELS:
            raise ValueError(f"Unknown logging channel: {channel}")
    env.update({"PYNTRAL_CLI_LOGGING": "1",
                "PYNTRAL_LOG_LEVEL": log_level.upper(),
                "PYNTRAL_LOG_FORMAT": log_format,
                "PYNTRAL_LOG_HTTP": log_http,
                "PYNTRAL_LOG_CHANNELS": ",".join(f"{k}={v}" for k, v in channel_settings.items()),
                "PYNTRAL_LOG_EVENTS": ",".join(f"{k}={'ON' if v else 'OFF'}" for k, v in event_settings.items()),
                "PYNTRAL_LOG_CHANNEL_FILES": json.dumps({
                    k: str(Path(v) if Path(v).is_absolute() else project / v)
                    for k, v in file_settings.items()}),
                "PYNTRAL_SLOW_REQUEST_MS": str(slow_request_ms)})
    if log_file:
        dest = Path(log_file)
        env["PYNTRAL_LOG_FILE"] = str(dest if dest.is_absolute() else project / dest)
    # The CLI owns reloads. Uvicorn's Windows reloader sends CTRL_C_EVENT,
    # which can reach the shared console (including this CLI and Vite).
    backend_cmd = [sys.executable, "-m", "uvicorn", app, "--host", "127.0.0.1",
                   "--port", str(backend_port), "--workers", "1"]
    if not access_log:
        backend_cmd.append("--no-access-log")
    backend_cmd += ["--log-level", uvicorn_log_level.lower()]
    if (project / ".env").exists():
        backend_cmd += ["--env-file", str(project / ".env")]
    frontend_cmd = _vite_dev_command(ui, frontend_port)
    print(f"[pyntral] Dev UI: http://127.0.0.1:{frontend_port}{base}", flush=True)
    return _run_dev_processes(project, ui, env, backend_cmd, frontend_cmd)


def _vite_dev_command(ui: Path, port: int) -> list[str]:
    # Run Vite directly, not through npm.cmd / cmd.exe / npm's extra process
    # layers. The process handle now belongs to the actual dev server.
    node = shutil.which("node.exe" if sys.platform == "win32" else "node")
    if node is None:
        raise RuntimeError("Node.js not found. Install Node.js >=22.12")
    vite = ui / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite.is_file():
        raise RuntimeError("Vite executable missing; reinstall frontend dependencies")
    return [node, str(vite), "--strictPort", "--host", "127.0.0.1", "--port", str(port)]


def _start_dev_process(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
               if sys.platform == "win32" else {"start_new_session": True})
    return subprocess.Popen(command, cwd=cwd, env=env, **options)


def _force_stop_dev_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        # Headless runners may have no attached console. Stop the entire owned
        # tree (e.g. Vite's helper processes) when graceful signaling fails.
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _stop_dev_process(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        try:
            if sys.platform == "win32":
                # CTRL_BREAK_EVENT can be targeted at the child process group,
                # unlike CTRL_C_EVENT. Uvicorn handles SIGBREAK on Windows.
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            _force_stop_dev_process(process)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _force_stop_dev_process(process)
        process.wait(timeout=5)


def _watch_python_changes(project: Path):
    default_filter = DefaultFilter()

    def relevant(change, name: str) -> bool:
        path = Path(name)
        try:
            relative = path.relative_to(project)
        except ValueError:
            return False
        return (path.suffix == ".py"
                and not any(part in WATCH_EXCLUDED_DIRS or part.startswith(".")
                            for part in relative.parts[:-1])
                and default_filter(change, name))

    return watch(project, watch_filter=relevant, debounce=350, step=75,
                 rust_timeout=300, yield_on_timeout=True, raise_interrupt=True)


def _run_dev_processes(project: Path, ui: Path, env: dict[str, str],
                       backend_cmd: list[str], frontend_cmd: list[str]) -> int:
    """Supervise one backend and one Vite process; reload only the backend."""
    backend = frontend = None
    reported_exit = False
    try:
        backend = _start_dev_process(backend_cmd, project, env)
        frontend = _start_dev_process(frontend_cmd, ui, env)
        print("[pyntral] Watching Python sources (Ctrl+C to stop)", flush=True)
        with closing(_watch_python_changes(project)) as changes:
            while True:
                frontend_code = frontend.poll()
                if frontend_code is not None:
                    print(f"[pyntral] Frontend exited (code {frontend_code})", file=sys.stderr, flush=True)
                    return frontend_code
                backend_code = backend.poll()
                if backend_code is not None and not reported_exit:
                    print(f"[pyntral] Backend exited (code {backend_code}); waiting for a Python change",
                          file=sys.stderr, flush=True)
                    reported_exit = True
                try:
                    batch = next(changes)
                except StopIteration:
                    return 0
                if not batch:
                    continue
                paths = sorted({str(Path(name).relative_to(project)) for _, name in batch})
                print(f"[pyntral] Python changes: {', '.join(paths)}. Reloading backend…", flush=True)
                _stop_dev_process(backend)
                backend = None
                # Do not start a replacement if the other server already died.
                frontend_code = frontend.poll()
                if frontend_code is not None:
                    return frontend_code
                backend = _start_dev_process(backend_cmd, project, env)
                reported_exit = False
    except KeyboardInterrupt:
        return 130
    finally:
        try:
            _stop_dev_process(frontend)
        finally:
            _stop_dev_process(backend)


def _python_source_state(project: Path) -> tuple[tuple[str, int, int], ...]:
    """Snapshot source files without scanning node_modules or generated caches."""
    excluded = WATCH_EXCLUDED_DIRS
    result: list[tuple[str, int, int]] = []
    for root, dirs, files in os.walk(project):
        dirs[:] = [name for name in dirs if name not in excluded and not name.startswith(".")]
        for name in files:
            if name.endswith(".py") or name == "pyntral.components.json":
                path = Path(root) / name
                try:
                    st = path.stat()
                except FileNotFoundError:
                    continue
                result.append((str(path.relative_to(project)), st.st_mtime_ns, st.st_size))
    return tuple(sorted(result))


def watch_types(project: Path, app: str, *, out: Path | None = None,
                editor: bool = True, interval: float = 0.5) -> None:
    """Regenerate in a fresh interpreter so imports never use stale Python modules."""
    if interval <= 0:
        raise ValueError("Watch interval must be positive")
    project = project.resolve()
    generate_types(project, app, out=out)
    if editor:
        configure_editor(project)
    state = _python_source_state(project)
    print("[pyntral] Watching Python bridge contracts (Ctrl+C to stop)", flush=True)
    while True:
        time.sleep(interval)
        next_state = _python_source_state(project)
        if next_state == state:
            continue
        # Debounce bursts of editor save events.
        time.sleep(0.25)
        next_state = _python_source_state(project)
        state = next_state
        args = [sys.executable, "-m", "pyntral.cli", "--project", str(project),
                "types", app]
        if out is not None:
            args += ["--out", str(out)]
        if editor:
            args.append("--editor")
        completed = subprocess.run(args, cwd=project, check=False)
        if completed.returncode:
            print("[pyntral] Bridge generation failed; watching for next change", file=sys.stderr)


def init_ui(project: Path) -> None:
    project = project.resolve()
    directory = project / "admin"
    directory.mkdir(parents=True, exist_ok=True)
    template = directory / "StatusBadge.tsx"
    config = project / "pyntral.components.json"
    if template.exists() or config.exists():
        raise RuntimeError("Admin extensions already exist; refusing to overwrite")
    template.write_text('''import type { CustomFieldProps } from "@pyntral/types";

export default function StatusBadge({ value }: CustomFieldProps) {
  return <span className="pill">{String(value ?? "—")}</span>;
}
''', encoding="utf-8")
    config.write_text(json.dumps({"fields": {"status-badge": "admin/StatusBadge.tsx"},
                                  "pages": {}}, indent=2) + "\n")
    print("[pyntral] Created pyntral.components.json and admin/StatusBadge.tsx")


def init_env(project: Path, username: str) -> None:
    from getpass import getpass
    import secrets

    dest = project.resolve() / ".env"
    if dest.exists():
        raise RuntimeError(".env already exists; refusing to overwrite credentials")
    if not username or "\n" in username or "=" in username:
        raise ValueError("Invalid username")
    password = getpass("Local admin password: ")
    if len(password) < 12:
        raise ValueError("Use at least 12 characters for your admin password")
    if password != getpass("Confirm password: "):
        raise ValueError("Passwords do not match")
    dest.write_text(
        f"ADMIN_USERNAME={username}\n"
        f"ADMIN_PASSWORD_HASH={hash_password(password)}\n"
        f"APP_SECRET_KEY={secrets.token_urlsafe(48)}\n"
        "ADMIN_SECURE_COOKIE=false\n"
        "DATABASE_URL=sqlite:///./shop.db\n"
    )
    try:
        dest.chmod(0o600)
    except OSError:
        pass
    print("[pyntral] Created local .env (gitignored). For production, use HTTPS and secure cookies.")


def doctor(project: Path) -> int:
    print(f"Python: {sys.version.split()[0]}")
    for exe in ("uv", "node", "npm"):
        resolved_name = "npm.cmd" if exe == "npm" and sys.platform == "win32" else exe
        command = shutil.which(resolved_name)
        print(f"{exe}: {command or 'MISSING'}")
    print(f"UI source: {_source_ui()}")
    print(f"Cache: {_cache(project.resolve())}")
    print(f"Built: {(project / CACHE_NAME / 'dist' / 'index.html').is_file()}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Pyntral build and dev tooling")
    parser.add_argument("--project", default=".", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="Build SPA with content-addressed cache")
    build_parser.add_argument("--force", action="store_true")
    build_parser.add_argument("--base", default="/admin/")
    build_parser.add_argument("--app", help="Generate typed Pydantic bridge client from module:app")
    export_parser = commands.add_parser("export-ui", help="Copy a compiled SPA to a runtime directory")
    export_parser.add_argument("destination", type=Path)
    dev_parser = commands.add_parser("dev", help="Start uvicorn + Vite HMR")
    dev_parser.add_argument("app", help="Import path, e.g. examples.shop.app:app")
    dev_parser.add_argument("--backend-port", type=int, default=8000)
    dev_parser.add_argument("--frontend-port", type=int, default=5173)
    dev_parser.add_argument("--base", default="/admin/")
    dev_parser.add_argument("--access-log", action="store_true",
                            help="Enable noisy Uvicorn per-request access logs (off by default)")
    dev_parser.add_argument("--log-level", default="INFO", help="Pyntral event level")
    dev_parser.add_argument("--uvicorn-log-level", default="WARNING", type=str.upper,
                            choices=("TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                            help="Uvicorn lifecycle/error level (independent from admin events)")
    dev_parser.add_argument("--log-format", choices=("compact", "json"), default="compact")
    dev_parser.add_argument("--log-http", choices=("off", "errors", "slow", "all"), default="errors",
                            help="Admin request events, independent of Uvicorn access logs")
    dev_parser.add_argument("--log-channel", action="append", default=[], metavar="NAME=LEVEL",
                            help="Override a channel; e.g. bridge=OFF or resource=DEBUG")
    dev_parser.add_argument("--log-file", help="Optional rotating log file (relative to project)")
    dev_parser.add_argument("--log-event", action="append", default=[], metavar="EVENT=OFF",
                            help="Disable individual events (or enable with ON)")
    dev_parser.add_argument("--log-channel-file", action="append", default=[], metavar="CHANNEL=PATH",
                            help="Write a separate rotating log for a channel")
    dev_parser.add_argument("--slow-request-ms", type=float, default=750.0)
    commands.add_parser("init-ui", help="Scaffold custom React component")
    types_parser = commands.add_parser("types", help="Generate typed TS bridge client from FastAPI app")
    types_parser.add_argument("app", help="Import path, e.g. examples.shop.app:app")
    types_parser.add_argument("--watch", action="store_true", help="Regenerate on Python changes")
    types_parser.add_argument("--out", type=Path, help="Copy generated client into a project-owned path")
    types_parser.add_argument("--editor", action="store_true", help="Configure root VS Code TypeScript project")
    schema_parser = commands.add_parser("schema", help="Export resource documentation without building the SPA")
    schema_parser.add_argument("app", help="Import path, e.g. examples.shop.app:app")
    schema_parser.add_argument("--out", type=Path, default=Path(".pyntral/schema.md"))
    schema_parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    commands.add_parser("doctor", help="Inspect toolchain and bundle")
    local_env = commands.add_parser("init-env", help="Generate local development credentials")
    local_env.add_argument("--username", default="admin")
    pw = commands.add_parser("hash-password", help="Generate a scrypt hash for ADMIN_PASSWORD_HASH")
    pw.add_argument("--password", help="Explicit password (discouraged: exposed to shell history)")
    args = parser.parse_args()
    try:
        if args.command == "build":
            build(args.project, force=args.force, base=args.base, app=args.app)
        elif args.command == "export-ui":
            print(f"[pyntral] Exported UI: {export_ui(args.project, args.destination)}")
        elif args.command == "dev":
            sys.exit(dev(args.project, args.app, backend_port=args.backend_port,
                         frontend_port=args.frontend_port, base=args.base,
                         access_log=args.access_log, log_level=args.log_level,
                         uvicorn_log_level=args.uvicorn_log_level,
                         log_format=args.log_format, log_http=args.log_http,
                         log_channels=tuple(args.log_channel), log_file=args.log_file,
                         slow_request_ms=args.slow_request_ms,
                         log_events=tuple(args.log_event),
                         channel_files=tuple(args.log_channel_file)))
        elif args.command == "init-ui":
            init_ui(args.project)
        elif args.command == "types":
            if args.watch:
                watch_types(args.project, args.app, out=args.out, editor=True)
            else:
                generated = generate_types(args.project, args.app, out=args.out)
                if args.editor:
                    configure_editor(args.project)
                print(f"[pyntral] Generated: {generated}")
        elif args.command == "schema":
            import importlib
            from .schema_docs import write_schema_docs
            from .typegen import _load_env_file
            project = args.project.resolve()
            _load_env_file(project / ".env")
            if str(project) not in sys.path:
                sys.path.insert(0, str(project))
            if ":" not in args.app:
                raise ValueError("App must look like module:app")
            module_name, attribute = args.app.split(":", 1)
            target = importlib.import_module(module_name)
            for name in attribute.split("."):
                target = getattr(target, name)
            admin = getattr(target.state, "pyntral", None)
            if admin is None:
                raise ValueError("FastAPI app does not have Pyntral mounted")
            destination = args.out if args.out.is_absolute() else project / args.out
            write_schema_docs(admin, destination, format=args.format)
            print(f"[pyntral] Resource reference: {destination}")
        elif args.command == "doctor":
            sys.exit(doctor(args.project))
        elif args.command == "init-env":
            init_env(args.project, username=args.username)
        elif args.command == "hash-password":
            from getpass import getpass
            print(hash_password(args.password or getpass("Password: ")))
    except KeyboardInterrupt:
        return
    except (RuntimeError, ValueError, ImportError, AttributeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"pyntral: {exc}\n")


if __name__ == "__main__":
    main()
