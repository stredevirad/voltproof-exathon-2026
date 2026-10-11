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


class _FakeConn:
    """Just enough of a pyexasol connection to drive load_file; IMPORT fails `fail_times` times first."""

    def __init__(self, error: str, fail_times: int, rows: int):
        self.error, self.fail_times, self.rows = error, fail_times, rows
        self.imports = self.rollbacks = self.commits = 0
        self.ext = self

    def execute(self, sql):
        return self

    def fetchval(self):
        return self.rows

    def insert_multi(self, *a, **k):
        pass

    def import_from_callback(self, *a, **k):
        self.imports += 1
        if self.imports <= self.fail_times:
            raise RuntimeError(self.error)

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1


_ETL5105 = ("ETL-5105: Following error occured while reading data from external connection [https://x/000.csv "
            "failed after 174960452 bytes. [OpenSSL SSL_read: SSL_ERROR_SYSCALL, errno 0],[56],[Failure when "
            "receiving data from the peer]]")


def _readings_file(tmp_path):
    row = ",".join(["X", "01-06-2018", "0"] + ["230"] * 60)
    return _write(tmp_path, "r.csv", (",".join(READINGS_HEADER) + "\r\n" + row + "\r\n" + row + "\r\n").encode())


def test_transient_import_error_is_retried_once_after_rollback(tmp_path):
    from pipeline.load_raw import load_file
    conn = _FakeConn(_ETL5105, fail_times=1, rows=2)
    r = load_file(conn, "S", 1, _readings_file(tmp_path), "readings", None, None)
    assert (conn.imports, conn.rollbacks, conn.commits, r["attempts"], r["rows"]) == (2, 1, 1, 2, 2)


def test_transient_import_error_twice_fails(tmp_path):
    from pipeline.load_raw import load_file
    conn = _FakeConn(_ETL5105, fail_times=2, rows=2)
    with pytest.raises(RuntimeError, match="ETL-5105"):
        load_file(conn, "S", 1, _readings_file(tmp_path), "readings", None, None)
    assert conn.commits == 0


def test_data_errors_are_not_retried(tmp_path):
    from pipeline.load_raw import load_file
    conn = _FakeConn("ETL-3050: [Column=5 Row=7] data exception - invalid character value", fail_times=1, rows=2)
    with pytest.raises(RuntimeError, match="ETL-3050"):
        load_file(conn, "S", 1, _readings_file(tmp_path), "readings", None, None)
    assert (conn.imports, conn.rollbacks) == (1, 0)
