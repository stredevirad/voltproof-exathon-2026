"""Uploads through the upload path (pipeline/upload.py, used by the web app and the command line).

Must-pass checks of the upload feature:
  1. the SYNTHETIC demo files uploaded give exactly the same result tables as the command-line demo build;
  3. VOLTPROOF_DEMO (and VOLTPROOF, if built) are unchanged after every upload test;
  4. the same readings in the one-reading-per-line layout give the same results;
  5. bad files fail with the right plain message;
  6. injection and path tricks in names are stored as plain text or refused;
plus: the upload database user cannot read or change any other schema, one build at a time, the upload limit and
"no delete while building" give plain messages, and delete removes the schema and the files. (Check 2, one real ESMI
file, is in tests/differential/test_upload_real.py.)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pyexasol
import pytest

from pipeline import build, buildlock, synthetic, upload
from pipeline.db import connect, schema_dataset
from pipeline.load_raw import LOCATIONS_HEADER, READINGS_HEADER
from pipeline.upload import UploadError
from tests.support.fingerprints import compare_schemas, fingerprint

pytestmark = pytest.mark.exasol
REF_SCHEMA = "VP_UPLOAD_REF"   # command-line build of the synthetic demo files, for comparison
# The synthetic manifest declares the readings file's period (January 2030); an upload has no declared period.
# 0 rows fall outside it, so only these two descriptive columns differ.
BY_DESIGN = {"QUALITY_FILE": {"PERIOD_FROM", "PERIOD_TO"}}


def _demo_files() -> tuple[Path, Path]:
    readings, locations = synthetic.OUT_DIR / synthetic.READINGS_FILE, synthetic.OUT_DIR / synthetic.LOCATION_FILE
    if not readings.exists() or not locations.exists():
        synthetic.generate()
    return readings, locations


def _protected_fingerprints() -> dict:
    out = {}
    with connect() as c:
        for schema, tables in (("VOLTPROOF_DEMO", None), ("VOLTPROOF", ["EVENT", "MONTHLY", "QUALITY_LOCATION",
                                                                          "POTENTIAL_SHARED_EVENT", "PARAMS",
                                                                          "SOURCE_FILE", "COINCIDENCE_BASELINE"])):
            if not schema_dataset(c, schema)["built"]:
                continue
            names = tables or [r[0] for r in c.execute(
                "SELECT TABLE_NAME FROM EXA_ALL_TABLES WHERE TABLE_SCHEMA = {s}", {"s": schema}).fetchall()]
            for t in sorted(names):
                out[(schema, t)] = fingerprint(c, schema, t, skip_columns=set())
    return out


@pytest.fixture(scope="module")
def protected():
    before = _protected_fingerprints()
    yield before
    assert _protected_fingerprints() == before, "an upload test changed VOLTPROOF or VOLTPROOF_DEMO"


def _upload(readings: Path, locations: Path | None = None, mapping: dict | None = None) -> dict:
    rec = upload.new_upload()
    upload.receive_path(rec["id"], "readings", readings)
    if locations:
        upload.receive_path(rec["id"], "locations", locations)
    upload.preview(rec["id"])
    summary = upload.validate(rec["id"], mapping)
    return {"id": rec["id"], "schema": rec["schema"], "summary": summary}


@pytest.fixture(scope="module")
def demo_upload(protected):
    readings, locations = _demo_files()
    assert build.main(["--schema", REF_SCHEMA, "--demo"]) == 0
    up = _upload(readings, locations)
    assert up["summary"]["ready_to_build"], up["summary"]
    rec = upload.build(up["id"])
    yield rec
    upload.delete(rec["id"]) if (upload.UPLOAD_DIR / rec["id"]).exists() else None


def test_synthetic_upload_equals_the_command_line_demo_build(demo_upload):
    assert demo_upload["status"] == "ready"
    assert demo_upload["build"]["provenance"]["different"] == 0 and demo_upload["build"]["provenance"]["missing"] == 0
    with connect() as c:
        result = compare_schemas(c, demo_upload["schema"], REF_SCHEMA, skip_columns=BY_DESIGN)
        info = schema_dataset(c, demo_upload["schema"])
    assert len(result["compared"]) >= 30 and "EVENT" in result["compared"] and "RAW_HOURLY" in result["compared"]
    assert result["different"] == [], result
    assert result["only_in_b"] == []
    assert info["upload"] and not info["synthetic"] and info["upload_files"] == 2 and info["real_files"] == 0


def test_the_upload_user_cannot_read_or_change_any_other_schema(demo_upload):
    with upload.uploader_connect() as c:
        for sql in ["SELECT COUNT(*) FROM VOLTPROOF_DEMO.EVENT", "SELECT COUNT(*) FROM VOLTPROOF.EVENT",
                    f"SELECT COUNT(*) FROM {REF_SCHEMA}.EVENT", "CREATE TABLE VOLTPROOF_DEMO.ZZ_UPLOAD_PROBE (X INT)",
                    "DELETE FROM VOLTPROOF_DEMO.EVENT", "DROP SCHEMA VOLTPROOF_DEMO CASCADE",
                    "CREATE USER ZZ_UPLOAD_PROBE IDENTIFIED BY \"x\"", "GRANT DBA TO VP_UPLOADER"]:
            with pytest.raises(pyexasol.ExaQueryError):
                c.execute(sql)
        assert c.execute(f"SELECT COUNT(*) FROM {demo_upload['schema']}.EVENT").fetchval() > 0
    with connect() as c:
        privs = {r[0] for r in c.execute("SELECT PRIVILEGE FROM EXA_DBA_SYS_PRIVS WHERE GRANTEE = 'VP_UPLOADER'")
                 .fetchall()}
        roles = {r[0] for r in c.execute("SELECT GRANTED_ROLE FROM EXA_DBA_ROLE_PRIVS WHERE GRANTEE = 'VP_UPLOADER'")
                 .fetchall()}
        owners = {r[0]: r[1] for r in c.execute("SELECT SCHEMA_NAME, SCHEMA_OWNER FROM EXA_ALL_SCHEMAS").fetchall()}
    assert privs == set(upload.UPLOADER_PRIVILEGES)
    assert roles <= {"PUBLIC"}
    assert owners[demo_upload["schema"]] == "VP_UPLOADER"
    assert all(owner != "VP_UPLOADER" for s, owner in owners.items() if not upload.is_upload_schema(s))


def test_one_build_at_a_time(tmp_path):
    readings, locations = _demo_files()
    up = _upload(readings, locations)
    with buildlock.build_lock("a test build"):
        assert buildlock.current()["what"] == "a test build"
        with pytest.raises(SystemExit, match="Another database build is running: a test build"):
            build.main(["--schema", "VP_TEST_LOCKED", "--demo"])
        with pytest.raises(buildlock.BuildBusy, match="Only one build can run at a time"):
            upload.build(up["id"])
        with pytest.raises(buildlock.BuildBusy, match="Only one build can run at a time"):
            upload.validate(up["id"], {"typed_locations": []})    # checking a file loads it: same lock
    assert buildlock.current() is None
    upload.delete(up["id"])


def test_uploads_beyond_the_limit_get_a_plain_message(monkeypatch):
    # The limit itself (10) is pinned by tests/unit/test_upload_names.py; here it is set to one more than the uploads
    # already on disk, so the test does not have to create ten.
    monkeypatch.setattr(upload, "MAX_UPLOADS", len(upload.list_uploads()) + 1)
    first = upload.new_upload()
    try:
        with pytest.raises(UploadError, match=r"There are already \d+ uploads on this computer\. Delete one you no "
                                              r"longer need, then upload again\."):
            upload.new_upload()
    finally:
        upload.delete(first["id"])
    again = upload.new_upload()  # deleting one frees its place
    upload.delete(again["id"])


def test_an_upload_being_built_cannot_be_deleted_until_the_build_ends():
    rec = upload.new_upload()
    folder = upload.UPLOAD_DIR / rec["id"]
    with buildlock.build_lock(f"upload {rec['id']}"):
        rec.update(status="building")
        upload.save(rec)
        with pytest.raises(UploadError, match="This upload is being built; delete it when the build has finished."):
            upload.delete(rec["id"])
        assert folder.exists()
    # the building process is gone (here: the lock released without a finished build): the upload says so and can
    # be deleted
    after = upload.load(rec["id"])
    assert after["status"] == "failed" and "interrupted" in after["error"]
    upload.delete(rec["id"])
    assert not folder.exists()


def test_a_refusal_before_the_build_starts_is_shown_on_the_page(monkeypatch):
    # The web app builds in a background thread; the page shows the upload's status and error. A refusal raised before
    # the build starts must still reach the record, or the page waits without a word.
    from app.api import uploads as routes

    readings, locations = _demo_files()
    up = _upload(readings, locations)
    low = "Not enough free disk space on C:\\ to build this upload safely (VoltProof keeps at least 10 GB free)."

    def no_space(extra_bytes):
        raise UploadError(low)
    monkeypatch.setattr(upload, "check_disk", no_space)
    routes._build_in_background(up["id"])
    rec = upload.load(up["id"])
    assert (rec["status"], rec["error"], rec.get("build")) == ("failed", low, None)

    monkeypatch.undo()
    rec.update(status="validated", error=None)
    upload.save(rec)
    with buildlock.build_lock("another build"):
        routes._build_in_background(up["id"])
    rec = upload.load(up["id"])
    assert rec["status"] == "failed" and "Only one build can run at a time" in rec["error"]
    upload.delete(up["id"])


def _write_long_from_demo(path: Path) -> int:
    """The SYNTHETIC readings, one reading per line (monitor, timestamp, voltage). Empty cells are left out, so
    those minutes have no line at all; an hour that the demo file repeats with the same values is written once."""
    readings, _ = _demo_files()
    seen, n = set(), 0
    with open(readings, newline="", encoding="utf-8") as src, open(path, "w", newline="", encoding="utf-8") as out:
        w = csv.writer(out)
        w.writerow(["monitor", "time", "voltage"])
        rows = csv.reader(src)
        next(rows)
        for row in rows:
            name, d, h = row[0], row[1], int(row[2])
            day, month, year = d.split("-")
            for minute, value in enumerate(row[3:]):
                key = (name, d, h, minute)
                if value.strip() == "" or key in seen:
                    continue
                seen.add(key)
                w.writerow([name, f"{year}-{month}-{day} {h:02d}:{minute:02d}", value])
                n += 1
    return n


def test_long_layout_gives_the_same_results(demo_upload, tmp_path):
    long_file = tmp_path / "long readings.csv"
    lines = _write_long_from_demo(long_file)
    _, locations = _demo_files()
    up = _upload(long_file, locations,
                 {"clock_local": "yes", "long": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "YMD",
                                                  "order_confirmed": True}})
    assert up["summary"]["ready_to_build"], up["summary"]
    assert up["summary"]["rows"] == lines
    rec = upload.build(up["id"])
    results = {"LOCATION", "LOCATION_IN_SCOPE", "SEGMENT", "EVENT", "UNCERTAIN_CLAIM", "DAILY", "MONTHLY",
               "MONITOR_WINDOW", "MEASURED_RUN", "LOCATION_DAY", "INTERRUPTION", "COINCIDENT_PAIR",
               "COINCIDENCE_CHAIN", "POTENTIAL_SHARED_EVENT", "POTENTIAL_SHARED_MEMBER", "COINCIDENCE_BASELINE",
               "BASELINE_INTERRUPTION", "BASELINE_SHIFTED", "BASELINE_PAIRS"}
    with connect() as c:
        same = compare_schemas(c, rec["schema"], demo_upload["schema"], only_tables=results)
        # Readings: same minutes and volts; line numbers differ by layout (one line per reading here)
        clean = compare_schemas(c, rec["schema"], demo_upload["schema"], only_tables={"READING_CLEAN"},
                                skip_columns={"READING_CLEAN": {"LINE_NO", "DUPLICATE_COUNT", "SOURCE_FILES"}})
        no_data = [c.execute(f"SELECT SUM(MINUTES) FROM {s}.SEGMENT WHERE SUPPLY_STATE = 'NO_DATA'").fetchval()
                   for s in (rec["schema"], demo_upload["schema"])]
    assert sorted(same["compared"]) == sorted(results), same
    assert same["different"] == [], same
    assert clean["different"] == [], clean
    assert no_data[0] == no_data[1] and int(no_data[0]) > 0   # missing minutes stay NO_DATA, never outage
    upload.delete(rec["id"])


# ---------------------------------------------------------------- bad files

def _wide(path: Path, rows: list[tuple[str, str, str, list[str]]]) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(READINGS_HEADER)
        for name, d, h, values in rows:
            w.writerow([name, d, h] + values)
    return path


def _locations(path: Path, names: list[str], state: str = "Test State") -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(LOCATIONS_HEADER)
        for n in names:
            w.writerow([n, "01-01-2024", "31-12-2024", "Test District", state, "Other", "Domestic"])
    return path


def _days(name: str, days: list[str], hours=range(24), value="230") -> list:
    return [(name, d, str(h), [value] * 60) for d in days for h in hours]


def _long(path: Path, lines: list[str], header: str = "monitor,time,voltage") -> Path:
    path.write_text(header + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path


DAYS = ["01-03-2024", "02-03-2024", "15-03-2024"]


def _check(tmp_path, readings: Path, locations: Path | None = None, mapping: dict | None = None) -> dict:
    up = _upload(readings, locations, mapping)
    upload.delete(up["id"])
    return up["summary"]


@pytest.mark.parametrize("case", ["not_numbers", "out_of_range", "120_volt", "hour_column_broken"])
def test_wide_files_that_are_not_230_volt_minute_readings_are_refused(tmp_path, protected, case):
    rows = {
        "not_numbers": _days("Shop A", DAYS, value="high"),
        "out_of_range": _days("Shop A", DAYS, value="4000"),
        "120_volt": _days("Shop A", DAYS, value="119"),
        "hour_column_broken": _days("Shop A", DAYS, hours=[0] * 24),
    }[case]
    expected = {"not_numbers": "not plain numbers", "out_of_range": "below 0 or above 500",
                "120_volt": "is 130 V or less", "hour_column_broken": "hour column looks broken"}[case]
    s = _check(tmp_path, _wide(tmp_path / "r.csv", rows), _locations(tmp_path / "l.csv", ["Shop A"]))
    assert not s["ready_to_build"]
    assert any(expected in r for r in s["refusals"]), s["refusals"]


@pytest.mark.parametrize("case", ["five_minutes", "seconds", "duplicates", "offset"])
def test_long_files_that_are_not_one_minute_local_readings_are_refused(tmp_path, protected, case):
    if case == "five_minutes":
        lines = [f"Shop A,2024-03-01 {h:02d}:{m:02d},231" for h in range(10) for m in range(0, 60, 5)]
        expected = "usually 5 minutes apart"
    elif case == "seconds":
        lines = [f"Shop A,2024-03-01 {h:02d}:{m:02d}:30,231" for h in range(5) for m in range(60)]
        expected = "more than one reading per minute"
    elif case == "duplicates":
        lines = [f"Shop A,2024-03-01 {h:02d}:{m:02d},231" for h in range(5) for m in range(60)] * 2
        expected = "more than one reading per minute"
    else:
        lines = [f"Shop A,2024-03-01T{h:02d}:{m:02d}:00Z,231" for h in range(5) for m in range(60)]
        expected = "time-zone mark other than +05:30"
    s = _check(tmp_path, _long(tmp_path / "r.csv", lines), _locations(tmp_path / "l.csv", ["Shop A"]),
               {"clock_local": "yes", "long": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "YMD",
                                                  "order_confirmed": True}})
    assert not s["ready_to_build"]
    assert any(expected in r for r in s["refusals"]), s["refusals"]


def test_files_that_cannot_be_read_get_a_plain_message(tmp_path, protected):
    def fails(path: Path, expected: str, step: str = "preview"):
        rec = upload.new_upload()
        try:
            with pytest.raises(UploadError, match=expected):
                upload.receive_path(rec["id"], "readings", path)
                upload.preview(rec["id"])
                upload.validate(rec["id"], {"long": {"location_col": 0, "ts_col": 1, "value_col": 2}})
        finally:
            upload.delete(rec["id"])
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    fails(empty, "The file is empty")
    utf16 = tmp_path / "utf16.csv"
    utf16.write_bytes("monitor,time,voltage\nA,2024-03-01 00:00,230\n".encode("utf-16"))
    fails(utf16, "UTF-16")
    one = tmp_path / "one.csv"
    one.write_text("voltage\n230\n231\n", encoding="utf-8")
    fails(one, "only one column")
    fails(_locations(tmp_path / "loc.csv", ["Shop A"]), "looks like a location file")
    ragged = _long(tmp_path / "ragged.csv", ["Shop A,2024-03-01 00:00,230", "Shop A,2024-03-01 00:01,230,extra"])
    fails(ragged, "Line 3 has 4 values, but the first line")
    latin = tmp_path / "latin.csv"
    latin.write_bytes("monitor,time,voltage\nA,2024-03-01 00:00,230\nM\xfcnchen,2024-03-01 00:01,230\n"
                      .encode("latin-1"))
    fails(latin, "Line 3 is not valid UTF-8")


def test_too_large_a_file_is_refused_while_it_streams(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "MAX_BYTES", 1000)
    big = _long(tmp_path / "big.csv", [f"Shop A,2024-03-01 00:{m:02d},230" for m in range(60)])
    rec = upload.new_upload()
    with pytest.raises(UploadError, match="larger than"):
        upload.receive_path(rec["id"], "readings", big)
    assert not list((upload.UPLOAD_DIR / rec["id"]).glob("*.part")) and \
        not (upload.UPLOAD_DIR / rec["id"] / "readings.dat").exists()
    upload.delete(rec["id"])


def test_dates_and_hours_the_data_cannot_decide_are_asked_not_guessed(tmp_path, protected):
    locs = _locations(tmp_path / "l.csv", ["Shop A"])
    # 1-24 hours: asked; once confirmed, hour 24 becomes 23:00-23:59 of the same day
    rows = _days("Shop A", DAYS, hours=range(1, 25))
    up = _upload(_wide(tmp_path / "h.csv", rows), locs)
    assert [q["key"] for q in up["summary"]["questions"]] == ["hour_base"]
    s = upload.validate(up["id"], {"hour_base": 1})
    assert s["ready_to_build"] and s["set_aside"] == []
    upload.delete(up["id"])
    # slash dates with both parts <= 12: asked, with an example from the file; the answer is used
    rows = _days("Shop A", ["03/04/2024", "05/04/2024"])
    up = _upload(_wide(tmp_path / "s.csv", rows), locs)
    q = up["summary"]["questions"]
    assert [x["key"] for x in q] == ["slash_order"] and "03/04/2024" in q[0]["text"]
    s = upload.validate(up["id"], {"slash_order": "MDY"})
    assert s["ready_to_build"] and (s["first_day"], s["last_day"]) == ("2024-03-04", "2024-05-04")
    upload.delete(up["id"])
    # the data decides when it can: 15/03 is day first, so no question and no override
    rows = _days("Shop A", ["14/03/2024", "15/03/2024"])
    up = _upload(_wide(tmp_path / "d.csv", rows), locs, {"slash_order": "MDY"})
    assert up["summary"]["questions"] == [] and up["summary"]["first_day"] == "2024-03-14"
    upload.delete(up["id"])
    # a long file whose dates contradict the chosen order is refused, never silently misread
    lines = [f"Shop A,15-03-2024 {h:02d}:{m:02d},231" for h in range(3) for m in range(60)]
    s = _check(tmp_path, _long(tmp_path / "c.csv", lines), locs,
               {"clock_local": "yes", "long": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "MDY",
                                                  "order_confirmed": True}})
    assert any("The dates say day first" in r for r in s["refusals"]), s["refusals"]


def test_monitors_without_district_and_state_are_set_aside_or_asked(tmp_path, protected):
    rows = _days("Shop A", DAYS) + _days("Shop B", DAYS)
    s = _check(tmp_path, _wide(tmp_path / "r.csv", rows), _locations(tmp_path / "l.csv", ["Shop A"]))
    assert s["ready_to_build"]
    assert any("1 monitor(s) without a district and state" in a["what"] and a["rows"] == 72 for a in s["set_aside"])
    s = _check(tmp_path, _wide(tmp_path / "r2.csv", rows))
    assert [q["key"] for q in s["questions"]] == ["typed_locations"]
    assert s["questions"][0]["monitors"] == ["Shop A", "Shop B"]


def test_dataverse_tab_files_are_read_as_delivered(tmp_path, protected):
    """Harvard Dataverse's archival .tab: tab-separated, text in double quotes, numbers bare (as in the real
    2014 file checked on 16 Oct 2026: same 58,976 rows as Dataverse's metadata, nothing set aside)."""
    tab = tmp_path / "readings.tab"
    with open(tab, "w", newline="", encoding="utf-8") as fh:
        fh.write("\t".join(READINGS_HEADER) + "\n")
        for d in DAYS:
            for h in range(24):
                cells = ["0" if h == 19 else "229"] * 60
                fh.write("\t".join(['"Shop A [Offline]"', f'"{d}"', str(h)] + cells) + "\n")
    up = _upload(tab, _locations(tmp_path / "l.csv", ["Shop A"]))
    assert up["summary"]["ready_to_build"] and up["summary"]["rows"] == 72, up["summary"]
    rec = upload.build(up["id"])
    with connect() as c:
        names = [r[0] for r in c.execute(f"SELECT DISPLAY_NAME FROM {rec['schema']}.QUALITY_LOCATION").fetchall()]
        events = c.execute(f"SELECT COUNT(*) FROM {rec['schema']}.EVENT").fetchval()
    assert names == ["Shop A"] and events == 3   # one evening hour without supply on each of the three days
    upload.delete(rec["id"])


