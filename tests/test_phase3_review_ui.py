# -*- coding: utf-8 -*-
"""Phase 3 人工审核 UI — 校验逻辑测试（冻结期安全：不触碰认知逻辑）。"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from treecut.services.phase3_review_ui import validate_v21

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")


def test_confidence_required():
    ok, msg, _ = validate_v21({"scene_family": "FACTORY"}, "", "REVIEWED")
    assert ok is False and "置信度" in msg


def test_status_required():
    ok, msg, _ = validate_v21({"scene_family": "FACTORY"}, "MEDIUM", "")
    assert ok is False and "状态" in msg


def test_empty_reviewed_rejected():
    ok, msg, status = validate_v21({}, "MEDIUM", "REVIEWED")
    assert ok is False
    assert status == "NEEDS_SECOND_REVIEW"


def test_multilabel_values_count():
    values = {"scene_family": "FACTORY", "scene_subtype": "FACTORY_SHOWROOM",
              "product_family": "ISLAND", "product_variant": "EXTENDABLE_ISLAND",
              "material": ["岩板", "实木"], "component": ["DRAWER", "TRACK_SOCKET"],
              "function": ["STORAGE", "POWER"], "action_group": "EXTEND",
              "action_sequence": ["PULL_OUT", "RETRACT"], "shot_scale": "MEDIUM",
              "shot_role": ["PERSON_TALKING", "FUNCTION_DEMO"],
              "people_presence": "YES"}
    ok, msg, status = validate_v21(values, "HIGH", "REVIEWED")
    assert ok is True and status == "REVIEWED"


def test_unplayable_excluded():
    ok, msg, status = validate_v21({}, "MEDIUM", "EXCLUDED", "视频无法播放 UNPLAYABLE")
    assert ok is True and status == "EXCLUDED"


def test_review_tables_exist():
    db = Path(DATA_ROOT) / "database" / "materials.db"
    conn = sqlite3.connect("file:" + str(db).replace("\\", "/") + "?mode=ro", uri=True)
    for t in ("human_annotation_v3", "targeted_human_review_v1"):
        n = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()[0]
        assert n == 1, f"{t} 缺失"
    conn.close()


def test_manifests_present():
    for f in ("THIRD_ADJUDICATION_V1.json", "TARGETED_REVIEW_BATCH_V1.json"):
        p = Path(DATA_ROOT) / f
        assert p.exists(), f
        d = json.loads(p.read_text(encoding="utf-8"))
        assert "segments" in d
