"""Fetch pipeline results from Exasol and compare them field by field with the oracle or with
hand-written expectations. Every compared field is tagged with the METHODOLOGY rule it tests, so any
mismatch is reported with its rule ID.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from tests.oracle.reference import Params

REPO_ROOT = Path(__file__).resolve().parents[2]

EVENT_FIELDS = {
    "start": "R-7", "end": "R-7", "min_duration": "R-10", "max_duration": "R-10",
    "bridged_minutes": "R-8", "start_certainty": "R-9", "end_certainty": "R-9",
    "is_interruption": "R-11", "zero_minutes": "R-16b",
}
DAILY_FIELDS = {
    "expected": "R-4/R-18", "observed": "R-6/R-18", "outage_lower": "R-14", "outage_upper": "R-15",
    "outage_zero": "R-16b", "low": "R-16", "high": "R-16", "evening_lower": "R-17",
    "evening_upper": "R-17", "interruptions": "R-13", "longest": "R-13",
}
MONTHLY_FIELDS = dict(DAILY_FIELDS, comparable="R-18")


def params_from_yaml(overrides: dict | None = None) -> Params:
    m = yaml.safe_load((REPO_ROOT / "config" / "method.yaml").read_text(encoding="utf-8"))
    flat = {
        "outage_max_v": m["classification"]["outage_max_v"],
        "normal_min_v": m["classification"]["normal_min_v"],
        "normal_max_v": m["classification"]["normal_max_v"],
        "min_valid_v": m["data_quality"]["min_valid_v"],
        "max_valid_v": m["data_quality"]["max_valid_v"],
        "gap_bridge_max_minutes": m["events"]["gap_bridge_max_minutes"],
        "max_uncertain_extension_minutes": m["events"]["max_uncertain_extension_minutes"],
        "interruption_min_minutes": m["events"]["interruption_min_minutes"],
        "evening_start_hour": m["windows"]["evening_start_hour"],
        "evening_end_hour_exclusive": m["windows"]["evening_end_hour_exclusive"],
        "comparable_min_coverage_exclusive": m["coverage"]["comparable_month_min_coverage_exclusive"],
    }
    key_map = {
        "events.gap_bridge_max_minutes": "gap_bridge_max_minutes",
        "events.max_uncertain_extension_minutes": "max_uncertain_extension_minutes",
        "events.interruption_min_minutes": "interruption_min_minutes",
        "data_quality.max_valid_v": "max_valid_v",
        "data_quality.min_valid_v": "min_valid_v",
    }
    for k, v in (overrides or {}).items():
        if k in key_map:
            flat[key_map[k]] = v
    return Params(**flat)


def _ts(v) -> dt.datetime:
    if isinstance(v, dt.datetime):
        return v.replace(microsecond=0)
    return dt.datetime.fromisoformat(str(v)[:19])


def _day(v) -> dt.date:
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


def fetch_sql(conn, schema: str, location_names: list[str] | None = None) -> dict:
    where = ""
    params = {}
    if location_names:
        where = "WHERE l.SOURCE_NAME IN ({names})"
        params = {"names": location_names}
    ev = conn.execute(
        f"""SELECT l.SOURCE_NAME, e.START_TS, e.END_TS, e.MIN_DURATION, e.MAX_DURATION, e.BRIDGED_MINUTES,
                   e.START_CERTAINTY, e.END_CERTAINTY, e.IS_INTERRUPTION, e.ZERO_MINUTES
            FROM {schema}.EVENT e JOIN {schema}.LOCATION l ON l.LOCATION_ID = e.LOCATION_ID {where}
            ORDER BY 1, 2""", params).fetchall()
    daily = conn.execute(
        f"""SELECT l.SOURCE_NAME, d.CAL_DAY, d.EXPECTED_MINUTES, d.OBSERVED_MINUTES, d.OUTAGE_MIN_LOWER,
                   d.OUTAGE_MIN_UPPER, d.OUTAGE_ZERO_MINUTES, d.LOW_MINUTES, d.HIGH_MINUTES,
                   d.EVENING_OUTAGE_LOWER, d.EVENING_OUTAGE_UPPER, d.INTERRUPTIONS, d.LONGEST_INTERRUPTION
            FROM {schema}.DAILY d JOIN {schema}.LOCATION l ON l.LOCATION_ID = d.LOCATION_ID {where}""",
        params).fetchall()
    monthly = conn.execute(
        f"""SELECT l.SOURCE_NAME, m.MONTH_KEY, m.EXPECTED_MINUTES, m.OBSERVED_MINUTES, m.OUTAGE_MIN_LOWER,
                   m.OUTAGE_MIN_UPPER, m.OUTAGE_ZERO_MINUTES, m.LOW_MINUTES, m.HIGH_MINUTES,
                   m.EVENING_OUTAGE_LOWER, m.EVENING_OUTAGE_UPPER, m.INTERRUPTIONS, m.LONGEST_INTERRUPTION,
                   m.IS_COMPARABLE
            FROM {schema}.MONTHLY m JOIN {schema}.LOCATION l ON l.LOCATION_ID = m.LOCATION_ID {where}""",
        params).fetchall()
    out = {"events": [], "daily": {}, "monthly": {}}
    for r in ev:
        out["events"].append({
            "location": r[0], "start": _ts(r[1]), "end": _ts(r[2]), "min_duration": int(r[3]),
            "max_duration": int(r[4]), "bridged_minutes": int(r[5]), "start_certainty": r[6],
            "end_certainty": r[7], "is_interruption": bool(r[8]), "zero_minutes": int(r[9]),
        })
    for r in daily:
        out["daily"][(r[0], _day(r[1]))] = dict(zip(DAILY_FIELDS, (int(x) for x in r[2:])))
    for r in monthly:
        vals = dict(zip(list(DAILY_FIELDS), (int(x) for x in r[2:13])))
        vals["comparable"] = bool(r[13])
        out["monthly"][(r[0], r[1])] = vals
    return out


def fetch_coincidence(conn, schema: str, districts: list[str] | None = None) -> dict:
    """Pairs, groups and baseline from the SQL tables, keyed by location NAME (ids are schema-specific)."""
    where, params = "", {}
    if districts:
        where, params = "WHERE p.DISTRICT IN ({d})", {"d": districts}
    pairs = conn.execute(
        f"""SELECT la.SOURCE_NAME AS NAME_A, p.START_A, lb.SOURCE_NAME AS NAME_B, p.START_B
            FROM {schema}.COINCIDENT_PAIR p
            JOIN {schema}.LOCATION la ON la.LOCATION_ID = p.LOCATION_A
            JOIN {schema}.LOCATION lb ON lb.LOCATION_ID = p.LOCATION_B {where}""", params).fetchall()
    gwhere = where.replace("p.DISTRICT", "g.DISTRICT")
    members = conn.execute(
        f"""SELECT g.DISTRICT, g.START_TS AS GROUP_START, l.SOURCE_NAME, m.START_TS AS MEMBER_START
            FROM {schema}.POTENTIAL_SHARED_EVENT g
            JOIN {schema}.POTENTIAL_SHARED_MEMBER m ON m.GROUP_ID = g.GROUP_ID
            JOIN {schema}.LOCATION l ON l.LOCATION_ID = m.LOCATION_ID {gwhere}""", params).fetchall()
    bwhere = where.replace("p.DISTRICT", "b.DISTRICT")
    base = conn.execute(
        f"""SELECT b.DISTRICT, b.MONTH_KEY, b.N_LOCATIONS, b.N_INTERRUPTIONS, b.OBSERVED_PAIRS, b.EXPECTED_PAIRS,
                   b.P_VALUE FROM {schema}.COINCIDENCE_BASELINE b {bwhere}""", params).fetchall()
    groups: dict = {}
    for d, gs, loc, ms in members:
        groups.setdefault((d, _ts(gs)), set()).add((loc, _ts(ms)))
    return {
        "pairs": {(a, _ts(sa), b, _ts(sb)) for a, sa, b, sb in pairs},
        "groups": {k: frozenset(v) for k, v in groups.items()},
        "baseline": {(d, mk): (int(nl), int(ni), int(o), round(float(e), 6), round(float(pv), 6))
                     for d, mk, nl, ni, o, e, pv in base},
    }


def oracle_coincidence(events: list[dict], district_of: dict[str, str], delta: int, theta: int,
                       n_shifts: int, comparable: set | None = None, comparable_only: bool = True) -> dict:
    """Run tests/oracle/coincidence.py on oracle events (interruptions only) in the same comparable shape.
    `comparable` = {(location, 'YYYY-MM')} of comparable location-months (from the oracle's monthly output);
    with comparable_only, only those interruptions enter the baseline (pairs and groups use all)."""
    from tests.oracle import coincidence as oc

    order = {name: i for i, name in enumerate(sorted(district_of))}
    ints = [dict(location=e["location"], district=district_of[e["location"]], start=e["start"], end=e["end"],
                 order=order[e["location"]]) for e in events if e["is_interruption"]]
    pairs = oc.pairs(ints, delta, theta)
    groups = oc.groups(ints, delta, theta)
    base_ints = ints
    if comparable_only:
        comparable = comparable or set()
        base_ints = [e for e in ints if (e["location"], e["start"].strftime("%Y-%m")) in comparable]
    base = oc.baseline(base_ints, delta, theta, n_shifts)
    return {
        "pairs": {(a["location"], a["start"], b["location"], b["start"]) for a, b in pairs},
        "groups": {(g["district"], g["start"]): frozenset((m["location"], m["start"]) for m in g["members"])
                   for g in groups},
        "baseline": {(b["district"], b["month"]): (b["n_locations"], b["n_interruptions"], b["observed_pairs"],
                                                   round(b["expected_pairs"], 6), round(b["p_value"], 6))
                     for b in base},
    }


def diff_coincidence(sql: dict, ref: dict, label_ref: str = "oracle") -> list[str]:
    problems = []
    for p in sorted(sql["pairs"] - ref["pairs"], key=str)[:20]:
        problems.append(f"[R-19] pair only in SQL: {p}")
    for p in sorted(ref["pairs"] - sql["pairs"], key=str)[:20]:
        problems.append(f"[R-19] pair only in {label_ref}: {p}")
    for k in sorted(set(sql["groups"]) | set(ref["groups"]), key=str):
        if sql["groups"].get(k) != ref["groups"].get(k):
            problems.append(f"[R-20] group {k}: SQL={sorted(sql['groups'].get(k, []))} "
                            f"{label_ref}={sorted(ref['groups'].get(k, []))}")
    for k in sorted(set(sql["baseline"]) | set(ref["baseline"]), key=str):
        if sql["baseline"].get(k) != ref["baseline"].get(k):
            problems.append(f"[R-21] baseline {k}: SQL={sql['baseline'].get(k)} {label_ref}={ref['baseline'].get(k)}")
    return problems


def oracle_as_comparable(res) -> dict:
    out = {"events": [], "daily": {}, "monthly": {}}
    for e in res.events:
        out["events"].append({
            "location": e["location"], "start": e["start"], "end": e["end"],
            "min_duration": e["min_duration"], "max_duration": e["max_duration"],
            "bridged_minutes": e["bridged_minutes"], "start_certainty": e["start_certainty"],
            "end_certainty": e["end_certainty"], "is_interruption": e["is_interruption"],
            "zero_minutes": e.get("zero_minutes", 0),
        })
    for (loc, day), d in res.daily.items():
        out["daily"][(loc, day)] = {k: d[k] for k in DAILY_FIELDS}
    for (loc, key), m in res.monthly.items():
        out["monthly"][(loc, key)] = {k: m[k] for k in MONTHLY_FIELDS}
    out["events"].sort(key=lambda e: (e["location"], e["start"]))
    return out


def diff(sql: dict, ref: dict, label_ref: str = "oracle") -> list[str]:
    """Return human-readable mismatches, each prefixed with the rule ID."""
    problems = []
    se = {(e["location"], e["start"]): e for e in sql["events"]}
    re_ = {(e["location"], e["start"]): e for e in ref["events"]}
    for k in sorted(set(se) | set(re_)):
        if k not in se:
            problems.append(f"[R-7] event {k} missing in SQL ({label_ref} has it)")
            continue
        if k not in re_:
            problems.append(f"[R-7] event {k} extra in SQL (not in {label_ref})")
            continue
        for f, rule in EVENT_FIELDS.items():
            if se[k][f] != re_[k][f]:
                problems.append(f"[{rule}] event {k} field {f}: SQL={se[k][f]!r} {label_ref}={re_[k][f]!r}")
    for name, fields in (("daily", DAILY_FIELDS), ("monthly", MONTHLY_FIELDS)):
        s, r = sql[name], ref[name]
        for k in sorted(set(s) | set(r), key=str):
            if k not in s or k not in r:
                problems.append(f"[R-12] {name} row {k} present only in {'SQL' if k in s else label_ref}")
                continue
            for f, rule in fields.items():
                if s[k][f] != r[k][f]:
                    problems.append(f"[{rule}] {name} {k} field {f}: SQL={s[k][f]!r} {label_ref}={r[k][f]!r}")
    return problems
