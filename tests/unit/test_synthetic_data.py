"""The SYNTHETIC demo set is deterministic, small, clearly labelled and in the ESMI file format (D-033)."""

from __future__ import annotations

import hashlib

from pipeline import synthetic
from pipeline.load_raw import LOCATIONS_HEADER, READINGS_HEADER, check_header, count_data_lines

EXPECTED_SHA256 = {
    "SYNTHETIC ESMI location information.csv": "7b74a89f58f48361a7e4e2562261a65ef4493787117ea89b022a121195d1955f",
    "SYNTHETIC ESMI minute-wise voltage data 2030 Jan.csv":
        "be23ace7751079faf1f588e3715ec8eb5c0a8e07e0d6d448ba7fd4636625df0b",
}


def test_generation_is_deterministic(tmp_path):
    m = synthetic.generate(tmp_path)
    got = {f["file"]: hashlib.sha256((tmp_path / f["file"]).read_bytes()).hexdigest() for f in m["files"]}
    assert got == EXPECTED_SHA256


def test_files_are_small_labelled_and_in_esmi_format(tmp_path):
    m = synthetic.generate(tmp_path)
    assert m["synthetic"] is True
    assert sum(f["bytes"] for f in m["files"]) < 5_000_000
    assert all(f["dataverse_file_id"] >= 900000000 and f["file"].startswith("SYNTHETIC ") for f in m["files"])
    loc, readings = (tmp_path / synthetic.LOCATION_FILE, tmp_path / synthetic.READINGS_FILE)
    check_header(loc, "locations")
    check_header(readings, "readings")
    assert loc.read_bytes().split(b"\r\n")[0].decode() == ",".join(LOCATIONS_HEADER)
    assert readings.read_bytes().split(b"\r\n")[0].decode() == ",".join(READINGS_HEADER)
    rows = [ln.split(",") for ln in loc.read_text(encoding="ascii").splitlines()[1:]]
    assert len(rows) == 20 and all(r[0].startswith("SYNTHETIC ") and "(SYNTHETIC)" in r[3] and r[4] == synthetic.STATE
                                   for r in rows)
    # missing hours exist (fewer rows than 20 monitors x 31 days x 24 h, plus the one duplicated hour)
    n = count_data_lines(readings)
    assert 20 * 31 * 24 * 0.95 < n < 20 * 31 * 24
