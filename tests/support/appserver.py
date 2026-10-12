"""Start the real app (uvicorn) on a free port for browser tests, optionally on a given schema."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_json(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read())


@contextmanager
def app_server(schema: str | None = None):
    port = free_port()
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    if schema:
        env["VOLTPROOF_SCHEMA"] = schema
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1",
                             "--port", str(port)], cwd=REPO_ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(base + "/api/health", timeout=5) as r:
                    if r.status == 200:
                        break
            except Exception:  # noqa: BLE001 - not up yet
                time.sleep(0.5)
        else:
            raise RuntimeError("server did not become healthy")
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)
