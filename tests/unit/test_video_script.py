"""The voice-over script generator (pipeline/video.py): screen times come from the last recording only when that
recording has every segment of the current timeline, and the committed script lists its screens in time order."""

from __future__ import annotations

import json
import re

from pipeline import video


def _timeline() -> dict:
    return {"segments": [{"id": "a", "hold": 10}, {"id": "b", "hold": 20}, {"id": "c", "hold": 5}]}


def test_a_recording_with_every_segment_gives_the_screen_times(tmp_path, monkeypatch):
    actual = tmp_path / "timeline_actual.json"
    actual.write_text(json.dumps({"segments": {"a": 0.9, "b": 11.2, "c": 31.5}}), encoding="utf-8")
    monkeypatch.setattr(video, "ACTUAL", actual)
    assert video.planned_starts(_timeline()) == {"a": 0.9, "b": 11.2, "c": 31.5}


def test_an_older_recording_without_a_new_segment_is_not_used(tmp_path, monkeypatch):
    actual = tmp_path / "timeline_actual.json"
    actual.write_text(json.dumps({"segments": {"a": 0.9, "c": 12.0}}), encoding="utf-8")
    monkeypatch.setattr(video, "ACTUAL", actual)
    assert video.planned_starts(_timeline()) == {"a": 0.0, "b": 10.0, "c": 30.0}
    monkeypatch.setattr(video, "ACTUAL", tmp_path / "no_recording_yet.json")
    assert video.planned_starts(_timeline()) == {"a": 0.0, "b": 10.0, "c": 30.0}


def test_the_committed_script_lists_every_screen_in_time_order():
    text = video.SCRIPT_MD.read_text(encoding="utf-8")
    times = [int(m) * 60 + int(s) for m, s in re.findall(r"^## (\d+):(\d\d) — ", text, flags=re.M)]
    assert len(times) == len(video.timeline()["segments"])
    assert times == sorted(times) and len(set(times)) == len(times), times
