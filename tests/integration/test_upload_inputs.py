"""Real-world files, from the council's break-it review of the upload feature (P2-A): spreadsheet exports, time zones,
a supply that is out for much of the time, 110-120 V supplies, sentinel values, repeated lines, and clean-up after a
crash. Each case checks the plain-language message or that the results equal those of the same readings written the
usual way."""

from __future__ import annotations

import csv
import time
from pathlib import Path

import pytest

from pipeline import upload
from pipeline.db import connect
from pipeline.load_raw import READINGS_HEADER
from pipeline.upload import UploadError
from tests.integration.test_uploads import (
    DAYS,
    _days,
    _locations,
    _long,
    _upload,
    _wide,
    protected,  # noqa: F401  (fixture: real and demo schemas stay unchanged)
)
from tests.support.fingerprints import compare_schemas

pytestmark = [pytest.mark.exasol, pytest.mark.usefixtures("protected")]
RESULTS = {"EVENT", "DAILY", "MONTHLY", "SEGMENT", "QUALITY_LOCATION", "INTERRUPTION", "UNCERTAIN_CLAIM"}
LONG_MAP = {"clock_local": "yes", "long": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "YMD",
                                           "order_confirmed": True}}


def _build_and_compare(a_id: str, b_id: str, skip: dict | None = None, only: set[str] = RESULTS) -> dict:
    ra, rb = upload.build(a_id), upload.build(b_id)
    with connect() as c:
        result = compare_schemas(c, ra["schema"], rb["schema"], only_tables=only, skip_columns=skip)
        events = [c.execute(f"SELECT COUNT(*) FROM {s}.EVENT").fetchval() for s in (ra["schema"], rb["schema"])]
    upload.delete(a_id)
    upload.delete(b_id)
    return {"different": result["different"], "compared": result["compared"], "events": events}


# ---------------------------------------------------------------- the voltage check

def test_a_supply_that_is_out_for_much_of_the_time_is_accepted_and_a_110_volt_supply_is_not(tmp_path):
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    # out (0 V) for 12 of every 24 hours: the typical supply reading is still 232 V
    rows = [("Shop A", d, str(h), ["0" if 6 <= h < 18 else "232"] * 60) for d in DAYS for h in range(24)]
    up = _upload(_wide(tmp_path / "heavy.csv", rows), locs)
    assert up["summary"]["ready_to_build"] and up["summary"]["typical_voltage"] == 232, up["summary"]
    upload.delete(up["id"])
    # a monitor that sags to a floor of about 101 V for half the day is also a 230 V supply
    rows = [("Shop A", d, str(h), ["101" if h < 12 else "229"] * 60) for d in DAYS for h in range(24)]
    up = _upload(_wide(tmp_path / "floor.csv", rows), locs)
    assert up["summary"]["ready_to_build"] and up["summary"]["typical_voltage"] == 229
    upload.delete(up["id"])
    # 119 V all day with one short spike to 240 V: still a 110-120 V supply, never an outage report
    rows = [("Shop A", d, str(h), ["240" if (d == DAYS[0] and h == 12) else "119"] * 60) for d in DAYS
            for h in range(24)]
    up = _upload(_wide(tmp_path / "us.csv", rows), locs)
    s = up["summary"]
    assert not s["ready_to_build"] and any("is 130 V or less" in r and "110-120 V" in r for r in s["refusals"]), s
    upload.delete(up["id"])
    # 140 V all the time: above the outage limit but not a 230 V supply
    up = _upload(_wide(tmp_path / "low.csv", _days("Shop A", DAYS, value="140")), locs)
    assert not up["summary"]["ready_to_build"]
    assert any("about 140 V" in r for r in up["summary"]["refusals"]), up["summary"]["refusals"]
    upload.delete(up["id"])


