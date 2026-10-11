"""Profile raw ESMI files (G1 evidence). Plain-Python, read-only; prints a summary and writes
reports/raw_profile_<file>.json. This is inspection tooling, not part of the analytical pipeline.

    .venv\\Scripts\\python.exe -m pipeline.profile_raw "data/raw/ESMI minute-wise voltage data 2018 June-Aug.csv"
"""

from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCATION_FILE = REPO_ROOT / "data" / "raw" / "ESMI location information.csv"


def profile_locations() -> dict:
    with LOCATION_FILE.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    names = [r["Location name"] for r in rows]
    dup_names = [n for n, c in collections.Counter(names).items() if c > 1]
    bad_dates = []
    for r in rows:
        for col in ("From date", "To date"):
            try:
                dt.datetime.strptime(r[col].strip(), "%d-%m-%Y")
            except ValueError:
                bad_dates.append((r["Location name"], col, r[col]))
    up = [r for r in rows if r["State"].strip().lower() == "uttar pradesh"]
    return {
        "rows": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "duplicate_names": dup_names,
        "offline_marked": sum("[Offline]" in n for n in names),
        "states": collections.Counter(r["State"].strip() for r in rows).most_common(),
        "categories": collections.Counter(r["Category"].strip() for r in rows).most_common(),
        "connection_types": collections.Counter(r["Connection Type"].strip() for r in rows).most_common(),
        "unparseable_dates": bad_dates[:20],
        "up_locations": len(up),
        "up_by_category_connection": collections.Counter(
            (r["Category"].strip(), r["Connection Type"].strip()) for r in up).most_common(),
        "up_districts": sorted({r["District"].strip() for r in up}),
    }


def profile_data(path: Path, loc_names: set[str]) -> dict:
    hours = collections.Counter()
    values = collections.Counter()
    nonint = 0
    blank = 0
    nonnum = 0
    widths = collections.Counter()
    keys = collections.Counter()
    loc_rows = collections.Counter()
    dates = set()
    bad_date = 0
    first_last = {}
    with path.open(newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        for row in rd:
            widths[len(row)] += 1
            if len(row) < 3:
                continue
            loc, d, h = row[0], row[1], row[2]
            loc_rows[loc] += 1
            keys[(loc, d, h)] += 1
            hours[h] += 1
            try:
                day = dt.datetime.strptime(d.strip(), "%d-%m-%Y").date()
                dates.add(day)
                fl = first_last.get(loc)
                first_last[loc] = (min(fl[0], day), max(fl[1], day)) if fl else (day, day)
            except ValueError:
                bad_date += 1
            for cell in row[3:]:
                c = cell.strip()
                if c == "":
                    blank += 1
                    continue
                try:
                    v = float(c)
                except ValueError:
                    nonnum += 1
                    continue
                if v != int(v):
                    nonint += 1
                values[int(v) if v == int(v) else v] += 1
    dup_keys = sum(1 for c in keys.values() if c > 1)
    total_cells = sum(values.values())
    zero = values.get(0, 0)
    between_1_130 = sum(c for v, c in values.items() if 0 < v <= 130)
    return {
        "file": path.name,
        "header_columns": len(header),
        "header_first": header[:4],
        "header_last": header[-2:],
        "row_widths": dict(widths),
        "data_rows": sum(loc_rows.values()),
        "locations": len(loc_rows),
        "locations_not_in_location_file": sorted(set(loc_rows) - loc_names)[:50],
        "date_min": str(min(dates)) if dates else None,
        "date_max": str(max(dates)) if dates else None,
        "unparseable_dates": bad_date,
        "hours_seen": sorted(hours, key=lambda x: int(x) if x.isdigit() else 99),
        "duplicate_location_date_hour_keys": dup_keys,
        "cells_numeric": total_cells,
        "cells_blank": blank,
        "cells_non_numeric": nonnum,
        "cells_non_integer": nonint,
        "value_min": min(values) if values else None,
        "value_max": max(values) if values else None,
        "cells_zero": zero,
        "cells_1_to_130": between_1_130,
        "cells_at_350": values.get(350, 0),
        "cells_over_300": sum(c for v, c in values.items() if v > 300),
        "value_histogram_by_10V": dict(sorted(collections.Counter((int(v) // 10) * 10 for v in values.elements()).items()))
        if total_cells < 0 else None,  # disabled (too slow); see buckets below
        "buckets": {
            "0": zero,
            "1-130": between_1_130,
            "131-204": sum(c for v, c in values.items() if 130 < v < 205),
            "205-270": sum(c for v, c in values.items() if 205 <= v <= 270),
            "271-349": sum(c for v, c in values.items() if 270 < v < 350),
            "350": values.get(350, 0),
        },
        "low_values_1_to_130_top": sorted(((v, c) for v, c in values.items() if 0 < v <= 130),
                                          key=lambda x: -x[1])[:15],
        "first_last_day_sample": {k: (str(a), str(b)) for k, (a, b) in list(first_last.items())[:5]},
    }


def main(argv: list[str]) -> int:
    loc = profile_locations()
    with LOCATION_FILE.open(newline="", encoding="utf-8") as fh:
        names = {r["Location name"] for r in csv.DictReader(fh)}
    out = {"location_file": loc}
    for f in argv:
        out[Path(f).name] = profile_data(Path(f), names)
    target = REPO_ROOT / "reports" / "raw_profile.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=1, default=str)[:12000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
