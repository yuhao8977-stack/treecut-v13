# -*- coding: utf-8 -*-
"""Stage 2.1 — BusinessCognitionServiceV2_1：Claim Gating + Confidence Calibration。

基于 V3 Calibration 结论：
  - STORAGE / STORAGE_EFFICIENCY Gate 收紧（V3: 2 TRUE / 1 OVERCONFIDENT / 2 FALSE）
  - 6 个 V3 未见错误的标签（CHARGING_POWER/DINING/OFFICE/POWER_CONVENIENCE/
    DINING_CONVENIENCE/WORK_FROM_HOME）仅做通用 EvidenceStrength 表达，不大改规则
  - 多档 ClaimStatus：CONFIRMED / SUPPORTED / CANDIDATE / WEAK / UNKNOWN / BLOCKED
  - Need→Value 解耦（NEED_VALUE_DERIVATION_GATE）
  - Power component-only → CANDIDATE
  - semantic_action 仍 VERY_LOW
  - UtteranceContext 修复冲突（假设语境不触发 scene conflict）

纪律：
  - 不改 Knowledge Snapshot V1.2 / AI_LOCK / Phase3 Human Truth / Fresh Holdout
  - V3 = KNOWN_CALIBRATION_DEV_SET（可分析，不可报新性能）
"""
from __future__ import annotations

import time

from treecut.services.evidence_resolver import EvidenceResolverV1
from treecut.services.conflict_resolver_v2 import ConflictResolverV2
from treecut.services.evidence_strength_v2 import EvidenceStrengthV2

KNOWLEDGE_VERSION = "KNOWLEDGE_BRAIN_V2_STAGE2_1"

# ======================================================================
# Claim 状态映射（多档）
# ======================================================================
# SUPPORTED 需要 Grade A/B；CANDIDATE 需要 Grade B/C 但 Segment 不足以证明；
# WEAK 需要 Grade D 或弱冲突；UNKNOWN 无足够信息；BLOCKED 负规则阻断。

# STORAGE Gate V2（V3 证明 NEEDS_REWORK）：
#   禁止 DRAWER only → STORAGE SUPPORTED；禁止组件 → STORAGE_EFFICIENCY SUPPORTED
STORAGE_ASR_WORDS = ("收纳", "储物", "放东西", "抽屉收", "柜内储物")
STORAGE_EFF_ASR_WORDS = ("增加收纳", "提高利用率", "更多储物", "收纳效率", "空间利用率")
# 明确供电/充电语境（POWER SUPPORTED 需要）
POWER_ASR_WORDS = ("充电", "取电", "供电", "插电")
# 假设语境（不触发场景冲突）
HYPOTHETICAL_MARKERS = ("如果", "假如", "要是", "比如", "比如说", "有宝宝的话",
                        "家里如果", "客户如果", "假设", "以后如果")


def _field_vals(ev, *names):
    out = []
    for n in names:
        v = ev.get(n, {}).get("value")
        if isinstance(v, list):
            out.extend(v)
        elif v:
            out.append(v)
    return out


