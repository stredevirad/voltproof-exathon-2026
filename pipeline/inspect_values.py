"""G1 inspection of specific voltage values (read-only evidence tooling).

Answers: which locations produce a given value, how it is distributed over time, what surrounds it
(runs), and how many readings exceed thresholds. Writes reports/value_inspection.json.

    .venv\\Scripts\\python.exe -m pipeline.inspect_values "data/raw/<file>.csv"
"""

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (101, 99, 350)


def main(path: str) -> int:
    per_loc = {t: collections.Counter() for t in TARGETS}
    over_350 = collections.Counter()
    max_by_loc = collections.Counter()
    run_examples = {t: [] for t in TARGETS}
    pure_rows = {t: collections.Counter() for t in TARGETS}  # rows where all 60 values == t
    hi_examples = []
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        for row in rd:
            loc, d, h = row[0], row[1], row[2]
            vals = [int(x) for x in row[3:]]
            mx = max(vals)
            if mx > max_by_loc[loc]:
                max_by_loc[loc] = mx
            for t in TARGETS:
                c = vals.count(t)
                if c:
                    per_loc[t][loc] += c
                    if c == 60:
                        pure_rows[t][loc] += 1
                    if len(run_examples[t]) < 6 and c >= 5:
                        run_examples[t].append({"location": loc, "date": d, "hour": h, "values": vals})
            n_over = sum(v > 350 for v in vals)
            if n_over:
                over_350[loc] += n_over
                if len(hi_examples) < 4:
                    hi_examples.append({"location": loc, "date": d, "hour": h, "values": vals})
    out = {
        "file": Path(path).name,
        "value_by_location_top": {str(t): per_loc[t].most_common(8) for t in TARGETS},
        "locations_with_value": {str(t): len(per_loc[t]) for t in TARGETS},
        "hours_entirely_that_value": {str(t): sum(pure_rows[t].values()) for t in TARGETS},
        "hours_entirely_that_value_by_location": {str(t): pure_rows[t].most_common(5) for t in TARGETS},
        "cells_over_350_by_location": over_350.most_common(10),
        "locations_with_max_over_350": sum(1 for v in max_by_loc.values() if v > 350),
        "examples": {str(t): run_examples[t][:3] for t in TARGETS},
        "examples_over_350": hi_examples,
    }
    target = REPO_ROOT / "reports" / "value_inspection.json"
    target.write_text(json.dumps(out, indent=1), encoding="utf-8")
    brief = {k: v for k, v in out.items() if not k.startswith("examples")}
    print(json.dumps(brief, indent=1))
    for t in TARGETS:
        for ex in out["examples"][str(t)][:2]:
            print(f"example {t}: {ex['location']} {ex['date']} h{ex['hour']}: {ex['values']}")
    for ex in hi_examples[:2]:
        print(f"example >350: {ex['location']} {ex['date']} h{ex['hour']}: {ex['values']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
