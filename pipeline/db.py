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

DEFAULT_DEPLOYMENT_DIR = r"D:\ExasolDeployments\voltproof"
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


def connect(schema: str | None = None, **kwargs) -> pyexasol.ExaConnection:
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
        fetch_dict=False,
        **kwargs,
    )
