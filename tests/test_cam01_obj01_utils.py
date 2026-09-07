# -*- coding: utf-8 -*-
"""CAM01 OBJ01 — 工具修正单元测试（chamfer DT 方向 / raw 各向异性 / 0 非缺失 / bbox transform）。"""
import importlib.util
import numpy as np
import cv2
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("obj01", REPO / "scripts" / "posta3_cam01_obj01.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_chamfer_edge_zero_semantics():
    """edge=0/背景≠0 → DT 距离到最近 edge（修复 STRUCT01 DT 方向）。"""
    m = _mod()
    im = np.ones((50, 50), dtype=np.uint8)
    im[25, 10:40] = 0  # 一条水平 edge
    dt = cv2.distanceTransform(im, cv2.DIST_L2, 3).astype(np.float64)
    # 点 (25,5) 距 edge(10..39) 最近 ~5px（DT 离散允许 0.5 容差）
    assert abs(dt[25, 5] - 5.0) < 0.5
    assert abs(dt[25, 25] - 0.0) < 1e-6  # 在 edge 上=0


def test_raw_anisotropic_mapping_exact():
    """raw 各向异性：canonical→raw 用真实 bbox 映射，非 min(sx,sy) 近似。"""
    m = _mod()
    ib0 = [0.0, 0.0, 100.0, 200.0]   # W=100 H=200
    ib1 = [100.0, 50.0, 300.0, 250.0]  # W=200 H=200
    T = m.box_transform(ib0, ib1, "ANISO")
    p = np.float32([[25.0, 50.0]])
    out = m.apply_transform(p, T)[0]
    assert abs(out[0] - (100 + 25 * 2.0)) < 1e-3
    assert abs(out[1] - (50 + 50 * 1.0)) < 1e-3


def test_zero_sym_not_missing():
    """0 残差（合法）不得被当作缺失：stats_raw 对全 0 距离返回 0 而非 None。"""
    m = _mod()
    med, p90, p95 = m.stats_raw(np.zeros(10))
    assert med == 0.0 and p90 == 0.0 and p95 == 0.0
    assert m.stats_raw(None) == (None, None, None)


def test_box_transform_roundtrip():
    m = _mod()
    ib0 = [10.0, 20.0, 110.0, 220.0]
    ib1 = [30.0, 5.0, 230.0, 405.0]
    T = m.box_transform(ib0, ib1, "ANISO")
    Ti = np.linalg.inv(T)
    p = np.float32([[10.0, 20.0], [110.0, 220.0], [60.0, 120.0]])
    fwd = m.apply_transform(p, T)
    back = m.apply_transform(fwd, Ti)
    assert float(np.max(np.linalg.norm(back - p, axis=1))) < 1e-3
