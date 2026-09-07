# -*- coding: utf-8 -*-
"""CAM01 V2.5/V2.6 — foreground overlap must be true union ∈[0,1]
（两个完全重叠 bbox 不得产生 2.0；CAM01_V25_DEFECT_OVERLAP_SUM_01）。"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("v26", REPO / "scripts" / "posta3_cam01_v26.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_fully_overlapping_boxes_ratio_le_1():
    m = _mod()
    rect = [0.0, 0.0, 100.0, 100.0]
    boxes = [[10.0, 10.0, 60.0, 60.0], [10.0, 10.0, 60.0, 60.0]]  # 完全重叠
    r = m.overlap_union(rect, boxes)
    assert 0.0 <= r <= 1.0, r
    assert r < 0.5, "两框全叠最多占 2500/10000=0.25"


def test_disjoint_boxes():
    m = _mod()
    rect = [0.0, 0.0, 100.0, 100.0]
    boxes = [[0.0, 0.0, 40.0, 40.0], [60.0, 60.0, 100.0, 100.0]]
    r = m.overlap_union(rect, boxes)
    assert abs(r - 0.32) < 1e-6, r
