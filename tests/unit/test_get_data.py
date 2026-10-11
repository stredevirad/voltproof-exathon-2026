"""Unit tests for the raw-file verifier (pipeline/get_data.py). No network, synthetic files only."""

import hashlib

import pytest

from pipeline import get_data


def _entry(tmp_path, content: bytes, *, md5: str, original_size: int, stored_size: int, tabular=True):
    return {
        "id": 999,
        "stored_name": "x.tab",
        "stored_size": stored_size,
        "original_name": "x.csv",
        "original_size": original_size,
        "md5": md5,
        "is_tabular": tabular,
    }


def test_original_csv_with_matching_md5_is_verified(tmp_path):
    data = b"h1,h2\n1,2\n"
    p = tmp_path / "x.csv"
    p.write_bytes(data)
    e = _entry(tmp_path, data, md5=hashlib.md5(data).hexdigest(), original_size=len(data), stored_size=999)
    r = get_data.verify(e, p)
    assert r["status"] == "verified"
    assert r["variant"] == "original"


def test_tab_export_verified_by_size_and_rows_when_md5_differs(tmp_path, monkeypatch):
    data = b"h1\th2\n1\t2\n3\t4\n"
    p = tmp_path / "x.tab"
    p.write_bytes(data)
    monkeypatch.setattr(get_data, "ddi_row_count", lambda fid: 2)
    e = _entry(tmp_path, data, md5="0" * 32, original_size=12345, stored_size=len(data))
    r = get_data.verify(e, p)
    assert r["variant"] == "tab-export"
    assert r["rows"] == 2
    assert r["status"] == "verified-size-and-rows"


def test_tab_export_with_wrong_row_count_is_a_mismatch(tmp_path, monkeypatch):
    data = b"h1\th2\n1\t2\n"
    p = tmp_path / "x.tab"
    p.write_bytes(data)
    monkeypatch.setattr(get_data, "ddi_row_count", lambda fid: 5)
    e = _entry(tmp_path, data, md5="0" * 32, original_size=12345, stored_size=len(data))
    assert get_data.verify(e, p)["status"] == "MISMATCH-rows"


def test_unknown_size_and_wrong_md5_is_a_mismatch(tmp_path):
    data = b"tampered"
    p = tmp_path / "x.csv"
    p.write_bytes(data)
    e = _entry(tmp_path, data, md5="0" * 32, original_size=1, stored_size=2)
    assert get_data.verify(e, p)["status"] == "MISMATCH"


def test_download_refuses_without_guestbook_details(monkeypatch):
    for env in [*get_data.GUESTBOOK_ENV.values(), get_data.INTENDED_USE_ENV]:
        monkeypatch.delenv(env, raising=False)
    with pytest.raises(SystemExit, match="DATAVERSE_GB_"):
        get_data.guestbook_body()
