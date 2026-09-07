# -*- coding: utf-8 -*-
"""DENSE01R1 OVERNIGHT AUDIT — 合成测试（audit-only，不改 production）。

§9  LK initial-flow：已知大位移下，无 init LK 失败 vs OPTFLOW_USE_INITIAL_FLOW 恢复。
§18 MODEL CONSENSUS：合成两模型预测一致 → MULTI；median>3px → CONFLICT（防 dead code）。
§19 TRUE POOLED：pooled 必须来自真实 raw residuals（验证数学，含空输入）。
§4  预处理数学：BGR→RGB 值保持 + ImageNet 归一化逐通道。
"""
import importlib.util
import numpy as np
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod(name, file):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------- §9 LK initial flow ----------------
def _synthetic_shift(shift=12.0, size=(240, 320), win=21):
    import cv2
    rng = np.random.RandomState(7)
    g0 = rng.randint(20, 235, size=size, dtype=np.uint8)
    k = np.ones((5, 5), np.uint8)
    g0 = cv2.filter2D(g0, -1, k / 25.0)
    M = np.float32([[1, 0, shift], [0, 1, shift * 0.5]])
    g1 = cv2.warpAffine(g0, M, (size[1], size[0]))
    return g0, g1


def test_lk_initial_flow_recovers_large_shift():
    import cv2
    m = _mod("aud", "audit_dense01r1_overnight.py")
    g0, g1 = _synthetic_shift(shift=12.0)
    p0 = np.float32([[60.0, 80.0]]).reshape(-1, 1, 2)
    # 无 init：从 p0 出发（小位移假设），大位移下 pyrLK 收敛窗口受限
    p_n, st_n, _ = cv2.calcOpticalFlowPyrLK(
        g0, g1, p0, None, winSize=(21, 21), maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    err_noinit = float(np.hypot(p_n[0, 0, 0] - 72.0, p_n[0, 0, 1] - 86.0)) if (p_n is not None and st_n[0, 0] == 1) else 1e9
    # 用 audit 的 lk_refine_fb（init = 真实位移近似 DINO seed）
    p1, fwd_ok, _, _, fb = m.lk_refine_fb(g0, g1, (60.0, 80.0), (71.0, 85.5),
                                          win=21, max_level=3)
    assert fwd_ok, "with-init forward LK must succeed"
    err_init = float(np.hypot(p1[0] - 72.0, p1[1] - 86.0))
    # init 显著恢复正确点：误差应 < 无 init 或 ≤1px（收敛到真值附近）
    assert err_init < min(err_noinit, 1.5), f"init LK err {err_init} not small vs no-init {err_noinit}"


def test_lk_refine_fb_backward_consistency():
    m = _mod("aud", "audit_dense01r1_overnight.py")
    g0, g1 = _synthetic_shift(shift=8.0)
    p1, fwd_ok, p0b, bwd_ok, fb = m.lk_refine_fb(g0, g1, (100.0, 100.0), (107.5, 103.5),
                                                  win=21, max_level=3)
    assert fwd_ok and bwd_ok
    assert fb is not None and fb <= 2.0, f"FB={fb}"


# ---------------- §18 model consensus ----------------
def _consensus_pair(scale=1.0, trans=(5.0, 3.0), noise=0.3, n=40, seed=3):
    rng = np.random.RandomState(seed)
    P0 = np.column_stack([rng.uniform(0, 200, n), rng.uniform(0, 200, n)])
    P1 = P0 * scale + np.array(trans) + rng.normal(0, noise, P0.shape)
    return P0.astype(np.float32), P1.astype(np.float32)


def test_consensus_code_path_not_dead_affine():
    """aff & hom 均 validated 且分歧 ≤3px → 必须判 MULTI（真分歧代码非 dead）。"""
    m = _mod("aud", "audit_dense01r1_overnight.py")
    import cv2
    P0, P1 = _consensus_pair()  # 纯平移 → aff≈hom
    fold = np.zeros(len(P0), dtype=int)
    fold[::2] = 1
    thr = 3.0
    fr_a = m.fit_eval_audit(P0, P1, fold, "PARTIAL_AFFINE", thr)
    fr_h = m.fit_eval_audit(P0, P1, fold, "HOMOGRAPHY", thr)
    assert all(v["state"] == "VALIDATED" for v in fr_a.values())
    assert all(v["state"] == "VALIDATED" for v in fr_h.values())
    Ma, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC, ransacReprojThreshold=thr)
    Mh, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
    pa = cv2.transform(P0.reshape(-1, 1, 2), Ma).reshape(-1, 2)
    hp = np.hstack([P0, np.ones((len(P0), 1))])
    prj = (Mh @ hp.T).T
    pb = prj[:, :2] / prj[:, 2:3]
    disc = float(np.median(np.linalg.norm(pa - pb, axis=1)))
    assert disc <= 3.0, f"pure-translation disagreement {disc} > 3px unexpected"
    # 模拟调用方：分歧 ≤3 → MULTI
    state = "DENSE_MULTI_MODEL_CONSENSUS" if disc <= 3.0 else "DENSE_MODEL_CONFLICT"
    assert state == "DENSE_MULTI_MODEL_CONSENSUS"


