# -*- coding: utf-8 -*-
"""Stage 2 — EvidenceResolverV1：统一证据包（不修改原始 Evidence）。

职责：读取多个 L1/L2 evidence → normalized evidence + reliability + agreement + conflict + missing + provenance。
关键：evidence_family 防同源重复计票（SigLIP component/function/material 同属 SIGLIP family，不算 3 票）。
"""
from __future__ import annotations

import time

# Phase3 字段可信等级 + evidence family
FIELD_RELIABILITY = {
    "people_presence": ("HIGH", "YOLO"),
    "component": ("MEDIUM_HIGH", "SIGLIP"),
    "function": ("MEDIUM_HIGH", "SIGLIP"),
    "product_family": ("MEDIUM", "SIGLIP"),
    "scene_family": ("LOW", "SIGLIP"),
    "product_variant": ("LOW", "SIGLIP"),
    "material": ("LOW", "SIGLIP"),
    "shot_role": ("LOW", "SIGLIP"),
    "action_sequence": ("VERY_LOW", "MOTION_ASR"),  # semantic_action = VERY_LOW
    "semantic_action": ("VERY_LOW", "MOTION_ASR"),
}

# 外部补充来源（若有）
EXTRA_FAMILIES = {"ASR": "ASR", "OCR": "OCR", "MOTION": "MOTION", "HUMAN": "HUMAN", "METADATA": "METADATA"}


class EvidenceResolverV1:
    """Evidence Packet 构建器。"""

    def resolve(self, seg_cog: dict, asr_text: str = "", ocr_text: str = "",
                metadata: dict | None = None) -> dict:
        ev = {}
        for field, val in seg_cog.items():
            if val in (None, "", "UNKNOWN", [], {}):
                continue
            rel, family = FIELD_RELIABILITY.get(field, ("LOW", "SIGLIP"))
            ev[field] = {"value": val, "reliability": rel, "family": family,
                         "provider": family, "source_timestamp": time.time()}
        # 补充来源
        if asr_text and asr_text.strip():
            ev["asr_text"] = {"value": asr_text, "reliability": "MEDIUM", "family": "ASR",
                              "provider": "ASR"}
        if ocr_text and ocr_text.strip():
            ev["ocr_text"] = {"value": ocr_text, "reliability": "MEDIUM", "family": "OCR",
                              "provider": "OCR"}
        # 强制 semantic_action VERY_LOW（Phase3 纪律）
        if "action_sequence" in ev:
            ev["action_sequence"] = {**ev["action_sequence"], "reliability": "VERY_LOW"}

        # family 计数（防同源重复计票）
        family_counts = {}
        for f, e in ev.items():
            fam = e.get("family", "UNKNOWN")
            family_counts[fam] = family_counts.get(fam, 0) + 1

        # 独立来源数（不同 family）
        independent = len([f for f, c in family_counts.items() if c > 0])

        return {
            "normalized_evidence": ev,
            "family_counts": family_counts,
            "independent_sources": independent,
            "provenance": {f: e.get("provider") for f, e in ev.items()},
            "created_at": time.time(),
        }

    def agreement(self, packet: dict, field: str, expected) -> str:
        """判断某 field 证据与期望值的一致状态。"""
        ev = packet["normalized_evidence"].get(field)
        if ev is None:
            return "MISSING"
        val = ev["value"]
        if isinstance(val, list):
            return "AGREE" if expected in val else "DISAGREE"
        return "AGREE" if val == expected else "DISAGREE"
