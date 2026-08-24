"""P2.7: feedback_learning — 反馈学习接口（未来扩展预留）。

作用：收集人工修改（human_feedback），未来用于：
  - 优化标签排序（AI 标签 vs 人工标签差异学习）
  - 优化素材推荐（High Value 素材加权）
  - 优化模板匹配（人工确认的场景/产品标签反哺）

当前实现：从 human_feedback 表读取反馈数据，提供学习用的特征视图。
未来可接入：标签排序模型、推荐权重、模板匹配参数。
"""
from __future__ import annotations

import sqlite3
import time
from collections import Counter
from contextlib import closing
from pathlib import Path


class FeedbackLearning:
    """反馈学习接口 — 读取人工反馈，输出可学习特征。"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)

    def _connect(self):
        connection = sqlite3.connect("file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def correction_stats(self) -> dict:
        """AI 标签 vs 人工标签差异统计（学习信号）。"""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT ai_type, verdict, COUNT(*) n FROM human_feedback "
                "GROUP BY ai_type, verdict").fetchall()
            corrections = connection.execute(
                "SELECT ai_type, ai_label, human_label FROM human_feedback "
                "WHERE human_label != '' AND human_label != ai_label").fetchall()
        stats = {"by_type_verdict": {}, "corrections": []}
        for r in rows:
            stats["by_type_verdict"].setdefault(r["ai_type"], {})[r["verdict"]] = r["n"]
        for r in corrections[:100]:
            stats["corrections"].append({
                "ai_type": r["ai_type"], "ai_label": r["ai_label"],
                "human_label": r["human_label"],
            })
        return stats

    def label_confusion(self, ai_type: str = "scene") -> dict:
        """标签混淆矩阵（AI → 人工），用于发现系统性误判。"""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT ai_label, human_label, COUNT(*) n FROM human_feedback "
                "WHERE ai_type=? AND human_label != '' GROUP BY ai_label, human_label",
                (ai_type,)).fetchall()
        confusion: dict = {}
        for r in rows:
            confusion.setdefault(r["ai_label"] or "(空)", {})[r["human_label"]] = r["n"]
        return confusion

    def high_value_candidates(self, top_k: int = 50) -> list[dict]:
        """基于人工评分推荐高价值素材（供未来模板/推荐系统）。"""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT asset_id, total_score FROM asset_quality "
                "ORDER BY total_score DESC LIMIT ?", (top_k,)).fetchall()
        return [dict(r) for r in rows]
