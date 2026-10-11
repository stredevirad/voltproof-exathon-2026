"""Independent reference implementation of docs/METHODOLOGY.md rules R-1 to R-18.

Deliberately simple and slow: plain loops over every minute, no shared code with the SQL pipeline,
no pandas. Used only by tests, to cross-check the Exasol SQL results exactly.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

OUTAGE, LOW, NORMAL, HIGH, NO_DATA = "OUTAGE", "LOW", "NORMAL", "HIGH", "NO_DATA"
ONE_MIN = dt.timedelta(minutes=1)


@dataclass(frozen=True)
class Params:
    outage_max_v: float = 130
    normal_min_v: float = 205
    normal_max_v: float = 270
    min_valid_v: float = 0
    max_valid_v: float | None = None  # no upper cut by default (D-013)
    gap_bridge_max_minutes: int = 0
    max_uncertain_extension_minutes: int = 60
    interruption_min_minutes: int = 1
    evening_start_hour: int = 17
    evening_end_hour_exclusive: int = 23
    comparable_min_coverage_exclusive: float = 0.90


@dataclass
class RawRow:
    location: str
    date: str
    hour: str
    values: list[str]  # 60 strings, "Min 0" .. "Min 59"
    source_row: int = 0


@dataclass
class Result:
    quarantine: list[dict] = field(default_factory=list)
    duplicates: int = 0
    conflicts: int = 0
    windows: dict = field(default_factory=dict)        # loc -> (first_minute, last_minute)
    states: dict = field(default_factory=dict)         # loc -> list[(minute, state, value)]
    events: list[dict] = field(default_factory=list)
    daily: dict = field(default_factory=dict)          # (loc, date) -> dict
    monthly: dict = field(default_factory=dict)        # (loc, 'YYYY-MM') -> dict


def classify(v: float, p: Params) -> str:
    if v <= p.outage_max_v:
        return OUTAGE
    if v < p.normal_min_v:
        return LOW
    if v <= p.normal_max_v:
        return NORMAL
    return HIGH


def _parse_number(s: str):
    try:
        return float(s)
    except ValueError:
        return None


def run(rows: list[RawRow], p: Params, date_format: str) -> Result:
    res = Result()

    # R-1, R-2: unpivot and validate
    readings: dict[tuple[str, dt.datetime], list[float]] = defaultdict(list)
    for r in rows:
        try:
            day = dt.datetime.strptime(r.date.strip(), date_format)
        except ValueError:
            res.quarantine.append({"location": r.location, "source_row": r.source_row, "reason": "bad_date"})
            continue
        hour_num = _parse_number(r.hour.strip())
        if hour_num is None or hour_num != int(hour_num) or not 0 <= hour_num <= 23:
            res.quarantine.append({"location": r.location, "source_row": r.source_row, "reason": "bad_hour"})
            continue
        base = day.replace(hour=int(hour_num), minute=0, second=0, microsecond=0)
        for i in range(60):
            raw = r.values[i].strip() if i < len(r.values) and r.values[i] is not None else ""
            if raw == "":
                continue  # blank cell: no reading
            v = _parse_number(raw)
            if v is None:
                res.quarantine.append({"location": r.location, "source_row": r.source_row,
                                       "minute": i, "reason": "non_numeric"})
                continue
            if v < p.min_valid_v or (p.max_valid_v is not None and v > p.max_valid_v):
                res.quarantine.append({"location": r.location, "source_row": r.source_row,
                                       "minute": i, "reason": "out_of_range"})
                continue
            readings[(r.location, base + dt.timedelta(minutes=i))].append(v)

    # R-3: duplicates and conflicts
    valid: dict[str, dict[dt.datetime, float]] = defaultdict(dict)
    for (loc, minute), vals in readings.items():
        if all(v == vals[0] for v in vals):
            valid[loc][minute] = vals[0]
            res.duplicates += len(vals) - 1
        else:
            res.conflicts += 1

    # R-4, R-5, R-6: window and minute states
    for loc in sorted(valid):
        minutes = valid[loc]
        first, last = min(minutes), max(minutes)
        res.windows[loc] = (first, last)
        seq = []
        m = first
        while m <= last:
            if m in minutes:
                seq.append((m, classify(minutes[m], p), minutes[m]))
            else:
                seq.append((m, NO_DATA, None))
            m += ONE_MIN
        res.states[loc] = seq

    cap = p.max_uncertain_extension_minutes
    for loc, seq in res.states.items():
        n = len(seq)
        # runs: list of [state, start_index, end_index]
        runs = []
        for i, (_, st, _) in enumerate(seq):
            if runs and runs[-1][0] == st:
                runs[-1][2] = i
            else:
                runs.append([st, i, i])

        # R-7, R-8: events (outage runs, optionally bridged across short NO_DATA runs)
        events = []
        k = 0
        while k < len(runs):
            st, s, e = runs[k]
            if st != OUTAGE:
                k += 1
                continue
            measured = e - s + 1
            bridged = 0
            j = k
            while (p.gap_bridge_max_minutes > 0 and j + 2 < len(runs)
                   and runs[j + 1][0] == NO_DATA
                   and runs[j + 1][2] - runs[j + 1][1] + 1 <= p.gap_bridge_max_minutes
                   and runs[j + 2][0] == OUTAGE):
                bridged += runs[j + 1][2] - runs[j + 1][1] + 1
                measured += runs[j + 2][2] - runs[j + 2][1] + 1
                j += 2
            end_idx = runs[j][2]
            # R-9, R-10: edge certainty and bounds
            if s == 0:
                start_cert, start_ext = "censored", cap
            elif runs[k - 1][0] == NO_DATA:
                gap = runs[k - 1][2] - runs[k - 1][1] + 1
                start_cert, start_ext = "bounded", min(gap, cap)
            else:
                start_cert, start_ext = "exact", 0
            if end_idx == n - 1:
                end_cert, end_ext = "censored", cap
            elif runs[j + 1][0] == NO_DATA:
                gap = runs[j + 1][2] - runs[j + 1][1] + 1
                end_cert, end_ext = "bounded", min(gap, cap)
            else:
                end_cert, end_ext = "exact", 0
            events.append({
                "location": loc,
                "start": seq[s][0],
                "end": seq[end_idx][0],  # last outage minute (inclusive)
                "min_duration": measured,
                "max_duration": measured + bridged + start_ext + end_ext,
                "bridged_minutes": bridged,
                "start_certainty": start_cert,
                "end_certainty": end_cert,
                "is_interruption": measured >= p.interruption_min_minutes,
            })
            k = j + 1
        res.events.extend(events)

        # R-15: possibly-outage NO_DATA minutes (union of both neighbours' claims; not at window edges)
        possibly = [False] * n
        for idx, (st, s, e) in enumerate(runs):
            if st != NO_DATA:
                continue
            left_out = idx > 0 and runs[idx - 1][0] == OUTAGE
            right_out = idx + 1 < len(runs) and runs[idx + 1][0] == OUTAGE
            for m in range(s, e + 1):
                if (left_out and m - s < cap) or (right_out and e - m < cap):
                    possibly[m] = True

        # R-12 .. R-18: daily aggregates
        days: dict[dt.date, dict] = {}
        for i, (minute, st, _) in enumerate(seq):
            d = days.setdefault(minute.date(), {
                "expected": 0, "observed": 0, "outage_lower": 0, "outage_upper": 0, "outage_zero": 0,
                "low": 0, "high": 0, "evening_lower": 0, "evening_upper": 0,
                "interruptions": 0, "longest": 0,
            })
            d["expected"] += 1
            evening = p.evening_start_hour <= minute.hour < p.evening_end_hour_exclusive
            if st != NO_DATA:
                d["observed"] += 1
            if st == OUTAGE:
                d["outage_lower"] += 1
                d["outage_upper"] += 1
                if seq[i][2] == 0:
                    d["outage_zero"] += 1
                if evening:
                    d["evening_lower"] += 1
                    d["evening_upper"] += 1
            elif st == NO_DATA and possibly[i]:
                d["outage_upper"] += 1
                if evening:
                    d["evening_upper"] += 1
            elif st == LOW:
                d["low"] += 1
            elif st == HIGH:
                d["high"] += 1
        for ev in events:
            if ev["is_interruption"]:
                d = days[ev["start"].date()]
                d["interruptions"] += 1
                d["longest"] = max(d["longest"], ev["min_duration"])
        for day, d in days.items():
            d["coverage_window"] = d["observed"] / d["expected"]
            d["coverage_calendar"] = d["observed"] / 1440
            res.daily[(loc, day)] = d

        months: dict[str, dict] = {}
        ratio_keys = ("coverage_window", "coverage_calendar")
        for day, d in days.items():
            key = f"{day.year:04d}-{day.month:02d}"
            mth = months.setdefault(
                key, {k: 0 for k in d if k not in ratio_keys and k != "longest"} | {"longest": 0}
            )
            for k2, v in d.items():
                if k2 in ratio_keys:
                    continue
                if k2 == "longest":
                    mth["longest"] = max(mth["longest"], v)
                else:
                    mth[k2] += v
        for key, mth in months.items():
            year, month = int(key[:4]), int(key[5:])
            nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
            calendar_minutes = (nxt - dt.date(year, month, 1)).days * 1440
            mth["coverage_window"] = mth["observed"] / mth["expected"]
            mth["coverage_calendar"] = mth["observed"] / calendar_minutes
            mth["comparable"] = mth["coverage_calendar"] > p.comparable_min_coverage_exclusive
            res.monthly[(loc, key)] = mth
    return res
