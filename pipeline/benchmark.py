"""Benchmarks recorded from real runs (docs/BENCHMARKS.md). Every number in that file comes from the JSON files
this script writes to docs/benchmarks/.

    .venv\\Scripts\\python.exe -m pipeline.benchmark build   --runs 3 [--cold]   # full UP build: IMPORT + all SQL
    .venv\\Scripts\\python.exe -m pipeline.benchmark queries --runs 5 [--cold]   # the app's interactive queries
    .venv\\Scripts\\python.exe -m pipeline.benchmark history                     # earlier formulations (audit log)

"Cold" = the first run after `scripts\\exa.ps1 stop` + `start` (database caches empty; the volume is already grown;
the Windows file cache is not cleared). "Warm" = repeated runs with the database running.
DB-side metrics (duration, CPU, temp RAM peak, disk read/write) come from Exasol's EXA_DBA_AUDIT_SQL, joined by
the session and statement ids that RUN_LOG records for every statement. Timestamps in the audit log are UTC.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from pipeline.db import DEFAULT_SCHEMA, connect

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "docs" / "benchmarks"
PY = sys.executable
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


class _MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_ram_gib() -> float:
    s = _MemStatus()
    s.dwLength = ctypes.sizeof(_MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return round(s.ullAvailPhys / 2**30, 2)


def total_ram_gib() -> float:
    s = _MemStatus()
    s.dwLength = ctypes.sizeof(_MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
    return round(s.ullTotalPhys / 2**30, 1)


RAM_FLOOR_GIB = 0.4  # stop a run if free host RAM falls below this (agreed with the project owner)


class RamSampler:
    """Minimum free host RAM while a run is in progress (sampled every 2 s). With `proc`, terminates it if free RAM
    falls below RAM_FLOOR_GIB and sets `tripped`."""

    def __init__(self, proc: subprocess.Popen | None = None):
        self.min_free = free_ram_gib()
        self.proc, self.tripped = proc, False
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.wait(2):
            self.min_free = min(self.min_free, free_ram_gib())
            if self.proc is not None and self.min_free < RAM_FLOOR_GIB and self.proc.poll() is None:
                self.tripped = True
                self.proc.terminate()

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join()


def conditions() -> dict:
    """Other memory-heavy software that changes host conditions between runs (recorded with every run)."""
    out = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                          "Get-Service Oracle* -ErrorAction SilentlyContinue | Where-Object Status -eq 'Running' | "
                          "ForEach-Object Name"], capture_output=True, text=True, check=False).stdout.split()
    return {"oracle_services_running": out, "free_ram_gib": free_ram_gib()}


def disk_free_gib() -> dict:
    return {d: round(shutil.disk_usage(f"{d}:\\").free / 2**30, 1) for d in ("C", "D")}


def environment() -> dict:
    with connect() as c:
        version = c.execute("SELECT PARAM_VALUE FROM EXA_METADATA WHERE PARAM_NAME = 'databaseProductVersion'").fetchval()
    return {"host": platform.node(), "os": platform.platform(), "processor": platform.processor(),
            "logical_cpus": os.cpu_count(), "host_ram_gib": total_ram_gib(), "exasol_version": version,
            "python": platform.python_version()}


def exa(*args: str) -> str:
    out = subprocess.run(PS + [str(REPO_ROOT / "scripts" / "exa.ps1"), *args], cwd=REPO_ROOT, capture_output=True,
                         text=True, check=False)
    return out.stdout + out.stderr


def restart_db() -> float:
    """Stop and start the deployment; return seconds until it reports database_ready."""
    t0 = time.perf_counter()
    exa("stop")
    exa("start")
    for _ in range(120):
        if "database_ready" in exa("status"):
            break
        time.sleep(5)
    else:
        raise SystemExit("database did not become ready after restart")
    # first successful connection marks readiness for SQL
    for _ in range(60):
        try:
            with connect() as c:
                c.execute("SELECT 1").fetchval()
            break
        except Exception:  # noqa: BLE001 - retry until the SQL port answers
            time.sleep(5)
    return round(time.perf_counter() - t0, 1)


def audit_for(ids: list[tuple[int, int]]) -> dict[tuple[int, int], dict]:
    """EXA_DBA_AUDIT_SQL metrics for (session_id, stmt_id) pairs (after FLUSH STATISTICS)."""
    if not ids:
        return {}
    with connect() as c:
        c.execute("FLUSH STATISTICS")
        out = {}
        sessions = sorted({s for s, _ in ids})
        for s in sessions:
            for r in c.execute(f"""SELECT SESSION_ID, STMT_ID, DURATION, CPU, TEMP_DB_RAM_PEAK, PERSISTENT_DB_RAM_PEAK,
                                          HDD_READ, HDD_WRITE, ROW_COUNT, SUCCESS
                                   FROM EXA_DBA_AUDIT_SQL WHERE SESSION_ID = {int(s)}""").fetchall():
                out[(int(r[0]), int(r[1]))] = {"db_seconds": float(r[2]) if r[2] is not None else None,
                                               "cpu_pct": float(r[3]) if r[3] is not None else None,
                                               "temp_ram_peak_mib": float(r[4]) if r[4] is not None else None,
                                               "persistent_ram_peak_mib": float(r[5]) if r[5] is not None else None,
                                               "hdd_read_mib_per_s": float(r[6]) if r[6] is not None else None,
                                               "hdd_write_mib_per_s": float(r[7]) if r[7] is not None else None}
    return out


def _save(kind: str, record: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{kind}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return path


def bench_build(runs: int, cold: bool, schema: str) -> None:
    for i in range(1, runs + 1):
        restart = restart_db() if cold else None
        before = {"free_ram_gib": free_ram_gib(), "disk_free_gib": disk_free_gib()}
        cond = conditions()
        t0 = time.perf_counter()
        started = dt.datetime.now().isoformat(timespec="seconds")
        proc = subprocess.Popen([PY, "-m", "pipeline.build", "--schema", schema], cwd=REPO_ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        with RamSampler(proc) as ram:
            out, _ = proc.communicate()
        wall = round(time.perf_counter() - t0, 1)
        if proc.returncode != 0 or ram.tripped:
            err = [ln.strip() for ln in out.splitlines() if "message" in ln or "Error" in ln][-3:]
            if ram.tripped:
                err = [f"stopped by the benchmark: free host RAM fell below {RAM_FLOOR_GIB} GiB "
                       f"(lowest {ram.min_free} GiB)"] + err
            _save("build", {"kind": "build", "mode": "cold" if cold else "warm", "run": i, "status": "failed",
                            "started_local": started, "wall_seconds": wall, "restart_seconds": restart,
                            "min_free_ram_gib_during": ram.min_free, "error": err})
            print(f"build {'cold' if cold else 'warm'} run {i}: FAILED after {wall}s: {err}")
            continue
        prov = subprocess.run([PY, "-m", "pipeline.check_provenance", schema], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=False).stdout.strip().splitlines()[-1:]
        load = json.loads((REPO_ROOT / "reports" / "load_raw.json").read_text(encoding="utf-8"))
        summary = json.loads((REPO_ROOT / "reports" / "build_summary.json").read_text(encoding="utf-8"))
        audit = audit_for([(int(s["session_id"]), int(s["stmt_id"])) for s in summary["steps"]])
        steps = [{"step": s["step"], "stmt_index": s["stmt_index"], "wall_seconds": s["wall_seconds"], "rows": s["rows"],
                  **audit.get((int(s["session_id"]), int(s["stmt_id"])), {})} for s in summary["steps"]]
        rec = {"kind": "build", "mode": "cold" if cold else "warm", "run": i, "started_local": started,
               "schema": schema, "restart_seconds": restart, "wall_seconds": wall,
               "load_seconds": round(sum(r["seconds"] for r in load), 2), "load_rows": sum(r["rows"] for r in load),
               "load_files": load, "sql_seconds": summary["sql_seconds"], "statements": len(steps),
               "clean_minutes": summary["clean_minutes"], "events": summary["events"], "provenance": prov,
               "host_before": before, "conditions": cond, "min_free_ram_gib_during": ram.min_free, "steps": steps}
        _save("build", rec)
        print(f"build {rec['mode']} run {i}: wall {wall}s (load {rec['load_seconds']}s, SQL {rec['sql_seconds']}s), "
              f"min free RAM {ram.min_free} GiB, restart {restart} s, {prov}")


def bench_queries(runs: int, cold: bool, warmup: bool = False) -> None:
    """The guided-demo path, timed in-process through the same service functions the API serves.
    With warmup: restart, run scripts/warmup.ps1's module (timed), then measure the first calls."""
    restart = restart_db() if cold else None
    warmup_seconds = None
    if warmup:
        t0 = time.perf_counter()
        subprocess.run([PY, "-m", "pipeline.warmup"], cwd=REPO_ROOT, check=True, capture_output=True, text=True)
        warmup_seconds = round(time.perf_counter() - t0, 1)
    from app.api import report, service  # after any restart, so the pool connects fresh

    demo = service.demo()
    lid, month, day, key, group = demo["location_id"], demo["month"], demo["day"], demo["event_key"], demo["group_key"]
    calls = {
        "locations (home list)": lambda: service.locations(),
        "location months": lambda: service.location(lid),
        "location-month view": lambda: service.month(lid, month),
        "day view (1,440 readings)": lambda: service.day(lid, day),
        "event evidence": lambda: service.event(key),
        "shared-event group": lambda: service.group(group),
        "evidence report (HTML + PDF)": lambda: report.generate(lid, month, pdf=True, reuse=False),
        "evidence report served again (pre-rendered, same data)": lambda: report.generate(lid, month, pdf=True),
    }
    mode = ("cold" if cold else "warm") + ("+warmup" if warmup else "")
    rec = {"kind": "queries", "mode": mode, "restart_seconds": restart, "warmup_seconds": warmup_seconds,
           "conditions": conditions(),
           "started_local": dt.datetime.now().isoformat(timespec="seconds"), "demo": demo, "timings": {}}
    for name, fn in calls.items():
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            fn()
            times.append(round(time.perf_counter() - t0, 4))
        rec["timings"][name] = times
        print(f"{name:32s} first {times[0]:.3f}s  then {', '.join(f'{t:.3f}' for t in times[1:])}")
    _save("queries", rec)


