# -*- coding: utf-8 -*-
"""Stage 2.1 — EvidenceStrengthV2：证据强度分级（Evidence Strength Report + Grade）。

每个潜在 Claim 形成 EvidenceStrengthReport：
  claim_category / claim_value
  direct_evidence[] / indirect_evidence[]
  evidence_families[] / independent_family_count
  correlated_evidence_count（同 provider 一致计数）
  highest_reliability
  semantic_consistency / context_support / context_contradiction
  negative_rule_result / conflict_status / semantic_action_dependency
  evidence_grade（A/B/C/D/NONE）
  reason_codes[]

Evidence Family 纪律（保持）：
  SIGLIP component/function/material/product 同 family → 不算独立来源；
  但可提升 semantic_consistency。
  独立来源仅来自不同 family（ASR/OCR/YOLO/HUMAN/METADATA/OTHER）。

Grade 语义（versioned policy，非死数字）：
  A: 可靠直接 Evidence + 独立第二 family 支持 + 无冲突
  B: 一个 MEDIUM_HIGH 以上直接 Evidence + 业务规则强匹配 + 无冲突
  C: 只有同 provider 一致 Evidence，或组件存在 + 间接业务推断
  D: LOW/VERY_LOW、弱关键词、semantic_action 主导
  NONE: 无有效 Evidence
"""
from __future__ import annotations

import time

# 可靠性序（越高越可靠）
RELIABILITY_ORDER = {"VERY_LOW": 0, "LOW": 1, "MEDIUM": 2, "MEDIUM_HIGH": 3, "HIGH": 4}
# 直接证据字段（reliability 达标线）
DIRECT_FIELD_MIN = "MEDIUM_HIGH"


