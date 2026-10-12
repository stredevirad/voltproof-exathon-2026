"""Demo-video tooling (G7). Not part of the VoltProof runtime; needs the project-local ffmpeg (scripts\\get-ffmpeg.ps1).

One source of truth: docs/deliverables/video_timeline.json (segments: id, screen, hold seconds, narration text).

    python -m pipeline.video script                 # writes docs/deliverables/VOICEOVER_SCRIPT.md (+ wording checks)
    python -m pipeline.video tts [--update-holds]   # Windows System.Speech narration per segment (draft voice)
    python -m pipeline.video record                 # warm-up, then the paced e2e recording -> reports/video-run/silent_*.webm
    python -m pipeline.video merge --audio tts      # draft MP4 from the TTS pieces
    python -m pipeline.video merge --audio <file>   # the team's one-take recording, split at its pauses
    python -m pipeline.video check <mp4>            # duration, size, codecs, frame size

Each narration piece is placed at its segment's actual start in the recording (reports/video-run/timeline_actual.json).
If a piece is longer than its segment, the hold is raised and the video re-recorded; the audio is never sped up.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TIMELINE = REPO_ROOT / "docs" / "deliverables" / "video_timeline.json"
SCRIPT_MD = REPO_ROOT / "docs" / "deliverables" / "VOICEOVER_SCRIPT.md"
RUN = REPO_ROOT / "reports" / "video-run"
ACTUAL = RUN / "timeline_actual.json"
TTS_DIR = REPO_ROOT / ".cache" / "video" / "tts"
PIECES = REPO_ROOT / ".cache" / "video" / "pieces"
VOICE = "Microsoft Zira Desktop"
VOICEOVER_DIR = REPO_ROOT / "docs" / "private" / "voiceover"  # the team's recording (gitignored)
LEAD_S = 0.4          # narration starts this long after its screen appears
MAX_VIDEO_S = 180.0   # competition limit: 3:00
MAX_NARRATION_S = 170.0


def timeline() -> dict:
    return json.loads(TIMELINE.read_text(encoding="utf-8"))


def ff(tool: str = "ffmpeg") -> str:
    hits = sorted((REPO_ROOT / ".tools" / "ffmpeg").glob(f"*/bin/{tool}.exe"))
    if not hits:
        raise SystemExit("ffmpeg not found: run scripts\\get-ffmpeg.ps1")
    return str(hits[-1])


def duration(path: Path) -> float:
    out = subprocess.run([ff("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def planned_starts(tl: dict) -> dict[str, float]:
    """Actual starts from the last recording if present, otherwise cumulative holds."""
    if ACTUAL.exists():
        return json.loads(ACTUAL.read_text(encoding="utf-8"))["segments"]
    t, out = 0.0, {}
    for s in tl["segments"]:
        out[s["id"]] = t
        t += s["hold"]
    return out


def _mmss(s: float) -> str:
    return f"{int(s // 60)}:{int(round(s % 60)):02d}"


def check_wording(text: str) -> list[str]:
    from pipeline.deck import check
    return check(text)


def cmd_script(_a) -> int:
    tl = timeline()
    starts = planned_starts(tl)
    segs = tl["segments"]
    problems = check_wording("\n".join(s["text"] for s in segs))
    words = sum(len(s["text"].split()) for s in segs)
    L = ["# Voice-over script (demo video, under 2:50 of speech)", "",
         "Generated from `docs/deliverables/video_timeline.json` by `python -m pipeline.video script`; do not edit by hand.",
         "", "**How to record (one take, on a phone):**",
         "- **Pace:** read each block at a calm pace. The times show when each screen appears in the video.",
         "- **Pauses:** pause for **about 2 seconds** wherever it says *(pause)*. The pauses are where the recording is",
         f"  cut into its {len(segs)} pieces, so there must be exactly {len(segs) - 1} of them and no other long silence.",
         "- **Running long:** if a block runs long, keep going. The video is re-timed to your reading; the audio is",
         "  never sped up.",
         "- **Where to save:** any common format (m4a, mp3, wav, aac, ogg), named `voiceover.<ext>` (for example",
         "  `voiceover.m4a`), in the team's private voice-over folder (gitignored; the path is in the team's notes).",
         "", f"Speech: {words} words. At about 140 words a minute that is {_mmss(words / 140 * 60)}; the limit is 2:50.", ""]
    for i, s in enumerate(segs):
        L += [f"## {_mmss(starts.get(s['id'], 0))} — {s['screen']}", "", s["text"], ""]
        if s.get("caption"):
            L += [f"*(On screen: \"{s['caption']}\")*", ""]
        if i < len(segs) - 1:
            L += ["*(pause)*", ""]
    if problems:
        L += ["", "**Wording check failed:** " + "; ".join(problems)]
    SCRIPT_MD.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"wrote {SCRIPT_MD.relative_to(REPO_ROOT)}: {len(segs)} segments, {words} words; wording check: "
          + ("passed" if not problems else "FAILED " + "; ".join(problems)))
    return 1 if problems else 0


def _speak(text: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.SelectVoice('{VOICE}'); $s.Rate = 0; $s.SetOutputToWaveFile('{out}'); "
          "$s.Speak([Console]::In.ReadToEnd()); $s.Dispose()")
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], input=text, text=True, check=True,
                   encoding="utf-8")


def cmd_tts(a) -> int:
    tl = timeline()
    total = 0.0
    changed = False
    print(f"{'segment':10s} {'speech':>8s} {'hold':>6s}")
    for s in tl["segments"]:
        wav = TTS_DIR / f"{s['id']}.wav"
        _speak(s["text"].replace("6:27", "six twenty-seven"), wav)
        d = wav_duration(wav)
        total += d
        need = math.ceil(d + LEAD_S + 1.6)
        flag = "" if need <= s["hold"] else f"  -> needs hold {need}"
        if a.update_holds and need > s["hold"]:  # only ever raise a hold
            s["hold"], changed = need, True
        print(f"{s['id']:10s} {d:7.1f}s {s['hold']:5d}s{flag}")
    holds = sum(s["hold"] for s in tl["segments"])
    print(f"speech {total:.1f} s (limit {MAX_NARRATION_S:.0f}); holds {holds} s + page actions (limit {MAX_VIDEO_S:.0f} s)")
    if changed:
        TIMELINE.write_text(json.dumps(tl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("holds updated in video_timeline.json; re-record with: python -m pipeline.video record")
    return 0 if total <= MAX_NARRATION_S and holds <= MAX_VIDEO_S - 6 else 1


def cmd_record(_a) -> int:
    py = sys.executable
    subprocess.run([py, "-m", "pipeline.warmup"], cwd=REPO_ROOT, check=True)
    raw = RUN / "raw"
    before = set(raw.glob("*.webm")) if raw.exists() else set()
    env = dict(os.environ, VOLTPROOF_RECORD_VIDEO="1")
    tests = REPO_ROOT / "reports" / "tests"
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(REPO_ROOT / "scripts" / "test.ps1"), "-Suite", "e2e", "-Part",
                        "test_demo_flow.py::test_guided_demo_workflow"], cwd=REPO_ROOT, env=env)
    for f in tests.glob("*e2e+test_demo_flow.py__test_guided_demo_workflow*"):  # keep TEST_REPORT runs separate
        shutil.move(str(f), str(RUN / f.name))
    if r.returncode != 0:
        print("recording test failed")
        return 1
    new = sorted(set(raw.glob("*.webm")) - before, key=lambda p: p.stat().st_mtime)
    if not new:
        print("no video written")
        return 1
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    dest = RUN / f"silent_{stamp}.webm"
    shutil.move(str(new[-1]), str(dest))
    shutil.copy(ACTUAL, RUN / f"silent_{stamp}.timeline.json")
    print(f"silent take: {dest.relative_to(REPO_ROOT)} ({duration(dest):.1f} s); segment starts: "
          + json.loads(ACTUAL.read_text(encoding="utf-8"))["segments"].__repr__())
    return 0


def _voiceover_file() -> Path:
    files = [f for f in VOICEOVER_DIR.glob("voiceover.*") if f.suffix.lower() in (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".opus", ".flac")]
    if len(files) != 1:
        raise SystemExit(f"expected exactly one voiceover.<ext> in {VOICEOVER_DIR}, found {len(files)}")
    return files[0]


def _latest_silent() -> Path:
    takes = sorted(RUN.glob("silent_*.webm"), key=lambda p: p.stat().st_mtime)
    if not takes:
        raise SystemExit("no silent take: run python -m pipeline.video record")
    return takes[-1]


def _speech_spans(audio: Path, n: int) -> list[tuple[float, float]]:
    """Split a one-take recording at its pauses into exactly n spans of speech."""
    total = duration(audio)
    for noise, d in ((-35, 1.2), (-35, 1.5), (-30, 1.2), (-40, 1.2), (-35, 1.0), (-30, 1.5), (-35, 0.9)):
        err = subprocess.run([ff(), "-hide_banner", "-i", str(audio), "-af", f"silencedetect=noise={noise}dB:d={d}",
                              "-f", "null", "-"], capture_output=True, text=True).stderr
        starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
        ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
        silences = list(zip(starts, ends + [total] * (len(starts) - len(ends)), strict=True))
        spans, t = [], 0.0
        for s0, s1 in silences:
            if s0 - t > 0.3:
                spans.append((t, s0))
            t = s1
        if total - t > 0.3:
            spans.append((t, total))
        if len(spans) == n:
            return spans
    raise SystemExit(f"could not split the recording into {n} pieces at its pauses (found {len(spans)} with the "
                     f"last setting). Keep exactly {n - 1} pauses of about 2 seconds and no other long silence.")


def cmd_merge(a) -> int:
    tl = timeline()
    segs = tl["segments"]
    video = Path(a.video) if a.video else _latest_silent()
    marks_file = video.with_name(video.stem + ".timeline.json")
    marks = json.loads((marks_file if marks_file.exists() else ACTUAL).read_text(encoding="utf-8"))["segments"]
    PIECES.mkdir(parents=True, exist_ok=True)
    if a.audio == "tts":
        pieces = [TTS_DIR / f"{s['id']}.wav" for s in segs]
        missing = [p for p in pieces if not p.exists()]
        if missing:
            raise SystemExit("TTS pieces missing: run python -m pipeline.video tts")
    else:
        audio = _voiceover_file() if a.audio == "voice" else Path(a.audio)
        print(f"narration: {audio.relative_to(REPO_ROOT) if audio.is_relative_to(REPO_ROOT) else audio}")
        spans = _speech_spans(audio, len(segs))
        pieces = []
        for s, (t0, t1) in zip(segs, spans, strict=True):
            out = PIECES / f"{s['id']}.wav"
            subprocess.run([ff(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
                            "-i", str(audio), "-ac", "1", "-ar", "48000", str(out)], check=True)
            pieces.append(out)
    # fit check: each piece must end before the next segment starts
    ids = [s["id"] for s in segs]
    vdur = duration(video)
    overflow = []
    for i, (s, p) in enumerate(zip(segs, pieces, strict=True)):
        start = marks[s["id"]] + LEAD_S
        end_limit = (marks[ids[i + 1]] if i + 1 < len(ids) else vdur) - 0.3
        d = duration(p)
        if start + d > end_limit:
            overflow.append((s["id"], d, math.ceil(d + LEAD_S + 1.6)))
    if overflow:
        print("narration longer than its screen; raise these holds in video_timeline.json and re-record "
              "(python -m pipeline.video record):")
        for sid, d, need in overflow:
            print(f"  {sid}: speech {d:.1f} s -> hold {need}")
        if a.update_holds:
            for s in segs:
                for sid, _, need in overflow:
                    if s["id"] == sid:
                        s["hold"] = max(s["hold"], need)
            TIMELINE.write_text(json.dumps(tl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            print("holds updated")
        return 2
    out = Path(a.out) if a.out else RUN / ("VoltProof_demo_DRAFT_tts.mp4" if a.audio == "tts" else "VoltProof_demo_voice.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    inputs = ["-i", str(video)]
    filters = []
    for i, (s, p) in enumerate(zip(segs, pieces, strict=True), start=1):
        inputs += ["-i", str(p)]
        ms = int((marks[s["id"]] + LEAD_S) * 1000)
        filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(1, len(pieces) + 1))
    filters.append(f"{mix}amix=inputs={len(pieces)}:normalize=0,apad[aout]")
    subprocess.run([ff(), "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
                    "-map", "0:v", "-map", "[aout]", "-c:v", "libx264", "-preset", "slow", "-crf", "26",
                    "-pix_fmt", "yuv420p", "-vf", "scale=1366:860", "-c:a", "aac", "-b:a", "128k", "-ac", "1",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    return cmd_check(argparse.Namespace(file=str(out)))


def cmd_check(a) -> int:
    f = Path(a.file)
    info = json.loads(subprocess.run([ff("ffprobe"), "-v", "error", "-show_entries",
                                      "format=duration,size:stream=codec_name,codec_type,width,height", "-of", "json",
                                      str(f)], capture_output=True, text=True, check=True).stdout)
    dur = float(info["format"]["duration"])
    size_mb = int(info["format"]["size"]) / 2**20
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    au = [s for s in info["streams"] if s["codec_type"] == "audio"]
    ok = dur <= MAX_VIDEO_S and v["codec_name"] == "h264" and au and au[0]["codec_name"] == "aac" \
        and (v["width"], v["height"]) == (1366, 860)
    print(f"{f.name}: {_mmss(dur)} ({dur:.1f} s), {size_mb:.1f} MB, {v['codec_name']} {v['width']}x{v['height']}, "
          f"audio {au[0]['codec_name'] if au else 'none'} -> {'OK' if ok else 'NOT OK'}"
          f"{'' if size_mb <= 25 else ' (over the preferred 25 MB)'}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("script")
    t = sub.add_parser("tts")
    t.add_argument("--update-holds", action="store_true")
    sub.add_parser("record")
    m = sub.add_parser("merge")
    m.add_argument("--audio", required=True,
                   help="'tts', 'voice' (voiceover.<ext> in the private voice-over folder) or the path of a recording")
    m.add_argument("--video", help="silent take (default: the latest reports/video-run/silent_*.webm)")
    m.add_argument("--out", help="default: reports/video-run/VoltProof_demo_DRAFT_tts.mp4 (tts) or "
                   "reports/video-run/VoltProof_demo_voice.mp4 (recording); the final file is committed separately")
    m.add_argument("--update-holds", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("file")
    a = ap.parse_args(argv)
    return {"script": cmd_script, "tts": cmd_tts, "record": cmd_record, "merge": cmd_merge, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
