"""Transparent filename pre-classification; model analysis confirms later."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CATEGORY_RULES = {
    "product_display": ("岛台", "产品", "展示", "细节", "功能", "岩板", "台面"),
    "factory_production": ("工厂", "生产", "车间", "加工", "设备", "制造"),
    "installation": ("安装", "施工", "落地", "组装", "调试"),
    "talking_head": ("口播", "讲解", "主播", "人物", "采访", "解说"),
    "customer_case": ("客户", "案例", "交付", "完工", "实拍", "业主", "女士", "小姐", "先生"),
    "interior_space": ("厨房", "客厅", "空间", "室内", "家装", "小户型", "餐厅"),
}


@dataclass(frozen=True)
class PreliminaryCategory:
    category: str
    confidence: float
    matched_words: tuple[str, ...]
    source: str = "filename_rule"


def classify_filename(path: str | Path) -> PreliminaryCategory:
    text = Path(path).stem.lower()
    # Names such as “上海刘女士” describe a delivered customer project. This is
    # business-purpose evidence and must not be outvoted by the visible room type.
    customer_markers = tuple(word for word in CATEGORY_RULES["customer_case"] if word in text)
    if customer_markers:
        return PreliminaryCategory(
            "customer_case", min(0.75, 0.5 + 0.1 * len(customer_markers)), customer_markers,
        )
    # A file explicitly named as a product film remains a product film even when
    # “small apartment” also occurs in the title.
    product_markers = tuple(word for word in ("产品", "岛台", "功能") if word in text)
    if product_markers:
        return PreliminaryCategory(
            "product_display", min(0.75, 0.5 + 0.1 * len(product_markers)), product_markers,
        )
    scores = {
        category: tuple(word for word in words if word.lower() in text)
        for category, words in CATEGORY_RULES.items()
    }
    category, matches = max(scores.items(), key=lambda item: len(item[1]))
    if not matches:
        return PreliminaryCategory("unclassified", 0.0, ())
    confidence = min(0.65, 0.25 + 0.15 * len(matches))
    return PreliminaryCategory(category, confidence, matches)


def resolve_business_category(filename: PreliminaryCategory, vision: dict,
                              objects: dict | None = None) -> dict:
    """Keep business purpose separate from the literal objects visible in one frame."""
    visual_category = str(vision.get("category") or "unclassified")
    visual_confidence = float(vision.get("confidence") or 0.0)
    objects = objects or {}
    object_category = str(objects.get("category") or "unclassified")
    object_confidence = float(objects.get("confidence") or 0.0)
    if filename.category != "unclassified" and filename.confidence >= 0.4:
        return {
            "category": filename.category,
            "confidence": filename.confidence,
            "source": "filename_and_vision" if visual_category == filename.category else "business_filename",
            "visual_category": visual_category,
            "visual_confidence": visual_confidence,
            "object_category": object_category,
            "object_confidence": object_confidence,
        }
    if visual_category == "unclassified" and object_category != "unclassified":
        return {
            "category": object_category, "confidence": object_confidence,
            "source": "object_support", "visual_category": visual_category,
            "visual_confidence": visual_confidence, "object_category": object_category,
            "object_confidence": object_confidence,
        }
    return {
        "category": visual_category,
        "confidence": visual_confidence,
        "source": "vision_model" if visual_category != "unclassified" else "unclassified",
        "visual_category": visual_category,
        "visual_confidence": visual_confidence,
        "object_category": object_category,
        "object_confidence": object_confidence,
    }
