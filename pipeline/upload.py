"""Upload your own voltage data: store it, stage it in Exasol, check it, and build it with the same SQL steps.

Every upload gets a random id, a folder data/uploads/<id>/ (gitignored) and its own schema VP_USER_<ID>. That schema
is created and owned by a separate database user, VP_UPLOADER, which can create, fill and drop only its own schemas:
it has no rights at all on VOLTPROOF, VOLTPROOF_DEMO or any other schema, so the database itself refuses any read or
write outside the upload. The password of that user is generated here, kept in data/.uploader.json (gitignored)
and never printed.

Steps (all analysis is SQL inside Exasol; Python only stores the file, reads 20 lines for the preview, streams the
file into Exasol and orchestrates):
  1. receive  the file is streamed to disk (150 MB cap) with its SHA-256; the original name is kept for display only.
  2. preview  layout (ESMI wide, or one reading per line) and the first 20 lines, for display.
  3. stage    sql/010 + sql/ingest/u10: the file's lines go unchanged into staging tables (file id + line number).
  4. validate sql/ingest/u20: plain counts (dates, hours, intervals, values, monitors) -> what would be set aside,
              questions the data cannot answer (day/month order, hours 1-24), and refusals (not voltage readings, not
              a 230 V supply, not 1-minute data, ...).
  5. build    sql/ingest/u20 + u30 (standard raw rows) + the unchanged steps 020-100, provenance in RUN_LOG and
              checked against Exasol's audit log; one build at a time (pipeline/buildlock.py).
  6. delete   drops the schema and removes the folder (files and any reports rendered from the upload).

    .venv\\Scripts\\python.exe -m pipeline.upload new --readings FILE [--locations FILE]
    .venv\\Scripts\\python.exe -m pipeline.upload validate ID [--long-columns LOC,TS,VALUE] [--long-order YMD] ...
    .venv\\Scripts\\python.exe -m pipeline.upload build ID
    .venv\\Scripts\\python.exe -m pipeline.upload list | delete ID
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import time
from pathlib import Path

import yaml

from pipeline import buildlock
from pipeline.check_provenance import verify as verify_provenance
from pipeline.db import connect, deployment_dir
from pipeline.load_raw import LOCATIONS_HEADER, READINGS_HEADER, is_transient_import_error
from pipeline.run_sql import SQL_DIR, flatten_params, resolve_steps, run_steps, split_statements

REPO_ROOT = Path(__file__).resolve().parents[1]
INGEST_DIR = SQL_DIR / "ingest"
UPLOAD_DIR = Path(os.environ.get("VOLTPROOF_UPLOAD_DIR") or REPO_ROOT / "data" / "uploads")
CREDENTIALS = Path(os.environ.get("VOLTPROOF_UPLOADER_FILE") or REPO_ROOT / "data" / ".uploader.json")
METHOD_UPLOAD = REPO_ROOT / "config" / "method.upload.yaml"
ANALYTICAL_STEPS = ["020", "030", "040", "050", "060", "070", "080", "090", "095", "100"]

UPLOADER = "VP_UPLOADER"
UPLOADER_PRIVILEGES = ["CREATE SESSION", "CREATE SCHEMA", "CREATE TABLE", "CREATE VIEW", "IMPORT"]
READINGS_FILE_ID, LOCATIONS_FILE_ID, TYPED_LOCATIONS_FILE_ID = 800000001, 800000002, 800000003
MAX_BYTES = 150_000_000          # one real 3-month ESMI file is 140 MB; measured peak RAM in docs/TEST_REPORT.md
MAX_UPLOADS = 10
MAX_TYPED_MONITORS = 200
MIN_FREE_GB = 10                 # free space kept on C: and on the database drive (CLAUDE.md)
PREVIEW_LINES = 20
ID_RE = re.compile(r"^[0-9a-f]{8}$")
SCHEMA_RE = re.compile(r"^VP_USER_[0-9A-F]{8}$")
PROTECTED = {"VOLTPROOF", "VOLTPROOF_DEMO"}
DATE_ORDERS = {"DMY", "MDY"}
LONG_ORDERS = {"YMD", "DMY", "MDY"}
CHUNK_LINES = 20000

DATE_ORDER_TEXT = {"DMY": "day first (3 April for 03/04/2018)", "MDY": "month first (4 March for 03/04/2018)",
                   "YMD": "year first (2018-04-03 is 3 April)"}


class UploadError(ValueError):
    """A problem with an upload, in plain words for the person uploading."""


# ---------------------------------------------------------------- names, records, storage

def schema_for(upload_id: str) -> str:
    """The only place an upload schema name is built: VP_USER_ + the 8-hex upload id."""
    if not isinstance(upload_id, str) or not ID_RE.fullmatch(upload_id):
        raise UploadError("Unknown upload.")
    schema = "VP_USER_" + upload_id.upper()
    if not SCHEMA_RE.fullmatch(schema) or schema in PROTECTED:
        raise UploadError("Unknown upload.")
    return schema


def is_upload_schema(name: str) -> bool:
    return bool(SCHEMA_RE.fullmatch(name or ""))


def display_name(raw: str | None) -> str:
    """A file name for display only: the last path part, printable characters, at most 120 characters."""
    name = re.split(r"[\\/]", raw or "")[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '<>"|?*').strip()
    return name[:120] or "uploaded file"


def _folder(upload_id: str) -> Path:
    schema_for(upload_id)  # validates the id
    return UPLOAD_DIR / upload_id


def _now() -> str:
    return dt.datetime.now().isoformat(sep=" ", timespec="seconds")


def save(rec: dict) -> None:
    path = _folder(rec["id"]) / "upload.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def load(upload_id: str) -> dict:
    path = _folder(upload_id) / "upload.json"
    if not path.exists():
        raise UploadError("Unknown upload.")
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("status") == "building" and buildlock.current() is None:
        # the process that was building ended (RAM guard, crash or restart): say so, keep everything deletable
        rec.update(status="failed", error="The build was interrupted before it finished. Build it again or delete it.")
        save(rec)
    return rec


def list_uploads() -> list[dict]:
    if not UPLOAD_DIR.exists():
        return []
    out = []
    for d in sorted(UPLOAD_DIR.iterdir()):
        if d.is_dir() and ID_RE.fullmatch(d.name) and (d / "upload.json").exists():
            try:
                out.append(load(d.name))
            except (UploadError, ValueError, OSError):
                continue
    return sorted(out, key=lambda r: r.get("created_at") or "")


def new_upload() -> dict:
    if len(list_uploads()) >= MAX_UPLOADS:
        raise UploadError(f"There are already {MAX_UPLOADS} uploads on this computer. Delete one you no longer need, "
                          "then upload again.")
    upload_id = secrets.token_hex(4)
    while (UPLOAD_DIR / upload_id).exists():
        upload_id = secrets.token_hex(4)
    rec = {"id": upload_id, "schema": schema_for(upload_id), "status": "new", "created_at": _now(),
           "readings": None, "locations": None, "preview": None, "mapping": None, "validation": None, "build": None,
           "error": None}
    save(rec)
    return rec


def receive(upload_id: str, role: str, chunks, original_name: str | None) -> dict:
    """Stream one file (an iterable of bytes chunks) into the upload folder; 150 MB cap; SHA-256 and MD5."""
    if role not in ("readings", "locations"):
        raise UploadError("Unknown file role.")
    rec = load(upload_id)
    if rec["status"] in ("building", "ready"):
        raise UploadError("This upload has already been built. Start a new upload to analyse another file.")
    folder = _folder(upload_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{role}.dat"
    tmp = folder / f"{role}.part"
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    try:
        with open(tmp, "wb") as fh:
            for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_BYTES:
                    raise UploadError(f"The file is larger than {MAX_BYTES // 1_000_000} MB, the limit for one upload "
                                      "on this laptop. Split it into smaller files (for example by month).")
                sha.update(chunk)
                md5.update(chunk)
                fh.write(chunk)
        if size == 0:
            raise UploadError("The file is empty.")
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    rec[role] = {"name": display_name(original_name), "stored": target.name, "bytes": size,
                 "sha256": sha.hexdigest(), "md5": md5.hexdigest(), "received_at": _now()}
    rec.update(status="uploaded", preview=None, validation=None, build=None, error=None)
    save(rec)
    return rec


def receive_path(upload_id: str, role: str, path: Path) -> dict:
    def chunks():
        with open(path, "rb") as fh:
            while True:
                b = fh.read(1 << 20)
                if not b:
                    return
                yield b
    return receive(upload_id, role, chunks(), path.name)


# ---------------------------------------------------------------- preview (display only)

def _norm_header(cells: list[str]) -> list[str]:
    return [re.sub(r"\s+", " ", re.sub(r"[._]", " ", c.replace("\ufeff", ""))).strip().lower() for c in cells]


WIDE_KEY = _norm_header(READINGS_HEADER)
LOCATIONS_KEY = _norm_header(LOCATIONS_HEADER)


def _head_lines(path: Path, n: int) -> tuple[list[str], str]:
    raw = path.read_bytes()[: 1 << 16]
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:400]:
        raise UploadError("The file looks like UTF-16 text. Save it as a UTF-8 (or plain) CSV file and upload it again.")
    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff")
    lines = text.splitlines()[: n + 1]
    if not lines or not lines[0].strip():
        raise UploadError("The first line of the file is empty; it must hold the column names.")
    first = lines[0]
    sep = "\t" if ("\t" in first and "," not in first) else ","
    return lines, sep


def _cells(line: str, sep: str) -> list[str]:
    return next(csv.reader([line], delimiter=sep))


def _suggest_long(header: list[str], rows: list[list[str]]) -> dict:
    low = [h.strip().lower() for h in header]

    def pick(words, exclude=()):
        for i, h in enumerate(low):
            if i not in exclude and any(w in h for w in words):
                return i
        return None
    ts = pick(["timestamp", "datetime", "date time", "time", "date"])
    value = pick(["volt", "value", "reading"], exclude={ts})
    if value is None:
        value = next((i for i in range(len(header)) if i != ts and rows
                      and all(re.fullmatch(r"-?\d+(\.\d+)?", (r[i] if i < len(r) else "").strip() or "x")
                              for r in rows[:5])), None)
    loc = pick(["location", "monitor", "site", "meter", "device", "name"], exclude={ts, value})
    order = "DMY"
    samples = [r[ts].strip() for r in rows if ts is not None and ts < len(r) and r[ts].strip()]
    if samples and re.match(r"^\d{4}[-/.]", samples[0]):
        order = "YMD"
    elif samples:
        parts = [re.findall(r"\d+", s)[:2] for s in samples]
        if any(len(p) == 2 and int(p[1]) > 12 for p in parts):
            order = "MDY"
    return {"location_col": loc, "ts_col": ts, "value_col": value, "order": order}


def preview(upload_id: str) -> dict:
    rec = load(upload_id)
    if not rec.get("readings"):
        raise UploadError("Upload a readings file first.")
    path = _folder(upload_id) / rec["readings"]["stored"]
    lines, sep = _head_lines(path, PREVIEW_LINES)
    header = _cells(lines[0], sep)
    rows = [[c[:60] for c in _cells(x, sep)] for x in lines[1:] if x.strip()]
    key = _norm_header(header)
    if key == LOCATIONS_KEY:
        raise UploadError("This looks like a location file (Location name, From date, To date, District, State, ...). "
                          "Upload it as the location file, and upload the voltage readings as the readings file.")
    if key == WIDE_KEY:
        out = {"layout": "wide", "sep": sep, "header": [h[:60] for h in header], "rows": rows,
               "explain": "ESMI layout: one row per monitor and hour, with 60 minute columns (Min 0 to Min 59)."}
    else:
        if len(header) < 2:
            raise UploadError("The file has only one column. VoltProof needs at least a date-and-time column and a "
                              "voltage column, separated by commas.")
        out = {"layout": "long", "sep": sep, "header": [h[:60] for h in header], "rows": rows,
               "suggest": _suggest_long(header, rows),
               "explain": "One reading per line: pick which column holds the monitor, the date and time, and the "
                          "voltage."}
    if rec.get("locations"):
        lpath = _folder(upload_id) / rec["locations"]["stored"]
        llines, lsep = _head_lines(lpath, 5)
        if _norm_header(_cells(llines[0], lsep)) != LOCATIONS_KEY:
            raise UploadError("The location file must have these columns: " + ", ".join(LOCATIONS_HEADER) + ".")
        out["locations_sep"] = lsep
    rec["preview"] = {k: v for k, v in out.items() if k not in ("rows",)}
    save(rec)
    return out


# ---------------------------------------------------------------- the restricted database user

def _uploader_password() -> str:
    """Ensure VP_UPLOADER exists with the privileges it needs and no others, and return its password."""
    stored = None
    if CREDENTIALS.exists():
        try:
            stored = json.loads(CREDENTIALS.read_text(encoding="utf-8")).get("password")
        except (OSError, ValueError):
            stored = None
    with connect() as c:
        exists = c.execute("SELECT COUNT(*) FROM EXA_DBA_USERS WHERE USER_NAME = {u}", {"u": UPLOADER}).fetchval()
        if exists and stored:
            return stored
        password = secrets.token_hex(24)  # generated here, hex only; Exasol's audit log does not keep it
        if exists:
            c.execute(f'ALTER USER {UPLOADER} IDENTIFIED BY "{password}"')
        else:
            c.execute(f'CREATE USER {UPLOADER} IDENTIFIED BY "{password}"')
            for priv in UPLOADER_PRIVILEGES:
                c.execute(f"GRANT {priv} TO {UPLOADER}")
    CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS.write_text(json.dumps({"user": UPLOADER, "password": password}), encoding="utf-8")
    try:
        os.chmod(CREDENTIALS, 0o600)
    except OSError:
        pass
    return password


def uploader_connect(**kwargs):
    """A connection as VP_UPLOADER: it can create and use only its own (VP_USER_) schemas."""
    return connect(user=UPLOADER, password=_uploader_password(), **kwargs)


# ---------------------------------------------------------------- staging

def _field_count(line: str, sep: str) -> int:
    if '"' not in line:
        return line.count(sep) + 1
    return len(_cells(line, sep))


def _stream(pipe, src, file_id: int, sep: str, expected: int):
    """Write '<file_id><sep><line_no><sep><original line>' for every non-empty data line; check UTF-8 and the
    number of values per line (Exasol parses the values)."""
    buf = []
    with open(src, "rb") as fh:
        next(fh)  # header = line 1
        for line_no, raw in enumerate(fh, start=2):
            try:
                line = raw.decode("utf-8").rstrip("\r\n")
            except UnicodeDecodeError:
                raise UploadError(f"Line {line_no} is not valid UTF-8 text. Save the file as a UTF-8 CSV file and "
                                  "upload it again.") from None
            if not line.strip():
                continue
            n = _field_count(line, sep)
            if n != expected:
                raise UploadError(f"Line {line_no} has {n} values, but the first line (the column names) has "
                                  f"{expected}. Every line must have the same columns.")
            buf.append(f"{file_id}{sep}{line_no}{sep}{line}\n")
            if len(buf) >= CHUNK_LINES:
                pipe.write("".join(buf).encode("utf-8"))
                buf.clear()
    if buf:
        pipe.write("".join(buf).encode("utf-8"))


def _import(conn, schema: str, path: Path, table: str, file_id: int, sep: str, expected: int,
            columns: list[str] | None = None, csv_cols: list[str] | None = None) -> float:
    params = {"column_separator": sep, "row_separator": "LF", "encoding": "UTF8"}
    if columns:
        params["columns"] = columns
    if csv_cols:
        params["csv_cols"] = csv_cols
    t0 = time.perf_counter()
    for attempt in (1, 2):
        try:
            conn.import_from_callback(_stream, str(path), (schema, table),
                                      callback_params={"file_id": file_id, "sep": sep, "expected": expected},
                                      import_params=params)
            break
        except UploadError:
            raise
        except Exception as exc:  # D-032: a dropped transport is retried once; anything else is reported plainly
            cause = exc.__cause__  # pyexasol wraps an error raised while streaming (ExaImportError ... from ex)
            if isinstance(cause, UploadError):
                conn.rollback()
                raise cause from None
            if attempt == 1 and is_transient_import_error(exc):
                conn.rollback()
                continue
            raise UploadError("Exasol could not read the file as CSV text (check that every line has the same "
                              "columns and that quoted values are closed).") from None
    return time.perf_counter() - t0


def _source_row(conn, file_id: int, info: dict, kind: str, expected: int, loaded: int, seconds: float) -> None:
    conn.ext.insert_multi(
        "SOURCE_FILE",
        [(file_id, info["name"], kind, info["bytes"], info["md5"], info["sha256"], expected, loaded, _now(),
          round(seconds, 3))],
        columns=["FILE_ID", "FILE_NAME", "FILE_KIND", "BYTES", "MD5", "SHA256", "ROWS_EXPECTED", "ROWS_LOADED",
                 "LOADED_AT", "LOAD_SECONDS"])


def _clean_text(value, limit: int = 200) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isprintable()).strip()
    return text[:limit]


def check_mapping(rec: dict, mapping: dict | None) -> dict:
    """The user's choices, checked against fixed lists; column choices are positions in the header."""
    pv = rec.get("preview") or {}
    mapping = mapping or {}
    layout = pv.get("layout")
    if layout not in ("wide", "long"):
        raise UploadError("Open the preview first.")
    m = {"layout": layout, "sep": pv.get("sep", ","), "locations_sep": pv.get("locations_sep", ","),
         "dash_order": mapping.get("dash_order") if mapping.get("dash_order") in DATE_ORDERS else None,
         "slash_order": mapping.get("slash_order") if mapping.get("slash_order") in DATE_ORDERS else None,
         "hour_base": 1 if mapping.get("hour_base") in (1, "1") else 0, "long": None, "typed_locations": []}
    if layout == "long":
        lm = mapping.get("long") or {}
        n = len(pv.get("header") or [])
        sug = pv.get("suggest") or {}

        def col(key):
            v = lm.get(key, sug.get(key))
            if v is None or v == "":
                return None
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise UploadError("Pick the columns from the list.") from None
            if not 0 <= v < n:
                raise UploadError("Pick the columns from the list.")
            return v
        loc, ts, val = col("location_col"), col("ts_col"), col("value_col")
        if ts is None or val is None:
            raise UploadError("Pick the column with the date and time and the column with the voltage.")
        chosen = [c for c in (loc, ts, val) if c is not None]
        if len(set(chosen)) != len(chosen):
            raise UploadError("Each column can be used for one thing only.")
        single = _clean_text(lm.get("single_monitor_name"), 120) or None
        if loc is None and not single:
            raise UploadError("The file has no monitor column: type a name for the monitor.")
        order = lm.get("order", sug.get("order"))
        m["long"] = {"location_col": loc, "ts_col": ts, "value_col": val, "n_cols": n,
                     "order": order if order in LONG_ORDERS else "DMY", "single_monitor_name": single}
    typed = mapping.get("typed_locations") or []
    if typed and rec.get("locations"):
        raise UploadError("A location file was uploaded, so district and state come from it.")
    if len(typed) > MAX_TYPED_MONITORS:
        raise UploadError(f"Typing details works for up to {MAX_TYPED_MONITORS} monitors; upload a location file.")
    for t in typed:
        name, district, state = (_clean_text(t.get(k), 300) for k in ("name", "district", "state"))
        if name and district and state:
            m["typed_locations"].append({"name": name, "district": district[:200], "state": state[:200]})
    return m


