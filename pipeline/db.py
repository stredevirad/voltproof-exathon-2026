"""Connection helper for the local Exasol Personal deployment.

Connection details come from the launcher's deployment directory:
  <EXASOL_DEPLOYMENT_DIR>/deployment.json  host, port, user, certificate policy (not secret)
  <EXASOL_DEPLOYMENT_DIR>/secrets.json     dbPassword (secret; read at runtime, never logged)

The local deployment uses a self-signed certificate and the launcher itself instructs clients to skip
validation. We do that only for loopback hosts; any other host requires normal certificate validation.
"""

from __future__ import annotations

import json
import os
import ssl
from dataclasses import dataclass
from pathlib import Path

import pyexasol

# Same default as scripts\_common.ps1: <drive of the repository>\ExasolDeployments\voltproof
DEFAULT_DEPLOYMENT_DIR = str(Path(Path(__file__).resolve().anchor) / "ExasolDeployments" / "voltproof")
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class ConnInfo:
    host: str
    port: int
    user: str
    skip_cert_validation: bool

    @property
    def dsn(self) -> str:
        return f"{self.host}:{self.port}"


def deployment_dir() -> Path:
    return Path(os.environ.get("EXASOL_DEPLOYMENT_DIR", DEFAULT_DEPLOYMENT_DIR))


def conn_info(ddir: Path | None = None) -> ConnInfo:
    ddir = ddir or deployment_dir()
    dep = json.loads((ddir / "deployment.json").read_text(encoding="utf-8"))
    c = dep["connection"]
    return ConnInfo(
        host=c["host"],
        port=int(c["dbPort"]),
        user=c["username"],
        skip_cert_validation=bool(c.get("insecureSkipCertValidation", False)),
    )


def _password(ddir: Path) -> str:
    return json.loads((ddir / "secrets.json").read_text(encoding="utf-8"))["dbPassword"]


# Analytical schema: VOLTPROOF unless VOLTPROOF_SCHEMA names another (e.g. a clean-start test next to the main build).
DEFAULT_SCHEMA = os.environ.get("VOLTPROOF_SCHEMA", "VOLTPROOF")
REAL_SCHEMA, DEMO_SCHEMA = "VOLTPROOF", "VOLTPROOF_DEMO"
SYNTHETIC_FILE_ID_MIN = 900000000  # pipeline/synthetic.py file ids; real files carry Dataverse ids (D-033)


def schema_dataset(conn, schema: str) -> dict:
    """What a schema holds: {'built': bool, 'synthetic': bool, 'real_files': n, 'synthetic_files': n}."""
    schema = schema.upper()
    tables = {r[0] for r in conn.execute(
        f"SELECT TABLE_NAME FROM EXA_ALL_TABLES WHERE TABLE_SCHEMA = '{schema}'").fetchall()}
    out = {"built": "QUALITY_LOCATION" in tables, "synthetic": False, "real_files": 0, "synthetic_files": 0}
    if "SOURCE_FILE" in tables:
        real, synth = conn.execute(
            f"SELECT SUM(CASE WHEN FILE_ID < {SYNTHETIC_FILE_ID_MIN} THEN 1 ELSE 0 END), "
            f"SUM(CASE WHEN FILE_ID >= {SYNTHETIC_FILE_ID_MIN} THEN 1 ELSE 0 END) FROM {schema}.SOURCE_FILE").fetchone()
        out["real_files"], out["synthetic_files"] = int(real or 0), int(synth or 0)
    if "PARAMS" in tables:
        v = conn.execute(f"SELECT NUM_VALUE FROM {schema}.PARAMS WHERE NAME = 'dataset.synthetic'").fetchval()
        out["synthetic"] = bool(v) or out["synthetic_files"] > 0
    else:
        out["synthetic"] = out["synthetic_files"] > 0
    return out


def require_real_data(schema: str, what: str) -> None:
    """Real-data-only tools (headline figures, benchmarks, Prayas validation) refuse a synthetic schema."""
    with connect() as c:
        info = schema_dataset(c, schema)
    if info["synthetic"]:
        raise SystemExit(f"{what} works on the real ESMI build only; schema {schema} holds SYNTHETIC demo data. "
                         f"Set VOLTPROOF_SCHEMA={REAL_SCHEMA} (built by scripts\\load.ps1 -Set first|up).")


def resolve_schema() -> str:
    """The schema the scripts use: VOLTPROOF_SCHEMA if set; else the real build if it exists; else the demo build."""
    if os.environ.get("VOLTPROOF_SCHEMA"):
        return os.environ["VOLTPROOF_SCHEMA"].upper()
    with connect() as c:
        if schema_dataset(c, REAL_SCHEMA)["built"]:
            return REAL_SCHEMA
        if schema_dataset(c, DEMO_SCHEMA)["built"]:
            return DEMO_SCHEMA
    return REAL_SCHEMA


def connect(schema: str | None = None, fetch_dict: bool = False, **kwargs) -> pyexasol.ExaConnection:
    ddir = deployment_dir()
    info = conn_info(ddir)
    sslopt = None
    if info.skip_cert_validation:
        if info.host not in LOOPBACK:
            raise RuntimeError(
                f"Refusing to skip certificate validation for non-loopback host {info.host!r}."
            )
        sslopt = {"cert_reqs": ssl.CERT_NONE}
    return pyexasol.connect(
        dsn=info.dsn,
        user=info.user,
        password=_password(ddir),
        schema=schema or "",
        encryption=True,
        websocket_sslopt=sslopt,
        compression=False,
        client_name="VoltProof",
        fetch_dict=fetch_dict,
        **kwargs,
    )
