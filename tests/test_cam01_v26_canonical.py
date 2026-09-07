# -*- coding: utf-8 -*-
"""CAM01 V2.6 R1 — canonical pair-support 单元测试（CAM01_V26_DEFECT_CANONICAL_CELL_01 修复验证）。"""
import importlib.util
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("v26r1", REPO / "scripts" / "posta3_cam01_v26r1.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_canon_rect_uses_each_frame_island():
    """TEST A: ib0/ib1 不同时，同一 normalized r2c3 → 帧内像素矩形不同；t1 用 ib1。"""
    m = _mod()
    ib0 = [0.0, 0.0, 600.0, 600.0]
    ib1 = [100.0, 100.0, 700.0, 700.0]
    rc0 = m.canon_to_frame_rect(ib0, 2, 3)
    rc1 = m.canon_to_frame_rect(ib1, 2, 3)
    assert rc0 != rc1
    assert rc0[0] == 300.0 and rc1[0] == 400.0  # c=3 → u=0.5..: x=ibx0+0.5*W


def test_same_normalized_foreground_aligns_canonical():
    """TEST B: 相同 normalized 前景（raw 坐标随岛台平移）→ canonical clean mask 相同。"""
    m = _mod()
    ib0 = [0.0, 0.0, 600.0, 600.0]
    ib1 = [100.0, 100.0, 700.0, 700.0]
    # 前景在 normalized 上同为 [0.25,0.25,0.5,0.5]
    d0 = [[150.0, 150.0, 300.0, 300.0]]
    d1 = [[250.0, 250.0, 400.0, 400.0]]
    c0 = m.mask_canon(ib0, d0)
    c1 = m.mask_canon(ib1, d1)
    assert np.array_equal(c0, c1)


def test_camera_shift_keeps_common_clean():
    """TEST C: 平移但同一 normalized cell 两端都 clean → common px 不因 raw shift 消失。"""
    m = _mod()
    ib0 = [0.0, 0.0, 600.0, 600.0]
    ib1 = [100.0, 100.0, 700.0, 700.0]
    c0 = m.mask_canon(ib0, [])
    c1 = m.mask_canon(ib1, [])
    common = c0 & c1
    px = m.canon_cell_px(common, 2, 3)
    cell_px = (m.CANON // m.GRID) ** 2
    assert px == cell_px  # 全 clean → 满格


def test_canon_512_is_used():
    """TEST D: CANON=512 真正参与（mask 尺寸 512×512，cell 面积=(512/6)^2）。"""
    m = _mod()
    c = m.mask_canon([0.0, 0.0, 100.0, 100.0], [])
    assert c.shape == (512, 512)
    assert m.canon_cell_px(c, 0, 0) == (512 // 6) ** 2