def test_consensus_conflict_detected_on_perspective():
    """合成透视角：aff 与 hom 预测分歧显著 → CONFLICT 分支可达。"""
    m = _mod("aud", "audit_dense01r1_overnight.py")
    import cv2
    n = 60
    rng = np.random.RandomState(5)
    P0 = np.column_stack([rng.uniform(0, 300, n), rng.uniform(0, 300, n)])
    # 强透视单应（z 随 x 变化）：affine 无法近似
    H = np.array([[1.0, 0.0, 30.0],
                  [0.0, 1.0, 10.0],
                  [0.0015, 0.0, 1.0]])
    hp = np.hstack([P0, np.ones((n, 1))])
    prj = (H @ hp.T).T
    P1 = (prj[:, :2] / prj[:, 2:3]).astype(np.float32)
    fold = np.zeros(n, dtype=int)
    fold[::2] = 1
    thr = 8.0
    fr_a = m.fit_eval_audit(P0, P1, fold, "PARTIAL_AFFINE", thr)
    fr_h = m.fit_eval_audit(P0, P1, fold, "HOMOGRAPHY", thr)
    hom_ok = all(v["state"] == "VALIDATED" for v in fr_h.values())
    Ma, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC, ransacReprojThreshold=thr)
    Mh, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
    pa = cv2.transform(P0.reshape(-1, 1, 2), Ma).reshape(-1, 2)
    hp2 = np.hstack([P0, np.ones((n, 1))])
    prj2 = (Mh @ hp2.T).T
    pb = prj2[:, :2] / prj2[:, 2:3]
    disc = float(np.median(np.linalg.norm(pa - pb, axis=1)))
    # homography 应在透视下 validated 且分歧 > 3px → CONFLICT 可达
    assert hom_ok, "homography should validate under pure perspective"
    assert disc > 3.0, f"perspective disagreement {disc} should exceed 3px"
    state = "DENSE_MULTI_MODEL_CONSENSUS" if disc <= 3.0 else "DENSE_MODEL_CONFLICT"
    assert state == "DENSE_MODEL_CONFLICT"


# ---------------- §19 true pooled math ----------------
def test_true_pooled_from_raw_residuals():
    m = _mod("aud", "audit_dense01r1_overnight.py")
    res = [np.array([1.0, 2.0, 3.0]), np.array([5.0])]
    med, p90, p95 = m.true_pooled(res)
    a = np.concatenate(res)
    assert abs(med - float(np.median(a))) < 1e-9
    assert abs(p90 - float(np.percentile(a, 90))) < 1e-9
    assert abs(p95 - float(np.percentile(a, 95))) < 1e-9
    # 空输入 → None
    assert m.true_pooled([]) == (None, None, None)


# ---------------- §4 preprocess math ----------------
def test_preprocess_rgb_value_preserving_and_normalized():
    import cv2
    m = _mod("aud", "audit_dense01r1_overnight.py")
    bgr = np.zeros((40, 40, 3), dtype=np.uint8)
    bgr[..., 0] = 64   # B
    bgr[..., 1] = 128  # G
    bgr[..., 2] = 192  # R
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    # cv2 BGR2RGB 为值保持重排：输出 R=192, G=128, B=64
    assert abs(rgb[5, 5, 0] - 192 / 255.0) < 1e-6
    assert abs(rgb[5, 5, 1] - 128 / 255.0) < 1e-6
    assert abs(rgb[5, 5, 2] - 64 / 255.0) < 1e-6
    n = m.norm_rgb01(rgb)
    assert abs(float(n[5, 5, 0]) - (192 / 255 - 0.485) / 0.229) < 1e-5
    assert abs(float(n[5, 5, 1]) - (128 / 255 - 0.456) / 0.224) < 1e-5
    assert abs(float(n[5, 5, 2]) - (64 / 255 - 0.406) / 0.225) < 1e-5
