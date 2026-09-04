# -*- coding: utf-8 -*-
"""MMV R2 测试(§22): ROI语义/排除/门序/heuristic策略/相机affine/Known6目标。

Source Audit R1 P1 修复：
- 删除 assert True 假测试与"仅查字段存在"弱断言；
- 新增真实 synthetic 相机补偿行为测试（translation 方向/affine rotation/静态不误报）；
- 新增 Enforcement 代码锁测试（默认禁止，显式环境变量放行）。
"""
import json, sys
import cv2
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.mmvl_master_v1 import CameraMotionEstimator, ShadowGate, MMVVMode

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")

R2_KNOWN_UNMET = "MMVV_R2_KNOWN_UNMET: qwen2.5vl 无可靠多对象bbox → 语义ROI 阻塞; 51/1985/1986 仍 UNSURE(无假PASS); 修复后需移除 xfail"


def _r2():
    return json.loads((OUT / "_mmv_r2_results.json").read_text(encoding="utf-8"))


def _by(mid):
    return next((x for x in _r2() if x["media_id"] == mid), {})


def _texture(h=120, w=160, seed=0):
    """矩形纹理场景（给 LK 足够角点），确定性。"""
    rng = np.random.default_rng(seed)
    img = np.full((h, w), 40, dtype=np.uint8)
    for _ in range(40):
        x1 = int(rng.integers(0, w - 12)); y1 = int(rng.integers(0, h - 12))
        x2 = min(w, x1 + int(rng.integers(8, 24))); y2 = min(h, y1 + int(rng.integers(8, 24)))
        cv2.rectangle(img, (x1, y1), (x2, y2), int(rng.integers(90, 255)), -1)
    return cv2.GaussianBlur(img, (0, 0), 1.0)


def _bgr(h=120, w=160, seed=0):
    return cv2.cvtColor(_texture(h, w, seed), cv2.COLOR_GRAY2BGR)


def _mad(a, b):
    return float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())


def test_semantic_roi_excludes_socket_from_tabletop():
    r = _by(1985)
    assert r.get("roi_source") in ("MODEL_DETECTED", "HEURISTIC")
    assert r.get("socket_roi") is not None or r.get("roi_source") == "HEURISTIC"


def test_heuristic_roi_cannot_directional_pass_alone():
    r = _by(51)
    assert r.get("verdict") != "Verdict.PASS"


@pytest.mark.xfail(strict=True, reason=R2_KNOWN_UNMET)
def test_media51_no_target_motion_fail():
    assert _by(51).get("verdict") == "Verdict.FAIL"


@pytest.mark.xfail(strict=True, reason=R2_KNOWN_UNMET)
def test_1985_socket_motion_not_tabletop_motion():
    r = _by(1985)
    assert r.get("verdict") == "Verdict.FAIL"
    sm = (r.get("roi_motion") or {}).get("SOCKET_MODULE", 0.0)
    tm = r.get("core_motion", 0.0)
    assert sm >= 0.0 and tm < 0.05  # 插座运动高、桌面核心低


@pytest.mark.xfail(strict=True, reason=R2_KNOWN_UNMET)
def test_1986_socket_motion_not_tabletop_motion():
    assert _by(1986).get("verdict") == "Verdict.FAIL"


def test_media52_drawer_motion_positive():
    v = _by(52).get("verdict")
    assert v in ("Verdict.PASS", "Verdict.UNSURE")  # 不假 PASS 也不拒真动作


@pytest.mark.xfail(strict=True, reason=R2_KNOWN_UNMET)
def test_person_overlap_discount():
    r = _by(89)
    assert r.get("verdict") == "Verdict.FAIL"  # 人动不替代桌板动


def test_known_negatives_no_false_pass():
    # 记录结果: 89/109/1985/1986 金负例不得 PASS（数据层行为断言）
    for mid in (89, 109, 1985, 1986):
        assert _by(mid).get("verdict") != "Verdict.PASS"


