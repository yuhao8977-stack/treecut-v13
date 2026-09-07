# -*- coding: utf-8 -*-
"""CAM01 DENSE01 R1 — 缺陷修正单元测试。"""
import importlib.util
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("d1r1", REPO / "scripts" / "posta3_cam01_dense01r1.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_rgb_channels_preserved_and_normalized():
    m = _mod()
    # BGR fixture with distinct channels
    import cv2
    bgr = np.zeros((40, 40, 3), dtype=np.uint8)
    bgr[..., 0] = 64   # B
    bgr[..., 1] = 128  # G
    bgr[..., 2] = 192  # R
    t = m.rgb_tensor_from_crop(bgr)  # BGR→RGB→ImageNet 归一化
    assert t.shape == (1, 3, 40, 40)
    # cv2.COLOR_BGR2RGB 是值保持的通道重排: BGR(64,128,192) → RGB 数组 [192,128,64]
    # （R 值 192 仍在 R 槽位；不是 "R←B" 值交换）
    # 通道顺序 RGB: ch0=R, ch1=G, ch2=B，各自用 ImageNet 对应统计量归一化
    r = float(t[0, 0, 5, 5]); g = float(t[0, 1, 5, 5]); b = float(t[0, 2, 5, 5])
    assert abs(r - (192 / 255 - 0.485) / 0.229) < 1e-4
    assert abs(g - (128 / 255 - 0.456) / 0.224) < 1e-4
    assert abs(b - (64 / 255 - 0.406) / 0.225) < 1e-4
    assert abs(r - g) > 0.5 and abs(g - b) > 0.5  # 未复制成相同通道


def test_padding_token_excluded():
    m = _mod()
    # content 200x300 letterboxed in 518 -> nw,nh; token fully inside content only
    Wc, Hc = 200.0, 300.0
    scale = min(518 / Wc, 518 / Hc)
    nw = int(Wc * scale)
    nh = int(Hc * scale)
    padx = (518 - nw) // 2
    pady = (518 - nh) // 2
    cvm = m.content_valid_mask(nw, nh, padx, pady, m.GRID, m.PATCH)
    # 完全在内容内的 token（col 使 14px 全在内容区）
    valid_col = (padx + 14 <= nw + padx)
    # 左上角 token 若 padx>=14 则全 padding → invalid
    if padx >= 14:
        assert not cvm[0, 0]
    # 存在内容 token
    assert cvm.any()


def test_invalid_token_cannot_win_mnn():
    m = _mod()
    f0 = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    f1 = np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]], dtype=np.float32)
    valid0 = np.array([True, False])   # token0 clean; token1 invalid (would sim 1.0 to f1[2])
    valid1 = np.array([True, True, True])
    pairs = m.valid_mnn(f0, f1, valid0, valid1)
    # clean token0 → f1[0]; token1 invalid 不得参与（即使其 nearest 是 f1[2] sim=1）
    assert pairs[0][1] == 0
    assert all(j != 2 for _, j, _ in pairs)


def test_raw_stride_correct():
    m = _mod()
    s = 2.0  # model px per raw px
    thr = m.coarse_ransac_thr(2.0, 2.0)
    assert abs(thr - m.PATCH / 2.0) < 1e-6


def test_true_pooled_metric():
    m = _mod()
    res = [np.array([1.0, 2.0, 3.0]), np.array([5.0])]
    med, p90, p95 = m.true_pooled(res)
    a = np.concatenate(res)
    assert abs(med - float(np.median(a))) < 1e-9
    assert abs(p90 - float(np.percentile(a, 90))) < 1e-9
