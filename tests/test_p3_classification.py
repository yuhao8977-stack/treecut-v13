# -*- coding: utf-8 -*-
"""P3 单元/集成测试：成片/原片分类 + 标签 + 人工纠错 + 重复分组。"""
from __future__ import annotations

import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in os.sys.path:
    os.sys.path.insert(0, SRC_DIR)

from treecut.library import Catalog, AssetsManager
from treecut.library.classification_store import ClassificationStore
from treecut.library.processing_state import ProcessingState


@pytest.fixture()
def isolated_env(tmp_path):
    os.environ["TREECUT_DATA_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("TREECUT_DATA_ROOT", None)


@pytest.fixture()
def env(isolated_env):
    db = os.path.join(isolated_env, "materials.db")
    cat = Catalog(db_path=db)
    am = AssetsManager(catalog=cat)
    ps = ProcessingState(assets=am)
    cls = ClassificationStore(assets=am)
    src = isolated_env / "src"
    src.mkdir()
    (src / "客户家_伸缩岛台_全景.mp4").write_bytes(os.urandom(1000))
    cat.scan(src)
    am.ensure_all_video_assets()
    ps.ensure_asset_stages_all()
    return cat, am, ps, cls, src


def test_asset_type_classifier_rules():
    from treecut.classify.asset_type import classify_asset_type
    # 成片特征
    t, c, r = classify_asset_type(
        duration_sec=35.0, scene_count=12, hard_subtitle_ratio=0.8,
        has_speech=True, has_music=True, text_items=30, cut_rate=0.34)
    assert t == "FINISHED"
    assert c >= 0.5
    assert "hard_subtitle" in r
    # 长原片特征
    t2, c2, r2 = classify_asset_type(
        duration_sec=600.0, scene_count=3, hard_subtitle_ratio=0.0,
        has_speech=False, has_music=False, text_items=0, cut_rate=0.005)
    assert t2 == "RAW"


def test_classification_store_schema(env):
    cat, am, ps, cls, src = env
    aid = am.list_assets(limit=5)[0]["asset_id"]
    cls.save_asset_type(aid, "FINISHED", 0.85, "hard_subtitle,speech")
    row = cls.get_asset_type(aid)
    assert row["asset_type"] == "FINISHED"


def test_labels_human_override(env):
    cat, am, ps, cls, src = env
    aid = am.list_assets(limit=5)[0]["asset_id"]
    # 模型标签
    cls.save_labels(aid, [{"category": "SCENE", "label": "客户家", "confidence": 0.6,
                           "source": "model"}])
    # 人工纠错：修正
    cls.save_human_label(aid, "客户家", category="SCENE")
    labels = cls.list_labels(asset_id=aid)
    human = [l for l in labels if l["source"] == "human"]
    model = [l for l in labels if l["source"] == "model"]
    assert human and human[0]["human_override"] == 1
    assert human[0]["label"] == "客户家"
    # 模型再次保存同标签不应覆盖 human
    cls.save_labels(aid, [{"category": "SCENE", "label": "客户家", "confidence": 0.2,
                           "source": "model"}])
    again = cls.list_labels(asset_id=aid)
    human_again = [l for l in again if l["source"] == "human"]
    assert human_again and human_again[0]["confidence"] == 1.0  # 未被模型覆盖


def test_duplicate_group(env):
    cat, am, ps, cls, src = env
    cls.save_duplicate_group("grp1", ["a1", "a2"], "exact", 1.0)
    groups = cls.list_duplicate_groups()
    assert len(groups) == 1
    assert groups[0]["asset_ids"] == ["a1", "a2"]


def test_p3_worker_lifecycle(env):
    from treecut.analysis.p3_worker import P3Worker
    cat, am, ps, cls, src = env
    worker = P3Worker(assets=am)
    result = worker.run(limit=5)
    assert result.scanned >= 1
    assets = am.list_assets(limit=5)
    aid = assets[0]["asset_id"]
    # 文件名含 "客户家/伸缩岛台/全景" → 规则标签应命中
    labels = cls.list_labels(asset_id=aid)
    tag_names = {l["label"] for l in labels}
    assert "客户家" in tag_names or "伸缩" in tag_names or "全景" in tag_names
    # 幂等：重跑 SKIP
    decision = ps.should_process(aid, "labels", pipeline_version="P3.1")
    assert decision == "SKIP_ALREADY_DONE"