def test_one_logger_far_from_230_volts_among_good_ones_is_flagged(tmp_path):
    rows = _days("Shop A", DAYS) + _days("Shop B", DAYS, value="118") + [("Shop B", "16-03-2024", "0", ["232"] * 60)]
    locs = _locations(tmp_path / "l.csv", ["Shop A", "Shop B"])
    up = _upload(_wide(tmp_path / "two.csv", rows), locs)
    s = up["summary"]
    assert s["ready_to_build"]
    assert any("1 monitor(s) have a typical reading far from a 230 V supply" in w and "Shop B" in w
               for w in s["warnings"]), s["warnings"]
    upload.delete(up["id"])


def test_codes_and_zero_readings_are_named_in_the_summary(tmp_path):
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    rows = _days("Shop A", DAYS)
    rows[5] = ("Shop A", rows[5][1], rows[5][2], ["999"] * 20 + ["231"] * 40)     # a logger code for 'no data'
    rows[9] = ("Shop A", rows[9][1], rows[9][2], ["0"] * 30 + [""] * 30)         # zeros and empty cells
    up = _upload(_wide(tmp_path / "codes.csv", rows), locs)
    s = up["summary"]
    assert s["ready_to_build"]
    assert any("above 500 V" in w and "high voltage" in w for w in s["warnings"]), s["warnings"]
    assert any("exactly 0 V" in w and "no supply" in w for w in s["warnings"]), s["warnings"]
    upload.delete(up["id"])


def test_empty_cells_stay_missing_data_and_never_become_an_outage(tmp_path):
    rows = _days("Shop A", DAYS)
    rows[30] = ("Shop A", rows[30][1], rows[30][2], [""] * 60)                    # a whole hour without readings
    rows[31] = ("Shop A", rows[31][1], rows[31][2], [""] * 30 + ["231"] * 30)
    up = _upload(_wide(tmp_path / "gaps.csv", rows), _locations(tmp_path / "l.csv", ["Shop A"]))
    rec = upload.build(up["id"])
    with connect() as c:
        no_data = c.execute(f"SELECT SUM(MINUTES) FROM {rec['schema']}.SEGMENT WHERE SUPPLY_STATE = 'NO_DATA'").fetchval()
        events = c.execute(f"SELECT COUNT(*) FROM {rec['schema']}.EVENT").fetchval()
    assert int(no_data) >= 90 and events == 0
    upload.delete(up["id"])


def test_missing_minutes_in_a_one_reading_per_line_file_stay_missing_data(tmp_path):
    """A minute with no line in a one-reading-per-line file stays NO_DATA, never 0 V. Added after a planted change
    (the long pivot in sql/ingest/u30 turning a missing minute 0 into "0") went unnoticed by the other tests."""
    lines = [f"Shop A,2024-03-13 {h:02d}:{m:02d},231" for h in range(24) for m in range(60)
             if not (h == 10 and m == 0) and not (h == 11 and m < 30)]
    up = _upload(_long(tmp_path / "gaps.csv", lines), _locations(tmp_path / "l.csv", ["Shop A"]), LONG_MAP)
    assert up["summary"]["ready_to_build"], up["summary"]
    rec = upload.build(up["id"])
    with connect() as c:
        no_data = c.execute(f"SELECT SUM(MINUTES) FROM {rec['schema']}.SEGMENT WHERE SUPPLY_STATE = 'NO_DATA'").fetchval()
        events = c.execute(f"SELECT COUNT(*) FROM {rec['schema']}.EVENT").fetchval()
    assert int(no_data) >= 31 and events == 0, (no_data, events)
    upload.delete(up["id"])


# ---------------------------------------------------------------- spreadsheet exports

