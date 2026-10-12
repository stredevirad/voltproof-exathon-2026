"""Warm up the database for a live demo: run the guided demo's queries once (so the first day view is not slow
after a database start) and pre-render the guided demo's evidence report. Runs no SQL build step, so it never
changes the data the pre-rendered report was built from.

Usage: scripts\\warmup.ps1 (after scripts\\exa.ps1 start, and again after any rebuild)
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "reports" / "warmup.json"


def main() -> int:
    from app.api import report, service

    t_all = time.perf_counter()
    demo = service.demo()
    if not demo:
        print("No guided-demo example in this build (load at least the 2018 June-Aug file).")
        return 1
    lid, month, day, key, group = demo["location_id"], demo["month"], demo["day"], demo["event_key"], demo["group_key"]
    steps = [
        ("home: locations", lambda: service.locations()),
        ("home: months of the demo location", lambda: service.location(lid)),
        ("location-month view", lambda: service.month(lid, month)),
        ("day view", lambda: service.day(lid, day)),
        ("event evidence", lambda: service.event(key)),
        ("shared-event group", lambda: service.group(group)),
        ("evidence report (pre-render or reuse)", lambda: report.generate(lid, month, pdf=True)),
    ]
    timings = []
    for name, fn in steps:
        t0 = time.perf_counter()
        result = fn()
        timings.append({"step": name, "seconds": round(time.perf_counter() - t0, 3)})
        extra = ""
        if isinstance(result, dict) and "report_id" in result:
            extra = (f"  {result['report_id']}, generated {result['generated_at_ist']}"
                     f"{' (reused)' if result.get('reused') else ' (rendered now)'}")
        print(f"  {name:40s} {timings[-1]['seconds']:7.2f} s{extra}")
    total = round(time.perf_counter() - t_all, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"finished_local": dt.datetime.now().isoformat(timespec="seconds"), "demo": demo,
                               "timings": timings, "total_seconds": total}, indent=1), encoding="utf-8")
    print(f"warm-up done in {total} s; the guided demo path is ready (other days may still take a few seconds "
          f"the first time)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