def _stage_key(rec: dict, m: dict) -> str:
    parts = [rec["readings"]["sha256"], (rec.get("locations") or {}).get("sha256"), m["layout"], m["sep"],
             json.dumps(m.get("long"), sort_keys=True), json.dumps(m["typed_locations"], sort_keys=True)]
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def params_for(rec: dict, m: dict, window: tuple[str, str] | None = None) -> dict:
    """Parameter overrides of an upload: config/method.upload.yaml plus the confirmed reading choices."""
    over = flatten_params(yaml.safe_load(METHOD_UPLOAD.read_text(encoding="utf-8")))
    lm = m.get("long") or {}
    over.update({"upload.layout": m["layout"], "upload.dash_order": m.get("dash_order") or "",
                 "upload.slash_order": m.get("slash_order") or "", "upload.hour_base": int(m.get("hour_base") or 0),
                 "upload.long_order": lm.get("order") or "", "upload.single_monitor_name":
                 lm.get("single_monitor_name") or ""})
    if window:
        over.update({"demo.window_from": window[0], "demo.window_to_exclusive": window[1]})
    return over


def _stage(conn, rec: dict, m: dict) -> None:
    schema = rec["schema"]
    folder = _folder(rec["id"])
    run_steps(conn, schema, [SQL_DIR / "010_raw_tables.sql", INGEST_DIR / "u10_staging.sql"],
              params_override=params_for(rec, m), quiet=True)
    for table in ("UPLOAD_WIDE", "UPLOAD_LONG", "UPLOAD_LOCATION_INPUT", "RAW_HOURLY", "RAW_LOCATION",
                  "SOURCE_FILE", "SOURCE_FILE_DECLARED"):
        conn.execute(f"DELETE FROM {table}")
    readings = folder / rec["readings"]["stored"]
    sep = m["sep"]
    if m["layout"] == "wide":
        expected = len(READINGS_HEADER)
        seconds = _import(conn, schema, readings, "UPLOAD_WIDE", READINGS_FILE_ID, sep, expected)
        loaded = conn.execute("SELECT COUNT(*) FROM UPLOAD_WIDE").fetchval()
    else:
        lm = m["long"]
        expected = lm["n_cols"]
        cols = ["FILE_ID", "LINE_NO"] + (["LOCATION_NAME"] if lm["location_col"] is not None else []) + \
               ["TS_STR", "VALUE_STR"]
        picks = ([lm["location_col"]] if lm["location_col"] is not None else []) + [lm["ts_col"], lm["value_col"]]
        csv_cols = ["1", "2"] + [str(c + 3) for c in picks]  # positions after the two prefix values
        seconds = _import(conn, schema, readings, "UPLOAD_LONG", READINGS_FILE_ID, sep, expected + 0,
                          columns=cols, csv_cols=csv_cols)
        loaded = conn.execute("SELECT COUNT(*) FROM UPLOAD_LONG").fetchval()
    _source_row(conn, READINGS_FILE_ID, rec["readings"], "readings", int(loaded), int(loaded), seconds)
    if rec.get("locations"):
        lpath = folder / rec["locations"]["stored"]
        lsec = _import(conn, schema, lpath, "RAW_LOCATION", LOCATIONS_FILE_ID, m["locations_sep"],
                       len(LOCATIONS_HEADER))
        lrows = conn.execute("SELECT COUNT(*) FROM RAW_LOCATION").fetchval()
        _source_row(conn, LOCATIONS_FILE_ID, rec["locations"], "locations", int(lrows), int(lrows), lsec)
    elif m["typed_locations"]:
        conn.ext.insert_multi("UPLOAD_LOCATION_INPUT",
                              [(i + 1, t["name"], t["district"], t["state"]) for i, t in enumerate(m["typed_locations"])],
                              columns=["LINE_NO", "LOCATION_NAME", "DISTRICT", "STATE_NAME"])
        info = {"name": "district and state typed on the upload page", "bytes": None, "md5": None, "sha256": None}
        n = len(m["typed_locations"])
        _source_row(conn, TYPED_LOCATIONS_FILE_ID, info, "locations", n, n, 0.0)
    conn.commit()


