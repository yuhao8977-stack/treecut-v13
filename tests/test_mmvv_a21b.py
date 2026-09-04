# -*- coding: utf-8 -*-
"""MMVV A2.1b — 鲁棒静态几何/JITTER 分离 + 相机可靠性真实来源（无媒体硬编码）测试。"""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    Action, FrameSemantics, MotionMetrics, TemporalEvidence, ROI,
    TemporalStateValidator, TargetObjectMotionRouter,
    build_geometry_direction_evidence, camera_reliability_evidence)

RUNNER = Path(__file__).resolve().parents[1] / "scripts" / "mmv_a21_run.py"
ISLAND = [100, 900, 700, 1400]


def tl(seq):
    return [{"t_s": float(i), "bbox_pixel": list(bb), "island_pixel": list(ISLAND)}
            for i, bb in enumerate(seq)]


def boxes_of_area(areas, base=(100, 100)):
    # 由目标面积反推 bbox（宽固定 200，变高）
    out = []
    for a in areas:
        h = a // 200
        out.append([base[0], base[1], base[0] + 200, base[1] + h])
    return out


def _val(action, geo, motion=0.5, obj="DRAWER"):
    def sem():
        return FrameSemantics(0.0, [obj], [], [ROI(obj, 0, 0, 10, 10, source="L3_HUMAN_ROI")])
    mm = MotionMetrics(roi_motion={obj: motion})
    ev = TemporalEvidence(before=sem(), middle=sem(), after=sem(), motion=mm,
                          requested_action=action, geometry_direction_evidence=geo)
    return TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)


def test_small_nonmonotonic_jitter_is_static():
    # 有界振荡：交替±10%面积、净变化小 → STATIC_WITH_ANNOTATION_JITTER
    areas = [40000, 36000, 44000, 37000, 42000]
    g = build_geometry_direction_evidence("DRAWER", "A", tl(boxes_of_area(areas)))
    assert g.direction_action == "STATIC"
    assert g.state_progress == "STATIC_WITH_ANNOTATION_JITTER"
    assert g.raw_features["robust"]["reversal_count"] >= 2


def test_large_monotonic_growth_is_action():
    areas = [20000, 40000, 80000]
    g = build_geometry_direction_evidence("DRAWER", "A", tl(boxes_of_area(areas)))
    assert g.direction_action == "DRAWER_OPEN" and g.state_progress == "PROGRESSION_UP"


def test_positive_drawer_regression_preserved():
    # 52 正例序列（A2.1 已 PASS）不得被鲁棒判定压成 STATIC
    areas = [17496, 18774, 31313]
    g = build_geometry_direction_evidence("DRAWER", "A", tl(boxes_of_area(areas)))
    assert g.direction_action == "DRAWER_OPEN" and g.state_progress == "PROGRESSION_UP"
    assert _val(Action.DRAWER_OPEN, g).verdict.value == "PASS"


def test_alternating_bbox_noise_not_progression():
    # 正负交替（大→小→大→回）不是 progression
    areas = [50000, 45000, 52000, 43000, 51000]
    g = build_geometry_direction_evidence("DRAWER", "A", tl(boxes_of_area(areas)))
    assert g.direction_action == "STATIC"
    assert g.raw_features["robust"]["direction_consistency"] == "LOW"


def test_net_change_small_but_pair_noise_large_is_static():
    # 单步噪声大(>6%)但首尾净变化小 → 仍静态(JITTER)，不是 UNKNOWN
    areas = [40000, 47000, 33000, 45000, 41000]
    g = build_geometry_direction_evidence("TABLETOP", "A", tl(boxes_of_area(areas)))
    assert g.state_progress in ("STATIC_STABLE", "STATIC_WITH_ANNOTATION_JITTER")
    assert g.direction_action == "STATIC"


def test_camera_reliability_not_media_id_hardcoded():
    good = [{"reliable": True, "inlier_ratio": 0.6, "feature_residual": 0.5, "translation_px": 3.0}]
    bad = [{"reliable": False, "inlier_ratio": 0.1, "feature_residual": 25.0, "translation_px": 40.0}]
    assert camera_reliability_evidence(good).camera_state == "RELIABLE"
    assert camera_reliability_evidence(bad).camera_state == "UNRELIABLE"
    assert camera_reliability_evidence([]).camera_state == "INSUFFICIENT"
    txt = RUNNER.read_text(encoding="utf-8")
    assert "mid in (" not in txt, "runner 不得按 media_id 硬编码相机不可靠"
    assert "(1985, 1986)" not in txt


def test_camera_unreliable_can_stay_unsure():
    g = build_geometry_direction_evidence("TABLETOP", "A", tl(boxes_of_area([100000] * 3)),
                                          camera_unreliable=True)
    v = _val(Action.EXTEND, g, obj="TABLETOP")
    assert v.verdict.value == "UNSURE"
    assert any("CAMERA_UNRELIABLE" in c for c in v.reason_codes)


def test_same_classifier_all_media():
    # 同一算法处理全部：builder 无 media 参数；runner 无 89/51/1985 特例分支
    sig = inspect.signature(build_geometry_direction_evidence)
    assert "media" not in sig.parameters and "mid" not in sig.parameters
    txt = RUNNER.read_text(encoding="utf-8")
    assert "if mid" not in txt and "media_id ==" not in txt.split("SLICES")[1]


def test_no_gt_used_in_machine_features():
    sig = inspect.signature(build_geometry_direction_evidence)
    for p in sig.parameters:
        assert "gt" not in p and "human" not in p and "truth" not in p
    sig2 = inspect.signature(camera_reliability_evidence)
    for p in sig2.parameters:
        assert "gt" not in p and "human" not in p
