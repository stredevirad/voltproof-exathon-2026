"""SYNTHETIC demo data: invented monitors in the ESMI file format, so the app can be tried without downloading
the real data. Everything here is made up. It is never loaded into the real-data schema, and no real-data
figure is ever computed from it (DECISIONS D-033).

What it writes (deterministic: a fixed seed and explicit CRLF line endings; about 4 MB):
  data/demo/SYNTHETIC ESMI location information.csv          same 7 columns as the real location file
  data/demo/SYNTHETIC ESMI minute-wise voltage data 2030 Jan.csv   same 63 columns as the real readings files
  data/demo/manifest.json                                    file ids 900000001+ (never Dataverse ids)

20 invented monitors in 3 invented districts of an invented state, January 2030 (outside every real file's
period). The data has random outages (0 V, sometimes a ~101 V floor), low and high voltage, a few missing
hours, one duplicated hour, and one evening interruption shared by every monitor in the largest district
(Synthpur, 17 January 2030, from 18:42), which the guided demo picks.

Usage: .venv\\Scripts\\python.exe -m pipeline.synthetic   (scripts\\load.ps1 -Set demo runs it)
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "demo"
SEED = 20300117
STATE = "SYNTHETIC State"
YEAR, MONTH, DAYS = 2030, 1, 31
LOCATION_FILE_ID, READINGS_FILE_ID = 900000001, 900000002
LOCATION_FILE = "SYNTHETIC ESMI location information.csv"
READINGS_FILE = "SYNTHETIC ESMI minute-wise voltage data 2030 Jan.csv"
# The shared evening interruption the guided demo shows
SHARED_DISTRICT = "Synthpur (SYNTHETIC)"
SHARED_DAY, SHARED_START = 17, (18, 42)  # 17 January 2030, 18:42
DISTRICTS = {
    "Synthpur (SYNTHETIC)": ["Amrit Tola", "Bel Chowk", "Chandan Pura", "Dhoop Gali", "Ekta Colony", "Gulab Bagh",
                             "Hira Tola", "Ira Nagar", "Jaamun Pura"],
    "Demogarh (SYNTHETIC)": ["Kanak Basti", "Lal Kuan", "Moti Pur", "Neem Chowk", "Oas Tola", "Pankh Nagar"],
    "Testganj (SYNTHETIC)": ["Rajat Pura", "Sona Gali", "Tara Colony", "Usha Bagh", "Vani Tola"],
}
CATEGORIES = ["Gram Panchayat", "Other Municipal Area", "District Headquarters"]
LOC_HEADER = "Location name,From date,To date,District,State,Category,Connection Type"
READ_HEADER = "Location name,Date,Hour," + ",".join(f"Min {i}" for i in range(60))


def monitors() -> list[dict]:
    out = []
    for d_index, (district, places) in enumerate(DISTRICTS.items()):
        for p_index, place in enumerate(places):
            out.append({"name": f"SYNTHETIC {place}-{district.split(' ')[0]}", "district": district,
                        "category": CATEGORIES[(d_index + p_index) % 3],
                        "connection": "Non-domestic" if p_index % 4 == 3 else "Domestic"})
    return out


def _day_minutes(rng: random.Random, profile: dict, day: int, shared: tuple[int, int] | None) -> list[int | None]:
    """1,440 voltages for one monitor-day (None = minute with no row; whole missing hours are handled later)."""
    base = profile["base"]
    v = []
    level = base
    for m in range(1440):
        h = m // 60
        evening = 17 <= h <= 22
        night = h < 5
        target = base - (22 if evening else 0) + (profile["night_high"] if night else 0)
        level += (target - level) * 0.05 + rng.gauss(0, 1.2)
        v.append(int(round(level)))
    # random outages; none within 90 minutes of the shared interruption, so its edges stay clean
    blocked = set()
    if shared:
        s = shared[0] * 60 + shared[1]
        blocked = set(range(s - 90, s + 150))
    for _ in range(rng.choice(profile["outages_per_day"])):
        start = rng.randrange(0, 1440)
        length = int(min(rng.expovariate(1 / profile["mean_outage_min"]) + 2, 300))
        span = range(start, min(1440, start + length))
        if blocked.intersection(span):
            continue
        floor = rng.random() < 0.15  # some monitors report about 101 V instead of 0 V in deep sags
        for m in span:
            v[m] = 101 if floor else 0
    if shared:
        s = shared[0] * 60 + shared[1] + profile["shared_offset"]
        for m in range(s, min(1440, s + profile["shared_minutes"])):
            v[m] = 0
    return v


def generate(out_dir: Path = OUT_DIR) -> dict:
    rng = random.Random(SEED)
    out_dir.mkdir(parents=True, exist_ok=True)
    mons = monitors()
    for i, mon in enumerate(mons):
        mon["profile"] = {
            "base": rng.randint(214, 246),
            "night_high": rng.choice([0, 0, 0, 34, 42]),        # some monitors run high (> 270 V) at night
            "outages_per_day": rng.choice([[0, 1, 2], [1, 2, 3], [2, 3, 4, 5]]),
            "mean_outage_min": rng.choice([12, 25, 45, 70]),
            "shared_offset": (0, 0, 1, 1, 2, 0, 1, 2, 1)[i] if mon["district"] == SHARED_DISTRICT else 0,
            "shared_minutes": rng.randint(35, 80),
        }
    loc_lines = [LOC_HEADER] + [
        f"{m['name']},01-01-{YEAR},31-01-{YEAR},{m['district']},{STATE},{m['category']},{m['connection']}"
        for m in mons]
    lines = [READ_HEADER]
    duplicate_done = False
    for mon in mons:
        for day in range(1, DAYS + 1):
            shared = SHARED_START if (mon["district"] == SHARED_DISTRICT and day == SHARED_DAY) else None
            minutes = _day_minutes(rng, mon["profile"], day, shared)
            date = f"{day:02d}-{MONTH:02d}-{YEAR}"
            for hour in range(24):
                # about 1 hour in 120 is missing (the monitor sent nothing); never around the shared interruption
                if not shared and rng.random() < 1 / 120:
                    continue
                vals = minutes[hour * 60:(hour + 1) * 60]
                line = f"{mon['name']},{date},{hour}," + ",".join(str(x) for x in vals)
                lines.append(line)
                if not duplicate_done and mon["district"] == "Testganj (SYNTHETIC)" and day == 9 and hour == 11:
                    lines.append(line)  # the same hour twice, identical values (a duplicate, not a conflict)
                    duplicate_done = True
    files = {LOCATION_FILE: "\r\n".join(loc_lines) + "\r\n", READINGS_FILE: "\r\n".join(lines) + "\r\n"}
    entries = []
    for (name, text), (fid, kind) in zip(files.items(), [(LOCATION_FILE_ID, "locations"),
                                                         (READINGS_FILE_ID, "readings")], strict=True):
        data = text.encode("ascii")
        (out_dir / name).write_bytes(data)
        entries.append({"dataverse_file_id": fid, "file": name, "kind": kind, "status": "verified",
                        "md5": hashlib.md5(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data),
                        "declared": None if kind == "locations" else
                        {"period_from": f"{YEAR}-{MONTH:02d}-01", "period_to": f"{YEAR}-{MONTH:02d}-{DAYS}"}})
    manifest = {"synthetic": True, "seed": SEED, "generated_by": "pipeline/synthetic.py",
                "generated_at": dt.date.today().isoformat(), "files": entries}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    _check_names_are_invented(mons)
    return manifest


def _check_names_are_invented(mons: list[dict]) -> None:
    """If the real location file is present, make sure no invented name or district collides with it."""
    real = REPO_ROOT / "data" / "raw" / "ESMI location information.csv"
    if not real.exists():
        return
    text = real.read_text(encoding="utf-8", errors="replace").lower()
    clashes = [m["name"] for m in mons if m["name"].lower() in text]
    clashes += [d for d in DISTRICTS if d.split(" ")[0].lower() in {ln.split(",")[3].strip().lower()
                                                                     for ln in text.splitlines()[1:] if ln.count(",") >= 6}]
    if clashes:
        raise SystemExit(f"synthetic names collide with real ESMI names: {clashes}")


def main() -> int:
    m = generate()
    for f in m["files"]:
        print(f"wrote data/demo/{f['file']} ({f['bytes']:,} bytes, sha256 {f['sha256'][:16]}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
