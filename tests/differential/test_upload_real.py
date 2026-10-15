"""Must-pass check 2 of the upload feature: one real ESMI file (2018 June-August, with the ESMI location file)
uploaded through the upload path gives the same per-location figures as the command-line build of that file.

The command-line build analyses Uttar Pradesh only and applies the file's declared period from Dataverse; the
upload analyses every state in the file and has no declared period (0 rows of this file fall outside it). So the
comparison covers every Uttar Pradesh location (all their tables) and every Uttar Pradesh district (the coincidence
tables), with file ids and file names left out. Needs the two files in data/raw (scripts/get-data.ps1 -Set first);
skips otherwise. Heavy: run it on its own, under the RAM guard.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from pipeline import build, load_raw, upload
from pipeline.db import connect, schema_dataset
from tests.support.fingerprints import FILE_COLUMNS, _session_formats, fingerprint

pytestmark = pytest.mark.exasol
REPO_ROOT = Path(__file__).resolve().parents[2]
RAW = REPO_ROOT / "data" / "raw"
READINGS, LOCATIONS = RAW / "ESMI minute-wise voltage data 2018 June-Aug.csv", RAW / "ESMI location information.csv"
FILE_IDS = {3362279, 3360848}
REF = "VP_UPLOAD_REAL_REF"
BY_LOCATION = ["LOCATION", "READING_CLEAN", "READING_CONFLICT", "MINUTE_READING", "VALUE_QUARANTINE", "HOUR_ROW",
               "SEGMENT", "MEASURED_RUN", "EVENT", "UNCERTAIN_CLAIM", "LOCATION_DAY", "DAILY", "MONTHLY",
               "MONITOR_WINDOW", "QUALITY_LOCATION", "INTERRUPTION", "POTENTIAL_SHARED_MEMBER"]
# Surrogate numbers that sql/060 and sql/100 assign over ALL locations and districts (ROW_NUMBER): the upload also
# holds other states, so the same event or group gets another number. The stable keys (EVENT_KEY, GROUP_KEY) and every
# figure are compared; only these numbers are left out.
SURROGATES = {"EVENT_ID", "EVENT_A", "EVENT_B", "GROUP_ID", "CHAIN_NO"}
BY_DISTRICT = ["COINCIDENT_PAIR", "COINCIDENCE_CHAIN", "POTENTIAL_SHARED_EVENT", "COINCIDENCE_BASELINE",
               "BASELINE_INTERRUPTION", "BASELINE_SHIFTED", "BASELINE_PAIRS"]

if not (READINGS.exists() and LOCATIONS.exists()):
    pytest.skip("the 2018 June-August ESMI file and the location file are not in data/raw", allow_module_level=True)


def _reference_ready() -> bool:
    with connect() as c:
        if not schema_dataset(c, REF)["built"]:
            return False
        ids = {int(r[0]) for r in c.execute(f"SELECT FILE_ID FROM {REF}.SOURCE_FILE").fetchall()}
    return ids == FILE_IDS


@pytest.fixture(scope="module")
def reference(tmp_path_factory) -> str:
    """The command-line build of exactly these two files (reused when it is already complete)."""
    if not _reference_ready():
        manifest = json.loads((REPO_ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
        files = [f for f in manifest["files"] if f["dataverse_file_id"] in FILE_IDS]
        assert {f["dataverse_file_id"] for f in files} == FILE_IDS and all(f["status"] == "verified" for f in files)
        m = tmp_path_factory.mktemp("manifest") / "manifest.json"
        m.write_text(json.dumps({"files": files}), encoding="utf-8")
        assert load_raw.main(["--schema", REF, "--manifest", str(m), "--raw-dir", str(RAW)]) == 0
        assert build.main(["--schema", REF, "--skip-load"]) == 0
    return REF


@pytest.fixture(scope="module")
def uploaded(reference):
    rec = upload.new_upload()
    upload.receive_path(rec["id"], "readings", READINGS)
    upload.receive_path(rec["id"], "locations", LOCATIONS)
    assert upload.preview(rec["id"])["layout"] == "wide"
    t0 = time.perf_counter()
    summary = upload.validate(rec["id"])
    assert summary["ready_to_build"], summary
    built = upload.build(rec["id"])
    built["wall_seconds_validate_and_build"] = round(time.perf_counter() - t0, 1)
    print(f"\nupload of {READINGS.name} ({READINGS.stat().st_size:,} bytes): {built['build']}, "
          f"validate+build {built['wall_seconds_validate_and_build']} s")
    out = os.environ.get("VOLTPROOF_UPLOAD_TIMING")
    if out:  # where the measured wall time is kept for the test report (docs/TEST_REPORT.md)
        Path(out).write_text(json.dumps({"file": READINGS.name, "bytes": READINGS.stat().st_size,
                                         "build": built["build"],
                                         "validate_and_build_seconds": built["wall_seconds_validate_and_build"]}),
                             encoding="utf-8")
    yield built
    upload.delete(built["id"])


def test_a_real_esmi_file_uploaded_gives_the_command_line_figures_for_every_up_location(reference, uploaded):
    up = uploaded["schema"]
    with connect() as c:
        _session_formats(c)
        cols = {t: {r[0] for r in c.execute("SELECT COLUMN_NAME FROM EXA_ALL_COLUMNS WHERE COLUMN_SCHEMA = {s} "
                                            "AND COLUMN_TABLE = {t}", {"s": REF, "t": t}).fetchall()}
                for t in BY_LOCATION + BY_DISTRICT}
        n_up = c.execute(f"SELECT COUNT(*) FROM {REF}.LOCATION_IN_SCOPE").fetchval()
        districts = c.execute(f"SELECT COUNT(DISTINCT DISTRICT) FROM {REF}.LOCATION l JOIN {REF}.LOCATION_IN_SCOPE s "
                              f"ON s.LOCATION_ID = l.LOCATION_ID").fetchval()
        extra_states = c.execute(f"SELECT COUNT(DISTINCT STATE_NAME) FROM {up}.QUALITY_LOCATION "
                                 f"WHERE STATE_NAME <> 'Uttar Pradesh'").fetchval()
        different, compared = [], []
        for t in BY_LOCATION + BY_DISTRICT:
            if "LOCATION_ID" in cols[t]:
                where = "WHERE LOCATION_ID IN (SELECT LOCATION_ID FROM {s}.LOCATION_IN_SCOPE)"
            elif "LOCATION_ID_A" in cols[t]:
                where = "WHERE LOCATION_ID_A IN (SELECT LOCATION_ID FROM {s}.LOCATION_IN_SCOPE)"
            elif "DISTRICT" in cols[t]:
                where = (f"WHERE DISTRICT IN (SELECT DISTINCT l.DISTRICT FROM {REF}.LOCATION l "
                         f"JOIN {REF}.LOCATION_IN_SCOPE s ON s.LOCATION_ID = l.LOCATION_ID)")
            else:
                pytest.fail(f"{t}: no LOCATION_ID or DISTRICT column to restrict on")
            # both sides restricted to the command-line build's Uttar Pradesh locations / districts
            skip = FILE_COLUMNS | SURROGATES
            fa = fingerprint(c, up, t, skip_columns=skip, where=where.format(s=REF))
            fb = fingerprint(c, REF, t, skip_columns=skip, where=where.format(s=REF))
            compared.append((t, fb[1]))
            if fa != fb:
                different.append(t)
    assert different == [], different
    assert n_up > 90 and districts >= 10  # 179 UP locations in the location file, 17 districts with readings (2018)
    assert extra_states > 0  # the upload also analysed the other states in the file
    assert all(rows > 0 for t, rows in compared if t not in ("READING_CONFLICT", "VALUE_QUARANTINE")), compared
