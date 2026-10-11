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

from pipeline.db import connect
from pipeline.run_sql import ensure_schema, resolve_steps, run_steps

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST = REPO_ROOT / "data" / "manifest.json"
LOCATION_FILE_ID = 3360848
NON_DATA_FILES = {3360847}  # About the initiative.pdf

IMPORT_PARAMS = {"column_separator": ",", "row_separator": "LF", "encoding": "UTF8"}
CHUNK_LINES = 20000


def count_data_lines(path: Path) -> int:
    with path.open("rb") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def _stream_with_line_numbers(pipe, src, file_id: int):
    """pyexasol import callback: write '<file_id>,<line_no>,<original line>\\n' for every data line."""
    buf = []
    with open(src, "r", encoding="utf-8", newline="") as fh:
        next(fh)  # header = line 1
        for line_no, line in enumerate(fh, start=2):
            buf.append(f"{file_id},{line_no},{line.rstrip(chr(13) + chr(10))}\n")
            if len(buf) >= CHUNK_LINES:
                pipe.write("".join(buf).encode("utf-8"))
                buf.clear()
    if buf:
        pipe.write("".join(buf).encode("utf-8"))


def load_file(conn, schema: str, file_id: int, path: Path, kind: str, md5: str | None,
              sha256: str | None) -> dict:
    table = "RAW_LOCATION" if kind == "locations" else "RAW_HOURLY"
    expected = count_data_lines(path)
    conn.execute(f"DELETE FROM {table} WHERE FILE_ID = {int(file_id)}")
    conn.execute(f"DELETE FROM SOURCE_FILE WHERE FILE_ID = {int(file_id)}")
    t0 = time.perf_counter()
    conn.import_from_callback(_stream_with_line_numbers, str(path), (schema, table),
                              callback_params={"file_id": int(file_id)}, import_params=IMPORT_PARAMS)
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
    return {"file": path.name, "table": table, "rows": loaded, "seconds": round(seconds, 3),
            "rows_per_second": round(loaded / seconds) if seconds else None,
            "mb_per_second": round(path.stat().st_size / 1e6 / seconds, 2) if seconds else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default="VOLTPROOF")
    args = ap.parse_args(argv)
    schema = args.schema.upper()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = [f for f in manifest["files"]
             if f.get("status") in ("verified", "verified-size-and-rows")
             and f["dataverse_file_id"] not in NON_DATA_FILES]
    if not files:
        raise SystemExit("No verified data files in data/manifest.json. Run scripts\\get-data.ps1 first.")
    files.sort(key=lambda f: f["dataverse_file_id"] != LOCATION_FILE_ID)  # locations first
    results = []
    with connect(autocommit=False) as conn:
        run_steps(conn, schema, resolve_steps(["010"]), quiet=True)
        conn.commit()
        ensure_schema(conn, schema)
        for f in files:
            kind = "locations" if f["dataverse_file_id"] == LOCATION_FILE_ID else "readings"
            r = load_file(conn, schema, f["dataverse_file_id"], RAW_DIR / f["file"], kind, f.get("md5"),
                          f.get("sha256"))
            results.append(r)
            print(f"loaded {r['file']}: {r['rows']:,} rows in {r['seconds']:.2f}s "
                  f"({r['rows_per_second']:,} rows/s, {r['mb_per_second']} MB/s)")
    out = REPO_ROOT / "reports" / "load_raw.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
