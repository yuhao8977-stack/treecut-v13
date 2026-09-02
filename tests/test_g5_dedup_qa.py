# -*- coding: utf-8 -*-
"""Dedup + G5 QA 测试: 级别/叙事近重/V2 回归/P0 门禁/V1/V2 负样本回归。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.production_dedup import (Shot, detect_duplicates, extract_presenter_from_case,
                                               narrative_score)
from treecut.services.production_qa import (check_av_sync, check_video_tail, check_caption_rendered,
                                            check_caption_size, check_source_eligibility,
                                            check_no_old_subtitle, check_no_watermark,
                                            check_claim_supported, check_action_demonstrated,
                                            check_beat_visual_alignment, check_dedup, verdict,
                                            check_voice_provider, check_bgm, check_loudness,
                                            check_story_consistent)


def test_exact_segment_duplicate_detected():
    a = Shot(media_id=1, subclip_start_s=2.0, subclip_end_s=4.0)
    b = Shot(media_id=1, subclip_start_s=2.0, subclip_end_s=4.0)
    hits = detect_duplicates([a, b])
    assert hits[0]["level"] == "EXACT_SEGMENT_DUPLICATE" and hits[0]["strength"] == "HIGH"


def test_same_asset_other_window_flagged():
    a = Shot(media_id=2, subclip_start_s=1.0, subclip_end_s=3.0)
    b = Shot(media_id=2, subclip_start_s=5.0, subclip_end_s=7.0)
    hits = detect_duplicates([a, b])
    assert hits[0]["level"] == "SAME_ASSET_NEAR_DUPLICATE"


def test_narrative_near_duplicate_v2_ending():
    # V2 风格: 同演示者/同功能文件夹/同 shot_role 的两个展示镜头(画面不同案例提示不同则分数低→需案例一致)
    a = Shot(media_id=10, folder_hint="【01】上层薄抽", case_id="【62】广州赖小姐",
             shot_role="feature", subclip_start_s=5.0, subclip_end_s=8.0)
    b = Shot(media_id=11, folder_hint="【01】上层薄抽", case_id="【62】广州赖小姐",
             shot_role="cta", subclip_start_s=18.0, subclip_end_s=20.7)
    hits = detect_duplicates([a, b])
    assert any(h["level"] == "NARRATIVE_NEAR_DUPLICATE" for h in hits)


def test_socket_vs_extend_no_dup():
    a = Shot(media_id=20, folder_hint="【21】伸缩功能", case_id="【21】北京陶先生", shot_role="feature")
    b = Shot(media_id=21, folder_hint="【05】公牛轨道插座", case_id="【20】河南王小姐", shot_role="feature")
    assert detect_duplicates([a, b]) == []


def test_presenter_extraction():
    assert extract_presenter_from_case("【62】广州赖小姐") == "赖小姐"
    assert extract_presenter_from_case(None) is None


def test_p0_av_mismatch_blocks_ready():
    res = [check_av_sync(22.67, 27.35)]  # V1 真实差 4.68s
    v = verdict(res)
    assert v["READY_FOR_HUMAN_REVIEW"] is False
    assert "AV_DURATION_MISMATCH" in v["P0_BLOCKERS"]


def test_v1_negative_regression():
    # V1: 脏源+无字幕+短视频+错配
    results = [check_source_eligibility(False, "PUBLISHED_REFERENCE"),
               check_no_old_subtitle("PRESENT"),
               check_no_watermark("PRESENT"),
               check_caption_rendered(False),
               check_video_tail(22.67, 27.35),
               check_beat_visual_alignment(False)]
    v = verdict(results)
    assert v["READY_FOR_HUMAN_REVIEW"] is False


def test_v2_negative_regression():
    # V2: 字幕太小(55)+无BGM+SAPI+伸缩口播配插座(语义FAIL)+重复结尾
    results = [check_caption_size(55),
               check_bgm(False, required=True),
               check_voice_provider("SAPI", production_ready=False),
               check_beat_visual_alignment(False),     # 伸缩口播→插座 错配
               check_action_demonstrated("FUNCTION_VISIBLE", "EXTEND"),  # 未演示动作
               check_story_consistent(True),
               check_dedup([{"pair": (0, 1), "level": "NARRATIVE_NEAR_DUPLICATE", "strength": "HIGH"}])]
    v = verdict(results)
    assert v["READY_FOR_HUMAN_REVIEW"] is False  # MAJOR_DUPLICATE + WRONG + ACTION FAIL
    keys = [r.key for r in results]
    assert "CAPTION_READABLE" in keys  # V2 债务 CAPTION_TOO_SMALL 被编码


def test_clean_project_passes():
    results = [check_av_sync(22.7, 22.65), check_video_tail(22.7, 22.65),
               check_caption_rendered(True), check_caption_size(66),
               check_source_eligibility(True, "PRODUCTION_CLEAN_SEMI"),
               check_no_old_subtitle("ABSENT"), check_no_watermark("ABSENT"),
               check_claim_supported(True, "C1"), check_beat_visual_alignment(True),
               check_action_demonstrated("ACTION_DEMONSTRATION_COMPLETE", "EXTEND"),
               check_dedup([]), check_loudness(-15.0, -3.4),
               check_bgm(True), check_voice_provider("voice-clone", True),
               check_story_consistent(True)]
    v = verdict(results)
    assert v["READY_FOR_HUMAN_REVIEW"] is True


def test_caption_too_small_warning_not_p0():
    r = check_caption_size(55)
    assert r.status == "WARNING"
    v = verdict([r])
    assert v["READY_FOR_HUMAN_REVIEW"] is True  # 不作为 P0 阻塞, 但记录债务
