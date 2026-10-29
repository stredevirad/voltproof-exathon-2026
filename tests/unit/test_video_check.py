"""`python -m pipeline.video check` judges the competition limits (3:00 at most, 40 MB at most, H.264 video with AAC
audio) and only reports the frame size: the final video is made outside the pipeline, not a merge output."""

from __future__ import annotations

import argparse
import json
import subprocess

import pytest

from pipeline import video


def _probe(monkeypatch, duration: float, size: int, width: int, audio: str | None = "aac") -> None:
    streams = [{"codec_type": "video", "codec_name": "h264", "width": width, "height": 960}]
    if audio:
        streams.append({"codec_type": "audio", "codec_name": audio})
    info = {"format": {"duration": str(duration), "size": str(size)}, "streams": streams}
    monkeypatch.setattr(video, "ff", lambda tool="ffmpeg": tool)
    monkeypatch.setattr(video.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=json.dumps(info), stderr=""))


@pytest.mark.parametrize(("duration", "size", "width", "audio", "expected"), [
    (170.783, 24_414_517, 1920, "aac", 0),    # the committed video (29 Oct: animated intro + live walkthrough)
    (134.056, 7_800_241, 1600, "aac", 0),     # the first submission's video (the team's recording)
    (134.056, 7_800_241, 1366, "aac", 0),     # a merge output
    (180.5, 7_800_241, 1600, "aac", 1),       # over 3:00
    (134.056, 41 * 2**20, 1600, "aac", 1),    # over 40 MB
    (134.056, 7_800_241, 1600, None, 1),      # no sound
])
def test_check_judges_the_competition_limits(monkeypatch, capsys, duration, size, width, audio, expected):
    _probe(monkeypatch, duration, size, width, audio)
    assert video.cmd_check(argparse.Namespace(file="demo.mp4")) == expected
    assert f"{width}x960" in capsys.readouterr().out
