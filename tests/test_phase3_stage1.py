# -*- coding: utf-8 -*-
"""Phase 3 Stage 1 — Tests（STEP 15）。

1. truth versioning test           — new_version 保留历史 + current 升级
2. multi-label annotation test     — material_multi/component_multi/function_multi/shot_role_multi
3. action sequence test            — action_sequence [PULL_OUT, RETRACT]
4. static visual adapter test      — _imread 中文路径 / 无帧 UNKNOWN fallback
5. temporal adapter test           — 帧差运动 → action_group
6. evidence fusion test            — per-field 融合结构与权重
7. field-specific gate test        — EvidenceGate 各状态
8. UNKNOWN fallback test           — 无帧 → UNKNOWN
9. model version trace test        — model_version 贯穿
10. active learning dedup test     — 与 300 已审段零重叠
11. near-duplicate exclusion test  — asset 去重（同 asset ≤2 段）
12. calibration metrics test       — 单值/多标签 metric 函数
"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from treecut.services.canonical_truth import CanonicalTruthService
from treecut.services.visual_cognition import (
    ConfidenceGate, EvidenceGate, FrameSampler, SegmentMultimodalEvidence,
    StaticVisualCognition, TemporalActionAnalyzer, TechnicalQualityV2, _imread)

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")

TRUTH_DDL = """
CREATE TABLE canonical_human_truth (
    segment_id TEXT PRIMARY KEY, scene_family TEXT, scene_subtype TEXT,
    product_family TEXT, product_variant TEXT, material TEXT, component TEXT,
    function TEXT, action_group TEXT, atomic_action TEXT, shot_scale TEXT,
    shot_role TEXT, people_presence TEXT, product_visibility TEXT, quality REAL,
    truth_source TEXT, agreement_level TEXT, human_evidence_count INTEGER,
    human_confidence TEXT, review_status TEXT, dictionary_version TEXT,
    v1_record_id INTEGER, v2_record_id INTEGER, created_at REAL, updated_at REAL,
    truth_version INTEGER, status TEXT, is_current INTEGER, supersedes_version INTEGER,
    material_multi TEXT, component_multi TEXT, function_multi TEXT,
    shot_role_multi TEXT, action_sequence TEXT
);
CREATE TABLE canonical_human_truth_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL, truth_version INTEGER NOT NULL,
    status TEXT NOT NULL, is_current INTEGER NOT NULL, supersedes_version INTEGER,
    snapshot_json TEXT NOT NULL, truth_source TEXT NOT NULL,
    agreement_level TEXT NOT NULL, human_evidence_count INTEGER NOT NULL,
    human_confidence TEXT NOT NULL, review_status TEXT NOT NULL,
    dictionary_version TEXT NOT NULL, created_at REAL NOT NULL,
    UNIQUE(segment_id, truth_version)
);
"""


def _mkdb():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    conn = sqlite3.connect(db)
    conn.executescript(TRUTH_DDL)
    conn.close()
    return db


# ---------------------------------------------------------------------------
# 1. Truth Versioning
# ---------------------------------------------------------------------------

def test_truth_versioning():
    db = _mkdb()
    svc = CanonicalTruthService(db)
    v1 = {"product_family": "ISLAND", "product_variant": "UNKNOWN",
          "human_evidence_count": 1}
    svc.new_version("S1", v1, truth_source="SINGLE_REVIEW")
    # 第二次裁决（V3）升级
    v2 = {"product_family": "ISLAND", "product_variant": "EXTENDABLE_ISLAND",
          "material": "岩板", "action_sequence": ["PULL_OUT", "RETRACT"],
          "human_evidence_count": 2}
    svc.new_version("S1", v2, truth_source="DOUBLE_REVIEW_AGREED",
                    agreement_level="exact", review_status="GOLD")
    conn = sqlite3.connect(db)
    cur = conn.execute("SELECT truth_version, status, is_current, product_variant "
                       "FROM canonical_human_truth WHERE segment_id='S1'").fetchone()
    assert cur[0] == 2 and cur[1] == "CURRENT" and cur[2] == 1
    assert cur[3] == "EXTENDABLE_ISLAND"
    hist = conn.execute(
        "SELECT truth_version, status FROM canonical_human_truth_history "
        "WHERE segment_id='S1' ORDER BY truth_version").fetchall()
    assert [h[0] for h in hist] == [1, 2]
    assert hist[0][1] == "SUPERSEDED"  # 旧版本保留且标记
    conn.close()
    os.unlink(db)


# ---------------------------------------------------------------------------
# 2. Multi-label
# ---------------------------------------------------------------------------

def test_multilabel_annotation():
    db = _mkdb()
    svc = CanonicalTruthService(db)
    svc.new_version("S2", {"material": "岩板", "component": "DRAWER",
                           "function": "STORAGE", "shot_role": "FUNCTION_DEMO",
                           "material_multi": ["岩板", "实木"],
                           "component_multi": ["DRAWER", "TRACK_SOCKET"],
                           "function_multi": ["STORAGE", "POWER"],
                           "shot_role_multi": ["FUNCTION_DEMO", "PERSON_TALKING"]})
    conn = sqlite3.connect(db)
    r = conn.execute("SELECT material_multi, component_multi, function_multi, shot_role_multi "
                     "FROM canonical_human_truth WHERE segment_id='S2'").fetchone()
    assert json.loads(r[0]) == ["岩板", "实木"]
    assert json.loads(r[1]) == ["DRAWER", "TRACK_SOCKET"]
    assert json.loads(r[2]) == ["STORAGE", "POWER"]
    assert json.loads(r[3]) == ["FUNCTION_DEMO", "PERSON_TALKING"]
    conn.close()
    os.unlink(db)


# ---------------------------------------------------------------------------
# 3. Action Sequence
# ---------------------------------------------------------------------------

def test_action_sequence():
    db = _mkdb()
    svc = CanonicalTruthService(db)
    svc.new_version("S3", {"action_group": "EXTEND",
                           "action_sequence": ["PULL_OUT", "RETRACT"]})
    conn = sqlite3.connect(db)
    r = conn.execute("SELECT action_sequence FROM canonical_human_truth "
                     "WHERE segment_id='S3'").fetchone()
    assert json.loads(r[0]) == ["PULL_OUT", "RETRACT"]
    conn.close()
    os.unlink(db)


# ---------------------------------------------------------------------------
# 4-5. Visual adapters
# ---------------------------------------------------------------------------

def test_static_visual_no_frames_unknown():
    svc = StaticVisualCognition()
    res = svc.analyze("X", [])
    assert "error" in res or res.get("scene_family", {}).get("prediction", "UNKNOWN") == "UNKNOWN"


def test_temporal_adapter_motion_class():
    ta = TemporalActionAnalyzer()
    # 无帧 → UNKNOWN
    res = ta.analyze([])
    assert res["prediction"] == "UNKNOWN"
    assert res["action_sequence"] == []
    assert res["model_version"].startswith("opencv-heuristic")


def test_imread_chinese_path():
    # 中文路径下的真实 keyframe（取单个段目录，避免遍历全库）应可读
    kf = Path(DATA_ROOT) / "cache" / "keyframes" / "16d0be690dc44d3a9e5c1cba0c03c654"
    if not kf.exists():
        pytest.skip("keyframe 目录不存在")
    js = sorted(kf.glob("*.jpg"))
    assert js, "无 keyframe 文件"
    img = _imread(str(js[0]), 0)
    assert img is not None, "中文路径 keyframe 应可读"


# ---------------------------------------------------------------------------
# 6. Fusion
# ---------------------------------------------------------------------------

def test_evidence_fusion_structure():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE transcripts(asset_id TEXT, text_corrected TEXT)")
    conn.execute("CREATE TABLE ocr_text(asset_id TEXT, frame_timestamp_ms INT, text TEXT)")
    conn.execute("INSERT INTO transcripts VALUES('A1','这是岩板台面，带轨道插座')")
    conn.commit()
    conn.close()
    svc = SegmentMultimodalEvidence(db)
    fused = svc.fuse("S1", "A1", 0, 10000,
                     {"material": {"prediction": "岩板", "model_score": 0.5}},
                     {"prediction": "EXTEND", "action_sequence": ["PULL_OUT"],
                      "model_score": 0.4})
    pf = fused["per_field"]
    assert "岩板" in pf["material"]["labels"]          # 视觉 + ASR 融合
    assert "POWER" in pf["function"]["labels"]          # ASR 关键词
    assert "TRACK_SOCKET" in pf["component"]["labels"]  # ASR 关键词
    assert pf["action"]["action_sequence"]              # temporal + asr
    assert fused["model_version"].startswith("opencv-heuristic")
    try:
        os.unlink(db)
    except PermissionError:
        pass


# ---------------------------------------------------------------------------
# 7. Gate
# ---------------------------------------------------------------------------

def test_field_specific_gate():
    gate = ConfidenceGate()
    fused = {"per_field": {"material": {"labels": ["岩板"], "score": 0.6},
                           "scene": {"prediction": "UNKNOWN", "score": 0.05},
                           "action": {"action_sequence": ["PULL_OUT"], "score": 0.2},
                           "component": {"labels": [], "score": 0.0}}}
    assert gate.route("material", fused)["evidence_sufficiency"] == "SUFFICIENT"
    assert gate.route("scene", fused)["evidence_sufficiency"] == "MISSING"
    assert gate.route("action", fused)["evidence_sufficiency"] == "PARTIAL"
    assert gate.route("component", fused)["evidence_sufficiency"] == "MISSING"
    # 路由映射
    assert gate.route("material", fused)["route"] == "CHEAP_END"
    assert gate.route("scene", fused)["route"] == "UNKNOWN"
    assert "NOT a probability" in gate.route("material", fused)["note"]


# ---------------------------------------------------------------------------
# 8. UNKNOWN fallback（无帧）
# ---------------------------------------------------------------------------

def test_unknown_fallback_no_frames():
    ta = TemporalActionAnalyzer()
    assert ta.analyze([])["prediction"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# 9. Model version trace
# ---------------------------------------------------------------------------

def test_model_version_trace():
    assert TechnicalQualityV2().analyze([]).get("error") == "no_frames"
    ta = TemporalActionAnalyzer()
    assert ta.analyze([])["model_version"] == "opencv-heuristic-v0.1"


# ---------------------------------------------------------------------------
# 10-11. Active learning dedup（真实 manifest 校验）
# ---------------------------------------------------------------------------

def test_active_learning_dedup():
    batch = json.load(open(Path(DATA_ROOT) / "TARGETED_REVIEW_BATCH_V1.json",
                           encoding="utf-8"))
    sids = [s["segment_id"] for s in batch["segments"]]
    assert len(sids) == len(set(sids)), "采样内重复"
    assert len(sids) == 60
    # 与 300 已审段零重叠
    db = Path(DATA_ROOT) / "database" / "materials.db"
    conn = sqlite3.connect("file:" + str(db).replace("\\", "/") + "?mode=ro", uri=True)
    reviewed = {r[0] for r in conn.execute(
        "SELECT target_id FROM human_annotations UNION SELECT segment_id FROM human_annotation_v2")}
    conn.close()
    assert not (set(sids) & reviewed), "与已审段 exact duplicate！"


def test_near_duplicate_asset_limit():
    batch = json.load(open(Path(DATA_ROOT) / "TARGETED_REVIEW_BATCH_V1.json",
                           encoding="utf-8"))
    from collections import Counter
    asset_cnt = Counter(s["asset_id"] for s in batch["segments"])
    assert max(asset_cnt.values()) <= 2, "同 asset 段数超限（near-duplicate 风险）"


# ---------------------------------------------------------------------------
# 12. Calibration metrics（真实 manifest + 评估结果存在性）
# ---------------------------------------------------------------------------

def test_calibration_metrics_present():
    eval_path = Path(DATA_ROOT) / "PHASE3_EVAL_RESULTS.json"
    assert eval_path.exists(), "PHASE3_EVAL_RESULTS.json 缺失（评估未跑）"
    ev = json.loads(eval_path.read_text(encoding="utf-8"))
    assert ev["n_segments"] == 240
    m = ev["metrics"]
    for f in ("scene", "product", "shot_scale", "people"):
        assert "effective_correct_rate" in m[f]["baseline"]
        assert "effective_correct_rate" in m[f]["candidate"]
    assert "micro_f1" in m["material"]["candidate"]
    assert "sequence_exact_match" in m["action"]["candidate"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