def history() -> None:
    """Earlier formulations of the three scale fixes, as recorded in the audit log (never re-run)."""
    with connect() as c:
        rows = c.execute(r"""SELECT SESSION_ID, STMT_ID, START_TIME, DURATION, SUCCESS, ERROR_CODE, TEMP_DB_RAM_PEAK,
                                    SUBSTR(REGEXP_REPLACE(SQL_TEXT, '\s+', ' '), 1, 140)
                             FROM EXA_DBA_AUDIT_SQL
                             WHERE DURATION > 120 AND COMMAND_NAME LIKE 'CREATE%'
                             ORDER BY START_TIME""").fetchall()
    rec = {"kind": "history", "recorded_local": dt.datetime.now().isoformat(timespec="seconds"),
           "statements": [{"session_id": str(r[0]), "stmt_id": int(r[1]), "start_utc": str(r[2]),
                           "db_seconds": float(r[3]), "success": bool(r[4]), "error_code": r[5],
                           "temp_ram_peak_mib": float(r[6]) if r[6] is not None else None, "sql_head": r[7]}
                          for r in rows]}
    _save("history", rec)
    for s in rec["statements"]:
        print(s)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["build", "queries", "history", "env"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--cold", action="store_true")
    ap.add_argument("--warmup", action="store_true", help="queries: run pipeline.warmup first")
    ap.add_argument("--schema", default=DEFAULT_SCHEMA)
    a = ap.parse_args(argv)
    if a.what == "env":
        rec = {"kind": "env", "recorded_local": dt.datetime.now().isoformat(timespec="seconds"), **environment(),
               "free_ram_gib": free_ram_gib(), "disk_free_gib": disk_free_gib()}
        _save("env", rec)
        print(rec)
    elif a.what == "build":
        bench_build(a.runs, a.cold, a.schema.upper())
    elif a.what == "queries":
        bench_queries(a.runs, a.cold, a.warmup)
    else:
        history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
