"""Exercise the supervisor independently of the npm toolchain, including real reloads."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from pyntral import cli


def test_reload_restarts_only_backend_and_recovers_after_failure(tmp_path, monkeypatch):
    app = tmp_path / "app.py"
    app.write_text("app = None")
    events = []
    processes = []

    class Process:
        def __init__(self, command):
            self.command = command
            self.returncode = None

        def poll(self):
            return self.returncode

    def start(command, cwd, env):
        process = Process(command)
        processes.append(process)
        events.append(("start", command[0]))
        return process

    def stop(process):
        if process is not None:
            events.append(("stop", process.command[0]))
            process.returncode = 0

    def changes(project):
        yield {(2, str(app))}
        # Backend startup failed; Vite and the watcher must survive.
        processes[-1].returncode = 1
        yield set()
        yield {(2, str(app))}
        # Only Vite exiting ends the dev session.
        processes[1].returncode = 0
        yield set()

    monkeypatch.setattr(cli, "_start_dev_process", start)
    monkeypatch.setattr(cli, "_stop_dev_process", stop)
    monkeypatch.setattr(cli, "_watch_python_changes", changes)
    assert cli._run_dev_processes(tmp_path, tmp_path, {}, ["backend"], ["vite"]) == 0
    assert events == [
        ("start", "backend"), ("start", "vite"), ("stop", "backend"),
        ("start", "backend"), ("stop", "backend"), ("start", "backend"),
        ("stop", "vite"), ("stop", "backend"),
    ]


def test_windows_stop_targets_child_group_not_console(monkeypatch):
    events = []

    class Process:
        def poll(self):
            return None

        def send_signal(self, value):
            events.append(value)

        def wait(self, timeout):
            events.append(timeout)
            return 0

    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(cli.signal, "CTRL_BREAK_EVENT", 1, raising=False)
    cli._stop_dev_process(Process())
    assert events == [1, 10]


def test_real_dev_reload_keeps_frontend_and_recovers_from_invalid_code(tmp_path):
    """Runs on Linux and Windows, without relying on mocked process behavior."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    source = tmp_path / "reload_app.py"
    marker = tmp_path / "frontend-stop"
    frontend_pid = tmp_path / "frontend-pid"
    log = tmp_path / "supervisor.log"

    def write_app(version):
        source.write_text(
            "import os\nfrom fastapi import FastAPI\napp = FastAPI()\n"
            "@app.get('/')\ndef index():\n"
            f"    return {{'version': {version}, 'pid': os.getpid()}}\n",
            encoding="utf-8",
        )

    write_app(1)
    supervisor = """
import os, sys
from pathlib import Path
from pyntral.cli import _run_dev_processes
project = Path(sys.argv[1])
frontend = [
    sys.executable, "-c",
    "import os,time; from pathlib import Path; "
    "Path('frontend-pid').write_text(str(os.getpid())); "
    "deadline=time.monotonic()+60; "
    "exec('while not Path(\\'frontend-stop\\').exists() and time.monotonic()<deadline:\\n time.sleep(.05)')"
]
backend = [sys.executable, "-m", "uvicorn", "reload_app:app",
           "--host", "127.0.0.1", "--port", sys.argv[2], "--workers", "1"]
raise SystemExit(_run_dev_processes(project, project, dict(os.environ), backend, frontend))
"""
    import json

    def wait_version(process, expected):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with urlopen(f"http://127.0.0.1:{port}/", timeout=0.4) as response:
                    data = json.load(response)
                if data["version"] == expected:
                    return data
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise AssertionError(f"Backend did not reach version {expected}:\n{log.read_text(errors='replace')}")

    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen([sys.executable, "-c", supervisor, str(tmp_path), str(port)],
                                   cwd=tmp_path, stdout=output, stderr=subprocess.STDOUT)
        try:
            first = wait_version(process, 1)
            assert frontend_pid.exists()
            original_frontend = frontend_pid.read_text()
            # Change file size too: Python bytecode caches use mtime/size.
            write_app(22)
            second = wait_version(process, 22)
            assert first["pid"] != second["pid"]
            assert frontend_pid.read_text() == original_frontend
            source.write_text("this is not valid Python !!!", encoding="utf-8")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and process.poll() is None:
                if "Backend exited (code" in log.read_text(errors="replace"):
                    break
                time.sleep(0.1)
            else:
                raise AssertionError(log.read_text(errors="replace"))
            assert process.poll() is None
            write_app(333)
            third = wait_version(process, 333)
            assert third["pid"] != second["pid"]
            assert frontend_pid.read_text() == original_frontend
            marker.touch()
            assert process.wait(timeout=20) == 0
        finally:
            marker.touch()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
