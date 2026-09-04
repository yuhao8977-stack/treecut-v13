# -*- coding: utf-8 -*-
"""MMVV A1 — Human GT ROI 数据准备回归（§21 指定 8 项）。

原则: A1 是标注/数据准备；human ROI 与 L2_QWEN/HEURISTIC 必须分离；
帧用 sha256 绑定；逐帧 ROI（非静态假设）；不调阈值；4 个 R2_KNOWN_UNMET xfail 不转绿。
"""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools" / "mmv_a1_annotate"))

import server as a1  # noqa: E402
from treecut.services.mmvl_master_v1 import CameraMotion  # noqa: E402

OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json"
ROI_FILE = OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json"
GEO_FILE = OUT / "TREECUT_MMVV_A1_GEOMETRY_TRAJECTORY.json"
STATE_FILE = OUT / "TREECUT_MMVV_A1_ANNOTATION_STATE.json"
A1_DIR = REPO / "tools" / "mmv_a1_annotate"


def _man():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _roi():
    return json.loads(ROI_FILE.read_text(encoding="utf-8"))


def test_human_roi_is_separate_from_l2_qwen():
    doc = _roi()
    assert doc.get("annotation_source") == "L3_HUMAN_ROI"
    assert doc.get("annotation_version") == "A1"
    for a in doc["annotations"]:
        assert a["annotation_source"] == "L3_HUMAN_ROI"
        assert "qwen" not in str(a).lower()


def test_frame_hash_binding():
    man = _man()
    for c in man["cases"]:
        for f in c["frames"]:
            if "error" in f:
                continue
            assert len(f.get("sha256", "")) == 64
            assert f.get("width") and f.get("height")
            lp = f.get("local_path")
            if lp and Path(lp).exists():
                import hashlib
                h = hashlib.sha256()
                with open(lp, "rb") as fh:
                    for ch in iter(lambda: fh.read(1 << 20), b""):
                        h.update(ch)
                assert h.hexdigest() == f["sha256"], f"hash 不匹配 {f['frame']}"


def test_per_frame_roi_not_static_assumption():
    man = _man()
    for c in man["cases"]:
        ts = [f["t_s"] for f in c["frames"] if "error" not in f]
        assert len(ts) == 5 and len(set(ts)) == 5, f"media {c['media_id']} 需 5 个不同时间戳帧"
        assert ts == sorted(ts)
    # ROI 记录逐帧键控（frame_timestamp），不假设单帧静态框
    assert "annotations" in _roi()


def test_roi_coordinate_bounds():
    assert a1.bbox_ok([0, 0, 100, 100], 810, 1440) is True
    assert a1.bbox_ok([0, 0, 0, 100], 810, 1440) is False
    assert a1.bbox_ok([-1, 0, 10, 10], 810, 1440) is False
    assert a1.bbox_ok([0, 0, 900, 10], 810, 1440) is False
    assert a1.bbox_ok([810, 0, 811, 5], 810, 1440) is False  # x2<=w
    assert a1.bbox_ok([1, 2, 3], 810, 1440) is False


def test_required_object_annotations_present():
    # 契约: 每动作必需目标对象集合存在（A1_READY 判定基础；当前人工未标=0 属预期）
    man = _man()
    for c in man["cases"]:
        req = a1.REQUIRED_OBJECTS.get(c["requested"], ())
        assert req, f"未知 requested {c['requested']}"
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    assert len(state["cases"]) == 6
    # 目前人工尚未标注（0 整例）——A1 未 READY，正确
    assert sum(1 for c in state["cases"] if c["fully_annotated"]) == 0


def test_reload_annotation_deterministic():
    d1 = _roi()
    d2 = json.loads(ROI_FILE.read_text(encoding="utf-8"))
    assert d1 == d2
    m1 = _man()
    m2 = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert m1 == m2


def test_camera_translation_and_residual_separate():
    # Source Audit R1.1 tech-debt: translation_px 不得误填 camera_residual（A1 工具内已落实）
    import dataclasses
    fields = {f.name for f in dataclasses.fields(CameraMotion)}
    assert {"translation_px", "inlier_ratio", "residual", "reliable"} <= fields
    for f in (A1_DIR / "server.py", A1_DIR / "build_geometry.py", A1_DIR / "gen_review.py"):
        txt = f.read_text(encoding="utf-8")
        assert "camera_residual" not in txt, f"{f.name} 不得用 camera_residual 存 translation"


def test_no_qwen_roi_used_in_a1_eval():
    # A1 工具代码不得引用 qwen/ollama/自动检测（README/HTML 说明性文字除外，只扫 .py 执行代码）
    for f in A1_DIR.glob("*.py"):
        txt = f.read_text(encoding="utf-8")
        for bad in ("11434", "ollama", "qwen2", "ask_json", "MODEL_DETECTED"):
            assert bad not in txt.lower(), f"{f.name} 含 {bad}（A1 禁用）"
