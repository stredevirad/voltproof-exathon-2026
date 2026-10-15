"""Uploads: the schema name is built in one place from a random 8-hex id, file names are display strings only,
and the user's column and date choices are checked against fixed lists (no database needed)."""

from __future__ import annotations

import pytest

from pipeline import upload
from pipeline.upload import UploadError, check_mapping, display_name, is_upload_schema, schema_for


def test_schema_name_comes_only_from_an_8_hex_id():
    assert schema_for("bebad8f4") == "VP_USER_BEBAD8F4"
    for bad in ["", "VOLTPROOF", "VOLTPROOF_DEMO", "../bebad8f4", "BEBAD8F4", "bebad8f", "bebad8f45",
                "bebad8f4; DROP SCHEMA VOLTPROOF CASCADE", "bebad8g4", "bebad8f4\n", None, 12345678]:
        with pytest.raises(UploadError):
            schema_for(bad)


def test_only_upload_schemas_are_recognised_as_uploads():
    assert is_upload_schema("VP_USER_0A1B2C3D")
    for name in ["VOLTPROOF", "VOLTPROOF_DEMO", "VP_BASECHECK", "VP_TEST_1", "VP_USER_", "VP_USER_0a1b2c3d",
                 "VP_USER_0A1B2C3D; DROP", "vp_user_0a1b2c3d", ""]:
        assert not is_upload_schema(name)


def test_file_names_are_display_strings_without_paths():
    assert display_name("../../etc/passwd") == "passwd"
    assert display_name("C:\\Users\\x\\..\\readings.csv") == "readings.csv"
    assert display_name("a\x00b\x1b[31mc.csv") == "ab[31mc.csv"
    assert display_name('<script>"x".csv') == "scriptx.csv"
    assert display_name("") == "uploaded file"
    assert len(display_name("x" * 500 + ".csv")) == 120


def _rec(layout="long", header=("monitor", "time", "volts")):
    return {"preview": {"layout": layout, "sep": ",", "header": list(header),
                        "suggest": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "YMD"}},
            "locations": None}


def test_column_choices_are_positions_in_the_header():
    m = check_mapping(_rec(), {"long": {"location_col": 0, "ts_col": 1, "value_col": 2, "order": "DMY"}})
    assert m["long"]["order"] == "DMY" and m["long"]["location_col"] == 0
    for bad in [{"ts_col": 7}, {"ts_col": -1}, {"ts_col": "1; DROP"}, {"ts_col": 2, "value_col": 2}]:
        with pytest.raises(UploadError):
            check_mapping(_rec(), {"long": {"location_col": 0, "ts_col": 1, "value_col": 2, **bad}})


def test_unknown_orders_fall_back_to_fixed_values():
    m = check_mapping(_rec(), {"dash_order": "'; DROP", "slash_order": "MDY", "hour_base": "7",
                               "long": {"order": "'); DROP SCHEMA x; --"}})
    assert m["dash_order"] is None and m["slash_order"] == "MDY" and m["hour_base"] == 0
    assert m["long"]["order"] == "DMY"


def test_a_single_monitor_file_needs_a_name_and_typed_text_is_cleaned():
    with pytest.raises(UploadError):
        check_mapping(_rec(header=("time", "volts")), {"long": {"location_col": None, "ts_col": 0, "value_col": 1}})
    m = check_mapping(_rec(header=("time", "volts")),
                      {"long": {"location_col": None, "ts_col": 0, "value_col": 1,
                                "single_monitor_name": "Shop\x07 meter"},
                       "typed_locations": [{"name": "Shop meter", "district": "Pune\n", "state": "Maharashtra"},
                                           {"name": "half", "district": "", "state": "X"}]})
    assert m["long"]["single_monitor_name"] == "Shop meter"
    assert m["typed_locations"] == [{"name": "Shop meter", "district": "Pune", "state": "Maharashtra"}]


def test_upload_limits_are_the_documented_ones():
    assert upload.MAX_BYTES == 150_000_000
    assert upload.READINGS_FILE_ID >= 800000000 and upload.TYPED_LOCATIONS_FILE_ID < 900000000
    assert upload.UPLOADER_PRIVILEGES == ["CREATE SESSION", "CREATE SCHEMA", "CREATE TABLE", "CREATE VIEW", "IMPORT"]
