# -*- coding: utf-8 -*-
"""Stage 2 — BusinessCognitionServiceV2 Candidate + BusinessClaimV2。

关键架构修正：
  1. Segment 不输出最终 PRIMARY_ROLE / PRIMARY_MOTHER_THEME，只输出 affinity（候选）
  2. search_intent 是 candidate
  3. BusinessClaimV2 统一模型（claim_status: CONFIRMED/SUPPORTED/WEAK/CANDIDATE/UNKNOWN/BLOCKED）
  4. Evidence family 防同源重复计票
  5. Negative Rule 优先门控
  6. semantic_action 永远 VERY_LOW
  7. Over-inference 防御：无依据推断全部降级 CANDIDATE/UNKNOWN
"""
from __future__ import annotations

import time

KNOWLEDGE_VERSION = "KNOWLEDGE_BRAIN_V2_STAGE2"

# Evidence Pattern → Business Meaning（hard claims，仅 SUPPORTED 级）
SEMANTIC_MAPPINGS = [
    {"rule_id": "SEM_002", "pattern": {"component": ["DRAWER"], "function": ["STORAGE"]},
     "claims": [{"category": "USER_NEED", "value": "STORAGE", "status": "SUPPORTED"},
                {"category": "BUSINESS_VALUE", "value": "STORAGE_EFFICIENCY", "status": "SUPPORTED"}]},
    {"rule_id": "SEM_003", "pattern": {"component": ["TRACK_SOCKET"], "function": ["POWER", "OFFICE", "SMALL_APPLIANCE"]},
     "claims": [{"category": "USER_NEED", "value": "CHARGING_POWER", "status": "SUPPORTED"},
                {"category": "BUSINESS_VALUE", "value": "POWER_CONVENIENCE", "status": "SUPPORTED"}]},
    {"rule_id": "SEM_004", "pattern": {"component": ["TRACK_SOCKET"]},
     "claims": [{"category": "BUSINESS_VALUE", "value": "POWER_CONVENIENCE", "status": "SUPPORTED",
                 "note": "产品能力（插座存在）；不产生 OPERATE_SOCKET action"}]},
    {"rule_id": "SEM_001", "pattern": {"component": ["EXTENDABLE_SECTION"], "function": ["EXTENDABLE"]},
     "claims": [{"category": "USER_NEED", "value": "GUEST_CAPACITY", "status": "SUPPORTED"},
                {"category": "BUSINESS_VALUE", "value": "FLEXIBLE_CAPACITY", "status": "SUPPORTED"}]},
    {"rule_id": "SEM_005", "pattern": {"component": ["COUNTERTOP"], "function": ["DINING"]},
     "claims": [{"category": "USER_NEED", "value": "DINING", "status": "SUPPORTED"},
                {"category": "BUSINESS_VALUE", "value": "DINING_CONVENIENCE", "status": "SUPPORTED"}]},
    {"rule_id": "SEM_006", "pattern": {"component": ["CABINET_DOOR"], "function": ["STORAGE"]},
     "claims": [{"category": "USER_NEED", "value": "STORAGE", "status": "SUPPORTED"},
                {"category": "BUSINESS_VALUE", "value": "STORAGE_EFFICIENCY", "status": "SUPPORTED"}]},
    {"rule_id": "SEM_007", "pattern": {"function": ["OFFICE"]},
     "claims": [{"category": "USER_NEED", "value": "OFFICE", "status": "SUPPORTED"},
                {"category": "BUSINESS_VALUE", "value": "WORK_FROM_HOME", "status": "SUPPORTED"}]},
]

# 母题 affinity（仅候选）
THEME_AFFINITY = [
    {"rule_id": "THEME_001", "needs": ["SPACE_EFFICIENCY", "GUEST_CAPACITY", "SPACE_DIVISION"],
     "theme": "SPACE_SOLUTION", "affinity": "MEDIUM"},
    {"rule_id": "THEME_002", "needs": ["FAMILY_GATHERING", "DINING", "GUEST_CAPACITY"],
     "theme": "FAMILY_SCENE", "affinity": "MEDIUM"},
    {"rule_id": "THEME_003", "needs": ["DECISION_CONFIDENCE", "INSTALLATION_CONFIDENCE", "DURABILITY"],
     "theme": "DECISION_AVOID_PIT", "affinity": "MEDIUM"},
    {"rule_id": "THEME_004", "needs": ["AESTHETICS", "STYLE_MATCH"],
     "theme": "AESTHETIC_STYLE", "affinity": "MEDIUM"},
    {"rule_id": "THEME_005", "needs": ["QUALITY_TRUST", "DURABILITY", "CRAFT"],
     "theme": "CRAFT_TRUST", "affinity": "MEDIUM"},
]

