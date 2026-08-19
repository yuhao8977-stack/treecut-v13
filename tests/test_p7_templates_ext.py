# -*- coding: utf-8 -*-
"""P7 测试：CT03-CT12 模板扩展注册。"""
from __future__ import annotations

import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in os.sys.path:
    os.sys.path.insert(0, SRC_DIR)


def test_all_12_templates_defined():
    from treecut.templates import TEMPLATES, list_templates
    assert len(TEMPLATES) == 12
    ids = {t["template_id"] for t in list_templates()}
    assert ids == {f"CT{i:02d}" for i in range(1, 13)}
    # 命名规则：全部 CT 前缀，无 B 编号
    assert all(tid.startswith("CT") for tid in ids)


def test_each_template_valid():
    from treecut.templates import list_templates
    for t in list_templates():
        assert t["version"] == "1.0"
        assert t.get("slots") and len(t["slots"]) >= 5
        for slot in t["slots"]:
            assert slot["order"] >= 1
            assert slot["min_duration"] < slot["max_duration"] or slot["min_duration"] == slot["max_duration"]
            # 语义查询或标签约束至少其一
            assert ("semantic_query" in slot and slot.get("semantic_query")) or \
                   slot.get("required_tags") or slot.get("preferred_tags")


@pytest.fixture()
def isolated_env(tmp_path):
    os.environ["TREECUT_DATA_ROOT"] = str(tmp_path)
    yield tmp_path
    os.environ.pop("TREECUT_DATA_ROOT", None)


def test_register_all(isolated_env):
    from treecut.library import Catalog, AssetsManager
    from treecut.templates import list_templates
    from treecut.templates.engine import TemplateEngine
    cat = Catalog(db_path=os.path.join(isolated_env, "materials.db"))
    am = AssetsManager(catalog=cat)
    engine = TemplateEngine(assets=am)
    for t in list_templates():
        engine.register_template(t)
    reg = engine.list_registered()
    assert len(reg) == 12
    with engine._connect() as conn:
        n = conn.execute("SELECT COUNT(*) n FROM template_slots").fetchone()["n"]
    # 总槽位数 = CT01:8 + CT02:9 + CT03:6 + CT04:7 + CT05:6 + CT06:7
    #             + CT07:6 + CT08:6 + CT09:6 + CT10:5 + CT11:6 + CT12:6 = 78
    assert n == 78
