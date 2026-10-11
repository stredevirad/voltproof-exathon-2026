"""Render fixture YAML files into raw CSVs in the exact ESMI byte layout (header row, CRLF line ends).

    .venv\\Scripts\\python.exe -m tests.fixtures.render          # all fixtures
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

FIXTURE_DIR = Path(__file__).resolve().parent
OUT_DIR = FIXTURE_DIR / "rendered"
READING_HEADER = ["Location name", "Date", "Hour"] + [f"Min {i}" for i in range(60)]
LOCATION_HEADER = ["Location name", "From date", "To date", "District", "State", "Category",
                   "Connection Type"]


def expand(values: str) -> list[str]:
    cells: list[str] = []
    for tok in str(values).split():
        if "*" in tok:
            v, n = tok.rsplit("*", 1)
            cells.extend(["" if v == "_" else v] * int(n))
        else:
            cells.append("" if tok == "_" else tok)
    if len(cells) != 60:
        raise ValueError(f"values expand to {len(cells)} cells, expected 60: {values!r}")
    return cells


def _dates(h: dict) -> list[str]:
    """`date: DD-MM-YYYY` or `dates: DD-MM-YYYY..DD-MM-YYYY` (inclusive range)."""
    import datetime as dt
    if "dates" not in h:
        return [h["date"]]
    a, b = (dt.datetime.strptime(x.strip(), "%d-%m-%Y").date() for x in h["dates"].split(".."))
    out = []
    while a <= b:
        out.append(a.strftime("%d-%m-%Y"))
        a += dt.timedelta(days=1)
    return out


def _hours(hour) -> list:
    """`hour: 10`, `hour: "0-23"` (inclusive range) or a verbatim string such as "24" or "x"."""
    s = str(hour)
    if "-" in s and s.replace("-", "").isdigit():
        a, b = (int(x) for x in s.split("-"))
        return list(range(a, b + 1))
    return [s]


def load(path: Path) -> dict:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    spec["id"] = path.stem
    return spec


def render(spec: dict, out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    d = out_dir / spec["id"]
    d.mkdir(parents=True, exist_ok=True)
    loc_lines = [",".join(LOCATION_HEADER)]
    for loc in spec["locations"]:
        loc_lines.append(",".join([loc["name"], loc.get("from", "01-01-2018"), loc.get("to", "31-12-2018"),
                                   loc["district"], loc.get("state", "Fixture State"),
                                   loc.get("category", "Gram Panchayat"), loc.get("connection", "Domestic")]))
    rd_lines = [",".join(READING_HEADER)]
    for h in spec.get("hours", []):
        for date_str in _dates(h):
            for hour in _hours(h["hour"]):
                # date and hour are written verbatim, so malformed values (e.g. 32-06-2018, 24) are allowed
                rd_lines.append(",".join([h["loc"], date_str, str(hour)] + expand(h["values"])))
    readings = d / "readings.csv"
    locations = d / "locations.csv"
    readings.write_bytes(("\r\n".join(rd_lines) + "\r\n").encode("utf-8"))
    locations.write_bytes(("\r\n".join(loc_lines) + "\r\n").encode("utf-8"))
    return locations, readings


def all_specs() -> list[dict]:
    return [load(p) for p in sorted(FIXTURE_DIR.glob("F[0-9][0-9]_*.yaml"))]


if __name__ == "__main__":
    for s in all_specs():
        lp, rp = render(s)
        print(f"{s['id']}: {rp.relative_to(FIXTURE_DIR)}")
    sys.exit(0)