# Content Role affinity（仅候选，非 primary）
ROLE_AFFINITY = [
    {"rule_id": "ROLE_001", "needs": ["GUEST_CAPACITY", "SPACE_EFFICIENCY", "FAMILY_GATHERING", "CHARGING_POWER"],
     "role": "CONVERSION", "affinity": "MEDIUM"},
    {"rule_id": "ROLE_002", "needs": ["DECISION_CONFIDENCE", "STORAGE", "DINING", "SIZE"],
     "role": "SEARCH", "affinity": "MEDIUM"},
    {"rule_id": "ROLE_003", "needs": ["QUALITY_TRUST"], "role": "TRUST", "affinity": "MEDIUM"},
]

# Shot Function 候选（需多证据）
SHOT_FUNCTION_RULES = [
    {"rule_id": "SF_001", "needs_vals": ["STORAGE_EFFICIENCY", "FLEXIBLE_CAPACITY", "POWER_CONVENIENCE"],
     "function": "FUNCTION_PROOF", "affinity": "MEDIUM"},
]

NEGATIVE_RULES = [
    {"rule_id": "NR001", "cond": {"component": ["TRACK_SOCKET"]}, "block": ["OPERATE_SOCKET"],
     "reason": "插座存在 ≠ 操作插座"},
    {"rule_id": "NR002", "cond": {"scene_family": ["FACTORY"]}, "block": ["REAL_CUSTOMER_CASE"],
     "reason": "工厂 ≠ 真实客户案例"},
    {"rule_id": "NR004", "cond": {"people_presence": ["YES"]}, "block": ["FAMILY_GATHERING"],
     "reason": "有人 ≠ 家庭聚会"},
    {"rule_id": "NR005", "cond": {"semantic_action_reliability": ["VERY_LOW"]},
     "block": ["FUNCTION_PROOF", "OPERATE_SOCKET", "FAMILY_GATHERING"],
     "reason": "semantic_action 不能单独触发"},
]


def _val_match(actual, need):
    if isinstance(actual, list):
        return any(v in actual for v in need)
    return actual in need


