"""Connection details: the launcher deployment directory by default; the VOLTPROOF_EXA_* override (used by CI on
Exasol's nano image) only when VOLTPROOF_EXA_DSN is set (no database needed)."""

from __future__ import annotations

import json

import pytest

from pipeline import db

ENV = (db.ENV_DSN, db.ENV_USER, db.ENV_PASSWORD_FILE)


@pytest.fixture
def deployment(tmp_path, monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "deployment.json").write_text(json.dumps({"connection": {
        "host": "127.0.0.1", "dbPort": 8563, "username": "sys", "insecureSkipCertValidation": True}}), encoding="utf-8")
    (tmp_path / "secrets.json").write_text(json.dumps({"dbPassword": "from-deployment"}), encoding="utf-8")
    monkeypatch.setenv("EXASOL_DEPLOYMENT_DIR", str(tmp_path))
    return tmp_path


def test_without_the_override_the_deployment_directory_is_used(deployment):
    assert db.conn_info() == db.ConnInfo("127.0.0.1", 8563, "sys", True)
    assert db._password(deployment) == "from-deployment"


def test_the_override_replaces_dsn_user_and_password(deployment, monkeypatch, tmp_path):
    pw = tmp_path / "pw.txt"
    pw.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setenv(db.ENV_DSN, "localhost:9563")
    monkeypatch.setenv(db.ENV_USER, "ci_user")
    monkeypatch.setenv(db.ENV_PASSWORD_FILE, str(pw))
    assert db.conn_info() == db.ConnInfo("localhost", 9563, "ci_user", True)
    assert db._password(deployment) == "from-file"


def test_the_override_defaults_to_sys_and_validates_certificates_off_loopback(deployment, monkeypatch, tmp_path):
    monkeypatch.setenv(db.ENV_DSN, "db.example.org:8563")
    monkeypatch.setenv(db.ENV_PASSWORD_FILE, str(tmp_path / "pw.txt"))
    assert db.conn_info() == db.ConnInfo("db.example.org", 8563, "sys", False)


@pytest.mark.parametrize("dsn", ["8563", "localhost", "localhost:", ":8563", "localhost:abc"])
def test_a_malformed_dsn_is_refused(deployment, monkeypatch, tmp_path, dsn):
    monkeypatch.setenv(db.ENV_DSN, dsn)
    monkeypatch.setenv(db.ENV_PASSWORD_FILE, str(tmp_path / "pw.txt"))
    with pytest.raises(RuntimeError):
        db.conn_info()


def test_the_override_needs_a_password_file(deployment, monkeypatch):
    monkeypatch.setenv(db.ENV_DSN, "127.0.0.1:8563")
    with pytest.raises(RuntimeError, match=db.ENV_PASSWORD_FILE):
        db.conn_info()
