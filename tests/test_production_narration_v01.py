# -*- coding: utf-8 -*-
"""V0.8.4 — TTS/SRT integration tests（真实 SAPI 合成，短文本，快速）。"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.output.production_narration import ProductionNarrationAdapter, validate_srt  # noqa: E402

TEXT = ("这个两米四的伸缩岛台，岩板台面耐刮耐高温，台下大抽屉用了静音滑轨，"
        "侧面预留升降插座，吃火锅很方便。岛台底部装了感应灯，厨房显得又大又整洁。")
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"


@pytest.fixture(scope="module")
def adapter():
    return ProductionNarrationAdapter()


@pytest.fixture(scope="module")
def art(adapter):
    with tempfile.TemporaryDirectory(prefix="tts_v084_") as d:
        a = adapter.generate(TEXT, Path(d))
        # 保留产物供断言（模块级临时目录在测试内有效）
        a._tmpdir = Path(d)
        yield a


def test_production_does_not_use_silence_placeholder(art):
    # 真实文本不应产出 ~2s 静音占位
    assert art.status == "NARRATION_READY", art.error
    assert art.audio_duration > 2.0
    assert abs(art.audio_duration - 2.0) > 0.5


def test_tts_generates_decodable_audio(art):
    assert art.wav and art.wav.exists()
    dec = subprocess.run([FFMPEG, "-v", "error", "-i", str(art.wav), "-f", "null", "-"],
                         capture_output=True, timeout=120)
    assert dec.returncode == 0


def test_tts_duration_sanity(art):
    # 100+ 汉字不得 <5s
    if art.text_chars >= 100:
        assert art.audio_duration >= 5.0
    assert art.chars_per_second > 1.0


def test_srt_is_non_empty(art):
    assert art.srt and art.srt.exists()
    srt_text = art.srt.read_text(encoding="utf-8")
    assert srt_text.strip() != ""


def test_srt_timestamps_monotonic(art):
    srt_text = art.srt.read_text(encoding="utf-8")
    v = validate_srt(srt_text, art.audio_duration)
    assert not v["errors"], v["errors"]
    assert v["blocks"] >= 2


def test_srt_within_audio_duration(art):
    srt_text = art.srt.read_text(encoding="utf-8")
    v = validate_srt(srt_text, art.audio_duration)
    assert all("audio" not in e for e in v["errors"])


def test_subtitle_text_coverage(art):
    assert art.text_coverage >= 0.95, art.text_coverage


def test_tts_failure_not_false_success(adapter):
    with tempfile.TemporaryDirectory(prefix="tts_fail_") as d:
        a = adapter.generate("", Path(d))
        assert a.status in ("SUBTITLE_GENERATION_FAILED", "TTS_GENERATION_FAILED")
        assert a.status != "NARRATION_READY"