class EvidenceStrengthV2:
    """证据强度分级引擎。"""

    def __init__(self):
        self.grade_policy_version = "EVIDENCE_STRENGTH_V2_POLICY_1"

    # ------------------------------------------------------------------
    def _family_of(self, field: str, ev_meta: dict) -> str:
        return ev_meta.get("family", "SIGLIP")

    def build_report(self, claim_category: str, claim_value: str,
                     packet: dict, required_fields: list[str] | None = None) -> dict:
        """为某个潜在 claim 构建 EvidenceStrengthReport。

        packet = EvidenceResolverV1 输出（normalized_evidence / family_counts / ...）。
        required_fields：该 claim 的证据触发字段（如 STORAGE → ["component","function"]）。
        """
        ev = packet.get("normalized_evidence", {})
        required_fields = required_fields or []

        # ---- direct / indirect ----
        direct, indirect = [], []
        for f, meta in ev.items():
            if f in ("asr_text", "ocr_text"):
                continue  # 文本证据单独处理（context_support）
            if meta.get("reliability", "LOW") in ("MEDIUM_HIGH", "HIGH"):
                direct.append({"field": f, "value": meta.get("value"),
                               "reliability": meta.get("reliability"),
                               "family": self._family_of(f, meta)})
            elif meta.get("reliability", "LOW") in ("MEDIUM", "LOW", "VERY_LOW"):
                indirect.append({"field": f, "value": meta.get("value"),
                                 "reliability": meta.get("reliability"),
                                 "family": self._family_of(f, meta)})

        # ---- families / independent count ----
        families = []
        for f, meta in ev.items():
            fam = self._family_of(f, meta)
            if fam not in families:
                families.append(fam)
        family_counts = packet.get("family_counts", {})
        independent_family_count = packet.get("independent_sources", 0)

        # 同 provider 一致计数（correlated）：SigLIP 内部多字段一致
        siglip_consistent = sum(1 for d in direct + indirect if d["family"] == "SIGLIP")

        # ---- highest reliability ----
        all_rel = [meta.get("reliability", "LOW") for meta in ev.values()]
        highest = max(all_rel, key=lambda r: RELIABILITY_ORDER.get(r, 0)) if all_rel else "NONE"

        # ---- semantic consistency（同 provider 字段与 claim 相关字段一致）----
        semantic_consistency = 0.0
        if required_fields:
            hit = 0
            for f in required_fields:
                if f in ev and ev[f].get("value"):
                    hit += 1
            semantic_consistency = hit / len(required_fields)

        # ---- semantic_action dependency ----
        sa_dep = bool(ev.get("action_sequence") or ev.get("semantic_action"))

        # ---- grade 计算 ----
        grade, reason_codes = self._grade(
            direct=direct, independent_family_count=independent_family_count,
            semantic_consistency=semantic_consistency, sa_dep=sa_dep,
            has_required_component=any(f in required_fields and f in ev
                                       for f in ("component", "function")),
        )

        return {
            "claim_category": claim_category, "claim_value": claim_value,
            "direct_evidence": direct,
            "indirect_evidence": indirect,
            "evidence_families": families,
            "independent_family_count": independent_family_count,
            "correlated_evidence_count": siglip_consistent,
            "highest_reliability": highest,
            "semantic_consistency": round(semantic_consistency, 2),
            "context_support": self._context_support(ev, claim_value),
            "context_contradiction": False,
            "negative_rule_result": "PENDING",
            "conflict_status": "NONE",
            "semantic_action_dependency": sa_dep,
            "evidence_grade": grade,
            "reason_codes": reason_codes,
            "grade_policy_version": self.grade_policy_version,
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
        }

    # ------------------------------------------------------------------
    def _context_support(self, ev: dict, claim_value: str) -> bool:
        """ASR/OCR 文本是否含 claim 相关语义（简单关键词级，供 grade 参考）。"""
        asr = str(ev.get("asr_text", {}).get("value", ""))
        ocr = str(ev.get("ocr_text", {}).get("value", ""))
        text = (asr + " " + ocr).lower()
        kw = {
            "STORAGE": ["收纳", "储物", "放东西", "抽屉收", "柜内储物"],
            "STORAGE_EFFICIENCY": ["增加收纳", "提高利用率", "更多储物", "收纳效率"],
            "CHARGING_POWER": ["充电", "取电", "供电", "插电"],
            "POWER_CONVENIENCE": ["充电方便", "取电方便", "供电方便", "轨道插座"],
            "DINING": ["用餐", "吃饭", "餐桌", "岛台用餐"],
            "DINING_CONVENIENCE": ["用餐方便", "吃饭方便"],
            "OFFICE": ["办公", "写作业", "工作", "书房"],
            "WORK_FROM_HOME": ["居家办公", "在家办公", "办公方便"],
            "GUEST_CAPACITY": ["待客", "多人", "聚会", "扩容"],
            "FLEXIBLE_CAPACITY": ["伸缩", "扩展", "变大", "弹性"],
        }
        return any(w in text for w in kw.get(claim_value, []))

    # ------------------------------------------------------------------
    def _grade(self, direct: list, independent_family_count: int,
               semantic_consistency: float, sa_dep: bool,
               has_required_component: bool) -> tuple[str, list]:
        """Grade 判定（versioned policy）。

        Grade A 的"独立第二 family"必须排除 VERY_LOW family：
        action_sequence/semantic_action（MOTION_ASR，VERY_LOW）不得作为独立支持来源，
        否则"组件+动作"会被误判为双源强证据（语义动作只是辅助线索）。
        """
        rc = []
        # NONE：无任何有效证据
        if not direct and not has_required_component:
            return "NONE", ["NO_VALID_EVIDENCE"]
        # 独立来源数：只计 reliability >= LOW 的 family（排除 VERY_LOW）
        indep_strong = max(0, independent_family_count -
                           (1 if sa_dep else 0)) if sa_dep else independent_family_count
        # A：可靠直接 Evidence + 独立第二 family（非 VERY_LOW）+ 无冲突
        if direct and indep_strong >= 2:
            rc.append("MULTI_FAMILY_DIRECT")
            return "A", rc
        # B：一个 MEDIUM_HIGH 以上直接 Evidence + 业务规则强匹配 + 无冲突
        if direct:
            rc.append("SINGLE_FAMILY_DIRECT")
            return "B", rc
        # C：只有同 provider 一致 Evidence，或组件存在 + 间接业务推断
        if has_required_component:
            rc.append("COMPONENT_ONLY_INFERRED")
            return "C", rc
        # D：LOW/VERY_LOW、弱关键词、semantic_action 主导
        if sa_dep:
            rc.append("SEMANTIC_ACTION_DOMINANT")
        else:
            rc.append("WEAK_KEYWORD_ONLY")
        return "D", rc
