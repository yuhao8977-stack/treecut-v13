# -*- coding: utf-8 -*-
"""B1 — narration duration contract unit tests (fail-closed)."""
import pytest

from treecut.quality.duration_contract import (
    FIT_SCRIPT_TO_TARGET, FIT_VIDEO_TO_NARRATION, STRICT_REJECT,
    NARRATION_TOO_SHORT, NARRATION_TOO_LONG, VOICE_COVERAGE_LOW,
    VOICE_TAIL_TOO_LONG, BGM_ONLY_AUDIO, resolve_plan_duration,
    check_duration_contract,
)
from treecut.application import CreativeRequest


def test_resolve_plan_strict_is_target():
    assert resolve_plan_duration(STRICT_REJECT, 25.0, 11.633) == 25.0


def test_resolve_plan_fit_video_is_narration():
    assert resolve_plan_duration(FIT_VIDEO_TO_NARRATION, 25.0, 11.633) == 11.633


def test_resolve_plan_fit_script_not_implemented():
    with pytest.raises(NotImplementedError):
        resolve_plan_duration(FIT_SCRIPT_TO_TARGET, 25.0, 11.633)


def test_short_narration_25_target_rejected():
    c = check_duration_contract(strategy=STRICT_REJECT, target_duration=25.0,
                                narration_duration=11.633, video_duration=25.0)
    assert c.passed is False and c.code == NARRATION_TOO_SHORT


def test_sufficient_narration_passes():
    c = check_duration_contract(strategy=STRICT_REJECT, target_duration=25.0,
                                narration_duration=24.6, video_duration=25.0)
    assert c.passed is True and c.code is None
    f = c.fields
    assert f["narration_coverage"] >= 0.95
    assert f["narration_tail_gap"] <= 0.8
    assert f["duration_contract_pass"] is True


def test_narration_longer_than_video_rejected():
    c = check_duration_contract(strategy=STRICT_REJECT, target_duration=25.0,
                                narration_duration=25.4, video_duration=25.0)
    assert c.passed is False and c.code == NARRATION_TOO_LONG


def test_coverage_low():
    c = check_duration_contract(strategy=FIT_VIDEO_TO_NARRATION,
                                target_duration=25.0, narration_duration=24.0,
                                video_duration=25.5)
    assert c.passed is False and c.code == VOICE_COVERAGE_LOW


def test_tail_too_long_and_outro_override():
    c = check_duration_contract(strategy=STRICT_REJECT, target_duration=25.0,
                                narration_duration=24.4, video_duration=25.5)
    assert c.passed is False and c.code == VOICE_TAIL_TOO_LONG
    c2 = check_duration_contract(strategy=STRICT_REJECT, target_duration=25.0,
                                 narration_duration=24.4, video_duration=25.5,
                                 intentional_outro=True)
    assert c2.passed is True


def test_no_narration_is_bgm_only():
    c = check_duration_contract(strategy=STRICT_REJECT, target_duration=25.0,
                                narration_duration=0.0, video_duration=25.0)
    assert c.passed is False and c.code == BGM_ONLY_AUDIO


def test_fields_present():
    c = check_duration_contract(strategy=STRICT_REJECT, target_duration=25.0,
                                narration_duration=24.6, video_duration=25.0)
    for key in ("narration_duration", "video_duration", "narration_coverage",
                "narration_tail_gap", "intentional_outro", "duration_contract_pass"):
        assert key in c.fields


def test_request_validate_strategy():
    with pytest.raises(ValueError):
        CreativeRequest(selling_points="x", narration="y",
                        duration_strategy="bad").validate()
    CreativeRequest(selling_points="x", narration="y").validate()  # default strict ok
