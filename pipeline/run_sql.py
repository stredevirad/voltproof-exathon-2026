"""Run the versioned SQL steps in sql/ against an Exasol schema and record provenance in RUN_LOG.

The SQL files are the single source of analytical truth. This module only:
  - loads config/method.yaml into the PARAMS table (flattened "section.key" names),
  - executes each statement of each step in order inside the chosen schema,
  - records file/statement hashes, timings, row counts and Exasol session + statement ids in RUN_LOG.

    .venv\\Scripts\\python.exe -m pipeline.run_sql --schema VOLTPROOF 010 020 030
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import yaml

from pipeline.db import DEFAULT_SCHEMA, connect, schema_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = REPO_ROOT / "sql"
METHOD_YAML = REPO_ROOT / "config" / "method.yaml"
MANIFEST = REPO_ROOT / "data" / "manifest.json"

IDENT = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                             timeout=10)
        return out.stdout.strip() or None
    except OSError:
        return None


def manifest_sha() -> str | None:
    if not MANIFEST.exists():
        return None
    return json.loads(MANIFEST.read_text(encoding="utf-8")).get("files_sha256")


def split_statements(sql: str) -> list[str]:
    """Split on semicolons that end a line, ignoring '--' comment lines. The SQL files are written so
    that statements end with ';' at end of line (no Lua bodies in these files)."""
    stmts, buf = [], []
    for line in sql.splitlines():
        stripped = line.strip()
        if not buf and (stripped == "" or stripped.startswith("--")):
            continue
        buf.append(line)
        if stripped.endswith(";") and not stripped.startswith("--"):
            text = "\n".join(buf).strip()
            stmts.append(text[:-1].rstrip())
            buf = []
    tail = "\n".join(buf).strip()
    if tail and not all(l.strip().startswith("--") or not l.strip() for l in buf):
        stmts.append(tail)
    return stmts


def flatten_params(d: dict, prefix: str = "") -> dict[str, object]:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten_params(v, key + "."))
        else:
            out[key] = v
    return out


def load_params(conn, method_path: Path = METHOD_YAML, overrides: dict | None = None) -> str:
    params = flatten_params(yaml.safe_load(method_path.read_text(encoding="utf-8")))
    if overrides:
        params.update(overrides)
    rows = []
    for name, value in sorted(params.items()):
        if isinstance(value, bool):
            rows.append((name, 1.0 if value else 0.0, str(value).lower()))
        elif isinstance(value, (int, float)):
            rows.append((name, float(value), str(value)))
        elif value is None:
            rows.append((name, None, None))
        else:
            rows.append((name, None, str(value)))
    conn.execute("DELETE FROM PARAMS")
    conn.ext.insert_multi("PARAMS", rows, columns=["NAME", "NUM_VALUE", "STR_VALUE"])
    return sha256_text(json.dumps(rows, sort_keys=True))


def resolve_steps(selectors: list[str]) -> list[Path]:
    files = sorted(SQL_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    if not selectors:
        return files
    chosen = []
    for sel in selectors:
        match = [f for f in files if f.name.startswith(sel)]
        if not match:
            raise SystemExit(f"No SQL step matches {sel!r}")
        chosen.extend(m for m in match if m not in chosen)
    return chosen


def ensure_schema(conn, schema: str) -> None:
    if not IDENT.match(schema):
        raise SystemExit(f"Invalid schema name {schema!r}")
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    conn.execute(f"OPEN SCHEMA {schema}")


def run_steps(conn, schema: str, steps: list[Path], params_override: dict | None = None,
              quiet: bool = False) -> list[dict]:
    if conn.attr.get("autocommit"):
        raise RuntimeError("run_steps needs a connection opened with autocommit=False "
                           "(statement ids for provenance are only exact without auto-commits).")
    ensure_schema(conn, schema)
    run_id = dt.datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    commit, man = git_commit(), manifest_sha()
    params_sha = None
    results = []
    for path in steps:
        sql = path.read_text(encoding="utf-8")
        file_sha = sha256_text(sql)
        if params_sha is None and not path.name.startswith("010_"):
            # PARAMS exists once 010 has run; load parameters before the first analytical step
            params_sha = load_params(conn, overrides=params_override)
        for idx, stmt in enumerate(split_statements(sql), start=1):
            # The probe SELECT is statement n, so the pipeline statement is n + 1. This holds only with
            # autocommit OFF: in autocommit mode Exasol inserts "COMMIT /* AUTO */" after every statement
            # (probe included), which shifts the numbering. run_steps therefore requires a non-autocommit
            # connection and commits once per step. Verified against EXA_DBA_AUDIT_SQL by
            # pipeline/check_provenance.py.
            stmt_id = int(conn.execute("SELECT CURRENT_STATEMENT").fetchval()) + 1
            started = dt.datetime.now()
            t0 = time.perf_counter()
            st = conn.execute(stmt)
            wall = time.perf_counter() - t0
            rows = st.rowcount() if st.result_type == "rowCount" else None
            session_id = int(conn.session_id())
            rec = {
                "run_id": run_id, "step": path.name, "stmt_index": idx, "sql_file_sha256": file_sha,
                "stmt_sha256": sha256_text(stmt), "params_sha256": params_sha, "started_at": started,
                "finished_at": dt.datetime.now(), "wall_seconds": round(wall, 3), "rows": rows,
                "session_id": session_id, "stmt_id": stmt_id,
            }
            results.append(rec)
            if path.name.startswith("010_") and idx == 1:
                pass  # RUN_LOG may not exist before the first statement of 010
            if not quiet:
                first_line = " ".join(stmt.split())[:90]
                print(f"  {path.name} #{idx:<3} {wall:8.3f}s rows={rows!s:<12} {first_line}")
        # write this step's provenance (RUN_LOG exists after 010)
        conn.ext.insert_multi(
            "RUN_LOG",
            [(r["run_id"], r["step"], r["stmt_index"], r["sql_file_sha256"], r["stmt_sha256"],
              r["params_sha256"], r["started_at"].isoformat(sep=" ", timespec="milliseconds"),
              r["finished_at"].isoformat(sep=" ", timespec="milliseconds"), r["wall_seconds"], r["rows"],
              r["session_id"], r["stmt_id"], commit, man)
             for r in results if r["step"] == path.name],
            columns=["RUN_ID", "STEP", "STMT_INDEX", "SQL_FILE_SHA256", "STMT_SHA256", "PARAMS_SHA256",
                     "STARTED_AT", "FINISHED_AT", "WALL_SECONDS", "ROWS_AFFECTED", "EXA_SESSION_ID",
                     "EXA_STMT_ID", "APP_GIT_COMMIT", "DATA_MANIFEST_SHA256"],
        )
        conn.commit()  # one transaction per step: a failing step leaves the previous state intact
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=DEFAULT_SCHEMA)
    ap.add_argument("steps", nargs="*", help="step prefixes, e.g. 010 020 (default: all)")
    args = ap.parse_args(argv)
    steps = resolve_steps(args.steps)
    with connect() as c:
        if schema_dataset(c, args.schema)["synthetic"]:
            raise SystemExit(f"Schema {args.schema.upper()} holds the SYNTHETIC demo set; rebuild it with "
                             "scripts\\load.ps1 -Set demo (running steps here would apply the real-data parameters).")
    with connect(autocommit=False) as conn:
        res = run_steps(conn, args.schema.upper(), steps)
    total = sum(r["wall_seconds"] for r in res)
    print(f"ran {len(res)} statements from {len(steps)} step(s) in {total:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
