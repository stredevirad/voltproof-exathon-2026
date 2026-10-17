"""Upload routes of the web API (the pipeline work is in pipeline/upload.py).

    POST   /api/uploads                         start an upload (returns its id)
    PUT    /api/uploads/{id}/files/{role}       the file itself as the request body (role: readings | locations)
    GET    /api/uploads/{id}/preview            layout and the first 20 lines, for display
    POST   /api/uploads/{id}/validate           the user's choices -> plain-language summary computed in Exasol
    POST   /api/uploads/{id}/build              start the build (one at a time); progress via GET /api/uploads/{id}
    GET    /api/uploads, /api/uploads/{id}      uploads on this computer and their state
    DELETE /api/uploads/{id}                    drop the schema and remove every file of the upload

Requests that change something must carry the header `X-VoltProof: 1` and, when the browser sends an Origin, come
from this app's own origin. A web page on another site can make a browser send simple requests to 127.0.0.1, but it
cannot add that header without the app's permission (which it never gives), so it cannot start, change or delete an
upload. File contents are never logged.
"""

from __future__ import annotations

import os
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from app.api import datasets
from pipeline import buildlock, upload
from pipeline.upload import UploadError

router = APIRouter(prefix="/api/uploads")
CHUNK = 1 << 20


def _public(rec: dict) -> dict:
    """What the page needs (no folder paths)."""
    keys = ("id", "schema", "status", "created_at", "readings", "locations", "preview", "mapping", "validation",
            "build", "error", "progress")
    out = {k: rec.get(k) for k in keys}
    for role in ("readings", "locations"):
        if out[role]:
            out[role] = {k: v for k, v in out[role].items() if k != "stored"}
    return out


def _plain(e: Exception) -> HTTPException:
    if isinstance(e, buildlock.BuildBusy):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


def check_request(request: Request) -> None:
    """Cross-site guard for every request that changes something (see the module docstring)."""
    if request.headers.get("x-voltproof") != "1":
        raise HTTPException(status_code=403, detail="This request must come from the VoltProof page itself.")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in {f"http://{request.headers.get('host', '')}"}:
        raise HTTPException(status_code=403, detail="This request must come from the VoltProof page itself.")


class Mapping(BaseModel):
    mapping: dict = {}


SAMPLES = {"readings": ("SYNTHETIC ESMI minute-wise voltage data 2030 Jan.csv", "readings in the ESMI layout"),
           "locations": ("SYNTHETIC ESMI location information.csv", "the matching location file")}


@router.get("/sample/{which}")
def sample(which: str):
    """Invented sample files to try the upload page with: the SYNTHETIC demo files, or a small one-reading-per-line file."""
    if which == "long":
        return Response(upload.sample_long_csv(), media_type="text/csv", headers={
            "Content-Disposition": 'attachment; filename="SYNTHETIC sample one reading per line.csv"'})
    if which not in SAMPLES:
        raise HTTPException(status_code=404, detail="unknown sample file")
    from pipeline import synthetic
    path = synthetic.OUT_DIR / SAMPLES[which][0]
    if not path.exists():
        synthetic.generate()
    return FileResponse(path, media_type="text/csv", filename=path.name)


@router.get("")
def list_uploads():
    return [_public(r) for r in upload.list_uploads()]


@router.post("")
def start(request: Request):
    check_request(request)
    try:
        return _public(upload.new_upload())
    except UploadError as e:
        raise _plain(e) from None


@router.get("/{upload_id}")
def status(upload_id: str):
    try:
        return _public(upload.load(upload_id))
    except UploadError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.put("/{upload_id}/files/{role}")
async def receive(upload_id: str, role: str, request: Request, name: str = ""):
    """Stream the request body to a temporary file (stopping at the size limit), then hand it to the pipeline."""
    check_request(request)
    if role not in ("readings", "locations"):
        raise HTTPException(status_code=404, detail="unknown file role")
    try:
        folder = upload.UPLOAD_DIR / upload_id
        upload.schema_for(upload_id)  # validates the id before anything touches the disk
        upload.load(upload_id)
    except UploadError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    tmp = folder / f"{role}.incoming"
    size = 0
    try:
        with open(tmp, "wb") as fh:
            async for chunk in request.stream():
                size += len(chunk)
                if size > upload.MAX_BYTES:
                    raise HTTPException(status_code=413, detail=(
                        f"The file is larger than {upload.MAX_BYTES // 1_000_000} MB, the limit for one upload on "
                        "this laptop. Split it into smaller files (for example by month)."))
                fh.write(chunk)

        def chunks():
            with open(tmp, "rb") as src:
                while b := src.read(CHUNK):
                    yield b
        rec = upload.receive(upload_id, role, chunks(), name)
        return _public(rec)
    except UploadError as e:
        raise _plain(e) from None
    finally:
        if tmp.exists():
            os.remove(tmp)


@router.get("/{upload_id}/preview")
def preview(upload_id: str):
    try:
        return upload.preview(upload_id)
    except UploadError as e:
        raise _plain(e) from None


@router.post("/{upload_id}/validate")
def validate(upload_id: str, body: Mapping, request: Request):
    check_request(request)
    try:
        upload.validate(upload_id, body.mapping)
        return _public(upload.load(upload_id))
    except UploadError as e:
        raise _plain(e) from None


def _build_in_background(upload_id: str) -> None:
    try:
        upload.build(upload_id)
    except (UploadError, buildlock.BuildBusy) as e:
        _record_refusal(upload_id, str(e))
    finally:
        datasets.forget()


def _record_refusal(upload_id: str, message: str) -> None:
    """A build that started records its own plain message. A refusal before it started (not enough free disk space;
    another build started first) leaves the record as it was, and the page would wait without a word: record it."""
    try:
        rec = upload.load(upload_id)
        if rec["status"] not in ("ready", "failed"):
            rec.update(status="failed", error=message, progress=None)
            upload.save(rec)
    except (UploadError, OSError, ValueError):
        pass


@router.post("/{upload_id}/build", status_code=202)
def build(upload_id: str, request: Request):
    check_request(request)
    try:
        rec = upload.load(upload_id)
        if not (rec.get("validation") or {}).get("ready_to_build"):
            raise UploadError("The checks found problems or open questions; answer them before building.")
        if buildlock.current():
            raise buildlock.BuildBusy(f"Another database build is running: {buildlock.current().get('what')}. "
                                      "Only one build can run at a time; try again when it has finished.")
    except (UploadError, buildlock.BuildBusy) as e:
        raise _plain(e) from None
    threading.Thread(target=_build_in_background, args=(upload_id,), daemon=True, name=f"build-{upload_id}").start()
    return JSONResponse(status_code=202, content={"id": upload_id, "status": "starting"})


@router.delete("/{upload_id}")
def delete(upload_id: str, request: Request):
    check_request(request)
    try:
        upload.delete(upload_id)
    except UploadError as e:
        raise _plain(e) from None
    finally:
        datasets.forget()
    return {"id": upload_id, "deleted": True}