class BusinessCognitionServiceV2_1:
    """V2.1：多档 Claim Status + 证据分级 + Storage/Power Gate。"""

    def __init__(self, knowledge_service=None, evidence_resolver=None,
                 conflict_resolver=None, evidence_strength=None):
        if knowledge_service is None:
            from treecut.services.knowledge_service import KnowledgeService
            knowledge_service = KnowledgeService()
        self.ks = knowledge_service
        self.er = evidence_resolver or EvidenceResolverV1()
        self.cr = conflict_resolver or ConflictResolverV2()
        self.es = evidence_strength or EvidenceStrengthV2()

    # ------------------------------------------------------------------
    def _build_claim(self, segment_id, category, value, status, grade, report,
                     rule_id=None, evidence_refs=None, reason_codes=None):
        return {
            "claim_id": f"CL-{segment_id[:8]}-{category}-{value}",
            "claim_category": category, "claim_value": value,
            "context_scope": "SEGMENT_SCOPE",
            "claim_status": status,
            "confidence": {"CONFIRMED": "HIGH", "SUPPORTED": "MEDIUM_HIGH",
                           "CANDIDATE": "LOW_MEDIUM", "WEAK": "LOW",
                           "UNKNOWN": "UNKNOWN", "BLOCKED": "BLOCKED"}.get(status, "LOW"),
            "evidence_grade": grade,
            "evidence_refs": evidence_refs or [],
            "rule_refs": [rule_id] if rule_id else [],
            "reason_codes": reason_codes or [],
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
        }

    # ------------------------------------------------------------------
    def _storage_gate(self, ev, report) -> tuple[str, list]:
        """STORAGE Gate V2：决定 STORAGE claim 状态。

        PATH A: DRAWER/CABINET + function STORAGE + Grade >= B → SUPPORTED
        PATH B: DRAWER/CABINET + ASR/OCR 明确收纳语义 → SUPPORTED
        PATH C: 明确视觉内容 + 可靠 function → SUPPORTED（semantic_action 不单独满足）
        只有组件 → CANDIDATE；更弱 → WEAK/UNKNOWN
        """
        comp = _field_vals(ev, "component")
        func = _field_vals(ev, "function")
        asr = str(ev.get("asr_text", {}).get("value", ""))
        has_drawer_cabinet = any(c in comp for c in ("DRAWER", "CABINET_DOOR"))
        has_storage_func = "STORAGE" in func
        grade = report.get("evidence_grade", "NONE")
        rc = []

        if not has_drawer_cabinet:
            return "UNKNOWN", ["NO_STORAGE_COMPONENT"]
        # PATH B：ASR 明确收纳语义（最强路径）
        if any(w in asr for w in STORAGE_ASR_WORDS):
            rc.append("STORAGE_PATH_B_ASR")
            return "SUPPORTED", rc
        # PATH A：组件 + function + grade >= B
        #   语境校验：ASR 非空但完全无收纳语义（如讲工艺/风格）→ 降级 CANDIDATE
        #   （镜头实际表达的不是收纳，组件+function 只是"潜在能力"）
        if has_storage_func and grade in ("A", "B"):
            if asr.strip() and not report.get("context_support"):
                rc.append("STORAGE_ASR_DIVERGENT")
                return "CANDIDATE", rc
            rc.append("STORAGE_PATH_A_FUNC_GRADE")
            return "SUPPORTED", rc
        # PATH C：仅 function（无 ASR、无独立 family）→ grade 可能 C
        if has_storage_func and grade == "C":
            rc.append("STORAGE_PATH_C_FUNC_ONLY")
            return "CANDIDATE", rc
        # 仅组件无 function → CANDIDATE（V3 核心修复）
        if has_drawer_cabinet and not has_storage_func:
            rc.append("STORAGE_COMPONENT_ONLY")
            return "CANDIDATE", rc
        # 更弱
        if grade in ("D", "NONE"):
            rc.append("STORAGE_WEAK_EVIDENCE")
            return "WEAK", rc
        return "CANDIDATE", rc

    # ------------------------------------------------------------------
    def _storage_efficiency_gate(self, ev, storage_status: str, report) -> tuple[str, list]:
        """STORAGE_EFFICIENCY 更高门槛：即使 STORAGE=SUPPORTED 也不自动升级。"""
        asr = str(ev.get("asr_text", {}).get("value", ""))
        func = _field_vals(ev, "function")
        grade = report.get("evidence_grade", "NONE")
        # 额外业务证据：ASR 明确表达效率提升，或多存储区/组织化使用
        if any(w in asr for w in STORAGE_EFF_ASR_WORDS):
            return "SUPPORTED", ["STORAGE_EFF_ASR_EXPLICIT"]
        # multiple storage zones（多组件储物）—— 需要 ASR/语境支持效率语义
        comp = _field_vals(ev, "component")
        storage_parts = [c for c in comp if c in ("DRAWER", "CABINET_DOOR", "COUNTERTOP")]
        if (len(storage_parts) >= 2 and storage_status == "SUPPORTED"
                and grade in ("A", "B") and report.get("context_support")):
            return "SUPPORTED", ["STORAGE_EFF_MULTI_ZONE"]
        # 否则最多 CANDIDATE（"可以储物" ≠ "储物效率高"）
        if storage_status in ("SUPPORTED", "CANDIDATE"):
            return "CANDIDATE", ["STORAGE_EFF_DERIVED_ONLY"]
        return "UNKNOWN", ["NO_STORAGE_BASE"]

    # ------------------------------------------------------------------
    def _power_gate(self, ev, report) -> tuple[str, list]:
        """POWER Gate：TRACK_SOCKET alone → CANDIDATE；有 function/ASR 供电语义 → SUPPORTED。"""
        comp = _field_vals(ev, "component")
        func = _field_vals(ev, "function")
        asr = str(ev.get("asr_text", {}).get("value", ""))
        has_socket = "TRACK_SOCKET" in comp
        if not has_socket:
            return "UNKNOWN", ["NO_SOCKET"]
        power_func = any(f in func for f in ("POWER", "OFFICE", "SMALL_APPLIANCE"))
        power_asr = any(w in asr for w in POWER_ASR_WORDS)
        grade = report.get("evidence_grade", "NONE")
        if (power_func or power_asr) and grade in ("A", "B"):
            return "SUPPORTED", ["POWER_FUNC_OR_ASR_GRADE_AB"]
        if power_func and grade == "C":
            return "CANDIDATE", ["POWER_FUNC_ONLY_GRADE_C"]
        if has_socket:  # component-only → CANDIDATE（V3 纪律）
            return "CANDIDATE", ["POWER_COMPONENT_ONLY"]
        return "UNKNOWN", ["NO_POWER_EVIDENCE"]

    # ------------------------------------------------------------------
    def _generic_gate(self, ev, claim_value, required_comp, required_func, report,
                      asr_words=None) -> tuple[str, list]:
        """通用路径：组件 + 匹配 function + Grade>=B → SUPPORTED；组件 only → CANDIDATE。"""
        comp = _field_vals(ev, "component")
        func = _field_vals(ev, "function")
        asr = str(ev.get("asr_text", {}).get("value", ""))
        has_comp = any(c in comp for c in (required_comp or []))
        has_func = required_func in func if required_func else True
        grade = report.get("evidence_grade", "NONE")
        rc = []
        if asr_words and any(w in asr for w in asr_words):
            rc.append("ASR_EXPLICIT")
            return "SUPPORTED", rc
        if has_comp and has_func and grade in ("A", "B"):
            rc.append("COMP_FUNC_GRADE_AB")
            return "SUPPORTED", rc
        if has_comp and has_func:
            rc.append("COMP_FUNC_LOWER_GRADE")
            return "CANDIDATE", rc
        if has_comp and not has_func:
            rc.append("COMPONENT_ONLY")
            return "CANDIDATE", rc
        return "UNKNOWN", ["NO_COMPONENT"]

    # ------------------------------------------------------------------
    def cognize(self, segment_id: str, seg_cog: dict, asr_text: str = "",
                ocr_text: str = "", asset_id: str = "") -> dict:
        packet = self.er.resolve(seg_cog, asr_text, ocr_text)
        conflicts = self.cr.resolve(packet)
        ev = packet["normalized_evidence"]
        claims = []
        reports = {}

        def add_claim(cat, val, status, grade, report, rule_id, rc):
            claims.append(self._build_claim(segment_id, cat, val, status, grade, report,
                                            rule_id=rule_id, reason_codes=rc))

        # ---- USER_NEEDS ----
        # STORAGE（V3 重点修复）
        rep = self.es.build_report("USER_NEED", "STORAGE", packet,
                                   required_fields=["component", "function"])
        reports["STORAGE"] = rep
        st, rc = self._storage_gate(ev, rep)
        add_claim("USER_NEED", "STORAGE", st, rep["evidence_grade"], rep, "GATE_STORAGE_V2", rc)

        # CHARGING_POWER（V3 4/4 TRUE，保持路径，通用表达）
        rep = self.es.build_report("USER_NEED", "CHARGING_POWER", packet,
                                   required_fields=["component", "function"])
        reports["CHARGING_POWER"] = rep
        st, rc = self._power_gate(ev, rep)
        add_claim("USER_NEED", "CHARGING_POWER", st, rep["evidence_grade"], rep,
                  "GATE_POWER_V2", rc)

        # GUEST_CAPACITY（UNTESTED_IN_V3，保持原路径，不加码）
        rep = self.es.build_report("USER_NEED", "GUEST_CAPACITY", packet,
                                   required_fields=["component", "function"])
        reports["GUEST_CAPACITY"] = rep
        st, rc = self._generic_gate(ev, "GUEST_CAPACITY", ["EXTENDABLE_SECTION"], "EXTENDABLE",
                                    rep, asr_words=("待客", "多人", "扩容"))
        add_claim("USER_NEED", "GUEST_CAPACITY", st, rep["evidence_grade"], rep,
                  "SEM_001", rc)

        # DINING（V3 4/4 TRUE，保持）
        rep = self.es.build_report("USER_NEED", "DINING", packet,
                                   required_fields=["component", "function"])
        reports["DINING"] = rep
        st, rc = self._generic_gate(ev, "DINING", ["COUNTERTOP"], "DINING",
                                    rep, asr_words=("用餐", "吃饭"))
        add_claim("USER_NEED", "DINING", st, rep["evidence_grade"], rep, "SEM_005", rc)

        # OFFICE（V3 4/4 TRUE，保持）
        rep = self.es.build_report("USER_NEED", "OFFICE", packet,
                                   required_fields=["function"])
        reports["OFFICE"] = rep
        st, rc = self._generic_gate(ev, "OFFICE", [], "OFFICE", rep,
                                    asr_words=("办公", "写作业", "工作"))
        add_claim("USER_NEED", "OFFICE", st, rep["evidence_grade"], rep, "SEM_007", rc)

        # ---- BUSINESS_VALUES（Need→Value 解耦：每个 value 独立门控）----
        # STORAGE_EFFICIENCY（V3 2 FALSE，更高门槛）
        rep = self.es.build_report("BUSINESS_VALUE", "STORAGE_EFFICIENCY", packet,
                                   required_fields=["component", "function"])
        reports["STORAGE_EFFICIENCY"] = rep
        storage_status = next((c["claim_status"] for c in claims
                               if c["claim_value"] == "STORAGE"), "UNKNOWN")
        st, rc = self._storage_efficiency_gate(ev, storage_status, rep)
        add_claim("BUSINESS_VALUE", "STORAGE_EFFICIENCY", st, rep["evidence_grade"], rep,
                  "GATE_STORAGE_EFF_V2", rc)

        # POWER_CONVENIENCE（独立门控，非 CHARGING_POWER 自动升级）
        rep = self.es.build_report("BUSINESS_VALUE", "POWER_CONVENIENCE", packet,
                                   required_fields=["component", "function"])
        reports["POWER_CONVENIENCE"] = rep
        st, rc = self._power_gate(ev, rep)
        add_claim("BUSINESS_VALUE", "POWER_CONVENIENCE", st, rep["evidence_grade"], rep,
                  "GATE_POWER_VALUE_V2", rc)

        # FLEXIBLE_CAPACITY（UNTESTED）
        rep = self.es.build_report("BUSINESS_VALUE", "FLEXIBLE_CAPACITY", packet,
                                   required_fields=["component", "function"])
        reports["FLEXIBLE_CAPACITY"] = rep
        st, rc = self._generic_gate(ev, "FLEXIBLE_CAPACITY", ["EXTENDABLE_SECTION"], "EXTENDABLE",
                                    rep, asr_words=("伸缩", "扩展"))
        add_claim("BUSINESS_VALUE", "FLEXIBLE_CAPACITY", st, rep["evidence_grade"], rep,
                  "SEM_001", rc)

        # DINING_CONVENIENCE（独立门控）
        rep = self.es.build_report("BUSINESS_VALUE", "DINING_CONVENIENCE", packet,
                                   required_fields=["component", "function"])
        reports["DINING_CONVENIENCE"] = rep
        st, rc = self._generic_gate(ev, "DINING_CONVENIENCE", ["COUNTERTOP"], "DINING",
                                    rep, asr_words=("用餐方便", "吃饭方便"))
        add_claim("BUSINESS_VALUE", "DINING_CONVENIENCE", st, rep["evidence_grade"], rep,
                  "SEM_005_VALUE", rc)

        # WORK_FROM_HOME（独立门控）
        rep = self.es.build_report("BUSINESS_VALUE", "WORK_FROM_HOME", packet,
                                   required_fields=["function"])
        reports["WORK_FROM_HOME"] = rep
        st, rc = self._generic_gate(ev, "WORK_FROM_HOME", [], "OFFICE", rep,
                                    asr_words=("居家办公", "办公方便", "在家办公"))
        add_claim("BUSINESS_VALUE", "WORK_FROM_HOME", st, rep["evidence_grade"], rep,
                  "SEM_007_VALUE", rc)

        # ---- Negative Rule 优先（对已生成 claims）----
        neg_checks = {
            "OPERATE_SOCKET": ["component=TRACK_SOCKET"],
            "REAL_CUSTOMER_CASE": ["scene=FACTORY"],
            "FAMILY_GATHERING": ["people_presence=YES"],
        }
        for claim in claims:
            if claim["claim_value"] in neg_checks:
                # NR 命中 → BLOCKED 并移除
                if claim["claim_value"] == "OPERATE_SOCKET" and "TRACK_SOCKET" in _field_vals(ev, "component"):
                    claim["claim_status"] = "BLOCKED"
                elif claim["claim_value"] == "REAL_CUSTOMER_CASE" and ev.get("scene_family", {}).get("value") == "FACTORY":
                    claim["claim_status"] = "BLOCKED"
                elif claim["claim_value"] == "FAMILY_GATHERING" and ev.get("people_presence", {}).get("value") == "YES":
                    claim["claim_status"] = "BLOCKED"
        # 移除 BLOCKED
        claims = [c for c in claims if c["claim_status"] != "BLOCKED"]

        # ---- 统计 ----
        from collections import Counter
        status_counts = Counter(c["claim_status"] for c in claims)
        needs = {c["claim_value"] for c in claims if c["claim_category"] == "USER_NEED"
                 and c["claim_status"] in ("SUPPORTED", "CONFIRMED")}
        vals = {c["claim_value"] for c in claims if c["claim_category"] == "BUSINESS_VALUE"
                and c["claim_status"] in ("SUPPORTED", "CONFIRMED")}

        # Search intent = candidate layer（与 claim 解耦，SUPPORTED 才派生）
        search_intent_candidates = []
        if "STORAGE" in needs:
            search_intent_candidates.append("ISLAND_STORAGE")
        if "CHARGING_POWER" in needs:
            search_intent_candidates.append("ISLAND_SOCKET")
        if "GUEST_CAPACITY" in needs:
            search_intent_candidates.append("EXTENDABLE_ISLAND")

        return {
            "segment_id": segment_id, "asset_id": asset_id,
            "engine_version": "BusinessCognitionV2_1",
            "knowledge_snapshot": "V1.2 (a9ac59f6…)",
            "evidence_packet": packet,
            "conflicts": conflicts,
            "evidence_strength_reports": reports,
            "business_claims": claims,
            "claim_status_counts": dict(status_counts),
            "user_needs": sorted(needs),
            "business_values": sorted(vals),
            "search_intent_candidates": search_intent_candidates,
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
        }
