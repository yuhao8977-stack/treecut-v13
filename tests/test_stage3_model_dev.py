# -*- coding: utf-8 -*-
"""Stage3 MODEL DEV — PeoplePresenceAnalyzerV2 / SemanticActionAnalyzerV1 回归测试。"""
import os
import sys

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.people_analyzer_v2 import (
    PeoplePresenceAnalyzerV2, PeopleResult, DEFAULT_THRESHOLD)
from treecut.services.semantic_action_v1 import SemanticActionAnalyzerV1, _asr_hits


def _sample_frames(n=3):
    import json
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


# ---------------- PeoplePresenceAnalyzerV2 ----------------

def test_people_default_threshold_frozen():
    assert DEFAULT_THRESHOLD == 0.70  # Stage3 DEV 冻结


def test_people_output_structure():
    az = PeoplePresenceAnalyzerV2()
    fr = _sample_frames(3)
    if not fr:
        return
    r = az.analyze(fr)
    assert r.prediction in ("YES", "NO", "UNKNOWN")
    assert isinstance(r.max_person_conf, float)
    assert r.frame_hit_count >= 0
    assert r.frames_sampled > 0
    assert r.provider in ("yolo", "siglip_fallback", "no_evidence")
    az.unload()


def test_people_no_frames_unknown():
    az = PeoplePresenceAnalyzerV2()
    r = az.analyze([])
    assert r.prediction == "UNKNOWN"
    assert r.provider == "none"
    az.unload()


def test_people_no_identity_output():
    """PeopleResult 结构无身份/年龄/性别字段（guard 为文本说明，不是字段）。"""
    az = PeoplePresenceAnalyzerV2()
    r = PeopleResult("YES")
    assert not hasattr(r, "name")
    assert not hasattr(r, "age")
    assert not hasattr(r, "gender")
    assert not hasattr(r, "identity")
    assert az.summary()["outputs"] == "YES/NO/UNKNOWN + max_person_conf/frame_hit_count/frames_sampled"
    az.unload()


# ---------------- SemanticActionAnalyzerV1 ----------------

def test_asr_rules_no_收纳_retract():
    """禁'收纳'作 RETRACT 强证据。"""
    assert "RETRACT" not in _asr_hits("这个柜子收纳功能很好")
    assert "RETRACT" in _asr_hits("把抽屉收回去")


def test_asr_rules_open_drawer():
    assert _asr_hits("打开抽屉给大家看") == ["OPEN_DRAWER"]


def test_semantic_action_static_default():
    az = SemanticActionAnalyzerV1()
    fr = _sample_frames(3)
    if not fr:
        return
    out = az.analyze(fr, asr_text="", component=["DRAWER"])
    assert "action_sequence" in out
    assert out["model_version"].startswith("semantic-action-v1")
    # 无 ASR + DRAWER hint → 低证据 → 静止/OTHER
    assert out["action_sequence"] in (["STATIC_DISPLAY"], ["PERSON_SPEAKING"], ["OTHER"])


def test_semantic_action_component_hint():
    az = SemanticActionAnalyzerV1()
    fr = _sample_frames(3)
    if not fr:
        return
    out = az.analyze(fr, asr_text="插上电", component=["TRACK_SOCKET"])
    assert "OPERATE_SOCKET" in out["action_sequence"]


def test_semantic_action_group_not_atomic():
    """A5：group 正确 ≠ atomic 正确；输出必须是 atomic 序列。"""
    az = SemanticActionAnalyzerV1()
    fr = _sample_frames(3)
    if not fr:
        return
    out = az.analyze(fr, asr_text="打开抽屉", component=["DRAWER"])
    assert out["action_sequence"] == ["OPEN_DRAWER"]
    assert out["prediction"] == "DRAWER"
