# -*- coding: utf-8 -*-
"""Stage 2 — ConflictResolverV1：证据冲突处理。

例：ASR"客户家" vs scene FACTORY → CONFLICTING_EVIDENCE。
scene 本身 LIMITED → 不能直接信 ASR，也不能强行二选一。
输出：conflict 状态 + 建议（基于 visual context / asset context / reliability / negative rules）。
"""
from __future__ import annotations

CONFLICT_POLICY = {
    "scene_vs_asr": {
        "fields": ["scene_family", "asr_text"],
        "note": "ASR 口语 vs 视觉场景：scene LIMITTED，ASR 口语也可能误；→ UNKNOWN 优先",
    },
    "material_vs_asr": {
        "fields": ["material", "asr_text"],
        "note": "材质弱预测 vs ASR 材质词：需更多证据，不强行二选一",
    },
}


class ConflictResolverV1:
    """检测证据冲突，输出 CONFLICTING_EVIDENCE + 处理建议。"""

    def resolve(self, packet: dict) -> dict:
        conflicts = []
        ev = packet.get("normalized_evidence", {})

        # ASR 场景词 vs 视觉场景
        asr = ev.get("asr_text", {}).get("value", "")
        scene = ev.get("scene_family", {}).get("value")
        if asr and scene:
            home_words = ("客户家", "家里", "入户", "客厅", "卧室")
            if any(w in str(asr) for w in home_words) and scene == "FACTORY":
                conflicts.append({
                    "type": "CONFLICTING_EVIDENCE",
                    "fields": ["scene_family", "asr_text"],
                    "asr_value": str(asr)[:40], "scene_value": scene,
                    "resolution": "CUSTOMER_HOME=UNKNOWN",
                    "reason": "scene LIMITTED 且 ASR 口语（家里/客户）不可作为场景硬证据；不强行二选一",
                })
            if any(w in str(asr) for w in home_words) and scene in ("CUSTOMER_HOME", "SHOWROOM"):
                conflicts.append({
                    "type": "SUPPORTED_EVIDENCE",
                    "fields": ["scene_family", "asr_text"],
                    "asr_value": str(asr)[:40], "scene_value": scene,
                    "resolution": "CONSISTENT（ASR 与视觉场景一致）",
                })

        # 材质弱 vs ASR 材质词
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
                "weak_count": len([c for c in conflicts if c["type"] == "WEAK_EVIDENCE_CONFLICT"])}
