"""One database build at a time: a lock shared by the command-line build (pipeline.build) and upload builds
(pipeline.upload, also when started from the web app).

The lock is an operating-system lock on a file under data/ (gitignored). The system releases it when the process
that holds it ends, so a build stopped by the RAM guard or a crash never leaves a stale lock behind. A second build
is refused at once with a plain message; it never waits.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = Path(os.environ.get("VOLTPROOF_BUILD_LOCK") or REPO_ROOT / "data" / ".build.lock")


class BuildBusy(RuntimeError):
    """Another database build is running."""


def _try_lock(fh) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fh) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def _info_path() -> Path:
    return LOCK_PATH.with_name(LOCK_PATH.name + ".info")


def current() -> dict | None:
    """What holds the lock now ({'what', 'pid', 'since'}), or None when no build is running."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_PATH, "a+b") as fh:
        if _try_lock(fh):
            _unlock(fh)
            return None
    try:
        return json.loads(_info_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"what": "a database build", "pid": None, "since": None}


@contextmanager
def build_lock(what: str):
    """Hold the build lock for the duration of the block; raise BuildBusy if another build holds it."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "a+b")
    if not _try_lock(fh):
        fh.close()
        held = current() or {}
        since = f" (since {held['since']})" if held.get("since") else ""
        raise BuildBusy(f"Another database build is running: {held.get('what', 'a database build')}{since}. "
                        "Only one build can run at a time; try again when it has finished.")
    try:
        _info_path().write_text(json.dumps({"what": what, "pid": os.getpid(),
                                            "since": dt.datetime.now().isoformat(timespec="seconds")}),
                                encoding="utf-8")
        yield
    finally:
        try:
            _info_path().unlink()
        except OSError:
            pass
        _unlock(fh)
        fh.close()
