"""Independent reference implementation of METHODOLOGY R-19 to R-21 (coincidence), plain loops only.

Input: interruption events as dicts with location, district, start, end (inclusive minute timestamps),
and a stable location order key (the SQL uses LOCATION_ID, i.e. the rank of the source name).
"""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict

ONE_MIN = dt.timedelta(minutes=1)


def _minutes(a: dt.datetime, b: dt.datetime) -> int:
    return int((a - b).total_seconds() // 60)


def is_pair(a: dict, b: dict, delta: int, theta: int) -> bool:
    if a["location"] == b["location"] or a["district"] != b["district"]:
        return False
    if abs(_minutes(a["start"], b["start"])) > delta:
        return False
    overlap = _minutes(min(a["end"], b["end"]), max(a["start"], b["start"])) + 1
    return max(0, overlap) >= theta


def pairs(events: list[dict], delta: int, theta: int) -> list[tuple[dict, dict]]:
    """R-19: all coincident pairs, each once, ordered (earlier start, then location order key) first."""
    evs = sorted(events, key=lambda e: (e["start"], e["order"]))
    out = []
    for i in range(len(evs)):
        for j in range(i + 1, len(evs)):
            if _minutes(evs[j]["start"], evs[i]["start"]) > delta:
                break  # sorted by start: no later event can be within delta of evs[i]
            if is_pair(evs[i], evs[j], delta, theta):
                out.append((evs[i], evs[j]))
    return out


def groups(events: list[dict], delta: int, theta: int) -> list[dict]:
    """R-20: start-time chains per district; a chain with >= 1 pair is a group; members are paired events."""
    by_d = defaultdict(list)
    for e in events:
        by_d[e["district"]].append(e)
    out = []
    for district, evs in by_d.items():
        evs.sort(key=lambda e: (e["start"], e["order"]))
        chains, cur = [], []
        for e in evs:
            if cur and _minutes(e["start"], cur[-1]["start"]) > delta:
                chains.append(cur)
                cur = []
            cur.append(e)
        if cur:
            chains.append(cur)
        for ch in chains:
            ps = pairs(ch, delta, theta)
            if not ps:
                continue
            members = {id(x): x for p in ps for x in p}
            mem = sorted(members.values(), key=lambda e: (e["start"], e["order"]))
            out.append({"district": district, "start": mem[0]["start"], "members": mem, "n_pairs": len(ps),
                        "end": max(m["end"] for m in mem)})
    return sorted(out, key=lambda g: (g["district"], g["start"]))


def baseline(events: list[dict], delta: int, theta: int, n_shifts: int) -> list[dict]:
    """R-21: circular whole-day shifts within each district-month."""
    by_dm = defaultdict(list)
    for e in events:
        by_dm[(e["district"], e["start"].year, e["start"].month)].append(e)
    out = []
    for (district, y, m), evs in sorted(by_dm.items()):
        days = calendar.monthrange(y, m)[1]
        locs = sorted({(e["order"], e["location"]) for e in evs})
        j_of = {loc: j for j, (_, loc) in enumerate(locs)}

        def in_month(x):
            return x["start"].year == y and x["start"].month == m

        def count(shift_k: int) -> int:
            shifted = []
            for e in evs:
                s = (j_of[e["location"]] * shift_k) % days
                new_day = (e["start"].day - 1 + s) % days + 1
                new_start = e["start"].replace(day=new_day)
                shifted.append(dict(e, start=new_start, end=new_start + (e["end"] - e["start"])))
            return sum(1 for a, b in pairs(shifted, delta, theta) if in_month(a) and in_month(b))

        observed = count(0)
        counts = [count(k) for k in range(1, n_shifts + 1)]
        out.append({"district": district, "month": f"{y:04d}-{m:02d}", "n_locations": len(locs),
                    "n_interruptions": len(evs), "observed_pairs": observed,
                    "expected_pairs": sum(counts) / n_shifts,
                    "p_value": sum(1 for c in counts if c >= observed) / n_shifts})
    return out