# ---------------------------------------------------------------- hostile names, delete

HOSTILE = "x'); DROP SCHEMA VOLTPROOF_DEMO CASCADE; --"
SCRIPT = "<script>alert(1)</script>"


def test_hostile_names_are_stored_as_plain_text(tmp_path, protected):
    rows = _days(HOSTILE, DAYS) + _days("Shop B", DAYS, value="0") + _days("Shop B", ["16-03-2024"])
    readings = _wide(tmp_path / "evil.csv", rows)
    rec = upload.new_upload()
    upload.receive(rec["id"], "readings", [readings.read_bytes()], "..\\..\\data\\raw\\evil.csv")
    upload.preview(rec["id"])
    typed = [{"name": HOSTILE, "district": SCRIPT, "state": "Robert'); DROP TABLE PARAMS;--"},
             {"name": "Shop B", "district": SCRIPT, "state": "Robert'); DROP TABLE PARAMS;--"}]
    s = upload.validate(rec["id"], {"typed_locations": typed})
    assert s["ready_to_build"], s
    built = upload.build(rec["id"])
    assert built["readings"]["name"] == "evil.csv"
    with connect() as c:
        names = {r[0]: (r[1], r[2]) for r in c.execute(
            f"SELECT SOURCE_NAME, DISTRICT, STATE_NAME FROM {built['schema']}.LOCATION").fetchall()}
        assert schema_dataset(c, "VOLTPROOF_DEMO")["built"]
        assert c.execute(f"SELECT COUNT(*) FROM {built['schema']}.PARAMS").fetchval() > 0
        groups = c.execute(f"SELECT COUNT(*) FROM {built['schema']}.POTENTIAL_SHARED_EVENT").fetchval()
    assert names[HOSTILE] == (SCRIPT, "Robert'); DROP TABLE PARAMS;--")
    assert groups == 0  # one monitor is always on, the other always off: nothing shared
    upload.delete(rec["id"])


def test_delete_removes_the_schema_and_every_file(tmp_path, protected):
    readings, locations = _demo_files()
    up = _upload(readings, locations)
    folder = upload.UPLOAD_DIR / up["id"]
    assert folder.exists() and upload.schema_exists(up["schema"])
    upload.delete(up["id"])
    assert not folder.exists()
    assert not upload.schema_exists(up["schema"])
    with pytest.raises(UploadError, match="Unknown upload"):
        upload.load(up["id"])