def _fetch_one(conn, sql: str) -> dict:
    st = conn.execute(sql)
    names = [c.lower() for c in st.columns()]
    row = st.fetchone()
    return dict(zip(names, row, strict=True)) if row else {}


def _num(v):
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return float(v) if "." in v else int(v)
        except ValueError:
            return v
    return v


def _read_stats(conn) -> dict:
    stats = {}
    for table in ("UPLOAD_WIDE_STATS", "UPLOAD_LONG_STATS", "UPLOAD_VALUE_STATS"):
        stats[table.lower()] = {k: _num(v) for k, v in _fetch_one(conn, f"SELECT * FROM {table}").items()}
    st = conn.execute("SELECT LOCATION_NAME, N_ROWS, DISTRICT, STATE_NAME, HAS_LOCATION FROM UPLOAD_MONITOR "
                      "ORDER BY LOCATION_NAME LIMIT 1000")
    stats["monitors"] = [{"name": r[0], "rows": int(r[1] or 0), "district": r[2], "state": r[3],
                          "has_location": bool(r[4])} for r in st.fetchall()]
    return stats


def _decide(stats: dict, m: dict, has_location_source: bool) -> dict:
    """Turn the counts computed in Exasol into: refusals (no build), questions (the user must answer), what will be
    set aside, warnings, and the resolved reading choices. The data decides the date order whenever it can; the
    user is asked only when it cannot, and an answer never overrides what the data shows."""
    refuse, questions, aside, warn = [], [], [], []
    resolved = {"dash_order": None, "slash_order": None, "hour_base": 0, "long_order": None}
    w, lg, v = stats["upload_wide_stats"], stats["upload_long_stats"], stats["upload_value_stats"]

    def order_from(max1, max2, n, answer, key, example):
        if not n:
            return None
        if (max1 or 0) > 12 and (max2 or 0) <= 12:
            return "DMY"
        if (max2 or 0) > 12 and (max1 or 0) <= 12:
            return "MDY"
        if (max1 or 0) <= 12 and (max2 or 0) <= 12:
            if answer in DATE_ORDERS:
                return answer
            questions.append({"key": key, "text": f"Your file has dates like {example}. Is the day or the month "
                              "written first?", "options": [{"value": "DMY", "label": DATE_ORDER_TEXT["DMY"]},
                                                            {"value": "MDY", "label": DATE_ORDER_TEXT["MDY"]}]})
            return None
        return "BOTH"  # some dates have a number above 12 in both places: they cannot be read either way

    if m["layout"] == "wide":
        rows = int(w.get("n_rows") or 0)
        if not rows:
            refuse.append("The file has no data lines.")
        if w.get("n_long_name"):
            refuse.append("Some monitor names are longer than 300 characters.")
        d = order_from(w.get("dash_max1"), w.get("dash_max2"), w.get("n_dash"), m.get("dash_order"), "dash_order",
                       w.get("dash_example"))
        resolved["dash_order"] = "DMY" if d == "BOTH" else d   # as step 030 reads dash dates
        if d == "BOTH":
            warn.append("Some dates with dashes have a number above 12 in both the day and the month place; those "
                        "lines cannot be read and will be set aside.")
        s = order_from(w.get("slash_max1"), w.get("slash_max2"), w.get("n_slash"), m.get("slash_order"),
                       "slash_order", w.get("slash_example"))
        resolved["slash_order"] = None if s == "BOTH" else s
        if s == "BOTH":
            aside.append({"what": "lines with dates like 13/13/2018 that cannot be read either way",
                          "rows": int(w.get("n_slash") or 0)})
        if w.get("n_date_other"):
            aside.append({"what": f"lines with a date VoltProof cannot read (for example "
                                  f"{w.get('date_other_example') or 'an empty date'})", "rows": int(w["n_date_other"])})
        h0, h24 = int(w.get("n_hour_0") or 0), int(w.get("n_hour_24") or 0)
        if rows > 48 and h0 > rows / 2:
            refuse.append("More than half the lines say hour 0. The hour column looks broken (every hour of a day "
                          "labelled 0), so the time of each reading cannot be known. This file cannot be analysed.")
        if h24 and not h0:
            if m.get("hour_base") == 1:
                resolved["hour_base"] = 1
            else:
                questions.append({"key": "hour_base", "text": "Your file numbers the hours 1 to 24. Is hour 1 the "
                                  "first hour of the day (00:00 to 00:59)?",
                                  "options": [{"value": 1, "label": "Yes, hour 1 is 00:00 to 00:59"},
                                              {"value": 0, "label": "No, set the hour-24 lines aside"}]})
                if m.get("hour_base") == 0 and "hour_base" in (m.get("answered") or []):
                    questions.pop()
                    aside.append({"what": "lines labelled hour 24", "rows": h24})
        elif h24:
            aside.append({"what": "lines labelled hour 24 (the file also uses hour 0)", "rows": h24})
        if w.get("n_hour_bad"):
            aside.append({"what": "lines with an hour that is not a whole number from 0 to 23",
                          "rows": int(w["n_hour_bad"])})
        if w.get("n_no_name"):
            aside.append({"what": "lines without a monitor name", "rows": int(w["n_no_name"])})
        first, last = w.get("first_day"), w.get("last_day")
    else:
        rows = int(lg.get("n_rows") or 0)
        if not rows:
            refuse.append("The file has no data lines.")
        if lg.get("n_long_name"):
            refuse.append("Some monitor names are longer than 300 characters.")
        if lg.get("n_offset"):
            refuse.append("The times carry a time-zone offset (like +05:30 or Z). VoltProof reads clock times as local "
                          "time and does not convert them; remove the offset and upload again.")
        order = (m.get("long") or {}).get("order")
        if order != "YMD":
            p1, p2 = lg.get("part1_max") or 0, lg.get("part2_max") or 0
            data_order = "DMY" if (p1 > 12 and p2 <= 12) else "MDY" if (p2 > 12 and p1 <= 12) else None
            if data_order and data_order != order:
                refuse.append(f"The dates say {DATE_ORDER_TEXT[data_order].split(' (')[0]}, not "
                              f"{DATE_ORDER_TEXT[order].split(' (')[0]}: choose that order and check again.")
            elif not data_order and p1 <= 12 and p2 <= 12 and lg.get("n_ts_ok"):
                if "long_order" not in (m.get("answered") or []):
                    questions.append({"key": "long_order", "text": f"Your file has times like {lg.get('ts_example')}. "
                                      "Is the day or the month written first?",
                                      "options": [{"value": "DMY", "label": DATE_ORDER_TEXT["DMY"]},
                                                  {"value": "MDY", "label": DATE_ORDER_TEXT["MDY"]}]})
        resolved["long_order"] = order
        ok, bad = int(lg.get("n_ts_ok") or 0), rows - int(lg.get("n_ts_ok") or 0) - int(lg.get("n_offset") or 0)
        if rows and ok < rows / 2:
            refuse.append(f"Most times could not be read with the chosen format (for example "
                          f"{lg.get('ts_bad_example')!r}). VoltProof reads 'date time' such as 2018-06-01 18:42, "
                          f"01-06-2018 18:42 or 06/01/2018 18:42:00.")
        elif bad > 0:
            aside.append({"what": f"lines whose time could not be read (for example {lg.get('ts_bad_example')!r})",
                          "rows": bad})
        if lg.get("n_subminute") or lg.get("n_duplicate"):
            refuse.append("The file has more than one reading per minute for a monitor. VoltProof analyses 1-minute "
                          "readings only (one reading per monitor per minute).")
        gaps, gap1, usual = int(lg.get("n_gaps") or 0), int(lg.get("n_gap_1") or 0), lg.get("usual_gap")
        if gaps and gap1 < gaps / 2:
            refuse.append(f"Readings are usually {usual:g} minutes apart. VoltProof analyses 1-minute readings only; "
                          "other intervals would turn every gap into missing data." if usual else
                          "Readings are not 1 minute apart. VoltProof analyses 1-minute readings only.")
        if lg.get("n_no_name"):
            aside.append({"what": "lines without a monitor name", "rows": int(lg["n_no_name"])})
        first, last = lg.get("first_day"), lg.get("last_day")
    n_values, n_num = int(v.get("n_values") or 0), int(v.get("n_numeric") or 0)
    median = v.get("median_positive")
    if rows and not n_values:
        refuse.append("The file has no voltage readings (all reading cells are empty).")
    elif n_values and n_num < 0.9 * n_values:
        refuse.append("Most reading values are not numbers, so this does not look like voltage readings.")
    elif n_num and int(v.get("n_0_500") or 0) < 0.95 * n_num:
        refuse.append("Many values are below 0 or above 500, so this does not look like household voltage readings "
                      "in volts.")
    elif median is not None and not 150 <= float(median) <= 300:
        refuse.append(f"The typical reading is about {float(median):.0f} V. VoltProof's voltage classes are made for "
                      "India's 230 V household supply (Prayas ESMI thresholds: 130 V or less is no supply), so this "
                      "file would be misread. It was not analysed.")
    monitors = stats["monitors"]
    missing = [x["name"] for x in monitors if not x["has_location"] and x["name"]]
    if not has_location_source and monitors and len(missing) == len(monitors):
        if len(monitors) > MAX_TYPED_MONITORS:
            refuse.append(f"The file has {len(monitors)} monitors. Upload a location file (Location name, From date, "
                          "To date, District, State, Category, Connection Type) instead of typing each one.")
        else:
            questions.append({"key": "typed_locations", "text": "Type the district and state of each monitor (or "
                              "upload a location file).", "monitors": [x["name"] for x in monitors]})
    elif missing:
        aside.append({"what": f"lines of {len(missing)} monitor(s) without a district and state "
                              f"(for example {missing[0]!r})",
                      "rows": sum(x["rows"] for x in monitors if x["name"] in set(missing))})
    states = sorted({x["state"] for x in monitors if x["has_location"] and x["state"]})
    return {"refusals": refuse, "questions": questions, "set_aside": aside, "warnings": warn, "resolved": resolved,
            "rows": rows, "monitors": len(monitors), "monitor_list": monitors[:300], "first_day": first,
            "last_day": last, "states": states, "typical_voltage": None if median is None else round(float(median)),
            "ready_to_build": not refuse and not questions}


