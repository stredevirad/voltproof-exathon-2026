"""The SYNTHETIC demo set (D-033): it builds into its own schema, holds nothing real, the guided demo lands on
the designed shared interruption, reports are labelled, and the SQL equals the independent oracle on the
whole set (events, daily and monthly aggregates, coincidence).

Builds into VP_DEMO_TEST (not VOLTPROOF_DEMO), so the quick-start schema is left alone.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from pipeline import build, synthetic
from pipeline.db import connect, schema_dataset
from tests.oracle.reference import run
from tests.support.claims import forbidden_hits
from tests.support.compare import (
    diff,
    diff_coincidence,
    fetch_coincidence,
    fetch_sql,
    oracle_as_comparable,
    oracle_coincidence,
    params_from_yaml,
)
from tests.support.rawfiles import name_matcher, read_rows

pytestmark = pytest.mark.exasol
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "VP_DEMO_TEST"
# Distinctive values of the real-data build; none may appear in anything built from synthetic data
REAL_TOKENS = ["102,845,781", "10,28,45,781", "408,223", "4,08,223", "3,945", "1,827.5", "21,970", "366.2",
               "Bahraich", "Huzurpur", "Lucknow", "Prayas, Energy Group, 2019"]
SHARED_GROUP = f"{synthetic.SHARED_DISTRICT} | {synthetic.YEAR}-{synthetic.MONTH:02d}-{synthetic.SHARED_DAY:02d} " \
               f"{synthetic.SHARED_START[0]:02d}:{synthetic.SHARED_START[1]:02d}"


@pytest.fixture(scope="module")
def built():
    assert build.main(["--schema", SCHEMA, "--demo"]) == 0
    return SCHEMA


def _in_schema(code: str) -> dict:
    """Run app code against the demo test schema in a fresh process (the app reads its schema at import)."""
    env = dict(os.environ, VOLTPROOF_SCHEMA=SCHEMA, PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True,
                         check=True).stdout
    return json.loads(out.strip().splitlines()[-1])


def test_demo_schema_holds_only_synthetic_data(built):
    with connect() as c:
        info = schema_dataset(c, built)
        names = [r[0] for r in c.execute(f"SELECT SOURCE_NAME FROM {built}.LOCATION").fetchall()]
        districts = {r[0] for r in c.execute(f"SELECT DISTINCT DISTRICT FROM {built}.LOCATION").fetchall()}
    assert info["synthetic"] and info["real_files"] == 0 and info["synthetic_files"] == 2
    assert names and all(n.startswith("SYNTHETIC ") for n in names)
    assert all("(SYNTHETIC)" in d for d in districts)


def test_building_demo_data_into_the_real_schema_is_refused():
    with pytest.raises(SystemExit, match="never goes into"):
        build.main(["--schema", "VOLTPROOF", "--demo", "--skip-load"])


def test_guided_demo_lands_on_the_designed_shared_interruption(built):
    d = _in_schema("import json; from app.api import service as s; print(json.dumps(s.demo()))")
    assert d["group_key"] == SHARED_GROUP
    assert d["synthetic"] is True and "January 2030" in d["rule"]
    g = _in_schema(f"import json; from app.api import service as s; print(json.dumps(s.group({d['group_key']!r}), default=str))")
    assert g["n_locations"] == len(synthetic.DISTRICTS[synthetic.SHARED_DISTRICT])


def test_demo_report_is_labelled_synthetic_and_quotes_no_real_figure(built):
    code = ("import json; from app.api import report, service as s; d = s.demo(); "
            "o = report.generate(d['location_id'], d['month'], pdf=False, reuse=False); "
            "print(json.dumps({'id': o['report_id'], 'html': str(report.path_for(o['report_id'], 'html')), "
            "'json': str(report.path_for(o['report_id'], 'json'))}))")
    r = _in_schema(code)
    assert r["id"].startswith("VP-DEMO-")
    side = json.loads(Path(r["json"]).read_text(encoding="utf-8"))
    html = Path(r["html"]).read_text(encoding="utf-8")
    assert side["synthetic"] is True and 'data-testid="synthetic-banner"' in html
    assert "SYNTHETIC" in side["provenance"]["attribution"]
    assert any("SYNTHETIC" in x for x in side["method"]["limitations"])
    assert not forbidden_hits(html)
    assert not [t for t in REAL_TOKENS if t in html]


def test_sql_equals_oracle_on_the_whole_synthetic_set(built):
    manifest = json.loads((synthetic.OUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    readings = [f for f in manifest["files"] if f["kind"] == "readings"]
    with connect() as c:
        all_names = dict(c.execute(f"SELECT SOURCE_NAME, DISTRICT FROM {built}.LOCATION").fetchall())
        sql = fetch_sql(c, built, sorted(all_names))
        sql_co = fetch_coincidence(c, built, sorted(set(all_names.values())))
    rows = []
    for f in readings:
        rows += read_rows(synthetic.OUT_DIR / f["file"], set(all_names), f["declared"], matcher=name_matcher(set(all_names)))
    # the demo overrides (config/method.demo.yaml) change scope and labels only, never a threshold
    ref = oracle_as_comparable(run(rows, params_from_yaml(), "%d-%m-%Y"))
    problems = diff(sql, ref)
    assert len(ref["events"]) > 1000
    assert not problems, "\n".join(problems[:40])
    co = yaml.safe_load((REPO_ROOT / "config" / "method.yaml").read_text(encoding="utf-8"))["coincidence"]
    comparable = {k for k, v in ref["monthly"].items() if v["comparable"]}
    ref_co = oracle_coincidence(ref["events"], all_names, co["max_start_offset_minutes"], co["min_overlap_minutes"],
                                co["baseline_shifts"], comparable=comparable,
                                comparable_only=bool(co["baseline_comparable_only"]))
    problems = diff_coincidence(sql_co, ref_co)
    assert ref_co["pairs"], "the synthetic set must contain coincident pairs"
    assert not problems, "\n".join(problems[:40])
