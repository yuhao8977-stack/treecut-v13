# -*- coding: utf-8 -*-
"""CAM01 STRUCT01 — ECC 方向/模型合成测试（known-point projection；禁止只看 warp 观感）。"""
import importlib.util
import numpy as np
import cv2
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("struct01", REPO / "scripts" / "posta3_cam01_struct01.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _synth_pair():
    """合成结构图：矩形/线 + 中频纹理（ECC 需足够梯度信号）。"""
    m = _mod()
    rng = np.random.default_rng(1)
    noise = cv2.GaussianBlur(rng.integers(0, 60, (256, 256), dtype=np.uint8), (5, 5), 0)
    g0 = noise.copy()
    cv2.rectangle(g0, (40, 40), (200, 90), 220, 2)
    cv2.rectangle(g0, (40, 120), (200, 140), 200, 2)
    cv2.line(g0, (60, 160), (220, 160), 190, 2)
    cv2.circle(g0, (120, 200), 40, 170, 2)
    return g0


def _run(model, dxy=(20, -8), rot=0.0, scale=1.0):
    m = _mod()
    g0 = _synth_pair()
    h, w = g0.shape
    c = np.float32([[scale * np.cos(rot), -scale * np.sin(rot), dxy[0]],
                    [scale * np.sin(rot), scale * np.cos(rot), dxy[1]]])
    g1 = cv2.warpAffine(g0, c, (w, h), flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REFLECT)
    mask = np.full((h, w), 255, dtype=np.uint8)
    F, converged = m.fit_ecc(g0, g1, mask, model)
    if F is None:
        return None, None, c
    pts = np.float32([[40, 40], [200, 90], [220, 160]]).reshape(-1, 1, 2)
    pred = cv2.transform(pts, F).reshape(-1, 2)
    truth = cv2.transform(pts, c).reshape(-1, 2)
    err = float(np.max(np.linalg.norm(pred - truth, axis=1)))
    return F, err, c


def _direction_ok(F, c, tol_ratio=0.5):
    """语义方向/量级检查：平移符号正确 + 位移量级在 [0.2,5]×truth（ECC 局部极小不claim亚像素精确）。"""
    m = _mod()
    h = 256
    pts = np.float32([[40, 40], [200, 90], [220, 160]]).reshape(-1, 1, 2)
    pred = cv2.transform(pts, F).reshape(-1, 2)
    truth = cv2.transform(pts, c).reshape(-1, 2)
    disp_p = pred - pts.reshape(-1, 2)
    disp_t = truth - pts.reshape(-1, 2)
    if float(np.linalg.norm(disp_t)) < 0.5:
        return float(np.max(np.linalg.norm(pred - truth, axis=1))) < 5.0
    dot = float(np.sum(disp_p * disp_t, axis=1).mean())
    ratio = float(np.linalg.norm(disp_p) / max(1e-6, np.linalg.norm(disp_t)))
    return dot > 0 and 0.2 <= ratio <= 5.0


def test_ecc_translation_direction_euclidean():
    F, err, _ = _run("EUCLIDEAN", dxy=(20.0, -8.0))
    assert F is not None and err is not None
    assert err < 3.0, f"euclidean translation err {err}"


def test_ecc_translation_direction_affine():
    F, err, _ = _run("AFFINE", dxy=(-15.0, 10.0))
    assert F is not None and err is not None
    assert err < 3.0, f"affine translation err {err}"


def test_ecc_rotation_direction_affine():
    import math
    F, _, c = _run("AFFINE", rot=math.radians(5.0))
    assert F is not None
    assert _direction_ok(F, c), "rotation 方向/量级语义错误"


def test_ecc_affine_scale_direction():
    F, _, c = _run("AFFINE", scale=1.06, dxy=(6.0, 4.0))
    assert F is not None
    assert _direction_ok(F, c), "affine scale 方向/量级语义错误"
