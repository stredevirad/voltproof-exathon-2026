"""Connection helper for the local Exasol Personal deployment.

Connection details come from the launcher's deployment directory:
  <EXASOL_DEPLOYMENT_DIR>/deployment.json  host, port, user, certificate policy (not secret)
  <EXASOL_DEPLOYMENT_DIR>/secrets.json     dbPassword (secret; read at runtime, never logged)

The local deployment uses a self-signed certificate and the launcher itself instructs clients to skip
validation. We do that only for loopback hosts; any other host requires normal certificate validation.

Optional override, used only when VOLTPROOF_EXA_DSN is set (CI runs Exasol's exasol/nano image, which has no
launcher deployment directory): VOLTPROOF_EXA_DSN=host:port, VOLTPROOF_EXA_USER (default sys) and
VOLTPROOF_EXA_PASSWORD_FILE (a file holding the password; read at runtime, never logged). Unset, nothing changes.
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


ENV_DSN, ENV_USER, ENV_PASSWORD_FILE = "VOLTPROOF_EXA_DSN", "VOLTPROOF_EXA_USER", "VOLTPROOF_EXA_PASSWORD_FILE"


def _env_override() -> ConnInfo | None:
    dsn = os.environ.get(ENV_DSN, "").strip()
    if not dsn:
        return None
    host, sep, port = dsn.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise RuntimeError(f"{ENV_DSN} must be host:port, got {dsn!r}.")
    if not os.environ.get(ENV_PASSWORD_FILE):
        raise RuntimeError(f"{ENV_DSN} is set, so {ENV_PASSWORD_FILE} must name the file that holds the password.")
    # same certificate rule as the launcher deployment: skip validation of the self-signed certificate on loopback only
    return ConnInfo(host=host, port=int(port), user=os.environ.get(ENV_USER) or "sys",
                    skip_cert_validation=host in LOOPBACK)


def conn_info(ddir: Path | None = None) -> ConnInfo:
    override = _env_override()
    if override:
        return override
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
    if _env_override():
        return Path(os.environ[ENV_PASSWORD_FILE]).read_text(encoding="utf-8").strip()
    return json.loads((ddir / "secrets.json").read_text(encoding="utf-8"))["dbPassword"]


# Analytical schema: VOLTPROOF unless VOLTPROOF_SCHEMA names another (e.g. a clean-start test next to the main build).
DEFAULT_SCHEMA = os.environ.get("VOLTPROOF_SCHEMA", "VOLTPROOF")
REAL_SCHEMA, DEMO_SCHEMA = "VOLTPROOF", "VOLTPROOF_DEMO"
SYNTHETIC_FILE_ID_MIN = 900000000  # pipeline/synthetic.py file ids; real files carry Dataverse ids (D-033)
UPLOAD_FILE_ID_MIN = 800000000     # uploaded files (pipeline/upload.py): 800000001+; never a Dataverse or synthetic id


def schema_dataset(conn, schema: str) -> dict:
    """What a schema holds: {'built': bool, 'synthetic': bool, 'upload': bool, 'real_files': n, 'synthetic_files': n,
    'upload_files': n}. Uploaded data (pipeline/upload.py) is marked by its file ids and by dataset.kind = upload."""
    schema = schema.upper()
    tables = {r[0] for r in conn.execute(
        f"SELECT TABLE_NAME FROM EXA_ALL_TABLES WHERE TABLE_SCHEMA = '{schema}'").fetchall()}
    out = {"built": "QUALITY_LOCATION" in tables, "synthetic": False, "upload": False, "real_files": 0,
           "synthetic_files": 0, "upload_files": 0}
    if "SOURCE_FILE" in tables:
        real, synth, upl = conn.execute(
            f"SELECT SUM(CASE WHEN FILE_ID < {UPLOAD_FILE_ID_MIN} THEN 1 ELSE 0 END), "
            f"SUM(CASE WHEN FILE_ID >= {SYNTHETIC_FILE_ID_MIN} THEN 1 ELSE 0 END), "
            f"SUM(CASE WHEN FILE_ID >= {UPLOAD_FILE_ID_MIN} AND FILE_ID < {SYNTHETIC_FILE_ID_MIN} THEN 1 ELSE 0 END) "
            f"FROM {schema}.SOURCE_FILE").fetchone()
        out["real_files"], out["synthetic_files"], out["upload_files"] = int(real or 0), int(synth or 0), int(upl or 0)
    kind = None
    if "PARAMS" in tables:
        v = conn.execute(f"SELECT NUM_VALUE FROM {schema}.PARAMS WHERE NAME = 'dataset.synthetic'").fetchval()
        kind = conn.execute(f"SELECT STR_VALUE FROM {schema}.PARAMS WHERE NAME = 'dataset.kind'").fetchval()
        out["synthetic"] = bool(v) or out["synthetic_files"] > 0
    else:
        out["synthetic"] = out["synthetic_files"] > 0
    out["upload"] = kind == "upload" or out["upload_files"] > 0
    return out


def require_real_data(schema: str, what: str) -> None:
    """Real-data-only tools (headline figures, benchmarks, Prayas validation) refuse a synthetic schema."""
    with connect() as c:
        info = schema_dataset(c, schema)
    if info["synthetic"]:
        raise SystemExit(f"{what} works on the real ESMI build only; schema {schema} holds SYNTHETIC demo data. "
                         f"Set VOLTPROOF_SCHEMA={REAL_SCHEMA} (built by scripts\\load.ps1 -Set first|up).")
    if info["upload"]:
        raise SystemExit(f"{what} works on the real ESMI build only; schema {schema} holds uploaded data. "
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


def connect(schema: str | None = None, fetch_dict: bool = False, *, user: str | None = None,
            password: str | None = None, **kwargs) -> pyexasol.ExaConnection:
    """Connect as the deployment's database user, or as `user` with `password` (the restricted upload user of
    pipeline/upload.py, which owns only the VP_USER_ schemas)."""
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
        user=user or info.user,
        password=password if user else _password(ddir),
        schema=schema or "",
        encryption=True,
        websocket_sslopt=sslopt,
        compression=False,
        client_name="VoltProof",
        fetch_dict=fetch_dict,
        **kwargs,
    )
