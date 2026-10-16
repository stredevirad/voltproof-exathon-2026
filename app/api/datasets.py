"""Which datasets the app may show, and the whitelist that every `ds` request parameter is checked against.

A dataset is a schema: the Prayas ESMI data (VOLTPROOF), the SYNTHETIC demo set (VOLTPROOF_DEMO), the server's own
dataset (VOLTPROOF_SCHEMA) and every upload that finished building (VP_USER_<id>, pipeline/upload.py). Anything else
is refused with 404 before any query runs; a request without `ds` uses the server's dataset, exactly as before.
"""

from __future__ import annotations

import time

from app.api.db import SCHEMA
from pipeline import upload
from pipeline.db import DEMO_SCHEMA, REAL_SCHEMA, connect, schema_dataset

_CACHE: dict = {"at": 0.0, "items": None}
TTL_SECONDS = 5.0


class UnknownDataset(LookupError):
    pass


def _kind(info: dict) -> str:
    if info["upload"]:
        return "upload"
    if info["synthetic"]:
        return "synthetic"
    return "real"


def _scan() -> list[dict]:
    items, seen = [], set()
    with connect() as c:
        for schema in [SCHEMA, REAL_SCHEMA, DEMO_SCHEMA]:
            if schema in seen:
                continue
            seen.add(schema)
            info = schema_dataset(c, schema)
            if info["built"]:
                items.append({"ds": schema, "kind": _kind(info), "default": schema == SCHEMA})
        for rec in upload.list_uploads():
            schema = rec.get("schema")
            if rec.get("status") != "ready" or not upload.is_upload_schema(schema) or schema in seen:
                continue
            info = schema_dataset(c, schema)
            if info["built"] and info["upload"]:
                seen.add(schema)
                r = rec.get("readings") or {}
                b = rec.get("build") or {}
                items.append({"ds": schema, "kind": "upload", "default": False, "upload_id": rec["id"],
                              "file_name": r.get("name"), "uploaded_at": r.get("received_at"),
                              "sha256": r.get("sha256"), "locations": b.get("locations"),
                              "first_day": (rec.get("validation") or {}).get("first_day"),
                              "last_day": (rec.get("validation") or {}).get("last_day")})
    return items


def available(refresh: bool = False) -> list[dict]:
    now = time.monotonic()
    if refresh or _CACHE["items"] is None or now - _CACHE["at"] > TTL_SECONDS:
        _CACHE.update(items=_scan(), at=now)
    return _CACHE["items"]


def forget() -> None:
    """Drop the cached list (after an upload is built or deleted)."""
    _CACHE.update(items=None, at=0.0)


def resolve(ds: str | None) -> str:
    """The schema for a request's `ds` value; the server's dataset when `ds` is absent."""
    if ds is None or ds == "":
        return SCHEMA
    names = {d["ds"] for d in available()}
    if ds not in names:
        names = {d["ds"] for d in available(refresh=True)}
        if ds not in names:
            raise UnknownDataset(ds)
    return ds
