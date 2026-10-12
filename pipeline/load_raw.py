"""Load raw ESMI files into Exasol with the native IMPORT (pyexasol HTTP transport).

Each data line is streamed unchanged, prefixed with "<file_id>,<line_no>," so the database stores the
exact physical source line number for provenance. Exasol parses the CSV, and no values are parsed or
altered in Python. Re-running replaces the rows of that file (idempotent).

    .venv\\Scripts\\python.exe -m pipeline.load_raw --schema VOLTPROOF --set first
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

from pipeline.db import DEFAULT_SCHEMA, connect
from pipeline.run_sql import ensure_schema, resolve_steps, run_steps

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST = REPO_ROOT / "data" / "manifest.json"
LOCATION_FILE_ID = 3360848
NON_DATA_FILES = {3360847}  # About the initiative.pdf

IMPORT_PARAMS = {"column_separator": ",", "row_separator": "LF", "encoding": "UTF8"}
CHUNK_LINES = 20000


READINGS_HEADER = ["Location name", "Date", "Hour"] + [f"Min {i}" for i in range(60)]
LOCATIONS_HEADER = ["Location name", "From date", "To date", "District", "State", "Category",
                    "Connection Type"]


class RawFileError(ValueError):
    """A raw file cannot be loaded as-is (empty, wrong encoding, unexpected header)."""


def check_header(path: Path, kind: str) -> None:
    """Fail early and clearly instead of loading a file whose layout we would misread."""
    raw = path.read_bytes()[:4096]
    if not raw:
        raise RawFileError(f"{path.name}: the file is empty (0 bytes); expected a header row.")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:200]:
        raise RawFileError(f"{path.name}: looks like UTF-16 (byte-order mark / NUL bytes). Save it as UTF-8/ASCII CSV.")
    try:  # header line only; data lines are checked while streaming (with their line number)
        first = raw.split(b"\n", 1)[0].decode("utf-8").lstrip("﻿").rstrip("\r")
    except UnicodeDecodeError as e:
        raise RawFileError(f"{path.name}: header is not valid UTF-8 ({e.reason} at byte {e.start}).") from None
    header = [c.strip() for c in first.split(",")]
    expected = LOCATIONS_HEADER if kind == "locations" else READINGS_HEADER
    if header != expected:
        diff_at = next((i for i, (a, b) in enumerate(zip(header, expected, strict=False)) if a != b), min(len(header), len(expected)))
        raise RawFileError(
            f"{path.name}: unexpected header (column {diff_at + 1}: got "
            f"{header[diff_at] if diff_at < len(header) else '<missing>'!r}, expected "
            f"{expected[diff_at] if diff_at < len(expected) else '<none>'!r}; {len(header)} columns vs {len(expected)}).")


def count_data_lines(path: Path) -> int:
    with path.open("rb") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def _stream_with_line_numbers(pipe, src, file_id: int):
    """pyexasol import callback: write '<file_id>,<line_no>,<original line>\\n' for every data line."""
    buf = []
    with open(src, "rb") as fh:
        next(fh)  # header = line 1
        for line_no, raw_line in enumerate(fh, start=2):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as e:
                raise RawFileError(f"{Path(src).name}: line {line_no} is not valid UTF-8 "
                                   f"({e.reason} at byte {e.start} of the line).") from None
            buf.append(f"{file_id},{line_no},{line.rstrip(chr(13) + chr(10))}\n")
            if len(buf) >= CHUNK_LINES:
                pipe.write("".join(buf).encode("utf-8"))
                buf.clear()
    if buf:
        pipe.write("".join(buf).encode("utf-8"))


def declared_periods() -> dict[int, dict]:
    """config/source_files.yaml: declared period and optional exclusion reason per Dataverse file id."""
    import yaml
    p = REPO_ROOT / "config" / "source_files.yaml"
    return {int(k): v for k, v in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).items()}


MAX_IMPORT_ATTEMPTS = 2


def is_transient_import_error(exc: BaseException) -> bool:
    """A dropped HTTP transport during IMPORT (ETL-5105 'failed after N bytes' / receive failure), not a data error."""
    text = str(exc)
    return "ETL-5105" in text and ("Failure when receiving data from the peer" in text or "failed after" in text)


def load_file(conn, schema: str, file_id: int, path: Path, kind: str, md5: str | None,
              sha256: str | None, declared: dict | None = None) -> dict:
    table = "RAW_LOCATION" if kind == "locations" else "RAW_HOURLY"
    check_header(path, kind)
    expected = count_data_lines(path)
    attempts = 0
    while True:
        attempts += 1
        conn.execute(f"DELETE FROM {table} WHERE FILE_ID = {int(file_id)}")
        conn.execute(f"DELETE FROM SOURCE_FILE WHERE FILE_ID = {int(file_id)}")
        conn.execute(f"DELETE FROM SOURCE_FILE_DECLARED WHERE FILE_ID = {int(file_id)}")
        if declared:
            conn.ext.insert_multi(
                "SOURCE_FILE_DECLARED",
                [(int(file_id), str(declared.get("period_from")) if declared.get("period_from") else None,
                  str(declared.get("period_to")) if declared.get("period_to") else None,
                  declared.get("exclude_reason"))],
                columns=["FILE_ID", "PERIOD_FROM", "PERIOD_TO", "EXCLUDE_REASON"])
        t0 = time.perf_counter()
        try:
            if expected > 0:  # a header-only file is valid and simply contributes no rows
                conn.import_from_callback(_stream_with_line_numbers, str(path), (schema, table),
                                          callback_params={"file_id": int(file_id)}, import_params=IMPORT_PARAMS)
            break
        except Exception as exc:
            # D-032: the HTTP transport between Windows and the database VM can drop mid-file (ETL-5105).
            # The whole file is rolled back (deletes included) and imported again, once; anything else fails.
            if attempts >= MAX_IMPORT_ATTEMPTS or not is_transient_import_error(exc):
                raise
            conn.rollback()
            print(f"  retrying {path.name}: transient IMPORT transport error ({str(exc).strip()[:120]})")
    seconds = time.perf_counter() - t0
    loaded = int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE FILE_ID = {int(file_id)}").fetchval())
    conn.ext.insert_multi(
        "SOURCE_FILE",
        [(int(file_id), path.name, kind, path.stat().st_size, md5, sha256, expected, loaded,
          dt.datetime.now().isoformat(sep=" ", timespec="seconds"), round(seconds, 3))],
        columns=["FILE_ID", "FILE_NAME", "FILE_KIND", "BYTES", "MD5", "SHA256", "ROWS_EXPECTED",
                 "ROWS_LOADED", "LOADED_AT", "LOAD_SECONDS"],
    )
    conn.commit()
    if loaded != expected:
        raise RuntimeError(f"{path.name}: loaded {loaded} rows but the file has {expected} data lines")
    return {"file": path.name, "table": table, "rows": loaded, "seconds": round(seconds, 3), "attempts": attempts,
            "rows_per_second": round(loaded / seconds) if seconds else None,
            "mb_per_second": round(path.stat().st_size / 1e6 / seconds, 2) if seconds else None}


def load_paths(conn, schema: str, files: list[tuple]) -> list[dict]:
    """Load explicit (file_id, path, kind[, declared]) entries into `schema` (used by fixtures and tests).
    The connection must have autocommit off; raw tables are created first."""
    run_steps(conn, schema, resolve_steps(["010"]), quiet=True)
    ensure_schema(conn, schema)
    return [load_file(conn, schema, f[0], f[1], f[2], None, None, f[3] if len(f) > 3 else None) for f in files]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=DEFAULT_SCHEMA)
    ap.add_argument("--manifest", default=str(MANIFEST), help="verified-file manifest (default data/manifest.json)")
    ap.add_argument("--raw-dir", default=str(RAW_DIR), help="folder holding the manifest's files")
    args = ap.parse_args(argv)
    schema = args.schema.upper()
    raw_dir = Path(args.raw_dir)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    files = [f for f in manifest["files"]
             if f.get("status") in ("verified", "verified-size-and-rows")
             and f["dataverse_file_id"] not in NON_DATA_FILES]
    if not files:
        raise SystemExit(f"No verified data files in {args.manifest}. Run scripts\\get-data.ps1 first.")

    def kind_of(f: dict) -> str:  # the synthetic manifest names the kind; real files are known by Dataverse id
        return f.get("kind") or ("locations" if f["dataverse_file_id"] == LOCATION_FILE_ID else "readings")

    files.sort(key=lambda f: kind_of(f) != "locations")  # locations first
    config_declared = declared_periods()
    declared = {int(f["dataverse_file_id"]): (f["declared"] if "declared" in f
                                              else config_declared.get(int(f["dataverse_file_id"])))
                for f in files}
    results = []
    with connect(autocommit=False) as conn:
        run_steps(conn, schema, resolve_steps(["010"]), quiet=True)
        conn.commit()
        ensure_schema(conn, schema)
        for f in files:
            r = load_file(conn, schema, f["dataverse_file_id"], raw_dir / f["file"], kind_of(f), f.get("md5"),
                          f.get("sha256"), declared.get(int(f["dataverse_file_id"])))
            results.append(r)
            print(f"loaded {r['file']}: {r['rows']:,} rows in {r['seconds']:.2f}s "
                  f"({r['rows_per_second']:,} rows/s, {r['mb_per_second']} MB/s)")
    out = REPO_ROOT / "reports" / "load_raw.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
