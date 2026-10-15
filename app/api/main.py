"""VoltProof web API + static web app (one process).

    .venv\\Scripts\\python.exe -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000

All analytical numbers come from tables materialised by the SQL pipeline inside Exasol. This API only reads
them, and renders evidence reports from them.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import datasets, report, service
from app.api.db import using

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = REPO_ROOT / "app" / "web" / "dist"

app = FastAPI(title="VoltProof", version="0.1.0",
              description="Traceable evidence of power cuts and poor supply from ESMI minute-wise voltage data.")
# The app is served on 127.0.0.1 only. Refusing any other Host header (400) stops a web page that points its
# own host name at 127.0.0.1 (DNS rebinding) from reading the app as if it were the same site.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

MONTH = re.compile(r"^\d{4}-\d{2}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EVENT_KEY = re.compile(r"^\d{1,9}-\d{12}$")


def _404(what: str):
    raise HTTPException(status_code=404, detail=f"{what} not found")


DS = Query(None, max_length=40, description="dataset (from /api/datasets); default: the server's dataset")


@contextmanager
def _dataset(ds: str | None):
    """Answer this request from dataset `ds`, which must be on the whitelist (app/api/datasets.py)."""
    try:
        schema = datasets.resolve(ds)
    except datasets.UnknownDataset:
        raise HTTPException(status_code=404, detail="dataset not found (it may have been deleted)") from None
    with using(schema):
        yield


@app.get("/api/datasets")
def list_datasets():
    return datasets.available()


@app.get("/api/health")
def health():
    try:
        return service.health()
    except Exception as e:  # plain-language error with a next step
        return JSONResponse(status_code=503, content={
            "database": "unavailable",
            "detail": "Cannot read the VoltProof tables in Exasol. Start the database with scripts\\exa.ps1 start "
                      "and build the data with scripts\\load.ps1.",
            "error": str(getattr(e, "message", e)).splitlines()[0][:200]})


@app.get("/api/meta")
def meta(ds: str | None = DS):
    with _dataset(ds):
        return service.meta()


@app.get("/api/states")
def states(ds: str | None = DS):
    with _dataset(ds):
        return service.states()


@app.get("/api/locations")
def locations(state: str | None = None, district: str | None = None, q: str | None = Query(None, max_length=80),
              ds: str | None = DS):
    with _dataset(ds):
        return service.locations(state, district, q)


@app.get("/api/locations/{location_id}")
def location(location_id: int, ds: str | None = DS):
    with _dataset(ds):
        return service.location(location_id) or _404("location")


@app.get("/api/locations/{location_id}/months/{month_key}")
def month(location_id: int, month_key: str, ds: str | None = DS):
    if not MONTH.match(month_key):
        raise HTTPException(status_code=400, detail="month must look like 2018-07")
    with _dataset(ds):
        return service.month(location_id, month_key) or _404("location-month")


@app.get("/api/locations/{location_id}/days/{day}")
def day(location_id: int, day: str, ds: str | None = DS):
    if not DAY.match(day):
        raise HTTPException(status_code=400, detail="day must look like 2018-07-25")
    with _dataset(ds):
        return service.day(location_id, day)


@app.get("/api/events/{event_key}")
def event(event_key: str, ds: str | None = DS):
    if not EVENT_KEY.match(event_key):
        raise HTTPException(status_code=400, detail="event key must look like 123-201807251827")
    with _dataset(ds):
        return service.event(event_key) or _404("event")


@app.get("/api/groups/{group_key:path}")
def group(group_key: str, ds: str | None = DS):
    with _dataset(ds):
        return service.group(group_key) or _404("potential shared supply event")


@app.get("/api/demo")
def demo(ds: str | None = DS):
    with _dataset(ds):
        return service.demo() or _404("demo preset (build the 2018 June-August data first)")


class ReportRequest(BaseModel):
    location_id: int
    month: str


@app.post("/api/reports")
def create_report(req: ReportRequest, ds: str | None = DS):
    if not MONTH.match(req.month):
        raise HTTPException(status_code=400, detail="month must look like 2018-07")
    with _dataset(ds):
        data = service.month(req.location_id, req.month)
        if not data:
            _404("location-month")
        return report.generate(req.location_id, req.month)


@app.get("/api/reports/{report_id}.{ext}")
def get_report(report_id: str, ext: str):
    path = report.path_for(report_id, ext)
    if path is None or not path.exists():
        _404("report")
    media = {"pdf": "application/pdf", "html": "text/html", "json": "application/json"}[ext]
    return FileResponse(path, media_type=media, filename=path.name if ext == "pdf" else None)


def _dist_file(path: str) -> Path | None:
    """The built web-app file that `path` names, or None if there is none. Raises 404 for a path that could
    leave WEB_DIST (`..` or `.` segments, an absolute or drive path, a backslash variant, a NUL byte) before it
    reaches the file system; the resolved file must also still lie inside WEB_DIST."""
    parts = path.replace("\\", "/").split("/")
    if path.startswith(("/", "\\")) or any(p in (".", "..") or ":" in p or "\x00" in p for p in parts):
        _404("page")
    try:
        root = WEB_DIST.resolve()
        candidate = (root / path).resolve()
    except (OSError, ValueError):
        _404("page")
    return candidate if candidate.is_relative_to(root) and candidate.is_file() else None


# Static single-page app (built by `npm run build` in app/web). Unknown non-API paths fall back to index.html;
# paths that try to leave the build folder get 404.
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            _404("API route")
        candidate = _dist_file(path) if path else None
        return FileResponse(candidate or WEB_DIST / "index.html")
