"""Ask VoltProof: a read-only database user that may only SELECT documented result views.

    python -m pipeline.ask setup     # schema VOLTPROOF_ASK with the views of sql/ask/reader_views.sql over VOLTPROOF,
                                     # and user VP_READER (password generated into data/.reader.json, gitignored)
    python -m pipeline.ask status    # what exists and what VP_READER may do
    python -m pipeline.ask revoke    # drop user VP_READER and schema VOLTPROOF_ASK, delete the password file

The views run with their owner's rights, so VP_READER gets CREATE SESSION and SELECT on the views schema and nothing
else: no table, no upload, no other schema, no write. An AI client can then query the views through Exasol's MCP
server as VP_READER (docs/ASK_VOLTPROOF.md); VoltProof itself never calls a language model.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from pathlib import Path

from pipeline.db import REAL_SCHEMA, connect, schema_dataset
from pipeline.run_sql import SQL_DIR, split_statements

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWS_SQL = SQL_DIR / "ask" / "reader_views.sql"
ASK_SCHEMA, READER = "VOLTPROOF_ASK", "VP_READER"
CREDENTIALS = Path(os.environ.get("VOLTPROOF_READER_FILE") or REPO_ROOT / "data" / ".reader.json")
VIEWS = ["ABOUT_THIS_DATA", "LOCATION_MONTH", "OUTAGE_EVENT", "POTENTIAL_SHARED_SUPPLY_EVENT", "DAILY_OUTAGE",
         "DATA_QUALITY", "PROVENANCE"]
REAL_ATTRIBUTION = ("Data: Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI), "
                    "https://doi.org/10.7910/DVN/CLLZZM, Harvard Dataverse, CC0 1.0. Uttar Pradesh monitors, "
                    "January 2016 to June 2019.")
SYNTHETIC_ATTRIBUTION = ("SYNTHETIC demo data: invented monitors, districts and readings; not ESMI data, and no "
                         "figure here describes real electricity supply.")
_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _ident(name: str) -> str:
    name = name.upper()
    if not _NAME.match(name):
        raise ValueError(f"not a plain identifier: {name!r}")
    return name


def create_views(source: str, ask: str = ASK_SCHEMA) -> None:
    """(Re)create the documented views of `source` in their own schema `ask`. Uploaded data is not offered."""
    source, ask = _ident(source), _ident(ask)
    if source.startswith("VP_USER_") or ask in (REAL_SCHEMA, source):
        raise ValueError(f"refusing views of {source} in {ask}")
    with connect() as c:
        info = schema_dataset(c, source)
        if not info["built"] or info["upload"]:
            raise ValueError(f"{source} is not a built ESMI or SYNTHETIC schema")
        attribution = SYNTHETIC_ATTRIBUTION if info["synthetic"] else REAL_ATTRIBUTION
        sql = (VIEWS_SQL.read_text(encoding="utf-8").replace("{{SOURCE}}", source).replace("{{ASK}}", ask)
               .replace("{{ATTRIBUTION}}", attribution))
        c.execute(f"CREATE SCHEMA IF NOT EXISTS {ask}")
        for stmt in split_statements(sql):
            c.execute(stmt)


def create_reader(user: str = READER, ask: str = ASK_SCHEMA, password: str | None = None) -> str:
    """Create or reset `user` with CREATE SESSION and SELECT on schema `ask` only; returns the password."""
    user, ask = _ident(user), _ident(ask)
    password = password or secrets.token_hex(24)  # hex only; Exasol's audit log does not keep it
    with connect() as c:
        if c.execute("SELECT COUNT(*) FROM EXA_DBA_USERS WHERE USER_NAME = {u}", {"u": user}).fetchval():
            c.execute(f'ALTER USER {user} IDENTIFIED BY "{password}"')
        else:
            c.execute(f'CREATE USER {user} IDENTIFIED BY "{password}"')
        c.execute(f"GRANT CREATE SESSION TO {user}")
        c.execute(f"GRANT SELECT ON SCHEMA {ask} TO {user}")
    return password


def drop(user: str = READER, ask: str = ASK_SCHEMA) -> None:
    user, ask = _ident(user), _ident(ask)
    with connect() as c:
        if c.execute("SELECT COUNT(*) FROM EXA_DBA_USERS WHERE USER_NAME = {u}", {"u": user}).fetchval():
            c.execute(f"DROP USER {user} CASCADE")
        c.execute(f"DROP SCHEMA IF EXISTS {ask} CASCADE")


def privileges(user: str = READER) -> dict:
    """What `user` holds: system privileges, object privileges and roles (read from the DBA views)."""
    user = _ident(user)
    with connect() as c:
        sys_privs = sorted(r[0] for r in c.execute(
            "SELECT PRIVILEGE FROM EXA_DBA_SYS_PRIVS WHERE GRANTEE = {u}", {"u": user}).fetchall())
        obj_privs = sorted(f"{r[0]} ON {r[1]} {r[2]}" for r in c.execute(
            "SELECT PRIVILEGE, OBJECT_TYPE, OBJECT_NAME FROM EXA_DBA_OBJ_PRIVS WHERE GRANTEE = {u}", {"u": user}).fetchall())
        roles = sorted(r[0] for r in c.execute(
            "SELECT GRANTED_ROLE FROM EXA_DBA_ROLE_PRIVS WHERE GRANTEE = {u}", {"u": user}).fetchall())
    return {"system": sys_privs, "objects": obj_privs, "roles": roles}


def reader_password() -> str:
    return json.loads(CREDENTIALS.read_text(encoding="utf-8"))["password"]


def setup() -> None:
    create_views(REAL_SCHEMA, ASK_SCHEMA)
    stored = None
    if CREDENTIALS.exists():
        try:
            stored = reader_password()
        except (OSError, ValueError, KeyError):
            stored = None
    password = create_reader(READER, ASK_SCHEMA, stored)
    CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS.write_text(json.dumps({"user": READER, "password": password}), encoding="utf-8")
    try:
        os.chmod(CREDENTIALS, 0o600)
    except OSError:
        pass
    print(f"{ASK_SCHEMA}: {len(VIEWS)} views over {REAL_SCHEMA}; user {READER} (password in "
          f"{CREDENTIALS.relative_to(REPO_ROOT) if CREDENTIALS.is_relative_to(REPO_ROOT) else CREDENTIALS}, never printed)")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd == "setup":
        setup()
    elif cmd == "revoke":
        drop(READER, ASK_SCHEMA)
        CREDENTIALS.unlink(missing_ok=True)
        print(f"dropped user {READER} and schema {ASK_SCHEMA}; password file removed")
    elif cmd == "status":
        print(json.dumps(privileges(READER), indent=1))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
