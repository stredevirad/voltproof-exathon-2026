"""G4 sanity evidence for one real district-month: baseline table, one example group, and a raw-CSV
spot check of that group's members (plain Python reading of the source file).

    .venv\\Scripts\\python.exe -m pipeline.g4_sanity Bahraich 2018-07
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

from pipeline.db import connect

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw" / "ESMI minute-wise voltage data 2018 June-Aug.csv"


def main(district: str, month: str) -> int:
    with connect(schema="VOLTPROOF") as c:
        print("COINCIDENCE_BASELINE (all district-months in scope):")
        for r in c.execute("SELECT DISTRICT, MONTH_KEY, N_LOCATIONS, N_INTERRUPTIONS, OBSERVED_PAIRS, "
                           "EXPECTED_PAIRS, P_VALUE FROM COINCIDENCE_BASELINE ORDER BY 1, 2").fetchall():
            ratio = float(r[4]) / float(r[5]) if float(r[5]) else float("inf")
            print(f"  {r[0]:<12} {r[1]}  locs={r[2]:>3} interruptions={r[3]:>6} observed={r[4]:>6} "
                  f"expected={float(r[5]):>9.1f} ratio={ratio:6.1f} p={float(r[6]):.2f}")
        g = c.execute(
            """SELECT GROUP_ID, GROUP_KEY, START_TS, END_TS, N_MEMBERS, N_LOCATIONS, N_PAIRS
               FROM POTENTIAL_SHARED_EVENT
               WHERE DISTRICT = {d} AND TO_CHAR(START_TS, 'YYYY-MM') = {m} AND HOUR(START_TS) BETWEEN 17 AND 22
               ORDER BY N_LOCATIONS DESC, START_TS LIMIT 1""", {"d": district, "m": month}).fetchone()
        print(f"\nexample evening group in {district} {month}: id={g[0]} key={g[1]} span {g[2]} -> {g[3]} "
              f"members={g[4]} locations={g[5]} pairs={g[6]}")
        members = c.execute(
            """SELECT l.SOURCE_NAME, m.START_TS, m.END_TS, m.OFFSET_FROM_GROUP_START_MIN
               FROM POTENTIAL_SHARED_MEMBER m JOIN LOCATION l ON l.LOCATION_ID = m.LOCATION_ID
               WHERE m.GROUP_ID = {g} ORDER BY m.START_TS, l.SOURCE_NAME""", {"g": g[0]}).fetchall()
        n_mon = c.execute("SELECT COUNT(DISTINCT LOCATION_ID) FROM INTERRUPTION WHERE DISTRICT = {d} "
                          "AND TO_CHAR(START_TS,'YYYY-MM') = {m}", {"d": district, "m": month}).fetchval()
    print(f"  ({n_mon} locations in {district} had interruptions that month)")
    # raw spot check: first outage minute (<= 130 V) at or after the member start, read straight from the CSV
    want = {(name, str(s)[:16]) for name, s, _, _ in members}
    found = {}
    names = {name for name, *_ in members}
    with RAW.open(newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            if row[0] not in names:
                continue
            day = dt.datetime.strptime(row[1], "%d-%m-%Y")
            for i, v in enumerate(row[3:]):
                ts = (day + dt.timedelta(hours=int(row[2]), minutes=i)).strftime("%Y-%m-%d %H:%M")
                if (row[0], ts) in want:
                    found[(row[0], ts)] = (row[3 + i - 1] if i > 0 else "(prev hour)", v)
    for name, s, e, off in members:
        k = (name, str(s)[:16])
        prev_v, v = found.get(k, ("?", "?"))
        print(f"  {name:<34} {str(s)[:16]} -> {str(e)[:16]}  offset +{int(off)} min | raw: previous minute "
              f"{prev_v} V, this minute {v} V")
    ok = all(k in found and float(found[k][1]) <= 130 for k in want)
    print(f"raw spot check (every member starts on a reading <= 130 V): {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