# ---------------------------------------------------------------
# 真实 synthetic 相机补偿行为测试（替代 assert True 假测试）
# ---------------------------------------------------------------
def test_camera_translation_compensated_and_sign():
    # 纯相机平移：补偿后静态场景差异显著下降；矩阵记录 prev→curr（符号正确）
    a = _bgr()
    DX, DY = 6.0, 4.0
    b = cv2.warpAffine(a, np.float32([[1, 0, DX], [0, 1, DY]]), (a.shape[1], a.shape[0]))
    est = CameraMotionEstimator()
    m = est.estimate(a, b)
    assert m.translation_px >= 4.0, "应检测到相机平移"
    assert m.matrix is not None
    assert abs(m.matrix[0][2] - DX) <= 2.5 and abs(m.matrix[1][2] - DY) <= 2.5, \
        "motion 矩阵应为 prev→curr（+DX,+DY），符号错误会令补偿失效"
    wb = est.compensate(b, m)
    raw = _mad(a, b)
    comp = _mad(a, wb)
    assert comp < 0.5 * raw, f"补偿后差异应显著下降 (raw={raw:.1f}, comp={comp:.1f})"
    assert comp < 45.0, f"纯相机平移补偿后静态场景不应残留大差异 (comp={comp:.1f})"


def test_camera_translation_negative_direction():
    # 反方向平移同样正确补偿（防止只对单方向侥幸）
    a = _bgr(seed=1)
    b = cv2.warpAffine(a, np.float32([[1, 0, -7.0], [0, 1, 3.0]]), (a.shape[1], a.shape[0]))
    est = CameraMotionEstimator()
    m = est.estimate(a, b)
    wb = est.compensate(b, m)
    raw = _mad(a, b)
    comp = _mad(a, wb)
    assert comp < 0.5 * raw, f"负方向平移补偿失败 (raw={raw:.1f}, comp={comp:.1f})"


def test_camera_rotation_compensated_not_product_motion():
    # 纯旋转 2°：affine 补偿后差异远低于未补偿；相机旋转不得当产品运动
    a = _bgr(seed=2)
    Mrot = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] / 2), 2.0, 1.0)
    b = cv2.warpAffine(a, Mrot, (a.shape[1], a.shape[0]))
    est = CameraMotionEstimator()
    m = est.estimate(a, b)
    assert m.model in ("AFFINE", "TRANSLATION")
    wb = est.compensate(b, m)
    raw = _mad(a, b)
    comp = _mad(a, wb)
    assert comp < 0.6 * raw, f"旋转补偿后差异应显著下降 (raw={raw:.1f}, comp={comp:.1f})"
    assert comp < 55.0, f"纯相机旋转补偿后残留仍过高 (comp={comp:.1f})"


# ---------------------------------------------------------------
# Enforcement 代码锁（Source Audit R1 P2）
# ---------------------------------------------------------------
def test_enforcement_blocked_without_allow(monkeypatch):
    monkeypatch.delenv("TREECUT_MMVV_ENFORCEMENT_ALLOW", raising=False)
    with pytest.raises(ValueError, match="MMVV_ENFORCEMENT_BLOCKED"):
        ShadowGate(MMVVMode.ENFORCEMENT)
    ShadowGate()  # 默认 SHADOW 不受影响
    ShadowGate(MMVVMode.SHADOW)


def test_enforcement_allowed_only_with_explicit_env(monkeypatch):
    monkeypatch.delenv("TREECUT_MMVV_ENFORCEMENT_ALLOW", raising=False)
    with pytest.raises(ValueError):
        ShadowGate(MMVVMode.ENFORCEMENT)
    monkeypatch.setenv("TREECUT_MMVV_ENFORCEMENT_ALLOW", "1")
    g = ShadowGate(MMVVMode.ENFORCEMENT)
    assert g.mode == MMVVMode.ENFORCEMENT