def _wide_semicolon(path: Path, rows, bom: bool, decimal_comma: bool) -> Path:
    with open(path, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as fh:
        w = csv.writer(fh, delimiter=";", lineterminator="\r\n")
        w.writerow(READINGS_HEADER)
        for name, d, h, cells in rows:
            w.writerow([name, d, h] + [c.replace(".", ",") if decimal_comma else c for c in cells])
    return path


def test_a_semicolon_file_with_a_byte_order_mark_and_decimal_commas_gives_the_same_results(tmp_path):
    cells = lambda h: ["0" if h == 19 else "229.5"] * 60    # noqa: E731 - small local helper
    rows = [("Shop A", d, str(h), cells(h)) for d in DAYS for h in range(24)]
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    usual = _upload(_wide(tmp_path / "usual.csv", rows), locs)
    sheet = _upload(_wide_semicolon(tmp_path / "sheet.csv", rows, bom=True, decimal_comma=True), locs)
    assert usual["summary"]["ready_to_build"] and sheet["summary"]["ready_to_build"], sheet["summary"]
    assert sheet["summary"]["typical_voltage"] in (229, 230)
    out = _build_and_compare(usual["id"], sheet["id"])
    assert out["different"] == [] and out["events"] == [3, 3], out


def _long_lines(day: str, style: str, sep: str, decimal: str) -> list[str]:
    """One day of 1-minute readings for one monitor with an evening hour at 0 V, written in a spreadsheet style."""
    y, m, d = day.split("-")
    lines = []
    for h in range(24):
        for mi in range(60):
            v = "0" if h == 19 else f"230{decimal}5"
            if style == "ampm":
                stamp = f"{d}/{m}/{y} {h % 12 or 12}:{mi:02d} {'AM' if h < 12 else 'PM'}"
            else:
                stamp = f"{day} {h:02d}:{mi:02d}"
            lines.append(sep.join(["Shop A", stamp, v]))
    return lines


def test_twelve_hour_clock_semicolons_and_decimal_commas_in_a_one_reading_per_line_file(tmp_path):
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    usual = _upload(_long(tmp_path / "iso.csv", _long_lines("2024-03-13", "iso", ",", ".")), locs, LONG_MAP)
    sheet_map = {"clock_local": "yes", "long": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "DMY",
                                                "order_confirmed": True}}
    sheet = _upload(_long(tmp_path / "sheet.csv", _long_lines("2024-03-13", "ampm", ";", ","),
                          header="monitor;time;volts"), locs, sheet_map)
    assert usual["summary"]["ready_to_build"] and sheet["summary"]["ready_to_build"], sheet["summary"]
    assert any("13 March 2024" in x for x in sheet["summary"]["reads_as"]), sheet["summary"]["reads_as"]
    out = _build_and_compare(usual["id"], sheet["id"], skip={"READING_CLEAN": {"LINE_NO"}})
    assert out["different"] == [] and out["events"] == [1, 1], out


def test_an_excel_workbook_is_named_as_such(tmp_path):
    book = tmp_path / "readings.xlsx"
    book.write_bytes(b"PK\x03\x04" + b"\x00" * 200)
    rec = upload.new_upload()
    try:
        upload.receive_path(rec["id"], "readings", book)
        with pytest.raises(UploadError, match="Excel workbook.*CSV"):
            upload.preview(rec["id"])
    finally:
        upload.delete(rec["id"])


# ---------------------------------------------------------------- time zones

def _zone_lines(suffix: str) -> list[str]:
    return [f"Shop A,2024-03-13T{h:02d}:{m:02d}:00{suffix},231" for h in range(5) for m in range(60)]


def test_india_offset_is_accepted_and_every_other_zone_is_refused(tmp_path):
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    ist = _upload(_long(tmp_path / "ist.csv", _zone_lines("+05:30")), locs, LONG_MAP)
    s = ist["summary"]
    assert s["ready_to_build"] and s["first_day"] == "2024-03-13", s
    assert any("+05:30 are read as India local clock time" in w for w in s["warnings"]), s["warnings"]
    upload.delete(ist["id"])
    for suffix in ("Z", "+01:00", "-05:00", "+0000"):
        other = _upload(_long(tmp_path / "other.csv", _zone_lines(suffix)), locs, LONG_MAP)
        assert not other["summary"]["ready_to_build"], suffix
        assert any("time-zone mark other than +05:30" in r for r in other["summary"]["refusals"]), suffix
        upload.delete(other["id"])


