# -*- coding: utf-8 -*-
"""CAM01 V2.2 R1 — holdout count gate regression（len(vi) → int(vi.sum())）。
布尔向量 sum=6（<8）即使 median/inlier 满足也必须 NOT_VALIDATED；sum=8 才可 VALIDATED。"""
import importlib.util
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("v22r1", REPO / "scripts" / "posta3_cam01_v22r1.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _pts(n_even):
    """按 cell 网格构造：fold=(gx+gy)%2；偶数 cell 数 = n_even，其余为奇数 cell（共 20 cell）。
    每点取 cell 中心，p1=p0（恒等，残差≈0、inlier≈1）。"""
    CELL = 40
    even_cells, odd_cells = [], []
    cx, cy = 0, 0
    while len(even_cells) < n_even:
        if (cx + cy) % 2 == 0:
            even_cells.append((cx, cy))
        cy += 1
        if cy > 5:
            cx += 1
            cy = 0
    while len(odd_cells) < 20 - n_even:
        if (cx + cy) % 2 == 1:
            odd_cells.append((cx, cy))
        cy += 1
        if cy > 5:
            cx += 1
            cy = 0
    pts = []
    for cx, cy in even_cells + odd_cells:
        pts.append([cx * CELL + 7.0, cy * CELL + 9.0])
    p = np.float32(pts).reshape(-1, 2)
    return p, p.copy()


def test_holdout_6_must_not_validate():
    """len=20 但 vi.sum()=6 → 即便 inlier/median 满足也绝不能 VALIDATED。"""
    m = _mod()
    p0, p1 = _pts(6)
    r = m.two_fold_validate(p0, p1)
    # fold(odd? fold=(gx+gy)%2 用 even=0) → fit0val1 的 holdout=odd=14；fit1val0 的 holdout=even=6
    f = r["folds"].get("fit1val0", {})
    assert f.get("holdout_n") == 6, f
    assert f.get("state") in ("NOT_VALIDATED", "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"), f
    assert r["pair_state"] != "LOCAL_ANCHOR_VALIDATED"


def test_holdout_8_can_validate():
    m = _mod()
    p0, p1 = _pts(8)
    r = m.two_fold_validate(p0, p1)
    for k, f in r["folds"].items():
        assert f.get("holdout_n") in (8, 12), f
        assert f.get("state") == "VALIDATED", f
    assert r["pair_state"] == "LOCAL_ANCHOR_VALIDATED"
