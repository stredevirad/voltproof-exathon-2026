"""Build the production schema end to end: load verified raw files, run every SQL step, check quality
and provenance. Used by scripts\\load.ps1.

    .venv\\Scripts\\python.exe -m pipeline.build --schema VOLTPROOF
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pipeline import load_raw
from pipeline.db import connect
from pipeline.run_sql import resolve_steps, run_steps

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYTICAL_STEPS = ["020", "030", "040", "050", "060", "070", "080", "090", "095"]
MAX_QUARANTINE_SHARE = 0.5


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default="VOLTPROOF")
    ap.add_argument("--skip-load", action="store_true", help="reuse raw tables already loaded")
    args = ap.parse_args(argv)
    schema = args.schema.upper()
    t0 = time.perf_counter()
    if not args.skip_load:
        load_raw.main(["--schema", schema])
    with connect(autocommit=False) as conn:
        res = run_steps(conn, schema, resolve_steps(ANALYTICAL_STEPS))
        files = conn.execute(
            f"SELECT FILE_NAME, FILE_KIND, ROWS_LOADED, ROWS_QUARANTINED, VALUES_QUARANTINED, MINUTES_IN_SCOPE "
            f"FROM {schema}.QUALITY_FILE ORDER BY FILE_ID").fetchall()
        summary = conn.execute(
            f"""SELECT (SELECT COUNT(*) FROM {schema}.QUALITY_LOCATION), (SELECT COUNT(*) FROM {schema}.READING_CLEAN),
                       (SELECT COUNT(*) FROM {schema}.EVENT), (SELECT COUNT(*) FROM {schema}.DAILY),
                       (SELECT COUNT(*) FROM {schema}.MONTHLY),
                       (SELECT COUNT(*) FROM {schema}.MONTHLY WHERE IS_COMPARABLE)""").fetchone()
    problems = []
    print("\nper-file quality:")
    for name, kind, loaded, q_rows, q_vals, in_scope in files:
        loaded, q_rows = int(loaded or 0), int(q_rows or 0)
        print(f"  {name}: {loaded:,} rows loaded, {q_rows:,} rows quarantined, {int(q_vals or 0):,} values "
              f"quarantined, {int(in_scope or 0):,} minutes in scope")
        if kind == "readings" and loaded and q_rows / loaded > MAX_QUARANTINE_SHARE:
            problems.append(f"{name}: {q_rows:,} of {loaded:,} rows quarantined; layout or format probably changed")
        if kind == "readings" and loaded and not in_scope:
            print(f"  note: {name} has no readings for the analytical scope (subset.* in config/method.yaml)")
    locs, minutes, events, days, months, comparable = (int(x) for x in summary)
    print(f"\nscope: {locs} locations | {minutes:,} clean minutes | {events:,} outage events | {days:,} "
          f"location-days | {months:,} location-months ({comparable:,} comparable)")
    total = sum(r["wall_seconds"] for r in res)
    print(f"SQL steps: {len(res)} statements in {total:.1f}s; build wall time {time.perf_counter() - t0:.1f}s")
    (REPO_ROOT / "reports").mkdir(exist_ok=True)
    (REPO_ROOT / "reports" / "build_summary.json").write_text(json.dumps({
        "schema": schema, "locations": locs, "clean_minutes": minutes, "events": events, "days": days,
        "months": months, "comparable_months": comparable, "sql_seconds": round(total, 2),
        "steps": [{k: (str(v) if k in ("started_at", "finished_at") else v) for k, v in r.items()} for r in res],
    }, indent=1), encoding="utf-8")
    if problems:
        print("\nBUILD FAILED:\n  " + "\n  ".join(problems))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