def test_one_reading_per_line_files_must_be_confirmed_as_local_clock_times(tmp_path):
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    f = _long(tmp_path / "plain.csv", [f"Shop A,2024-03-13 {h:02d}:{m:02d},231" for h in range(5) for m in range(60)])
    mapping = {"long": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "YMD", "order_confirmed": True}}
    up = _upload(f, locs, mapping)
    keys = [q["key"] for q in up["summary"]["questions"]]
    assert keys == ["clock_local"] and not up["summary"]["ready_to_build"]
    s = upload.validate(up["id"], {**mapping, "clock_local": "no"})
    assert not s["ready_to_build"] and any("not local clock times" in r for r in s["refusals"]), s
    s = upload.validate(up["id"], {**mapping, "clock_local": "yes"})
    assert s["ready_to_build"] and s["questions"] == []
    upload.delete(up["id"])


# ---------------------------------------------------------------- repeated lines, privacy, clean-up

def test_the_same_readings_written_twice_count_once(tmp_path):
    rows = _days("Shop A", [DAYS[0], DAYS[2]], value="231")   # 15-03 settles the day/month order: no question
    rows = [(n, d, h, ["0" if h == "19" else "231"] * 60) for n, d, h, _ in rows]
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    once = _upload(_wide(tmp_path / "once.csv", rows), locs)
    twice = _upload(_wide(tmp_path / "twice.csv", rows + rows), locs)
    out = _build_and_compare(once["id"], twice["id"], skip={"QUALITY_LOCATION": {"READINGS_RAW", "DUPLICATE_READINGS"}})
    assert out["different"] == [] and out["events"] == [2, 2], out


def test_typed_names_never_reach_the_database_audit_log(tmp_path):
    probe = f"ZZ-AUDIT-PROBE-{int(time.time())}"
    rows = _days("Shop A", DAYS)
    readings = _wide(tmp_path / "r.csv", rows)
    rec = upload.new_upload()
    upload.receive_path(rec["id"], "readings", readings)
    upload.preview(rec["id"])
    upload.validate(rec["id"], {"typed_locations": [{"name": "Shop A", "district": probe, "state": "up"}]})
    built = upload.build(rec["id"])
    with connect() as c:
        c.execute("FLUSH STATISTICS")
        hits = c.execute("SELECT COUNT(*) FROM EXA_DBA_AUDIT_SQL WHERE SQL_TEXT LIKE {p}", {"p": f"%{probe}%"}).fetchval()
        state = c.execute(f"SELECT STATE_NAME FROM {built['schema']}.LOCATION").fetchval()
    assert hits == 0
    assert state == "Uttar Pradesh"   # 'up' is stored in one spelling, so UP reports cite the UPERC regulations
    upload.delete(rec["id"])


def test_leftovers_of_a_crash_are_cleaned_up(tmp_path):
    orphan = "VP_USER_DEADBEEF"
    with upload.uploader_connect() as c:
        c.execute(f"CREATE SCHEMA IF NOT EXISTS {orphan}")
    stray = upload.UPLOAD_DIR / "feedface"            # a folder without a record
    stray.mkdir(parents=True, exist_ok=True)
    empty = upload.new_upload()                      # started, never given a file
    kept = upload.new_upload()
    upload.receive_path(kept["id"], "readings", _wide(tmp_path / "r.csv", _days("Shop A", DAYS[:1])))
    cut = upload.new_upload()                        # a build whose process ended (RAM guard, crash)
    rec = upload.load(cut["id"])
    rec.update(status="building", progress={"step": "060_events.sql", "done": 9, "total": 50})
    upload.save(rec)
    time.sleep(1.2)
    out = upload.reconcile(max_age_minutes=0, drop_schemas=True)
    assert orphan in out["schemas_dropped"] and "feedface" in out["folders_removed"], out
    assert empty["id"] in out["uploads_removed"] and not (upload.UPLOAD_DIR / empty["id"]).exists()
    assert (upload.UPLOAD_DIR / kept["id"]).exists()
    assert not upload.schema_exists(orphan)
    after = upload.load(cut["id"])
    assert after["status"] == "failed" and "interrupted" in after["error"]
    for rid in (kept["id"], cut["id"]):
        upload.delete(rid)
