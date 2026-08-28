# -*- coding: utf-8 -*-
"""Stage 2 STEP 0 — AnnotationService Persistence Parity 测试。

验证：统一保存入口（save_v3 / save_targeted_review）写出 Schema 完整、
JSON 多列可解析、Standalone 与 Main 两路径最终都走同一入口。
"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from treecut.services.annotation_governance import AnnotationService

V21 = "ANNOTATION_DICTIONARY_V2_1"

VALUES = {
    "scene_family": "FACTORY", "scene_subtype": "FACTORY_SHOWROOM",
    "product_family": "ISLAND", "product_variant": "EXTENDABLE_ISLAND",
    "material": ["岩板", "实木"], "component": ["DRAWER", "TRACK_SOCKET"],
    "function": ["STORAGE", "POWER"], "action_group": "EXTEND",
    "action_sequence": ["PULL_OUT", "RETRACT"], "shot_scale": "MEDIUM",
    "shot_role": ["PERSON_TALKING", "FUNCTION_DEMO"],
    "people_presence": "YES", "product_visibility": "VISIBLE",
    "quality": 80.0, "comment": "test",
}


def _mkdb():
    """建含两张审核表的临时 DB（0008 结构）。"""
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    conn = sqlite3.connect(db)
    conn.executescript("""
    CREATE TABLE human_annotation_v3 (
        v3_id INTEGER PRIMARY KEY AUTOINCREMENT, segment_id TEXT NOT NULL UNIQUE,
        scene_family TEXT NOT NULL DEFAULT '', scene_subtype TEXT NOT NULL DEFAULT '',
        product_family TEXT NOT NULL DEFAULT '', product_variant TEXT NOT NULL DEFAULT '',
        material_multi TEXT NOT NULL DEFAULT '[]', component_multi TEXT NOT NULL DEFAULT '[]',
        function_multi TEXT NOT NULL DEFAULT '[]', action_group TEXT NOT NULL DEFAULT '',
        action_sequence TEXT NOT NULL DEFAULT '[]', shot_scale TEXT NOT NULL DEFAULT '',
        shot_role_multi TEXT NOT NULL DEFAULT '[]', people_presence TEXT NOT NULL DEFAULT '',
        product_visibility TEXT NOT NULL DEFAULT '', quality REAL,
        human_confidence TEXT NOT NULL DEFAULT '', review_status TEXT NOT NULL DEFAULT '',
        comment TEXT NOT NULL DEFAULT '', operator TEXT NOT NULL DEFAULT '',
        dictionary_version TEXT NOT NULL DEFAULT 'ANNOTATION_DICTIONARY_V2_1',
        created_at REAL NOT NULL);
    CREATE TABLE targeted_human_review_v1 (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT, segment_id TEXT NOT NULL UNIQUE,
        scene_family TEXT NOT NULL DEFAULT '', scene_subtype TEXT NOT NULL DEFAULT '',
        product_family TEXT NOT NULL DEFAULT '', product_variant TEXT NOT NULL DEFAULT '',
        material_multi TEXT NOT NULL DEFAULT '[]', component_multi TEXT NOT NULL DEFAULT '[]',
        function_multi TEXT NOT NULL DEFAULT '[]', action_group TEXT NOT NULL DEFAULT '',
        action_sequence TEXT NOT NULL DEFAULT '[]', shot_scale TEXT NOT NULL DEFAULT '',
        shot_role_multi TEXT NOT NULL DEFAULT '[]', people_presence TEXT NOT NULL DEFAULT '',
        product_visibility TEXT NOT NULL DEFAULT '', quality REAL,
        human_confidence TEXT NOT NULL DEFAULT '', review_status TEXT NOT NULL DEFAULT '',
        comment TEXT NOT NULL DEFAULT '', operator TEXT NOT NULL DEFAULT '',
        dictionary_version TEXT NOT NULL DEFAULT 'ANNOTATION_DICTIONARY_V2_1',
        selection_reason TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);
    """)
    conn.close()
    return db


def test_save_v3_schema_complete():
    db = _mkdb()
    svc = AnnotationService(db)
    svc.save_v3("S1", VALUES, "MEDIUM", "REVIEWED", operator="tester")
    conn = sqlite3.connect(db)
    r = conn.execute("SELECT * FROM human_annotation_v3 WHERE segment_id='S1'").fetchone()
    cols = [d[1] for d in conn.execute("PRAGMA table_info(human_annotation_v3)")]
    row = dict(zip(cols, r))
    assert row["dictionary_version"] == V21
    assert json.loads(row["material_multi"]) == ["岩板", "实木"]
    assert json.loads(row["component_multi"]) == ["DRAWER", "TRACK_SOCKET"]
    assert json.loads(row["function_multi"]) == ["STORAGE", "POWER"]
    assert json.loads(row["action_sequence"]) == ["PULL_OUT", "RETRACT"]
    assert json.loads(row["shot_role_multi"]) == ["PERSON_TALKING", "FUNCTION_DEMO"]
    assert row["human_confidence"] == "MEDIUM" and row["review_status"] == "REVIEWED"
    assert row["quality"] == 80.0
    conn.close()
    os.unlink(db)


def test_save_targeted_review_schema_complete():
    db = _mkdb()
    svc = AnnotationService(db)
    svc.save_targeted_review("S2", VALUES, "HIGH", "GOLD", selection_reason="coverage_gap")
    conn = sqlite3.connect(db)
    r = conn.execute("SELECT * FROM targeted_human_review_v1 WHERE segment_id='S2'").fetchone()
    cols = [d[1] for d in conn.execute("PRAGMA table_info(targeted_human_review_v1)")]
    row = dict(zip(cols, r))
    assert row["selection_reason"] == "coverage_gap"
    assert json.loads(row["material_multi"]) == ["岩板", "实木"]
    assert row["dictionary_version"] == V21
    conn.close()
    os.unlink(db)


def test_standalone_main_same_entry():
    """Standalone 与 Main 的 _persist 均收敛到同一 AnnotationService 方法。"""
    from treecut.services import phase3_review_ui as prui
    import inspect
    src_sa = inspect.getsource(prui.AdjudicationV1App._persist)
    src_st = inspect.getsource(prui.TargetedReviewV1App._persist)
    from treecut.services import review_center as rc
    src_rc = inspect.getsource(rc.ReviewTaskWindow._persist)
    assert "save_v3(" in src_sa and "save_targeted_review(" in src_st
    assert "save_v3(" in src_rc and "save_targeted_review(" in src_rc
    assert "INSERT OR REPLACE" not in src_sa
    assert "INSERT OR REPLACE" not in src_st
    assert "INSERT OR REPLACE" not in src_rc
