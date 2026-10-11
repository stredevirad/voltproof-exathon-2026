"""G3 evidence: profile date formats, duplicates and conflicts in raw ESMI files (read-only).

    .venv\\Scripts\\python.exe -m pipeline.profile_2019 "data/raw/ESMI voltage data 2019 Jan-June.csv" ...
"""

from __future__ import annotations

import collections
import csv
import re
import sys
from pathlib import Path

DMY = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
SLASH = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def profile(path: Path, up_names: set[str]) -> None:
    fmt = collections.Counter()
    first_max = second_max = 0
    keys = collections.defaultdict(list)
    widths = collections.Counter()
    crlf = None
    with path.open("rb") as fb:
        head = fb.read(2000)
        crlf = b"\r\n" in head
    with path.open(newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        for row in rd:
            widths[len(row)] += 1
            d = row[1].strip()
            if DMY.match(d):
                fmt["DD-MM-YYYY"] += 1
            elif m := SLASH.match(d):
                fmt["a/b/YYYY"] += 1
                first_max = max(first_max, int(m.group(1)))
                second_max = max(second_max, int(m.group(2)))
            else:
                fmt["other"] += 1
            keys[(row[0], d, row[2])].append(tuple(row[3:]))
    dup_same = sum(1 for v in keys.values() if len(v) > 1 and len(set(v)) == 1)
    dup_diff = sum(1 for v in keys.values() if len(v) > 1 and len(set(v)) > 1)
    diff_cells = 0
    for v in keys.values():
        if len(v) > 1 and len(set(v)) > 1:
            diff_cells += sum(1 for i in range(60) if len({r[i] for r in v}) > 1)
    up_keys = [k for k in keys if k[0] in up_names]
    up_diff = sum(1 for k in up_keys if len(keys[k]) > 1 and len(set(keys[k])) > 1)
    print(f"=== {path.name}")
    print(f"  header ok: {len(header) == 63}; widths {dict(widths)}; CRLF: {crlf}")
    print(f"  date formats: {dict(fmt)}; slash dates: max first part {first_max}, max second part {second_max}")
    print(f"  rows {sum(len(v) for v in keys.values()):,}; distinct location-hours {len(keys):,}")
    print(f"  repeated location-hours: identical {dup_same:,}, differing {dup_diff:,} ({diff_cells:,} differing minute cells)")
    print(f"  UP location-hours {len(up_keys):,}, of which differing repeats {up_diff:,}")
    ex = [k for k, v in keys.items() if len(v) > 1 and len(set(v)) > 1][:2]
    for k in ex:
        v = keys[k]
        diffs = [i for i in range(60) if len({r[i] for r in v}) > 1]
        print(f"  example {k}: {len(v)} copies; differing minutes {diffs[:12]}... e.g. min {diffs[0]}: "
              f"{[r[diffs[0]] for r in v]}")


def main(argv: list[str]) -> int:
    loc = Path("data/raw/ESMI location information.csv")
    with loc.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    up = {r["Location name"] for r in rows if r["State"].strip() == "Uttar Pradesh"}
    for f in argv:
        profile(Path(f), up)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
