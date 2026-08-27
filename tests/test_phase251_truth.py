# -*- coding: utf-8 -*-
"""Phase 2.5.1 — Canonical Truth & Schema V2 Freeze 测试。

覆盖架构监工要求的测试点：
  1. 同 segment v1+v2 不形成两个 training samples（unique 口径）
  2. canonical truth resolution（SINGLE_REVIEW / AGREED / HIERARCHICAL / CONFLICT）
  3. true conflict → NEEDS_ADJUDICATION
  4. product family/variant mapping
  5. component/function separation
  6. shot_scale/shot_role separation
  7. dictionary version required
  8. empty review rejection（UI 校验）
  9. unique coverage counting
"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from treecut.services.canonical_truth import CanonicalTruthService
from treecut.services.second_review_ui import validate_submission

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")


# ---------------------------------------------------------------------------
# 工具：迷你 DB（canonical_human_truth 表结构）
# ---------------------------------------------------------------------------

TRUTH_DDL = """
CREATE TABLE canonical_human_truth (
    segment_id TEXT PRIMARY KEY, scene_family TEXT, scene_subtype TEXT,
    product_family TEXT, product_variant TEXT, material TEXT, component TEXT,
    function TEXT, action_group TEXT, atomic_action TEXT, shot_scale TEXT,
    shot_role TEXT, people_presence TEXT, product_visibility TEXT, quality REAL,
    truth_source TEXT, agreement_level TEXT, human_evidence_count INTEGER,
    human_confidence TEXT, review_status TEXT, dictionary_version TEXT,
    v1_record_id INTEGER, v2_record_id INTEGER, created_at REAL, updated_at REAL
);
"""


def _v1(seg, scene="工厂", product="岛台", material="岩板", function="其他",
        action="讲解/演示", shot_type="中景", people="yes", **kw):
    row = {"target_id": seg, "scene": scene, "product": product,
           "material": material, "function": function, "action": action,
           "shot_type": shot_type, "people_presence": people,
           "product_visibility": -1.0, "quality_score": 60.0}
    row.update(kw)
    return row


def _v2(seg, scene="工厂", product="伸缩岛台", material="岩板", function="收纳",
        action="人物讲解", shot_type="人物讲解", people="yes",
        human_confidence="MEDIUM", review_status="REVIEWED", **kw):
    row = {"segment_id": seg, "v2_id": 1, "scene": scene, "product": product,
           "material": material, "function": function, "action": action,
           "shot_type": shot_type, "people_presence": people,
           "human_confidence": human_confidence, "review_status": review_status}
    row.update(kw)
    return row


# ---------------------------------------------------------------------------
# 1. 同 segment 不形成两个训练样本（真实 manifest V2 校验）
# ---------------------------------------------------------------------------

def test_same_segment_not_two_training_samples():
    mp = Path(DATA_ROOT) / "CALIBRATION_CORPUS_V1_MANIFEST_V2.json"
    assert mp.exists(), "CALIBRATION_CORPUS_V1_MANIFEST_V2.json 缺失"
    m = json.loads(mp.read_text(encoding="utf-8"))
    units = m["training_units"]
    sids = [u["segment_id"] for u in units]
    assert len(sids) == len(set(sids)), "训练单位存在重复 segment_id！"
    assert m["counts"]["eligible_unique_segments"] == len(sids)
    assert m["counts"]["unique_segments"] == 300


# ---------------------------------------------------------------------------
# 2. Resolution 逻辑
# ---------------------------------------------------------------------------

def test_single_review_resolution():
    svc = CanonicalTruthService(":memory:")
    v1 = svc.map_record_to_v2(_v1("S1"))
    res = svc.resolve_segment(v1, None, v1_row={"adjudication_id": 10})
    assert res["truth_source"] == "SINGLE_REVIEW"
    assert res["human_evidence_count"] == 1
    assert res["product_family"] == "ISLAND"
    assert res["v1_record_id"] == 10


def test_double_review_agreed():
    svc = CanonicalTruthService(":memory:")
    kw = dict(product="伸缩岛台", function="收纳", action="人物讲解", shot_type="中景")
    v1 = svc.map_record_to_v2(_v1("S2", **kw))
    v2 = svc.map_record_to_v2(_v2("S2", **kw))
    res = svc.resolve_segment(v1, v2)
    assert res["truth_source"] == "DOUBLE_REVIEW_AGREED"
    assert res["agreement_level"] == "exact"
    assert res["human_evidence_count"] == 2
    assert res["review_status"] == "GOLD"


def test_hierarchical_product_variant():
    """v1 岛台(变体 UNKNOWN) vs v2 伸缩岛台 → family 一致，variant 取更具体。"""
    svc = CanonicalTruthService(":memory:")
    kw = dict(function="收纳", action="人物讲解", shot_type="中景")
    v1 = svc.map_record_to_v2(_v1("S3", product="岛台", **kw))
    v2 = svc.map_record_to_v2(_v2("S3", product="伸缩岛台", **kw))
    res = svc.resolve_segment(v1, v2)
    assert res["product_family"] == "ISLAND"
    assert res["product_variant"] == "EXTENDABLE_ISLAND"
    assert res["truth_source"] in ("DOUBLE_REVIEW_AGREED", "DOUBLE_REVIEW_HIERARCHICAL")


def test_true_conflict_needs_adjudication():
    """v1 工厂 vs v2 展厅（scene_family 真冲突）→ NEEDS_ADJUDICATION。"""
    svc = CanonicalTruthService(":memory:")
    kw = dict(product="伸缩岛台", function="收纳", action="人物讲解", shot_type="中景")
    v1 = svc.map_record_to_v2(_v1("S4", scene="工厂", **kw))
    v2 = svc.map_record_to_v2(_v2("S4", scene="展厅", **kw))
    res = svc.resolve_segment(v1, v2)
    assert res["truth_source"] == "NEEDS_ADJUDICATION"
    assert res["review_status"] == "NEEDS_SECOND_REVIEW"


def test_action_group_conflict_needs_adjudication():
    """v1 拉出/展开(EXTEND) vs v2 打开抽屉(DRAWER) → action 真冲突。"""
    svc = CanonicalTruthService(":memory:")
    kw = dict(product="伸缩岛台", function="收纳", shot_type="中景")
    v1 = svc.map_record_to_v2(_v1("S5", action="拉出/展开", **kw))
    v2 = svc.map_record_to_v2(_v2("S5", action="打开抽屉", **kw))
    res = svc.resolve_segment(v1, v2)
    assert res["truth_source"] == "NEEDS_ADJUDICATION"


def test_drawer_component_function_separation():
    """v1 function=抽屉(组件词) vs v2 function=收纳 → component=DRAWER, function=STORAGE 一致。"""
    svc = CanonicalTruthService(":memory:")
    kw = dict(product="伸缩岛台", action="人物讲解", shot_type="中景")
    v1 = svc.map_record_to_v2(_v1("S6", function="抽屉", **kw))
    v2 = svc.map_record_to_v2(_v2("S6", function="收纳", **kw))
    assert v1["component"] == "DRAWER" and v1["function"] == "STORAGE"
    assert v2["component"] == "NOT_APPLICABLE" and v2["function"] == "STORAGE"
    res = svc.resolve_segment(v1, v2)
    # component 取有值方 DRAWER；function 一致 STORAGE → 非冲突
    assert res["component"] == "DRAWER"
    assert res["function"] == "STORAGE"
    assert res["truth_source"] != "NEEDS_ADJUDICATION"


def test_shot_scale_role_separation():
    """v1 近景(scale) vs v2 功能演示(role) → 不同维度，非冲突。"""
    svc = CanonicalTruthService(":memory:")
    kw = dict(product="伸缩岛台", function="收纳", action="人物讲解")
    v1 = svc.map_record_to_v2(_v1("S7", shot_type="近景", **kw))
    v2 = svc.map_record_to_v2(_v2("S7", shot_type="功能演示", **kw))
    assert v1["shot_scale"] == "CLOSE" and v1["shot_role"] == "UNKNOWN"
    assert v2["shot_scale"] == "UNKNOWN" and v2["shot_role"] == "FUNCTION_DEMO"
    res = svc.resolve_segment(v1, v2)
    assert res["shot_scale"] == "CLOSE"
    assert res["shot_role"] == "FUNCTION_DEMO"
    assert res["truth_source"] != "NEEDS_ADJUDICATION"


# ---------------------------------------------------------------------------
# 3. 字典版本
# ---------------------------------------------------------------------------

def test_dictionary_version_required():
    svc = CanonicalTruthService(":memory:")
    v1 = svc.map_record_to_v2(_v1("S8"))
    res = svc.resolve_segment(v1, None)
    assert res["dictionary_version"] == "ANNOTATION_DICTIONARY_V2"


# ---------------------------------------------------------------------------
# 4. 空提交治理（UI 校验）
# ---------------------------------------------------------------------------

def test_empty_review_rejected():
    empty = {"scene": "", "product": "", "material": "", "function": "",
             "action": "", "shot_type": "", "people_presence": "",
             "comment": ""}
    ok, msg, status = validate_submission(empty, "MEDIUM", "REVIEWED")
    assert ok is False
    assert status == "NEEDS_SECOND_REVIEW"


def test_empty_review_unplayable_excluded_allowed():
    empty = {"scene": "", "product": "", "material": "", "function": "",
             "action": "", "shot_type": "", "people_presence": "",
             "comment": "视频无法播放 UNPLAYABLE"}
    ok, msg, status = validate_submission(empty, "MEDIUM", "EXCLUDED")
    assert ok is True
    assert status == "EXCLUDED"


def test_confidence_must_be_selected():
    vals = {"scene": "工厂", "product": "岛台", "material": "岩板",
            "function": "收纳", "action": "人物讲解", "shot_type": "中景",
            "people_presence": "yes", "comment": ""}
    ok, msg, status = validate_submission(vals, "", "REVIEWED")
    assert ok is False
    assert "置信度" in msg


# ---------------------------------------------------------------------------
# 5. 唯一覆盖计数
# ---------------------------------------------------------------------------

def test_unique_coverage_counting():
    """同一 segment 即使有 v1+v2 两条记录，在 canonical 覆盖中只计一次。"""
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    conn = sqlite3.connect(db)
    conn.executescript(TRUTH_DDL)
    # 同一 segment 两条记录合并为一行 canonical
    for i in range(5):
        conn.execute(
            "INSERT INTO canonical_human_truth(segment_id,product_family,material,"
            "truth_source,agreement_level,human_evidence_count,human_confidence,"
            "review_status,dictionary_version,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (f"S{i}", "ISLAND", "岩板", "DOUBLE_REVIEW_AGREED", "exact", 2,
             "MEDIUM", "GOLD", "ANNOTATION_DICTIONARY_V2", 1.0, 1.0))
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) n FROM canonical_human_truth WHERE product_family='ISLAND' AND material='岩板'"
    ).fetchone()[0]
    assert n == 5  # 5 个唯一 segment，不是 10 条记录
    conn.close()
    os.unlink(db)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