def validate(upload_id: str, mapping: dict | None = None) -> dict:
    """Stage the file (only when the file or the column choices changed) and compute the summary in Exasol."""
    rec = load(upload_id)
    if rec["status"] == "building":
        raise UploadError("This upload is being built.")
    if rec["status"] == "ready":
        raise UploadError("This upload has already been built.")
    if not rec.get("readings"):
        raise UploadError("Upload a readings file first.")
    if not rec.get("preview"):
        preview(upload_id)
        rec = load(upload_id)
    m = check_mapping(rec, mapping)
    m["answered"] = [k for k in ("dash_order", "slash_order", "hour_base", "long_order")
                     if (mapping or {}).get(k) is not None or (k == "long_order" and ((mapping or {}).get("long") or {})
                                                               .get("order_confirmed"))]
    key = _stage_key(rec, m)
    with uploader_connect(autocommit=False) as conn:
        if rec.get("stage_key") != key:
            _stage(conn, rec, m)
            rec["stage_key"] = key
        has_locations = bool(rec.get("locations")) or bool(m["typed_locations"])
        for _ in range(2):  # a second pass when the data decided differently from the choices counted with
            run_steps(conn, rec["schema"], [INGEST_DIR / "u20_validate.sql"], params_override=params_for(rec, m),
                      quiet=True)
            summary = _decide(_read_stats(conn), m, has_locations)
            res = summary["resolved"]
            new = {"dash_order": res["dash_order"], "slash_order": res["slash_order"], "hour_base": res["hour_base"]}
            if all(m.get(k) == v for k, v in new.items()):
                break
            m.update(new)
    rec.update(mapping=m, validation=summary, status="validated", error=None)
    save(rec)
    return summary


