"""Phase 0.6 回归测试：accuracy / value 模块基础回归（内存库）。

验证：
  1. accuracy 表结构创建（含 V1.2 人工内容字段）
  2. content_value 表结构 + 评分可执行
  3. 素材池分类 ABCD 阈值逻辑
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
    fd, path = tempfile.mkstemp(suffix=".db", prefix="av_", dir=str(root))
    import os
    os.close(fd)
    return path


def test_accuracy_schema_has_human_fields():
    from treecut.cognitive.accuracy import AccuracyEngine
    db = _mem_db()
    eng = AccuracyEngine(db)
    conn = sqlite3.connect(db, timeout=10)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(accuracy_review)")}
    conn.close()
    for col in ("human_scene", "human_product", "human_material",
                "human_function", "template_verdict", "truth_reason"):
        assert col in cols, f"accuracy_review 缺列 {col}"


def test_value_schema_and_classify():
    from treecut.cognitive.value import ContentValueEngine
    db = _mem_db()
    eng = ContentValueEngine(db)
    conn = sqlite3.connect(db, timeout=10)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(content_value)")}
    conn.close()
    for col in ("user_value", "product_merit", "trust_value",
                "comm_value", "deal_value", "total_score", "pool_class"):
        assert col in cols, f"content_value 缺列 {col}"


def test_value_pool_classification_thresholds():
    """ABCD 分类阈值：空特征素材按 content_type='' → C/D。"""
    from treecut.cognitive.value import ContentValueEngine
    db = _mem_db()
    eng = ContentValueEngine(db)
    # 空素材（无 ASR/OCR/分类）
    f = {"content_type": "", "elements": [], "evidence": {},
         "asr": "", "ocr": "", "scenes": [], "has_talk": False}
    cls, reason = eng._classify_pool(30.0, f)
    assert cls == "D", f"30分应为D，实际{cls}"
    f2 = {"content_type": "产品介绍", "elements": ["尺寸展示"], "evidence": {},
          "asr": "尺寸2米4 收纳抽屉", "ocr": "", "scenes": [], "has_talk": True}
    cls2, _ = eng._classify_pool(75.0, f2)
    assert cls2 == "A", f"75分有讲解应为A，实际{cls2}"


def test_value_dims_weights():
    """五维权重固定 25/25/20/20/10。"""
    from treecut.cognitive.value import ContentValueEngine
    assert ContentValueEngine.DIM_WEIGHTS == {
        "user_value": 25, "product_merit": 25,
        "trust_value": 20, "comm_value": 20, "deal_value": 10,
    }
