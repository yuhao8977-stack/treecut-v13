"""Shared object-detection evidence rules for the active Florence detector."""
from __future__ import annotations


OBJECT_BUSINESS_TERMS = {
    "person": ("人物",),
    "dining table": ("餐桌", "桌面", "室内空间"),
    "chair": ("椅子", "室内空间"),
    "couch": ("沙发", "客厅", "室内空间"),
    "sink": ("水槽", "厨房", "室内空间"),
    "oven": ("烤箱", "厨房", "室内空间"),
    "refrigerator": ("冰箱", "厨房", "室内空间"),
    "bed": ("床", "卧室", "室内空间"),
    "potted plant": ("绿植", "室内空间"),
    "cell phone": ("手机", "屏幕"),
    "mobile phone": ("手机", "屏幕"),
    "laptop": ("电脑", "屏幕"),
    "tv": ("电视", "屏幕"),
    "kitchen island": ("岛台", "产品展示", "室内空间"),
    "cabinet": ("柜体", "产品展示", "室内空间"),
    "countertop": ("台面", "产品展示", "室内空间"),
}

INTERIOR_OBJECTS = {
    "dining table", "chair", "couch", "sink", "oven", "refrigerator", "bed",
    "potted plant", "kitchen island", "cabinet", "countertop",
}
SCREEN_OBJECTS = {"cell phone", "mobile phone", "laptop"}


def assess_detections(detections: list[dict], confidence: float = 0.45) -> dict:
    accepted = [item for item in detections if float(item.get("confidence") or 0) >= confidence]
    labels = tuple(dict.fromkeys(
        str(item.get("class") or "").lower() for item in accepted if item.get("class")
    ))
    terms = tuple(dict.fromkeys(
        term for label in labels for term in OBJECT_BUSINESS_TERMS.get(label, ())
    ))
    interior_hits = [
        item for item in accepted
        if str(item.get("class") or "").lower() in INTERIOR_OBJECTS
    ]
    if interior_hits:
        category = "interior_space"
        category_confidence = min(0.72, 0.38 + 0.06 * len(interior_hits))
    else:
        category, category_confidence = "unclassified", 0.0
    screen = [
        item for item in accepted
        if str(item.get("class") or "").lower() in SCREEN_OBJECTS
        and float(item.get("confidence") or 0) >= 0.85
    ]
    return {
        "accepted_labels": labels,
        "business_terms": terms,
        "category": category,
        "confidence": round(category_confidence, 4),
        "needs_review": bool(screen),
        "review_reasons": tuple(f"screen_device:{item['class']}" for item in screen),
        "rule_version": "object_business_v2_florence",
    }


def combine_review_evidence(vision_risk: dict, object_assessment: dict) -> dict:
    reasons = list(dict.fromkeys(
        list(vision_risk.get("matched_risk_words") or ())
        + list(object_assessment.get("review_reasons") or ())
    ))
    needs_review = bool(vision_risk.get("needs_review") or object_assessment.get("needs_review"))
    return {"eligible_for_auto_edit": not needs_review, "needs_review": needs_review,
            "reasons": reasons}
