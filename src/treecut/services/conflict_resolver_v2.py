# -*- coding: utf-8 -*-
"""Stage 2.1 — ConflictResolverV2：仅 ASSERTED 语境触发场景冲突。

修复 V1 过度敏感：ASR 出现"家里/客户家"等词（多为假设/条件/泛例语境）
不再自动产生 CONFLICTING_EVIDENCE。

只有：明确 ASSERTED（"这是客户家"等）+ 另一可靠证据 FACTORY
才允许 CONFLICTING_EVIDENCE。
"""
from __future__ import annotations

from treecut.services.utterance_context import UtteranceContextV1

CONFLICT_POLICY_V2 = {
    "scene_vs_asr": {
        "fields": ["scene_family", "asr_text"],
        "note": "仅 ASSERTED 语境 + FACTORY 才冲突；HYPOTHETICAL/CONDITIONAL/QUOTED 不冲突",
    },
    "material_vs_asr": {
        "fields": ["material", "asr_text"],
        "note": "材质弱预测 vs ASR 材质词：需更多证据，不强行二选一",
    },
}


class ConflictResolverV2:
    """V2 冲突检测：语境感知。"""

    def __init__(self):
        self.uc = UtteranceContextV1()

    def resolve(self, packet: dict) -> dict:
        conflicts = []
        ev = packet.get("normalized_evidence", {})

        # ---- ASR 场景词 vs 视觉场景（仅 ASSERTED）----
        asr = ev.get("asr_text", {}).get("value", "")
        scene = ev.get("scene_family", {}).get("value")
        if asr and scene:
            ctx = self.uc.classify(asr)
            if ctx["context"] == "ASSERTED" and scene == "FACTORY":
                conflicts.append({
                    "type": "CONFLICTING_EVIDENCE",
                    "fields": ["scene_family", "asr_text"],
                    "asr_value": str(asr)[:40], "scene_value": scene,
                    "utterance_context": "ASSERTED",
                    "resolution": "CUSTOMER_HOME=UNKNOWN",
                    "reason": "明确断言客户家 + 工厂场景 → 冲突，不强行二选一",
                })
            elif ctx["context"] in ("HYPOTHETICAL", "CONDITIONAL", "GENERIC_EXAMPLE", "QUOTED", "NEGATED"):
                conflicts.append({
                    "type": "NON_ASSERTED_CONTEXT",
                    "fields": ["asr_text"],
                    "asr_value": str(asr)[:40],
                    "utterance_context": ctx["context"],
                    "matched": ctx["matched"],
                    "resolution": "NO_CONFLICT（假设/条件/泛例语境，非场景断言）",
                    "reason": "话语为假设/条件/泛例，不得作为 CURRENT_CONTEXT=HOME 断言，"
                             "也不得与 FACTORY 产生冲突",
                })
            elif ctx["context"] == "ASSERTED" and scene in ("CUSTOMER_HOME", "SHOWROOM"):
                conflicts.append({
                    "type": "SUPPORTED_EVIDENCE",
                    "fields": ["scene_family", "asr_text"],
                    "asr_value": str(asr)[:40], "scene_value": scene,
                    "resolution": "CONSISTENT（ASR 与视觉场景一致）",
                })

        # ---- 材质弱 vs ASR 材质词（保留 V1 逻辑）----
        mat = ev.get("material", {}).get("value")
        mat_rel = ev.get("material", {}).get("reliability", "LOW")
        if mat and mat_rel == "LOW" and asr:
            mat_words = ("实木", "原木", "大理石", "奢石", "不锈钢", "玻璃", "黑胡桃")
            if any(w in str(asr) for w in mat_words):
                conflicts.append({
                    "type": "WEAK_EVIDENCE_CONFLICT",
                    "fields": ["material", "asr_text"],
                    "material_value": str(mat)[:30], "asr_value": str(asr)[:40],
                    "resolution": "MATERIAL_CLAIM=WEAK/UNKNOWN",
                    "reason": "material 弱预测 + ASR 材质词 ≠ 实体材质断言（NR003）",
                })

        return {"conflicts": conflicts,
                "conflict_count": len([c for c in conflicts if c["type"] == "CONFLICTING_EVIDENCE"]),
                "supported_count": len([c for c in conflicts if c["type"] == "SUPPORTED_EVIDENCE"]),
                "weak_count": len([c for c in conflicts if c["type"] == "WEAK_EVIDENCE_CONFLICT"]),
                "non_asserted_count": len([c for c in conflicts if c["type"] == "NON_ASSERTED_CONTEXT"])}
