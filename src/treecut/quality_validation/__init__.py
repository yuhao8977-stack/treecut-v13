"""P2.7: 质量验证系统（quality_validation）。

模块组成：
  store.py        — 数据库（human_feedback / broken_assets / asset_quality / asset_status）
  scoring.py      — 100 分评分逻辑
  sampler.py      — 抽检机制（随机 + 分类覆盖）
  report.py       — 报告生成（AI 准确率 / OCR / BROKEN）
  ui.py           — tkinter 人工审核界面
  industry_tags.json — 家具行业标签库
"""
from __future__ import annotations

from treecut.quality_validation.store import (
    QualityValidationStore, ASSET_STATUS,
    VERDICT_CORRECT, VERDICT_PARTIAL, VERDICT_WRONG,
    SCORE_DIMENSIONS,
)

__all__ = [
    "QualityValidationStore", "ASSET_STATUS",
    "VERDICT_CORRECT", "VERDICT_PARTIAL", "VERDICT_WRONG",
    "SCORE_DIMENSIONS",
]