class BusinessClaimV2:
    """统一业务声明。"""

    def __init__(self, category, value, status, segment_id, evidence_refs=None,
                 knowledge_refs=None, rule_refs=None, negative_checks=None, reason=None):
        self.claim_id = f"CL-{segment_id[:8]}-{category}-{value}"
        self.claim_category = category
        self.claim_value = value
        self.context_scope = "SEGMENT_SCOPE"
        self.claim_status = status
        self.confidence = {"CONFIRMED": "HIGH", "SUPPORTED": "MEDIUM_HIGH",
                           "WEAK": "LOW", "CANDIDATE": "LOW", "UNKNOWN": "UNKNOWN",
                           "BLOCKED": "BLOCKED"}.get(status, "LOW")
        self.evidence_refs = evidence_refs or []
        self.knowledge_refs = knowledge_refs or []
        self.rule_refs = rule_refs or []
        self.negative_rule_checks = negative_checks or []
        self.reason_codes = [reason] if reason else []
        self.created_at = time.strftime("%Y-%m-%d %H:%M")

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class BusinessCognitionServiceV2:
    """V2：BusinessClaim 模型 + affinity + Negative 优先 + Evidence family 门控。"""

    def __init__(self, knowledge_service=None, evidence_resolver=None, conflict_resolver=None):
        if knowledge_service is None:
            from treecut.services.knowledge_service import KnowledgeService
            knowledge_service = KnowledgeService()
        self.ks = knowledge_service
        if evidence_resolver is None:
            from treecut.services.evidence_resolver import EvidenceResolverV1
            evidence_resolver = EvidenceResolverV1()
        self.er = evidence_resolver
        if conflict_resolver is None:
            from treecut.services.conflict_resolver import ConflictResolverV1
            conflict_resolver = ConflictResolverV1()
        self.cr = conflict_resolver

    def cognize(self, segment_id: str, seg_cog: dict, asr_text: str = "",
                ocr_text: str = "", asset_id: str = "") -> dict:
        # 1) Evidence Resolution
        packet = self.er.resolve(seg_cog, asr_text, ocr_text)
        conflicts = self.cr.resolve(packet)

        # 2) Knowledge retrieval（facts + rules 分离）
        retrieved_facts = self.ks.retrieve_facts()
        retrieved_rules = self.ks.retrieve_business_rules()
        # 3) Semantic mapping（hard claims，检查 negative + evidence family）
        claims = []
        ev = packet["normalized_evidence"]
        has_sa = "action_sequence" in ev
        for rule in SEMANTIC_MAPPINGS:
            if all(_val_match(ev.get(f, {}).get("value"), need) for f, need in rule["pattern"].items()):
                for c in rule["claims"]:
                    claims.append(BusinessClaimV2(c["category"], c["value"], c["status"],
                                                  segment_id,
                                                  evidence_refs=list(rule["pattern"].keys()),
                                                  knowledge_refs=[r["knowledge_id"] for r in retrieved_rules[:5]],
                                                  rule_refs=[rule["rule_id"]],
                                                  reason=c.get("note")))

        # 4) Negative rule 优先（对已生成 claims）
        for claim in claims:
            for nr in NEGATIVE_RULES:
                cond = nr["cond"]
                matched = True
                for k, v in cond.items():
                    if k == "semantic_action_reliability":
                        if not has_sa:
                            matched = False
                    elif k in ev:
                        if not _val_match(ev[k]["value"], v):
                            matched = False
                    else:
                        matched = False
                if matched and claim.claim_value in nr["block"]:
                    claim.claim_status = "BLOCKED"
                    claim.negative_rule_checks.append(nr["rule_id"])
                    claim.reason_codes.append(f"NR:{nr['rule_id']}")
        # 移除 BLOCKED
        claims = [c for c in claims if c.claim_status != "BLOCKED"]

        # 5) Affinity 候选（role/theme/intent/shot function —— 非 primary）
        needs = {c.claim_value for c in claims if c.claim_category == "USER_NEED"}
        vals = {c.claim_value for c in claims if c.claim_category == "BUSINESS_VALUE"}
        role_affinity = []
        for rule in ROLE_AFFINITY:
            if any(n in needs for n in rule["needs"]):
                role_affinity.append({"role": rule["role"], "affinity": rule["affinity"],
                                      "rule_id": rule["rule_id"], "confidence": "MEDIUM"})
        theme_affinity = []
        for rule in THEME_AFFINITY:
            if any(n in needs for n in rule["needs"]):
                theme_affinity.append({"theme": rule["theme"], "affinity": rule["affinity"],
                                       "rule_id": rule["rule_id"]})
        shot_func_candidates = []
        for rule in SHOT_FUNCTION_RULES:
            if any(v in vals for v in rule["needs_vals"]) and not has_sa:
                shot_func_candidates.append({"function": rule["function"], "affinity": rule["affinity"]})

        # search intent candidates（基于 needs/values 派生，非 primary）
        search_intent_candidates = []
        if "STORAGE" in needs:
            search_intent_candidates.append("ISLAND_STORAGE")
        if "CHARGING_POWER" in needs:
            search_intent_candidates.append("ISLAND_SOCKET")
        if "GUEST_CAPACITY" in needs:
            search_intent_candidates.append("EXTENDABLE_ISLAND")

        # 6) 置信度聚合（family 防重复计票）
        indep = packet["independent_sources"]
        conf = "UNKNOWN" if not claims else (
            "HIGH" if indep >= 2 and any(c.claim_status == "SUPPORTED" for c in claims)
            else "MEDIUM" if indep >= 1 else "LOW")

        return {
            "segment_id": segment_id, "asset_id": asset_id,
            "evidence_packet": packet,
            "conflicts": conflicts,
            "business_claims": [c.to_dict() for c in claims],
            "content_role_affinity": role_affinity,
            "mother_theme_affinity": theme_affinity,
            "search_intent_candidates": search_intent_candidates,
            "shot_function_candidates": shot_func_candidates,
            "user_needs": sorted(needs),
            "business_values": sorted(vals),
            "confidence": conf,
            "knowledge_version": KNOWLEDGE_VERSION,
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
        }