# ---------------------------------------------------------------- build, delete

def _free_gb(path: str) -> float:
    try:
        return shutil.disk_usage(path).free / 1e9
    except OSError:
        return float("inf")


def check_disk(extra_bytes: int) -> None:
    need = MIN_FREE_GB + 15 * extra_bytes / 1e9
    drives = {"C:\\"} if os.name == "nt" else {"/"}
    drives.add(str(Path(deployment_dir()).anchor or "/"))
    for d in sorted(drives):
        if _free_gb(d) < need:
            raise UploadError(f"Not enough free disk space on {d} to build this upload safely (VoltProof keeps at "
                              f"least {MIN_FREE_GB} GB free). Delete old uploads or free some space, then try again.")


def _window(first: str | None, last: str | None) -> tuple[str, str] | None:
    if not first or not last:
        return None
    a = dt.date.fromisoformat(str(first)[:10]).replace(day=1)
    b = dt.date.fromisoformat(str(last)[:10])
    nxt = (b.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return a.isoformat(), nxt.isoformat()


def build(upload_id: str, progress=None) -> dict:
    """Build a validated upload: u20 + u30 + the unchanged steps 020-100, then the provenance check."""
    rec = load(upload_id)
    val = rec.get("validation") or {}
    if rec["status"] == "ready":
        raise UploadError("This upload has already been built.")
    if rec["status"] not in ("validated", "failed") or not val:
        raise UploadError("Check the file first (validation), then build.")
    if not val.get("ready_to_build"):
        raise UploadError("The checks found problems or open questions; answer them before building.")
    check_disk(int(rec["readings"]["bytes"]))
    m = rec["mapping"]
    steps = [INGEST_DIR / "u20_validate.sql", INGEST_DIR / "u30_canonical.sql"] + resolve_steps(ANALYTICAL_STEPS)
    total = sum(len(split_statements(p.read_text(encoding="utf-8"))) for p in steps)
    with buildlock.build_lock(f"upload {rec['readings']['name']}"):
        rec.update(status="building", error=None, progress={"step": None, "done": 0, "total": total})
        save(rec)
        t0 = time.perf_counter()
        done = {"n": 0}

        def tick(step, idx):
            done["n"] += 1
            rec["progress"] = {"step": step, "done": done["n"], "total": total}
            save(rec)
            if progress:
                progress(step, done["n"], total)
        try:
            params = params_for(rec, m, _window(val.get("first_day"), val.get("last_day")))
            with uploader_connect(autocommit=False) as conn:
                res = run_steps(conn, rec["schema"], steps, params_override=params, quiet=True, progress=tick)
                counts = _fetch_one(conn, "SELECT (SELECT COUNT(*) FROM QUALITY_LOCATION) AS LOCATIONS, "
                                          "(SELECT COUNT(*) FROM READING_CLEAN) AS MINUTES, "
                                          "(SELECT COUNT(*) FROM EVENT) AS EVENTS, "
                                          "(SELECT COUNT(*) FROM MONTHLY) AS MONTHS, "
                                          "(SELECT COUNT(*) FROM MONTHLY WHERE IS_COMPARABLE) AS COMPARABLE_MONTHS, "
                                          "(SELECT COUNT(*) FROM POTENTIAL_SHARED_EVENT) AS SHARED_EVENTS")
            prov = verify_provenance(rec["schema"])
            if prov["different"] or prov["missing"]:
                raise UploadError("The provenance check failed (a build statement does not match Exasol's audit "
                                  "log), so the results are not shown.")
            if not int(counts.get("locations") or 0):
                raise UploadError("Nothing could be analysed: no monitor has readings with a known district and "
                                  "state.")
            rec.update(status="ready", progress=None, build={
                "built_at": _now(), "seconds": round(time.perf_counter() - t0, 1), "statements": len(res),
                "provenance": prov, **{k: int(v or 0) for k, v in counts.items()}})
            save(rec)
            return rec
        except UploadError as e:
            rec.update(status="failed", error=str(e), progress=None)
            save(rec)
            raise
        except Exception as e:  # keep the message plain; the detail goes to the server log, never file contents
            rec.update(status="failed", progress=None,
                       error="The build stopped with a database error. Delete this upload and try again; if it "
                             "happens again, the file may be too large for this laptop.")
            save(rec)
            raise UploadError(rec["error"]) from e


def delete(upload_id: str) -> None:
    """Drop the upload's schema and remove its folder (files, record and any reports rendered from it)."""
    rec = load(upload_id)
    schema = schema_for(upload_id)
    if rec["status"] == "building":
        raise UploadError("This upload is being built; delete it when the build has finished.")
    with uploader_connect() as c:
        c.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    folder = _folder(upload_id).resolve()
    if folder.parent != UPLOAD_DIR.resolve():
        raise UploadError("Unknown upload.")
    shutil.rmtree(folder, ignore_errors=False)


def schema_exists(schema: str) -> bool:
    with connect() as c:
        return bool(c.execute("SELECT COUNT(*) FROM EXA_ALL_SCHEMAS WHERE SCHEMA_NAME = {s}", {"s": schema}).fetchval())


# ---------------------------------------------------------------- command line

def _print_summary(s: dict) -> None:
    print(f"rows {s['rows']:,} | monitors {s['monitors']} | {s['first_day']} to {s['last_day']} | "
          f"states {', '.join(s['states']) or '-'} | typical reading {s['typical_voltage']} V")
    for r in s["refusals"]:
        print("  REFUSED: " + r)
    for q in s["questions"]:
        print("  QUESTION (" + q["key"] + "): " + q["text"])
    for a in s["set_aside"]:
        print(f"  set aside: {a['rows']:,} {a['what']}")
    for w in s["warnings"]:
        print("  note: " + w)
    print("  ready to build" if s["ready_to_build"] else "  not ready to build")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upload your own 1-minute voltage data (stays on this computer).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--readings", required=True)
    n.add_argument("--locations")
    v = sub.add_parser("validate")
    v.add_argument("id")
    v.add_argument("--long-columns", help="LOCATION,TIMESTAMP,VOLTAGE column positions (0-based; '-' for none)")
    v.add_argument("--long-order", choices=sorted(LONG_ORDERS))
    v.add_argument("--single-monitor-name")
    v.add_argument("--dash-order", choices=sorted(DATE_ORDERS))
    v.add_argument("--slash-order", choices=sorted(DATE_ORDERS))
    v.add_argument("--hour-base", type=int, choices=[0, 1])
    v.add_argument("--typed-locations", help="JSON file: [{name, district, state}, ...]")
    b = sub.add_parser("build")
    b.add_argument("id")
    sub.add_parser("list")
    d = sub.add_parser("delete")
    d.add_argument("id")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "new":
            rec = new_upload()
            receive_path(rec["id"], "readings", Path(args.readings))
            if args.locations:
                receive_path(rec["id"], "locations", Path(args.locations))
            pv = preview(rec["id"])
            print(f"upload {rec['id']} -> schema {schema_for(rec['id'])}; layout {pv['layout']}")
            if pv["layout"] == "long":
                print("  columns: " + ", ".join(f"{i}={h}" for i, h in enumerate(pv["header"])))
                print(f"  suggested: {pv['suggest']}")
        elif args.cmd == "validate":
            mapping: dict = {}
            for k in ("dash_order", "slash_order", "hour_base"):
                if getattr(args, k) is not None:
                    mapping[k] = getattr(args, k)
            if args.long_columns or args.long_order or args.single_monitor_name:
                lm: dict = {}
                if args.long_columns:
                    loc, ts, val = (None if x in ("-", "") else int(x) for x in args.long_columns.split(","))
                    lm.update(location_col=loc, ts_col=ts, value_col=val)
                if args.long_order:
                    lm.update(order=args.long_order, order_confirmed=True)
                if args.single_monitor_name:
                    lm["single_monitor_name"] = args.single_monitor_name
                mapping["long"] = lm
            if args.typed_locations:
                mapping["typed_locations"] = json.loads(Path(args.typed_locations).read_text(encoding="utf-8"))
            _print_summary(validate(args.id, mapping))
        elif args.cmd == "build":
            rec = build(args.id, progress=lambda s, i, t: print(f"  {i}/{t} {s}", end="\r"))
            print(f"\nbuilt {rec['schema']}: {rec['build']}")
        elif args.cmd == "list":
            for r in list_uploads():
                print(f"{r['id']}  {r['status']:<10} {r.get('created_at')}  {(r.get('readings') or {}).get('name')}")
        elif args.cmd == "delete":
            delete(args.id)
            print(f"deleted upload {args.id} (schema and files)")
    except (UploadError, buildlock.BuildBusy) as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
