# -*- coding: utf-8 -*-
"""Stage 2 STEP 25 — Vision/GPU 回归测试。"""
import os
import sys
import time

import pytest

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.vision_runtime import VisionRuntimeProvider
from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2

MODELS = r"C:\Users\admin\dsh_models"


# ---------------------------------------------------------------------------
# GPU runtime
# ---------------------------------------------------------------------------

def test_gpu_runtime_detection():
    rt = VisionRuntimeProvider(MODELS)
    s = rt.summary()
    assert s["torch_cuda"] is True, "RTX 3050 应被 torch 识别"
    assert s["backend"] == "PYTORCH_CUDA"
    assert s["available_vram_mb"] >= 6000


def test_gpu_real_inference_smoke():
    rt = VisionRuntimeProvider(MODELS)
    sm = rt.gpu_smoke()
    assert "output_shape" in sm
    assert sm["output_shape"] == [512, 512]
    assert sm["matmul_512x512_ms"] < 500


def test_fallback_cpu_path():
    # 强制 CPU 后端仍可用（不崩溃）
    import torch
    torch.cuda.is_available = lambda: False
    rt = VisionRuntimeProvider(MODELS)
    assert rt.summary()["device"] == "cpu"
    torch.cuda.is_available = lambda: True


def test_model_unload_reload():
    rt = VisionRuntimeProvider(MODELS)
    an = StaticVisionAnalyzerV2(rt)
    an._ensure_model()
    key = list(rt._models.keys())[0] if rt._models else None
    an.unload()
    assert len(rt._models) == 0


def test_vram_leak_stable():
    import torch
    rt = VisionRuntimeProvider(MODELS)
    an = StaticVisionAnalyzerV2(rt)
    frames = _sample_frames(3)
    an.analyze(frames)
    v1 = torch.cuda.memory_allocated()
    for _ in range(3):
        an.analyze(frames)
    v2 = torch.cuda.memory_allocated()
    # 重复推理 VRAM 应稳定（允许小幅波动）
    assert (v2 - v1) / 1e6 < 300, f"VRAM 泄漏: {(v2-v1)/1e6:.1f}MB"
    an.unload()


# ---------------------------------------------------------------------------
# Static vision inference
# ---------------------------------------------------------------------------

def _sample_frames(n=3):
    import sqlite3
    db = os.path.join(DATA_ROOT, "database", "materials.db")
    conn = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    seg = conn.execute(
        "SELECT segment_id FROM canonical_human_truth WHERE is_current=1 LIMIT 1").fetchone()
    fr = [r[0] for r in conn.execute(
        "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT ?",
        (seg[0], n))]
    conn.close()
    return fr


def test_static_inference_fields():
    rt = VisionRuntimeProvider(MODELS)
    an = StaticVisionAnalyzerV2(rt)
    res = an.analyze(_sample_frames(3))
    assert "error" not in res
    for f in ("scene_family", "product_family", "shot_scale", "people_presence"):
        assert res[f]["prediction"]
        assert res[f]["model_score"] >= 0
    for f in ("material", "component", "function", "shot_role"):
        assert isinstance(res[f]["prediction"], list)
    an.unload()


def test_unknown_fallback_no_frames():
    rt = VisionRuntimeProvider(MODELS)
    an = StaticVisionAnalyzerV2(rt)
    res = an.analyze([])
    assert "error" in res


def test_multilabel_output():
    rt = VisionRuntimeProvider(MODELS)
    an = StaticVisionAnalyzerV2(rt)
    res = an.analyze(_sample_frames(2))
    assert set(res["material"]["prediction"]) <= {"岩板", "实木", "奢石", "大理石", "肤感",
                                                  "不锈钢", "玻璃", "其他", "UNKNOWN"}
    an.unload()


def test_policy_mode_routing_final():
    """Stage3 FINAL PRE-REVIEW BATCH 裁定：material/shot_role 走 v1 旧路由，component/function 走 v2。"""
    rt = VisionRuntimeProvider(MODELS)
    an = StaticVisionAnalyzerV2(rt)
    assert an.MULTI_POLICY["material"]["policy_mode"] == "v1"
    assert an.MULTI_POLICY["shot_role"]["policy_mode"] == "v1"
    assert an.MULTI_POLICY["component"]["policy_mode"] == "v2"
    assert an.MULTI_POLICY["function"]["policy_mode"] == "v2"
    # 多标签输出带 per-label scores（Policy 模拟 / near-dup 审计依赖）
    res = an.analyze(_sample_frames(2))
    for f in ("material", "component", "function", "shot_role"):
        assert "scores" in res[f], f"{f} 缺少 scores"
        assert isinstance(res[f]["scores"], dict) and len(res[f]["scores"]) > 0
    an.unload()


# ---------------------------------------------------------------------------
# Holdout 隔离
# ---------------------------------------------------------------------------

def test_holdout_exclusion():
    import json
    cand = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_CANDIDATES.json"),
                          encoding="utf-8"))
    sids = [s["segment_id"] for s in cand["segments"]]
    assert len(sids) == 30
    assert len(set(sids)) == 30
    assert len({s["asset_id"] for s in cand["segments"]}) == 30  # asset 唯一
    import sqlite3
    conn = sqlite3.connect("file:" + os.path.join(DATA_ROOT, "database", "materials.db").replace("\\", "/") + "?mode=ro", uri=True)
    excl = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    conn.close()
    assert not (set(sids) & excl), "Holdout 与 canonical 重叠！"
    assert cand["guard"] == "DO_NOT_TRAIN; DO_NOT_CALIBRATE"


def test_holdout_composition():
    import json
    from collections import Counter
    cand = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_CANDIDATES.json"),
                          encoding="utf-8"))
    comp = Counter(s["selection_reason"] for s in cand["segments"])
    assert comp["random_audit"] == 10 and comp["low_evidence"] == 10 and comp["coverage_gap"] == 10


# ---------------------------------------------------------------------------
# 模型文件真实性
# ---------------------------------------------------------------------------

def test_models_downloaded_real():
    sig = os.path.join(MODELS, "models--google--siglip-base-patch16-224")
    clip = os.path.join(MODELS, "models--openai--clip-vit-base-patch32")
    assert os.path.exists(sig), "SigLIP 未下载"
    assert os.path.exists(clip), "CLIP 未下载"


def test_temporal_flow_real_frames():
    from treecut.services.temporal_action_v2 import TemporalActionAnalyzerV2
    import sqlite3
    db = os.path.join(DATA_ROOT, "database", "materials.db")
    conn = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    seg = conn.execute("SELECT segment_id FROM canonical_human_truth WHERE is_current=1 LIMIT 1").fetchone()
    fr = [r[0] for r in conn.execute(
        "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms", (seg[0],))]
    conn.close()
    assert len(fr) >= 3
    r = TemporalActionAnalyzerV2().analyze(fr)
    assert r["prediction"] in ("STATIC", "SPEAKING", "EXTEND", "DRAWER", "OTHER", "UNKNOWN")
    assert "motion_profile" in r
    assert r["model_version"] == "temporal-flow-v1"
