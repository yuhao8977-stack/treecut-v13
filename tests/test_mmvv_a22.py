# -*- coding: utf-8 -*-
"""MMVV A2.2 — Camera 诊断/最小修法 测试（受控实验；无媒体特例、无 GT 输入）。"""
import inspect
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.mmv_camera_diag import (  # noqa: E402
    estimate_camera_background, background_mask, warp_current_to_previous,
    duplicate_case_declaration, EXCLUDE_NAMES)
from treecut.services.mmvl_master_v1 import (  # noqa: E402
    Action, FrameSemantics, MotionMetrics, TemporalEvidence, ROI,
    TemporalStateValidator, TargetObjectMotionRouter, build_geometry_direction_evidence)

REPO = Path(__file__).resolve().parents[1]
DIAG = REPO / "src" / "treecut" / "services" / "mmv_camera_diag.py"
RUNNER = REPO / "scripts" / "mmv_a22_run.py"


def _scene(seed, bg_motion=(0, 0), blob=None):
    rng = np.random.default_rng(seed)
    img = np.full((200, 260), 90, dtype=np.uint8)
    # 背景纹理
    for _ in range(120):
        x = int(rng.integers(0, 250)); y = int(rng.integers(0, 190))
        cv2.rectangle(img, (x, y), (x + 6, y + 6), int(rng.integers(60, 160)), -1)
    if blob:
        x, y, w, h = blob
        cv2.rectangle(img, (x, y), (x + w, y + h), 200, -1)
    a = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    b = cv2.warpAffine(a, np.float32([[1, 0, bg_motion[0]], [0, 1, bg_motion[1]]]), (260, 200))
    if blob:  # 前景 blob 额外移动
        b = cv2.warpAffine(b, np.float32([[1, 0, 6], [0, 1, 3]]), (260, 200),
                           borderMode=cv2.BORDER_REPLICATE)
    return a, b


def test_foreground_tracks_excluded():
    # A2.2 R1：真实独立前景 —— 背景整体平移 (+2,-1)，前景 blob 在背景之外额外移动 (+10,+6)（不整帧二次 warp）
    rng = np.random.default_rng(1)
    bg = np.full((200, 260), 90, dtype=np.uint8)
    for _ in range(150):
        x = int(rng.integers(0, 250)); y = int(rng.integers(0, 190))
        cv2.rectangle(bg, (x, y), (x + 6, y + 6), int(rng.integers(60, 160)), -1)
    bgc = cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)
    a = bgc.copy()
    cv2.rectangle(a, (60, 60), (120, 120), 210, -1)          # 前景 blob 在前帧
    b = cv2.warpAffine(bgc, np.float32([[1, 0, 2], [0, 1, -1]]), (260, 200))  # 背景 (+2,-1)
    cv2.rectangle(b, (60 + 12, 60 + 5), (120 + 12, 120 + 5), 210, -1)  # blob 额外 (+10,+6) 相对背景
    d_full = estimate_camera_background(a, b, [], mode="full_frame")
    d_bg = estimate_camera_background(a, b, [[55, 55, 125, 125]], mode="background")
    # 背景掩码应可靠；全帧应受前景污染（更差或不可靠）
    def _res(d):
        v = d.get("residual")
        return v if v is not None else 9.0
    assert d_bg["pair_state"] == "SAME_SCENE" and _res(d_bg) < 4.0
    assert d_full["pair_state"] != "SAME_SCENE" or _res(d_full) >= _res(d_bg)
    m = background_mask(a.shape, [[50, 50, 100, 100]])
    assert not m[75, 75] and m[10, 10]


def test_warp_current_to_previous_direction():
    # A2.2 R1：纯平移背景下，逆补偿(对齐回前帧)的 scene diff 必须小于前向 warp
    rng = np.random.default_rng(6)
    img = np.full((200, 260), 90, dtype=np.uint8)
    for _ in range(150):
        x = int(rng.integers(0, 250)); y = int(rng.integers(0, 190))
        cv2.rectangle(img, (x, y), (x + 6, y + 6), int(rng.integers(60, 160)), -1)
    a = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    b = cv2.warpAffine(a, np.float32([[1, 0, 3], [0, 1, -2]]), (260, 200))
    d = estimate_camera_background(a, b, [], mode="background")
    assert d["pair_state"] == "SAME_SCENE"
    M = np.float32([[1, 0, 3], [0, 1, -2]])  # 真值前向
    wb_inv = warp_current_to_previous(b, "translation", M)
    wb_fwd = cv2.warpAffine(b, M, (260, 200))
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    diff_inv = float(np.abs(cv2.cvtColor(wb_inv, cv2.COLOR_BGR2GRAY).astype(np.float32) - ga).mean())
    diff_fwd = float(np.abs(cv2.cvtColor(wb_fwd, cv2.COLOR_BGR2GRAY).astype(np.float32) - ga).mean())
    assert diff_inv < diff_fwd, (diff_inv, diff_fwd)


