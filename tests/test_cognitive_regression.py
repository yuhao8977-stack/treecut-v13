"""Phase 0.6 回归测试：cognitive 模块基础回归。

使用内存 SQLite（不触碰生产库），验证：
  1. 认知表结构创建（CognitiveStore.ensure_schema）
  2. 行业分类（IndustryEngine._classify_content_v2 双层结构）
  3. 场景修正（_correct_scenes 工厂规则）
  4. 内容元素识别
  5. 产品组合识别（材质+岛台）
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


def _mem_db() -> str:
    """临时文件库（E 盘可写；CognitiveStore 用普通连接，需真实文件路径）。"""
    import tempfile
    root = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\p0_tests")
    root.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".db", prefix="cog_", dir=str(root))
    import os
    os.close(fd)
    return path


def test_store_schema_creates_tables():
    from treecut.cognitive.store import CognitiveStore
    db = _mem_db()
    store = CognitiveStore(db)
    store.ensure_schema()
    conn = sqlite3.connect(db, timeout=10)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for t in ("scene_semantics", "knowledge_entries", "content_classification",
              "account_dna", "content_templates", "learning_rules"):
        assert t in tables, f"缺少表 {t}"


def test_classify_v2_double_layer():
    """V2 双层分类：产品介绍主类型 + 元素。"""
    from treecut.cognitive.industry import IndustryEngine, CONTENT_TYPE_RULES
    db = _mem_db()
    eng = IndustryEngine(db)
    text = "这款岛台用的是岩板台面 尺寸是2米4 收纳抽屉非常顺滑"
    main_type, conf, elements, evidence = eng._classify_content_v2(text, text)
    assert main_type in ("产品介绍", "产品展示", "功能展示")
    assert conf > 0.2
    assert isinstance(elements, list)
    assert "功能展示" in elements or "材质展示" in elements or "尺寸展示" in elements


def test_classify_v2_customer_case_needs_strong_evidence():
    """客户案例需 ≥2 强证据；称呼词不构成证据。"""
    from treecut.cognitive.industry import IndustryEngine
    db = _mem_db()
    eng = IndustryEngine(db)
    # 只有客户称呼词 → 不应判客户案例
    text = "李女士委托我们定制了一款岛台 颜色很好看"
    main_type, _, _, _ = eng._classify_content_v2(text, text)
    assert main_type != "客户案例"
    # 完工+实景双证据 → 客户案例
    text2 = "客户家完工交付 实景效果很好 已经装好了"
    main2, _, _, _ = eng._classify_content_v2(text2, text2)
    assert main2 == "客户案例"


def test_correct_scenes_factory_show():
    """工厂内产品空镜 → 只判工厂，移除安装现场。"""
    from treecut.cognitive.industry import IndustryEngine
    db = _mem_db()
    eng = IndustryEngine(db)
    scenes = [{"name": "安装现场", "score": 0.8}, {"name": "展厅", "score": 0.6}]
    texts = {"path": "【工厂】产品类01\\空镜\\DJI_0001.MP4",
             "asr": "", "vision": "", "ocr": ""}
    out = eng._correct_scenes(scenes, texts, texts["path"])
    assert len(out) == 1
    assert out[0]["name"] == "工厂"


def test_compose_products_material_combo():
    """材质+岛台 → 细粒度产品。"""
    from treecut.cognitive.industry import IndustryEngine
    db = _mem_db()
    eng = IndustryEngine(db)
    products = [{"name": "岛台", "score": 1.0}]
    materials = [{"name": "岩板", "score": 1.0}]
    out = eng._compose_products(products, materials, "岩板岛台 伸缩")
    names = [p["name"] for p in out]
    assert "岩板岛台" in names


def test_simplify_traditional():
    """繁简归一化覆盖行业高频字。"""
    from treecut.cognitive.industry import simplify_traditional
    assert simplify_traditional("伸縮") == "伸缩"
    assert simplify_traditional("飽抽") == "饱抽"
    assert simplify_traditional("顏色") == "颜色"
