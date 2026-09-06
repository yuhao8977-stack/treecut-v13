# -*- coding: utf-8 -*-
"""POST-A3 GEOM01 — RELATIVE_ANCHOR_V1 合成场景测试（旧法缺陷证明 + 新法行为）。"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _lab():
    spec = importlib.util.spec_from_file_location("posta3_geometry_lab", REPO / "scripts" / "posta3_geometry_lab.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _tl_from(lab, bboxes):
    ib = lab.island()
    return [{"t_s": float(i), "bbox": list(b), "island": list(ib)} for i, b in enumerate(bboxes)]


def test_extend_right_detected_by_both():
    lab = _lab()
    b = [[300, 180, 400 + i * 60, 380] for i in range(5)]
    old_a, _, _ = lab.old_direction(_tl_from(lab, b))
    new = lab.new_classify(_tl_from(lab, b))
    assert old_a == "EXTEND" and new["action"] == "EXTEND" and new["axis"] == "RIGHT"


def test_retract_right_detected_by_both():
    lab = _lab()
    b = [[300, 180, 640 - i * 60, 380] for i in range(5)]
    old_a, _, _ = lab.old_direction(_tl_from(lab, b))
    new = lab.new_classify(_tl_from(lab, b))
    assert old_a == "RETRACT" and new["action"] == "RETRACT"


def test_perspective_grow_is_static_new_not_old():
    """GEOM01 核心：纯推近（岛台与目标同比例放大）→ 面积↑ 但相对锚点不变。
    旧法 OLD_ABS_AREA 误判 EXTEND；新法必须 STATIC。"""
    lab = _lab()
    tl = []
    for i, k in enumerate([1.0, 1.1, 1.2, 1.3, 1.4]):
        tl.append({"t_s": float(i),
                   "bbox": [int(300 * k), int(180 * k), int(560 * k), int(380 * k)],
                   "island": [int(100 * k), int(100 * k), int(700 * k), int(500 * k)]})
    old_a, _, _ = lab.old_direction(tl)
    new = lab.new_classify(tl)
    assert old_a == "EXTEND", "旧法应暴露面积误判"
    assert new["action"] == "STATIC", "新法必须免疫透视缩放"


def test_perspective_shrink_is_static_new_not_old():
    lab = _lab()
    tl = []
    for i, k in enumerate([1.0, 0.92, 0.84, 0.76, 0.68]):
        tl.append({"t_s": float(i),
                   "bbox": [int(300 * k), int(180 * k), int(560 * k), int(380 * k)],
                   "island": [int(100 * k), int(100 * k), int(700 * k), int(500 * k)]})
    old_a, _, _ = lab.old_direction(tl)
    new = lab.new_classify(tl)
    assert old_a == "RETRACT", "旧法应暴露面积误判"
    assert new["action"] == "STATIC"


def test_static_both_static():
    lab = _lab()
    tl = _tl_from(lab, [[300, 180, 560, 380]] * 5)
    old_a, _, _ = lab.old_direction(tl)
    new = lab.new_classify(tl)
    assert old_a == "STATIC" and new["action"] == "STATIC"


def test_new_emits_anchor_codes_on_progression():
    lab = _lab()
    b = [[300, 180, 400 + i * 60, 380] for i in range(5)]
    new = lab.new_classify(_tl_from(lab, b))
    assert "ANCHOR_EDGE_STABLE" in new["codes"] and "FAR_EDGE_OUTWARD_PROGRESS" in new["codes"]
