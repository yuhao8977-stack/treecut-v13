# -*- coding: utf-8 -*-
"""P5 测试：模板注册 + 槽位候选推荐 + 选镜保存。"""
from __future__ import annotations

import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in os.sys.path:
    os.sys.path.insert(0, SRC_DIR)


@pytest.fixture()
def isolated_env(tmp_path):
    os.environ["TREECUT_DATA_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("TREECUT_DATA_ROOT", None)


def test_template_definitions():
    from treecut.templates import CT01, CT02, list_templates
    assert CT01["template_id"] == "CT01"
    assert CT02["template_id"] == "CT02"
    assert len(CT01["slots"]) == 8
    assert len(CT02["slots"]) == 9
    # 版本化 + 命名规则（无 B 编号）
    ids = [t["template_id"] for t in list_templates()]
    assert all(tid.startswith("CT") for tid in ids)


def test_template_register(isolated_env):
    from treecut.library import Catalog, AssetsManager
    from treecut.templates import list_templates
    from treecut.templates.engine import TemplateEngine

    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    engine = TemplateEngine(assets=am)
    for t in list_templates():
        engine.register_template(t)
    reg = engine.list_registered()
    assert len(reg) == 2
    # 槽位表
    with engine._connect() as conn:
        n = conn.execute("SELECT COUNT(*) n FROM template_slots").fetchone()["n"]
    assert n == 17  # 8 + 9


def test_recommend_slot(isolated_env):
    from treecut.library import Catalog, AssetsManager
    from treecut.library.classification_store import ClassificationStore
    from treecut.library.processing_state import ProcessingState
    from treecut.library.segments import SegmentStore
    from treecut.templates import CT01
    from treecut.templates.engine import TemplateEngine

    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    ps = ProcessingState(assets=am)
    store = SegmentStore(assets=am)
    cls = ClassificationStore(assets=am)
    engine = TemplateEngine(assets=am)
    engine.register_template(CT01)

    # 造 asset + segment + 标签
    src = isolated_env / "src"
    src.mkdir()
    (src / "v.mp4").write_bytes(os.urandom(1000))
    cat.scan(src)
    am.ensure_all_video_assets()
    aid = am.list_assets(limit=5)[0]["asset_id"]
    store.save_segments(aid, [{"segment_id": "seg1", "scene_no": 0,
                               "start_ms": 0, "end_ms": 3000}])
    cls.save_labels(aid, [{"category": "SCENE", "label": "客户家", "confidence": 0.9,
                           "source": "rule"},
                          {"category": "SHOT", "label": "全景", "confidence": 0.9,
                           "source": "rule"}])
    # 槽位 2（客户家+全景）应命中
    candidates = engine.recommend_slot("CT01", "1.0", 2, top_k=5)
    assert len(candidates) >= 1
    assert candidates[0].segment_id == "seg1"
    assert "必备标签" in candidates[0].reason or "标签命中" in candidates[0].reason


def test_save_selection(isolated_env):
    from treecut.library import Catalog, AssetsManager
    from treecut.templates.engine import TemplateEngine
    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    engine = TemplateEngine(assets=am)
    engine.save_selection("PRJ-TEST-001", "CT01", "1.0", 1, "seg1", "selected", score=0.8)
    with engine._connect() as conn:
        row = conn.execute(
            "SELECT * FROM project_segments WHERE project_id='PRJ-TEST-001'").fetchone()
    assert row["selection_status"] == "selected"
    assert row["segment_id"] == "seg1"
