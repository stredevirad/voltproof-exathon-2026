"""Read-only database access for the web app: a small pyexasol connection pool and typed rows.

pyexasol connections are not thread-safe, so each request checks out its own connection (pool size 4,
well under the 18 usable connections). The app only SELECTs from tables the pipeline materialised; it
must not run while scripts\\load.ps1 rebuilds them (CREATE OR REPLACE swaps tables).
"""

from __future__ import annotations

import os
import queue
import threading
from contextlib import contextmanager

import pyexasol

from pipeline.db import connect

SCHEMA = os.environ.get("VOLTPROOF_SCHEMA", "VOLTPROOF")
POOL_SIZE = 4


class Pool:
    def __init__(self, size: int = POOL_SIZE, schema: str = SCHEMA):
        self._idle: queue.Queue = queue.Queue()
        self._size = size
        self._created = 0
        self._lock = threading.Lock()
        self.schema = schema

    def _new(self):
        return connect(schema=self.schema, autocommit=True, fetch_dict=True)

    @contextmanager
    def connection(self):
        try:
            conn = self._idle.get_nowait()
        except queue.Empty:
            with self._lock:
                make = self._created < self._size
                if make:
                    self._created += 1
            if make:
                try:
                    conn = self._new()
                except Exception:
                    with self._lock:
                        self._created -= 1
                    raise
            else:
                conn = self._idle.get(timeout=30)
        healthy = True
        try:
            yield conn
        except (pyexasol.ExaCommunicationError, pyexasol.ExaConnectionError):
            healthy = False
            raise
        finally:
            if healthy and not conn.is_closed:
                self._idle.put(conn)
            else:
                with self._lock:
                    self._created -= 1

    def close(self):
        while not self._idle.empty():
            try:
                self._idle.get_nowait().close()
            except Exception:
                pass


POOL = Pool()


def _converter(col: dict):
    t = col.get("type")
    if t == "DECIMAL":
        return int if (col.get("scale") or 0) == 0 else float
    if t == "DOUBLE":
        return float
    if t == "TIMESTAMP":
        return lambda v: v[:16].replace(" ", "T")  # local IST minute, e.g. 2018-07-25T18:27
    if t == "DATE":
        return lambda v: v[:10]
    if t == "BOOLEAN":
        return bool
    return None


def query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a read-only query and return rows as dicts with lower-case keys and proper Python types."""
    with POOL.connection() as c:
        st = c.execute(sql, params or {})
        cols = st.columns()
        conv = {name: _converter(meta) for name, meta in cols.items()}
        out = []
        for row in st.fetchall():
            rec = {}
            for k, v in row.items():
                f = conv.get(k)
                rec[k.lower()] = f(v) if (f is not None and v is not None) else v
            out.append(rec)
        return out


def query_one(sql: str, params: dict | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None
