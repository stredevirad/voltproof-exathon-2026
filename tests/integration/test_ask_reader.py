"""Ask VoltProof (pipeline/ask.py): the read-only user can read the documented views and nothing else.

A test user and views schema are built over the SYNTHETIC demo schema with the same code as `pipeline.ask setup`,
then dropped. The real VP_READER, when it exists, must hold exactly CREATE SESSION and SELECT on VOLTPROOF_ASK.
"""

from __future__ import annotations

import pyexasol
import pytest

from pipeline import ask
from pipeline.db import DEMO_SCHEMA, connect, schema_dataset

pytestmark = pytest.mark.exasol

USER, ASK = "VP_READER_TEST", "VP_ASK_TEST"


@pytest.fixture(scope="module")
def reader():
    with connect() as c:
        if not schema_dataset(c, DEMO_SCHEMA)["built"]:
            pytest.skip(f"{DEMO_SCHEMA} is not built (scripts/load.ps1 -Set demo)")
    ask.drop(USER, ASK)
    ask.create_views(DEMO_SCHEMA, ASK)
    password = ask.create_reader(USER, ASK)
    conn = connect(user=USER, password=password)
    yield conn
    conn.close()
    ask.drop(USER, ASK)


def _refused(conn, sql: str) -> bool:
    try:
        conn.execute(sql)
    except pyexasol.ExaQueryError:
        return True
    return False


def test_the_reader_can_read_every_documented_view(reader):
    for v in ask.VIEWS:
        assert reader.execute(f"SELECT COUNT(*) FROM {ASK}.{v}").fetchval() > 0, v
    about = dict(reader.execute(f"SELECT TOPIC, NOTE FROM {ASK}.ABOUT_THIS_DATA").fetchall())
    assert "SYNTHETIC" in about["source"] and "never counted as an outage" in about["missing data"]


def test_every_view_and_column_is_documented(reader):
    with connect() as c:
        views = dict(c.execute("SELECT VIEW_NAME, VIEW_COMMENT FROM EXA_ALL_VIEWS WHERE VIEW_SCHEMA = {s}",
                               {"s": ASK}).fetchall())
        undocumented = c.execute("SELECT COLUMN_TABLE, COLUMN_NAME FROM EXA_ALL_COLUMNS WHERE COLUMN_SCHEMA = {s} "
                                 "AND (COLUMN_COMMENT IS NULL OR COLUMN_COMMENT = '')", {"s": ASK}).fetchall()
    assert sorted(views) == sorted(ask.VIEWS) and all(views.values())
    assert not undocumented


def test_the_reader_cannot_read_any_table_or_other_schema(reader):
    with connect() as c:  # one table from every other schema: raw data, results, uploads, test schemas
        targets = c.execute("SELECT TABLE_SCHEMA, MIN(TABLE_NAME) FROM EXA_ALL_TABLES WHERE TABLE_SCHEMA <> {s} "
                            "GROUP BY TABLE_SCHEMA", {"s": ASK}).fetchall()
    targets += [(DEMO_SCHEMA, "RAW_HOURLY"), (DEMO_SCHEMA, "EVENT"), (DEMO_SCHEMA, "RUN_LOG")]
    readable = [f"{s}.{t}" for s, t in targets if not _refused(reader, f"SELECT * FROM {s}.{t} LIMIT 1")]
    assert not readable, f"the reader can read: {readable}"
    assert _refused(reader, "SELECT * FROM EXA_DBA_AUDIT_SQL LIMIT 1")
    visible = {r[0] for r in reader.execute("SELECT TABLE_SCHEMA FROM EXA_ALL_TABLES").fetchall()}
    assert not visible, f"tables visible to the reader: {visible}"


def test_the_reader_cannot_write_or_grant(reader):
    for sql in [f"CREATE TABLE {ASK}.X (A INT)", "CREATE SCHEMA VP_READER_TEST_OWN",
                f"DELETE FROM {ASK}.ABOUT_THIS_DATA", f"INSERT INTO {ASK}.ABOUT_THIS_DATA VALUES ('a', 'b')",
                f"DROP VIEW {ASK}.OUTAGE_EVENT", f"CREATE OR REPLACE VIEW {ASK}.V AS SELECT 1 AS A FROM DUAL",
                f"DELETE FROM {DEMO_SCHEMA}.EVENT", f"GRANT SELECT ON SCHEMA {ASK} TO PUBLIC",
                f"CREATE USER VP_READER_TEST_2 IDENTIFIED BY \"x{USER}1\""]:
        assert _refused(reader, sql), sql


def test_the_real_reader_holds_only_session_and_select_on_its_views():
    with connect() as c:
        if not c.execute("SELECT COUNT(*) FROM EXA_DBA_USERS WHERE USER_NAME = {u}", {"u": ask.READER}).fetchval():
            pytest.skip("VP_READER is not set up here (python -m pipeline.ask setup)")
    assert ask.privileges(ask.READER) == {"system": ["CREATE SESSION"],
                                          "objects": [f"SELECT ON SCHEMA {ask.ASK_SCHEMA}"], "roles": []}
