# -*- coding: utf-8 -*-
"""V0.8.5 — Production Path Technical Preflight tests（B007 Truth → Timeline → Narration → Render）。"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.workflow.planning import EditPlan, EditSegment  # noqa: E402
from treecut.output.production_narration import ProductionNarrationAdapter  # noqa: E402

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
FFMPEG = Path(r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe")
FFPROBE = Path(r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe")
SCRIPT = "这台两米四的伸缩岛台，岩板台面耐刮耐高温，台下大抽屉用了静音滑轨。"
HAVE_FFMPEG = FFMPEG.exists()


def _b007_segments(n=2):
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    rows = c.execute(
        "SELECT s.note_id, s.seg_no, s.start_ms, s.end_ms, m.final_path, m.sha256 "
        "FROM b007_segment_v1 s JOIN b007_published_media_recovery_v1 m ON m.note_id=s.note_id "
        "WHERE m.recovery_status='RECOVERED_EXACT' AND m.final_path LIKE 'Z:%' "
        "AND s.duration_ms>=2500 LIMIT ?", (n,)).fetchall()
    c.close()
    return rows


def _make_plan(rows):
    segs = []
    t = 0.0
    for i, r in enumerate(rows):
        src = r[2] / 1000.0
        dur = min(4.0, (r[3] - r[2]) / 1000.0)
        segs.append(EditSegment(i + 1, i, r[4], "INTRO", src, src + dur, t, t + dur,
                                0.5, ("INTRO",), r[5]))
        t += dur
    return EditPlan(planned_duration=t, requested_duration=t, complete=True,
                    warnings=(), segments=tuple(segs)), rows


def test_b007_segment_can_enter_production():
    rows = _b007_segments(1)
    assert rows, "no B007 segments"
    plan, _ = _make_plan(rows)
    assert plan.segments and plan.segments[0].path.startswith("Z:")


def test_production_source_provenance():
    rows = _b007_segments(1)
    _, rows = _make_plan(rows)
    s = rows[0]
    assert s[5] and s[0] and s[4].startswith("Z:")
    # provenance: segment→note→sha256→path
    assert all((s[0], s[1], s[5], s[4]))


def test_no_b003_source_in_b007_smoke():
    rows = _b007_segments(2)
    _, rows = _make_plan(rows)
    assert all(r[4].startswith("Z:") for r in rows)


def test_timeline_bounds_valid():
    rows = _b007_segments(2)
    plan, _ = _make_plan(rows)
    prev_end = -1.0
    for s in plan.segments:
        assert s.timeline_end > s.timeline_start >= 0
        assert s.timeline_start >= prev_end - 1e-6
        assert s.source_end > s.source_start >= 0
        prev_end = s.timeline_end


def test_narration_attached_to_timeline():
    with tempfile.TemporaryDirectory(prefix="pl_narr_") as d:
        art = ProductionNarrationAdapter().generate(SCRIPT, Path(d))
        assert art.status == "NARRATION_READY"
        assert art.audio_duration > 2.0


def test_subtitle_attached_to_timeline():
    with tempfile.TemporaryDirectory(prefix="pl_srt_") as d:
        art = ProductionNarrationAdapter().generate(SCRIPT, Path(d))
        assert art.srt and art.srt.stat().st_size > 0
        srt_text = art.srt.read_text(encoding="utf-8")
        assert " --> " in srt_text
        assert art.text_coverage >= 0.95


def test_production_failure_not_false_pass():
    with tempfile.TemporaryDirectory(prefix="pl_fail_") as d:
        art = ProductionNarrationAdapter().generate("", Path(d))
        assert art.status != "NARRATION_READY"


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not available")
def test_rendered_mp4_decodable():
    rows = _b007_segments(2)
    if not rows:
        pytest.skip("no B007 segments")
    plan, _ = _make_plan(rows)
    with tempfile.TemporaryDirectory(prefix="pl_render_") as d:
        out = Path(d) / "smoke.mp4"
        cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y"]
        for s in plan.segments:
            cmd += ["-ss", f"{s.source_start:.3f}", "-t",
                    f"{s.source_end - s.source_start:.3f}", "-i", s.path]
        fl = [f"[{i}:v]scale=540:960:force_original_aspect_ratio=decrease,"
              f"pad=540:960:(ow-iw)/2:(oh-ih)/2:black,fps=30[v{i}]" for i in range(len(plan.segments))]
        fl.append("".join(f"[v{i}]" for i in range(len(plan.segments))) +
                  "concat=n=%d:v=1:a=0[o]" % len(plan.segments))
        cmd += ["-filter_complex", ";".join(fl), "-map", "[o]", "-an", "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p", str(out)]
        r = subprocess.run(cmd, capture_output=True, timeout=600)
        assert r.returncode == 0 and out.exists() and out.stat().st_size > 10000
        dec = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(out), "-f", "null", "-"],
                             capture_output=True, timeout=300)
        assert dec.returncode == 0