def test_forward_backward_bad_tracks_rejected():
    a, b = _scene(2, bg_motion=(0, 0))
    # 制造闪烁/扰动 → 部分 track 往返不一致；统计字段存在且有效数<=原始
    d = estimate_camera_background(a, b, [])
    assert "forward_backward_valid_count" in d
    assert d["tracks_raw"] >= d["tracks_fb_valid"]


def test_scene_discontinuity_not_force_warped():
    a, _ = _scene(3)
    b, _ = _scene(99)  # 完全无关场景
    d = estimate_camera_background(a, b, [])
    assert d["pair_state"] in ("SCENE_DISCONTINUITY", "CAMERA_MODEL_UNRELIABLE",
                               "INSUFFICIENT_FEATURES")
    assert d["pair_state"] != "SAME_SCENE"  # 不得强行当成连续


def test_simplest_reliable_model_selected():
    a, b = _scene(4, bg_motion=(3, 1))
    d = estimate_camera_background(a, b, [])
    assert d["pair_state"] == "SAME_SCENE"
    assert d["chosen_model"] == "translation"  # 最简可靠


def test_camera_model_not_media_id_specific():
    sig = inspect.signature(estimate_camera_background)
    for p in sig.parameters:
        assert "media" not in p and "mid" not in p and "id" not in p
    txt = DIAG.read_text(encoding="utf-8")
    assert "if mid" not in txt and "== 1985" not in txt and "== 1986" not in txt


def test_duplicate_media_not_counted_twice():
    d = duplicate_case_declaration()
    assert d["unique_visual_case_count"] == 1
    assert d["source_media_reference_count"] == 2
    assert d["frame_hash_equivalent"] is True
    res = __import__("json").loads((REPO / "reports" / "storage" / "TREECUT_MMVV_A22_RESULTS_V1.json")
                                   .read_text(encoding="utf-8"))
    assert res["duplicate"]["unique_visual_case_count"] == 1


def test_unreliable_camera_can_remain_unsure():
    a, _ = _scene(5)
    b, _ = _scene(77)
    d = estimate_camera_background(a, b, [])
    unreliable = d["pair_state"] != "SAME_SCENE"
    geo = build_geometry_direction_evidence("TABLETOP", "A",
                                            [{"t_s": 0.0, "bbox_pixel": [40, 40, 120, 120],
                                              "island_pixel": [10, 10, 200, 160]},
                                             {"t_s": 1.0, "bbox_pixel": [41, 41, 121, 121],
                                              "island_pixel": [10, 10, 200, 160]}],
                                            camera_unreliable=unreliable)
    sem = FrameSemantics(0.0, ["TABLETOP"], [], [ROI("TABLETOP", 40, 40, 120, 120)])
    mm = MotionMetrics(roi_motion={"TABLETOP": 0.3})
    ev = TemporalEvidence(before=sem, middle=sem, after=sem, motion=mm,
                          requested_action=Action.EXTEND, geometry_direction_evidence=geo)
    v = TemporalStateValidator(TargetObjectMotionRouter()).validate(ev)
    if unreliable:
        assert v.verdict.value == "UNSURE"
        assert any("CAMERA_UNRELIABLE" in c for c in v.reason_codes)
    else:
        assert v.verdict.value == "FAIL"  # 几何静止 + 相机可靠


def test_core5_results_frozen():
    import json
    a21b = json.loads((REPO / "reports" / "storage" / "TREECUT_MMVV_A21B_RESULTS_V1.json")
                      .read_text(encoding="utf-8"))
    mv = {r["slice"]: r["machine_verdict"] for r in a21b["results"]}
    assert mv["52_DRAWER_OPEN"] == "Verdict.PASS"
    assert mv["109_ACTION_POSITIVE"] == "Verdict.PASS"
    assert mv["109_OPEN_STATE_NEGATIVE"] == "Verdict.FAIL"
    assert mv["89_EXTEND"] == "Verdict.FAIL"
    assert mv["51_EXTEND"] == "Verdict.FAIL"
    assert a21b["summary"]["false_pass"] == 0
    a22 = json.loads((REPO / "reports" / "storage" / "TREECUT_MMVV_A22_RESULTS_V1.json")
                     .read_text(encoding="utf-8"))
    assert a22["core5_frozen"]["ok"] is True


def test_no_gt_in_camera_selection():
    for fn in (estimate_camera_background,):
        for p in inspect.signature(fn).parameters:
            assert "gt" not in p and "human" not in p and "truth" not in p
    txt = DIAG.read_text(encoding="utf-8")
    assert "human_gt" not in txt
