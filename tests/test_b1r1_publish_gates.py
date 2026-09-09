# -*- coding: utf-8 -*-
"""B1R1 — publish-gate unit tests: script completeness & audible-end logic."""
from treecut.quality.publish_gates import (
    SCRIPT_TRUNCATED, SCRIPT_NO_TERMINAL_PUNCTUATION, AUDIBLE_END_TOO_CLOSE,
    check_script_completeness, check_audible_end, last_sentence,
)


def test_old_139_counterexample_truncated():
    # the B1 success narration ended mid-sentence "台面宽度可以按户"
    text = ("小户型也能拥有实用岛台。平时收起来不占过道，需要时轻轻拉出，"
            "立刻多出一张工作台。台面宽度可以按户")
    g = check_script_completeness(text)
    assert g.passed is False
    assert g.code == SCRIPT_TRUNCATED


def test_no_terminal_punctuation_fails():
    g = check_script_completeness("小户型也能拥有实用岛台")
    assert g.passed is False
    assert g.code == SCRIPT_NO_TERMINAL_PUNCTUATION


def test_complete_script_passes():
    g = check_script_completeness("小户型也能拥有实用岛台。拉开就是工作台，收起来不占地方。")
    assert g.passed is True and g.code is None
    assert g.fields["last_char"] == "。"
    assert g.fields["last_sentence"].endswith("。")


def test_last_sentence_extraction():
    text = "第一句。第二句更完整，包含细节。最后一句结束。"
    assert last_sentence(text) == "最后一句结束。"


def test_audible_end_pass_and_too_close():
    ok = check_audible_end(last_voice_s=24.6, video_duration_s=25.0,
                           narration_duration_s=24.8)
    assert ok.passed is True
    assert ok.fields["audible_tail_gap"] == 0.4
    bad = check_audible_end(last_voice_s=24.95, video_duration_s=25.0,
                            narration_duration_s=24.99)
    assert bad.passed is False and bad.code == AUDIBLE_END_TOO_CLOSE


def test_audible_end_outro_override():
    g = check_audible_end(last_voice_s=24.95, video_duration_s=25.0,
                          narration_duration_s=24.99, intentional_outro=True)
    assert g.passed is True
