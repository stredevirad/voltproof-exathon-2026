"""Loader input validation: empty, header-only, wrong column order, wrong encoding (synthetic files)."""

import pytest

from pipeline.load_raw import LOCATIONS_HEADER, READINGS_HEADER, RawFileError, check_header, count_data_lines


def _write(tmp_path, name, data: bytes):
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_empty_file_gives_clear_error(tmp_path):
    p = _write(tmp_path, "empty.csv", b"")
    with pytest.raises(RawFileError, match="empty"):
        check_header(p, "readings")


def test_header_only_file_is_valid_and_has_zero_rows(tmp_path):
    p = _write(tmp_path, "header.csv", (",".join(READINGS_HEADER) + "\r\n").encode())
    check_header(p, "readings")
    assert count_data_lines(p) == 0


def test_wrong_column_order_is_rejected_with_position(tmp_path):
    cols = list(READINGS_HEADER)
    cols[1], cols[2] = cols[2], cols[1]  # Hour before Date
    p = _write(tmp_path, "swapped.csv", (",".join(cols) + "\r\n").encode())
    with pytest.raises(RawFileError, match="column 2"):
        check_header(p, "readings")


def test_missing_minute_columns_are_rejected(tmp_path):
    p = _write(tmp_path, "short.csv", (",".join(READINGS_HEADER[:40]) + "\r\n").encode())
    with pytest.raises(RawFileError, match="40 columns vs 63"):
        check_header(p, "readings")


def test_utf16_file_is_rejected(tmp_path):
    p = _write(tmp_path, "utf16.csv", (",".join(LOCATIONS_HEADER) + "\r\n").encode("utf-16"))
    with pytest.raises(RawFileError, match="UTF-16"):
        check_header(p, "locations")


def test_non_utf8_header_is_rejected(tmp_path):
    p = _write(tmp_path, "bad_header.csv", b"Location name,From date,To date,District,St\xe4te,Category,Connection Type\r\n")
    with pytest.raises(RawFileError, match="header is not valid UTF-8"):
        check_header(p, "locations")


def test_non_utf8_data_line_is_reported_with_its_line_number(tmp_path):
    from pipeline.load_raw import _stream_with_line_numbers

    header = ",".join(LOCATIONS_HEADER).encode()
    p = _write(tmp_path, "latin.csv", header + b"\r\nok,a,b,c,d,e,f\r\nCaf\xe9,a,b,c,d,e,f\r\n")
    check_header(p, "locations")  # the header itself is fine

    class Sink:
        def __init__(self):
            self.data = b""

        def write(self, b):
            self.data += b

    with pytest.raises(RawFileError, match="line 3 is not valid UTF-8"):
        _stream_with_line_numbers(Sink(), str(p), file_id=7)


def test_stream_prefixes_file_id_and_physical_line_number(tmp_path):
    from pipeline.load_raw import _stream_with_line_numbers

    p = _write(tmp_path, "ok.csv", b"h1,h2\r\na,1\r\nb,2\r\n")

    class Sink:
        data = b""

        def write(self, b):
            Sink.data += b

    _stream_with_line_numbers(Sink(), str(p), file_id=42)
    assert Sink.data == b"42,2,a,1\n42,3,b,2\n"


def test_readings_header_on_location_kind_is_rejected(tmp_path):
    p = _write(tmp_path, "mixup.csv", (",".join(READINGS_HEADER) + "\r\n").encode())
    with pytest.raises(RawFileError, match="unexpected header"):
        check_header(p, "locations")
