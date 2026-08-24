"""P2.7: 100 分制人工评分逻辑（家具/小红书岛台内容）。

五维评分（每维 0/10/20）：
  scene    场景识别 20  — 是否正确识别画面（客户家/工厂/展厅/生产/安装/运输/厨房/客厅）
  product  产品识别 20  — 是否正确识别产品（岛台/岩板岛台/餐桌/餐边柜/吧台/厨房柜体）
  function 功能识别 20  — AI 是否理解产品功能（伸缩/展开/抽屉/收纳/轨道插座/隐藏电器）
  value    镜头价值 20  — 是否值得用于视频生产（客户入户/空间展示/产品细节/功能展示）
  business 商业价值 20  — 是否适合获客（客户案例/尺寸展示/价格咨询/装修需求）
"""
from __future__ import annotations

from treecut.quality_validation.store import SCORE_DIMENSIONS

# 每维的可选分数
ALLOWED_SCORES = (0, 10, 20)

# 评分维度中文名与说明
DIMENSION_LABELS = {
    "scene": "场景识别",
    "product": "产品识别",
    "function": "功能识别",
    "value": "镜头价值",
    "business": "商业价值",
}

DIMENSION_DESCRIPTIONS = {
    "scene": "AI 是否正确识别画面（客户家/工厂/展厅/生产/安装/运输/厨房空间/客厅空间）",
    "product": "是否正确识别产品（岛台/岩板岛台/奢石岛台/实木岛台/餐桌/餐边柜/吧台/厨房柜体）",
    "function": "AI 是否理解产品功能（伸缩/展开/收缩/抽屉/薄抽/深抽/收纳/轨道插座/隐藏电器/烤箱位/水吧）",
    "value": "素材是否值得用于视频生产（高价值：客户入户/空间展示/产品细节/功能展示/使用场景；低价值：空镜/重复/模糊/人物挡住产品/无关画面）",
    "business": "是否适合获客（高价值：客户案例/尺寸展示/价格咨询/装修需求/痛点解决；低价值：单纯展示/无信息）",
}

# 分数档位含义
SCORE_MEANING = {
    20: "完全正确/高价值",
    10: "部分正确/中等价值",
    0: "错误/低价值",
}


def validate_scores(scores: dict) -> dict:
    """校验并规范化五维评分。scores: {dimension: 0|10|20}"""
    cleaned = {}
    for dim in SCORE_DIMENSIONS:
        val = scores.get(dim, 0)
        if val not in ALLOWED_SCORES:
            raise ValueError(f"{DIMENSION_LABELS[dim]} 评分必须为 {ALLOWED_SCORES}，收到 {val}")
        cleaned[dim] = val
    cleaned["total"] = sum(cleaned.values())
    return cleaned


def score_to_grade(total: int) -> str:
    """总分 → 等级（用于素材状态建议）。"""
    if total >= 80:
        return "HIGH_VALUE"
    if total >= 60:
        return "READY"
    if total >= 40:
        return "REVIEW"
    return "LOW_VALUE"


def dimension_report(scores: dict) -> dict:
    """返回带说明的评分明细（供 UI 展示）。"""
    cleaned = validate_scores(scores)
    detail = []
    for dim in SCORE_DIMENSIONS:
        detail.append({
            "dimension": dim,
            "label": DIMENSION_LABELS[dim],
            "score": cleaned[dim],
            "meaning": SCORE_MEANING[cleaned[dim]],
            "description": DIMENSION_DESCRIPTIONS[dim],
        })
    return {"total": cleaned["total"], "grade": score_to_grade(cleaned["total"]),
            "dimensions": detail}
