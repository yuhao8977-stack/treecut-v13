# -*- coding: utf-8 -*-
"""Stage 2.1 — 导出 Business Rules V2.1（knowledge/business_rules_v2_1/knowledge.json）。

内容 = V2.1 Claim Gating 规则：
  - EvidenceStrengthV2（Grade A/B/C/D/NONE + family 纪律）
  - STORAGE Gate V2（PATH A/B/C + 语境校验）
  - STORAGE_EFFICIENCY 更高门槛（Need→Value 解耦）
  - POWER component-only → CANDIDATE
  - UtteranceContextV1 / ConflictResolverV2（假设语境不冲突）
  - Claim Status 六档定义
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_KNOWLEDGE = r"C:\Users\admin\github\treecut-v13\knowledge"
OUT_DIR = os.path.join(REPO_KNOWLEDGE, "business_rules_v2_1")
OUT = os.path.join(OUT_DIR, "knowledge.json")

NOW = "2026-08-29 16:30"
SOURCE = "USER_CURATED_STRUCTURED_KB"
SRC_TYPE = "internal_business_model"
VER = "2.1"
SECTION = "P4_STAGE2_1_CLAIM_GATING"


def rec(kid, title, statement, payload, ktype="BUSINESS_RULE", conf="MEDIUM"):
    return {
        "knowledge_id": kid, "namespace": "business_rules_v2_1",
        "knowledge_type": ktype, "title": title, "statement": statement,
        "structured_payload": payload,
        "source": SOURCE, "source_type": SRC_TYPE, "source_version": VER,
        "confidence": conf, "status": "ACTIVE",
        "effective_date": "2026-08-29", "expires_at": None, "ttl_days": None,
        "tags": ["business_rules_v2_1", ktype],
        "related_entities": [], "created_at": NOW, "updated_at": None,
        "supersedes": "business_rules_v2", "superseded_by": None,
        "source_requirement_class": "NO_EXTERNAL_SOURCE_NEEDED",
        "validation_status": "SYSTEM_GUARDRAIL", "future_validation": None,
        "needs_external_verification": False, "section": SECTION,
        "review_note": "Stage2.1 Claim Gating 规则冻结（基于 V3 Calibration 结论）",
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    records = []

    # ---- EvidenceStrengthV2 ----
    records.append(rec(
        "ESV2-001", "Evidence Grade A/B/C/D/NONE",
        "Grade A: 可靠直接 Evidence + 独立第二 family（非 VERY_LOW）+ 无冲突；"
        "B: MEDIUM_HIGH 直接 Evidence + 规则强匹配；C: 同 provider 一致或组件+推断；"
        "D: LOW/VERY_LOW/弱关键词/语义动作主导；NONE: 无有效证据",
        {"rule_id": "ESV2-001", "grades": ["A", "B", "C", "D", "NONE"],
         "policy_version": "EVIDENCE_STRENGTH_V2_POLICY_1",
         "note": "semantic_action(MOTION_ASR,VERY_LOW) 不得作为独立第二 family 来源"},
        ktype="EVIDENCE_POLICY", conf="MEDIUM"))

    records.append(rec(
        "ESV2-002", "Family 防重复计票（保持）",
        "SIGLIP component/function/material/product 同 family 不算独立来源；"
        "可提升 semantic_consistency；独立来源仅 ASR/OCR/YOLO/HUMAN/METADATA/OTHER",
        {"rule_id": "ESV2-002", "note": "EvidenceResolverV1 family 纪律延续"},
        ktype="EVIDENCE_POLICY", conf="MEDIUM"))

    # ---- Claim Status ----
    records.append(rec(
        "CS-001", "Claim Status 六档",
        "CONFIRMED(仅 Human Verified/明确事实链) / SUPPORTED(Grade A/B+规则+NR通过+无冲突) / "
        "CANDIDATE(Grade B/C 业务合理但 Segment 不足) / WEAK(Grade D 或弱冲突) / "
        "UNKNOWN(无足够信息) / BLOCKED(NR 阻断)",
        {"rule_id": "CS-001", "statuses": ["CONFIRMED", "SUPPORTED", "CANDIDATE",
                                           "WEAK", "UNKNOWN", "BLOCKED"]},
        ktype="BUSINESS_RULE", conf="MEDIUM"))

    # ---- STORAGE Gate V2 ----
    records.append(rec(
        "SG-001", "STORAGE Gate V2（V3 证明 NEEDS_REWORK）",
        "禁止 DRAWER only → STORAGE SUPPORTED；PATH A: DRAWER/CABINET+STORAGE function+Grade>=B"
        "（ASR 非空但无收纳语义 → 降级 CANDIDATE）；PATH B: ASR 明确收纳语义 → SUPPORTED；"
        "PATH C: 明确视觉使用+可靠 function（semantic_action 不单独满足）；仅组件 → CANDIDATE",
        {"rule_id": "SG-001", "paths": ["A_COMP_FUNC_GRADE", "B_ASR_EXPLICIT", "C_VISUAL_USE"],
         "asr_words": ["收纳", "储物", "放东西", "抽屉收", "柜内储物"]},
        ktype="BUSINESS_RULE", conf="MEDIUM"))

    records.append(rec(
        "SG-002", "STORAGE_EFFICIENCY 更高门槛",
        "即使 STORAGE=SUPPORTED 也不自动 STORAGE_EFFICIENCY=SUPPORTED（'可以储物'≠'效率高'）；"
        "需 ASR 明确效率语义 或 多存储区+语境支持；否则最多 CANDIDATE",
        {"rule_id": "SG-002", "asr_words": ["增加收纳", "提高利用率", "更多储物", "收纳效率"]},
        ktype="BUSINESS_RULE", conf="MEDIUM"))

    # ---- Need→Value 解耦 ----
    records.append(rec(
        "NV-001", "NEED_VALUE_DERIVATION_GATE",
        "Need 不自动升级 Value：STORAGE→STORAGE_EFFICIENCY、CHARGING_POWER→POWER_CONVENIENCE、"
        "DINING→DINING_CONVENIENCE、OFFICE→WORK_FROM_HOME 均需 Value 自身 Business Rule+Evidence",
        {"rule_id": "NV-001", "pairs": [["STORAGE", "STORAGE_EFFICIENCY"],
                                        ["CHARGING_POWER", "POWER_CONVENIENCE"],
                                        ["DINING", "DINING_CONVENIENCE"],
                                        ["OFFICE", "WORK_FROM_HOME"]]},
        ktype="BUSINESS_RULE", conf="MEDIUM"))

    # ---- POWER ----
    records.append(rec(
        "PG-001", "POWER component-only → CANDIDATE",
        "TRACK_SOCKET alone → POWER_CONVENIENCE 最多 CANDIDATE；"
        "有 function/ASR 供电语义 + Grade>=B → SUPPORTED",
        {"rule_id": "PG-001", "asr_words": ["充电", "取电", "供电", "插电"]},
        ktype="BUSINESS_RULE", conf="MEDIUM"))

    # ---- UtteranceContext / Conflict ----
    records.append(rec(
        "UC-001", "UtteranceContextV1",
        "话语语境分类：ASSERTED/HYPOTHETICAL/CONDITIONAL/GENERIC_EXAMPLE/NEGATED/QUOTED/UNKNOWN；"
        "假设语境（如果/假如/要是/比如/有宝宝的话等）不得作为 CURRENT_CONTEXT=HOME，"
        "也不得与 FACTORY 冲突",
        {"rule_id": "UC-001", "types": ["ASSERTED", "HYPOTHETICAL", "CONDITIONAL",
                                        "GENERIC_EXAMPLE", "NEGATED", "QUOTED", "UNKNOWN"],
         "hypothetical_markers": ["如果", "假如", "要是", "比如", "比如说", "有宝宝的话",
                                  "家里如果", "客户如果", "假设", "以后如果"]},
        ktype="EVIDENCE_POLICY", conf="MEDIUM"))

    records.append(rec(
        "CF-001", "ConflictResolverV2（仅 ASSERTED 触发）",
        "只有明确 ASSERTED（'这是客户家'等）+ 另一可靠证据 FACTORY 才允许 CONFLICTING_EVIDENCE；"
        "假设/条件/泛例语境记录 NON_ASSERTED_CONTEXT 但不冲突",
        {"rule_id": "CF-001", "asserted_patterns": ["这是客户家", "我们现在在客户家",
                                                    "这个是业主家里的"]},
        ktype="EVIDENCE_POLICY", conf="MEDIUM"))

    doc = {"namespace": "business_rules_v2_1", "count": len(records), "records": records,
           "source": "Stage2.1 Claim Gating 规则冻结（基于 V3 Calibration：STORAGE NEEDS_REWORK，"
                     "6 标签 NO_ERROR_OBSERVED，GUEST_CAPACITY/FLEXIBLE UNTESTED）",
           "supersedes": "business_rules_v2"}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT, "| records:", len(records))


if __name__ == "__main__":
    main()
