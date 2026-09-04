# -*- coding: utf-8 -*-
"""MMVV A2.1 — 目标身份 + 几何方向/状态通道测试（无真实媒体，合成几何）。

覆盖（架构师 §17）：multiple_same_label_not_hits0 / target_instance_binding_deterministic /
relative_geometry_to_island_body / static_geometry_not_action / drawer_partial_to_open_supported /
drawer_open_state_static_rejected / geometry_direction_reaches_validator /
model_action_not_reused_for_geometry / camera_unreliable_can_remain_unsure
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    Action, FrameSemantics, MotionMetrics, TemporalEvidence, ROI, Verdict,
    TemporalStateValidator, TargetObjectMotionRouter,
    build_geometry_direction_evidence, bind_target_timeline)

ISLAND = [100, 900, 700, 1400]  # 常量岛台（参考系）


def _tl(seq, island=True):
    """seq: list of [x1,y1,x2,y2] per frame t=0..n-1（同实例）."""
    out = []
    for i, bb in enumerate(seq):
        out.append({"t_s": float(i), "bbox_pixel": list(bb),
                    "island_pixel": list(ISLAND) if island else None})
    return out


def _ev(requested, roi_motion, geo, model_action=Action.UNKNOWN, obj="DRAWER"):
    before = FrameSemantics(0.0, [obj], [], [ROI(obj, 0, 0, 10, 10, source="L3_HUMAN_ROI")])
    middle = FrameSemantics(1.0, [obj], [], [ROI(obj, 0, 0, 10, 10, source="L3_HUMAN_ROI")])
    after = FrameSemantics(2.0, [obj], [], [ROI(obj, 0, 0, 10, 10, source="L3_HUMAN_ROI")])
    mm = MotionMetrics(roi_motion=roi_motion)
    return TemporalEvidence(before=before, middle=middle, after=after, motion=mm,
                            requested_action=requested, model_action=model_action,
                            geometry_direction_evidence=geo)


def _val(ev):
    return TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)


# 1) 同标签多框：绑定后不得串线（hits[0] 病态）
def test_multiple_same_label_not_hits0():
    # 每帧两个抽屉：左抽屉静止(100..300)，右抽屉静止(500..700)；交叉绑定应稳定
    left = [[100, 100, 300, 300]] * 3
    boxes_by_t = {0.0: [{"object_name": "DRAWER", "bbox_pixel": left[0]},
                        {"object_name": "DRAWER", "bbox_pixel": [500, 100, 700, 300]}],
                  1.0: [{"object_name": "DRAWER", "bbox_pixel": [500, 100, 700, 300]},
                        {"object_name": "DRAWER", "bbox_pixel": left[1]}],  # 顺序翻转（诱骗 hits[0]）
                  2.0: [{"object_name": "DRAWER", "bbox_pixel": left[2]},
                        {"object_name": "DRAWER", "bbox_pixel": [500, 100, 700, 300]}]}
    binding = {0.0: 0, 1.0: 1, 2.0: 0}  # 人工绑定：追踪左抽屉
    tl = bind_target_timeline(boxes_by_t, binding)
    assert len(tl) == 3
    # 绑定后追踪的是左抽屉：所有 box 一致(不串线)
    g = build_geometry_direction_evidence("DRAWER", "A", tl)
    assert g.direction_action == "STATIC", g.direction_action
    assert g.raw_features["abs_per_frame"][0]["cx"] == g.raw_features["abs_per_frame"][2]["cx"]  # 稳定


def test_target_instance_binding_deterministic():
    boxes_by_t = {0.0: [{"object_name": "DRAWER", "bbox_pixel": [100, 100, 300, 300]},
                        {"object_name": "DRAWER", "bbox_pixel": [500, 100, 700, 300]}],
                  1.0: [{"object_name": "DRAWER", "bbox_pixel": [100, 100, 300, 300]},
                        {"object_name": "DRAWER", "bbox_pixel": [500, 100, 700, 300]}]}
    b1 = bind_target_timeline(boxes_by_t, {0.0: 1, 1.0: 1})
    b2 = bind_target_timeline(boxes_by_t, {0.0: 1, 1.0: 1})
    assert [x["bbox_pixel"] for x in b1] == [x["bbox_pixel"] for x in b2]
    # None = 跳过该帧
    b3 = bind_target_timeline(boxes_by_t, {0.0: 1, 1.0: None})
    assert [x["t_s"] for x in b3] == [0.0]


def test_relative_geometry_to_island_body():
    # 同一物理抽屉，岛台宽度变化(模拟缩放)不应改变"静止"判定
    g1 = build_geometry_direction_evidence("DRAWER", "A", _tl([[100, 100, 300, 300]] * 3))
    g2 = build_geometry_direction_evidence("DRAWER", "A",
                                           [{"t_s": float(i), "bbox_pixel": [100, 100, 300, 300],
                                             "island_pixel": [100, 900, 1400, 1400]} for i in range(3)])
    assert g1.direction_action == "STATIC" and g2.direction_action == "STATIC"
    assert g1.raw_features["rel_per_frame"][0].get("area_ratio") is not None  # 相对特征已算


def test_static_geometry_not_action():
    # 桌板几何稳定 + pixel 声称在动 → FAIL NO_TARGET_GEOMETRY_CHANGE（几何优先于 pixel）
    g = build_geometry_direction_evidence("TABLETOP", "A",
                                          _tl([[200, 400, 900, 700], [201, 400, 901, 700], [200, 401, 900, 701]]))
    assert g.direction_action == "STATIC"
    v = _val(_ev(Action.EXTEND, {"TABLETOP": 0.6}, g, obj="TABLETOP"))
    assert v.verdict == Verdict.FAIL and "NO_TARGET_GEOMETRY_CHANGE" in v.reason_codes


def test_drawer_partial_to_open_supported():
    # 抽屉面积单调增长（PARTIAL→FULL，允许非 CLOSED→OPEN）+ motion → PASS
    g = build_geometry_direction_evidence("DRAWER", "A",
                                          _tl([[100, 100, 200, 220], [100, 100, 260, 320], [100, 100, 340, 460]]))
    assert g.direction_action == "DRAWER_OPEN"
    assert g.state_progress == "PROGRESSION_UP"
    v = _val(_ev(Action.DRAWER_OPEN, {"DRAWER": 1.0}, g))
    assert v.verdict == Verdict.PASS and "GEOMETRY_PROGRESSION_SUPPORTED" in v.reason_codes


def test_drawer_open_state_static_rejected():
    # 抽屉开着但静止（几何稳定）+ pixel 噪声 → FAIL OPEN_STATE_NOT_OPEN_ACTION
    g = build_geometry_direction_evidence("DRAWER", "A",
                                          _tl([[100, 100, 340, 460], [101, 100, 341, 460], [100, 101, 340, 461]]))
    assert g.direction_action == "STATIC"
    v = _val(_ev(Action.DRAWER_OPEN, {"DRAWER": 0.3}, g))
    assert v.verdict == Verdict.FAIL
    assert "NO_GEOMETRY_PROGRESSION" in v.reason_codes and "OPEN_STATE_NOT_OPEN_ACTION" in v.reason_codes


def test_geometry_direction_reaches_validator():
    # geometry_direction_evidence 真实进入 TemporalEvidence 并被 validator 使用
    g = build_geometry_direction_evidence("DRAWER", "A",
                                          _tl([[100, 100, 200, 220], [100, 100, 280, 340], [100, 100, 360, 480]]))
    ev = _ev(Action.DRAWER_OPEN, {"DRAWER": 1.2}, g)
    assert ev.geometry_direction_evidence is not None
    assert _val(ev).verdict == Verdict.PASS


def test_model_action_not_reused_for_geometry():
    # model_action(假设 Qwen 反了=RETRACT) 不得覆盖机器几何(DRAWER_OPEN)
    g = build_geometry_direction_evidence("DRAWER", "A",
                                          _tl([[100, 100, 200, 220], [100, 100, 280, 340], [100, 100, 360, 480]]))
    v = _val(_ev(Action.DRAWER_OPEN, {"DRAWER": 1.2}, g, model_action=Action.RETRACT))
    assert v.verdict == Verdict.PASS  # 几何通道独立于 model_action


def test_camera_unreliable_can_remain_unsure():
    # 相机不可靠 + 相对几何抖动 → 允许 UNSURE(CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE)
    g = build_geometry_direction_evidence("TABLETOP", "A",
                                          _tl([[200, 400, 900, 700], [260, 380, 940, 720], [210, 410, 910, 690]]),
                                          camera_unreliable=True)
    assert g.confidence_class == "UNSTABLE_CAMERA" and g.camera_unreliable
    v = _val(_ev(Action.EXTEND, {"TABLETOP": 0.6}, g, obj="TABLETOP"))
    assert v.verdict == Verdict.UNSURE
    assert "CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE" in v.reason_codes

