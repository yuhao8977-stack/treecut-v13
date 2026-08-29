# -*- coding: utf-8 -*-
"""Stage3 TRACK 2/3 — Mini 批 + SemanticActionAnalyzerV2 回归测试。"""
import json
import os
import sys

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.semantic_action_v2 import (
    SemanticActionAnalyzerV2, TRANSITION_ACTION, STATE_PROMPTS)


def _sample_frames(n=4):
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"),
                         encoding="utf-8"))
    sid = man["segments"][0]["segment_id"]
    import sqlite3
    conn = sqlite3.connect("file:" + os.path.join(
        DATA_ROOT, "database", "materials.db").replace("\\", "/") + "?mode=ro", uri=True)
    fr = [r[0] for r in conn.execute(
        "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT ?",
        (sid, n))]
    conn.close()
    return fr


# ---------------- Mini 批 ----------------

def test_mini_batch_manifest_18():
    mini = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_MINI_V1.json"),
                          encoding="utf-8"))
    segs = mini["segments"]
    assert len(segs) == 18
    assert len({s["segment_id"] for s in segs}) == 18
    assert len({s["asset_id"] for s in segs}) == 18  # 独立 asset
    comp = mini["composition"]
    assert comp.get("OPERATE_SOCKET") == 8
    assert comp.get("CUSTOMER_HOME") == 5
    assert comp.get("SOLID_WOOD") == 5
    # 盲审契约：无 AI 预测/分数/证据字段（novelty_score 是采样元数据，非 AI 猜测）
    for s in segs:
        for k in s:
            assert not any(w in k.lower() for w in ("prediction", "model_score", "siglip",
                                                    "yolo", "provider", "evidence", "candidate_score")), k


def test_mini_batch_neardup_pass():
    nd = json.load(open(os.path.join(DATA_ROOT, "STAGE3_MINI_BATCH_FINAL_NEARDUP.json"),
                        encoding="utf-8"))
    assert nd["pass"] is True
    for k, v in nd["result"].items():
        assert v.get("EXACT", 0) == 0
        assert v.get("NEAR", 0) == 0


# ---------------- SemanticActionAnalyzerV2 ----------------

def test_transition_table():
    assert TRANSITION_ACTION[("DRAWER", "CLOSED", "OPEN")] == "OPEN_DRAWER"
    assert TRANSITION_ACTION[("DRAWER", "OPEN", "CLOSED")] == "CLOSE_DRAWER"
    assert TRANSITION_ACTION[("CABINET_DOOR", "CLOSED", "OPEN")] == "OPEN_CABINET"
    assert TRANSITION_ACTION[("CABINET_DOOR", "OPEN", "CLOSED")] == "CLOSE_CABINET"
    assert TRANSITION_ACTION[("EXTENDABLE_SECTION", "RETRACTED", "EXTENDED")] == "PULL_OUT"
    assert TRANSITION_ACTION[("EXTENDABLE_SECTION", "EXTENDED", "RETRACTED")] == "RETRACT"
    assert TRANSITION_ACTION[("SOCKET", "IDLE", "INTERACTED")] == "OPERATE_SOCKET"


def test_state_prompts_exist():
    for obj in ("DRAWER", "CABINET_DOOR", "EXTENDABLE_SECTION", "SINK_COVER", "SOCKET"):
        assert obj in STATE_PROMPTS
        assert len(STATE_PROMPTS[obj]) >= 2


def test_v2_insufficient_frames():
    az = SemanticActionAnalyzerV2()
    out = az.analyze([])
    assert out["prediction"] == "UNKNOWN"
    assert out["action_sequence"] == []
    az.unload()


def test_v2_smoke_on_sample():
    fr = _sample_frames(4)
    if len(fr) < 3:
        return
    az = SemanticActionAnalyzerV2()
    out = az.analyze(fr, component=["DRAWER"])
    assert "action_sequence" in out
    assert out["model_version"].startswith("semantic-action-v2")
    assert "object_states" in out["evidence"]
    az.unload()


def test_v2_motion_hint_not_label():
    """光流方向只作 hint：无状态变化时不得直接定标签。"""
    from treecut.services.semantic_action_v2 import SemanticActionAnalyzerV2 as A2
    az = A2()
    # 空帧 → UNKNOWN（无状态证据时 motion hint 不产生标签）
    out = az.analyze([], component=["DRAWER"])
    assert out["prediction"] == "UNKNOWN"
    az.unload()
