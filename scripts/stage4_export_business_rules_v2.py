# -*- coding: utf-8 -*-
"""Stage 2 — 导出 Business Rules V2（knowledge/business_rules_v2/knowledge.json）。

内容 = Stage2 认知引擎冻结规则：
  - EVIDENCE_FAMILY 策略（EvidenceResolverV1）
  - CONFLICT_POLICY（ConflictResolverV1）
  - SEMANTIC_MAPPINGS SEM_001-007
  - NEGATIVE_RULES NR001/002/004/005（V2）
  - THEME_AFFINITY / ROLE_AFFINITY / SHOT_FUNCTION_RULES
规则以 knowledge 记录形式落地（Git 版本化），与 knowledge_brain.db 结构对齐。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO_KNOWLEDGE = r"C:\Users\admin\github\treecut-v13\knowledge"
OUT_DIR = os.path.join(REPO_KNOWLEDGE, "business_rules_v2")
OUT = os.path.join(OUT_DIR, "knowledge.json")

NOW = "2026-08-29 15:20"
SOURCE = "USER_CURATED_STRUCTURED_KB"
SRC_TYPE = "internal_business_model"
VER = "1.2"
SECTION = "P4_STAGE2_BUSINESS_COGNITION_V2"


def rec(kid, title, statement, payload, ktype="BUSINESS_RULE", conf="MEDIUM"):
    return {
        "knowledge_id": kid, "namespace": "business_rules_v2",
        "knowledge_type": ktype, "title": title, "statement": statement,
        "structured_payload": payload,
        "source": SOURCE, "source_type": SRC_TYPE, "source_version": VER,
        "confidence": conf, "status": "ACTIVE",
        "effective_date": "2026-08-29", "expires_at": None, "ttl_days": None,
        "tags": ["business_rules_v2", ktype],
        "related_entities": [], "created_at": NOW, "updated_at": None,
        "supersedes": None, "superseded_by": None,
        "source_requirement_class": "NO_EXTERNAL_SOURCE_NEEDED",
        "validation_status": "SYSTEM_GUARDRAIL", "future_validation": None,
        "needs_external_verification": False, "section": SECTION,
        "review_note": "Stage2 Business Cognition 认知引擎规则冻结（V1.2 知识快照之上）",
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    records = []

    # ---- Evidence Family 策略（EvidenceResolverV1）----
    fam = {
        "people_presence": ("HIGH", "YOLO"),
        "component": ("MEDIUM_HIGH", "SIGLIP"),
        "function": ("MEDIUM_HIGH", "SIGLIP"),
        "product_family": ("MEDIUM", "SIGLIP"),
        "scene_family": ("LOW", "SIGLIP"),
        "product_variant": ("LOW", "SIGLIP"),
        "material": ("LOW", "SIGLIP"),
        "shot_role": ("LOW", "SIGLIP"),
        "action_sequence": ("VERY_LOW", "MOTION_ASR"),
        "semantic_action": ("VERY_LOW", "MOTION_ASR"),
        "asr_text": ("MEDIUM", "ASR"),
        "ocr_text": ("MEDIUM", "OCR"),
    }
    records.append(rec(
        "EF001", "Evidence Family 防重复计票",
        "SigLIP 家族（component/function/material/product_family 等）同属一源，不得当作多票；"
        "独立来源仅按 family 计数：YOLO/SIGLIP/ASR/OCR/MOTION_ASR/HUMAN/METADATA。",
        {"rule_id": "EF001", "field_reliability": fam,
         "independent_families": ["YOLO", "SIGLIP", "ASR", "OCR", "MOTION_ASR", "HUMAN", "METADATA"],
         "note": "同 provider 多字段 = 1 票；≥2 family 才计为 multi-source"},
        ktype="EVIDENCE_POLICY", conf="MEDIUM"))

    records.append(rec(
        "EF002", "semantic_action 永远 VERY_LOW",
        "action_sequence/semantic_action 的 reliability 强制 VERY_LOW（Phase3 纪律）；"
        "不得单独作为功能演示/家庭聚会/操作动作的高置信证据。",
        {"rule_id": "EF002", "forced_reliability": "VERY_LOW",
         "fields": ["action_sequence", "semantic_action"],
         "note": "NR005 依赖此策略"},
        ktype="EVIDENCE_POLICY", conf="HIGH"))

    # ---- Conflict 策略（ConflictResolverV1）----
    records.append(rec(
        "CF001", "ASR 口语 vs 视觉场景冲突",
        "ASR 出现 客户家/家里/入户/客厅/卧室 等词而 scene=FACTORY → CONFLICTING_EVIDENCE，"
        "resolution=CUSTOMER_HOME=UNKNOWN（不强行二选一）。",
        {"rule_id": "CF001", "pattern": "scene=FACTORY + ASR home_words",
         "resolution": "CUSTOMER_HOME=UNKNOWN",
         "reason": "scene LIMITTED 且 ASR 口语不可作为场景硬证据"},
        ktype="EVIDENCE_POLICY", conf="MEDIUM"))

    records.append(rec(
        "CF002", "材质弱预测 vs ASR 材质词",
        "material 为 LOW 可靠且 ASR 出现 实木/原木/大理石 等词 → WEAK_EVIDENCE_CONFLICT，"
        "resolution=MATERIAL_CLAIM=WEAK/UNKNOWN（NR003）。",
        {"rule_id": "CF002", "pattern": "material reliability=LOW + ASR material_words",
         "resolution": "MATERIAL_CLAIM=WEAK/UNKNOWN",
         "reason": "弱材质识别不能支撑真实材质/性能断言"},
        ktype="EVIDENCE_POLICY", conf="MEDIUM"))

    # ---- Semantic Mappings（SEM_001-007，SUPPORTED 级）----
    sem = [
        ("SEM_001", {"component": ["EXTENDABLE_SECTION"], "function": ["EXTENDABLE"]},
         [("USER_NEED", "GUEST_CAPACITY"), ("BUSINESS_VALUE", "FLEXIBLE_CAPACITY")]),
        ("SEM_002", {"component": ["DRAWER"], "function": ["STORAGE"]},
         [("USER_NEED", "STORAGE"), ("BUSINESS_VALUE", "STORAGE_EFFICIENCY")]),
        ("SEM_003", {"component": ["TRACK_SOCKET"], "function": ["POWER", "OFFICE", "SMALL_APPLIANCE"]},
         [("USER_NEED", "CHARGING_POWER"), ("BUSINESS_VALUE", "POWER_CONVENIENCE")]),
        ("SEM_004", {"component": ["TRACK_SOCKET"]},
         [("BUSINESS_VALUE", "POWER_CONVENIENCE")]),
        ("SEM_005", {"component": ["COUNTERTOP"], "function": ["DINING"]},
         [("USER_NEED", "DINING"), ("BUSINESS_VALUE", "DINING_CONVENIENCE")]),
        ("SEM_006", {"component": ["CABINET_DOOR"], "function": ["STORAGE"]},
         [("USER_NEED", "STORAGE"), ("BUSINESS_VALUE", "STORAGE_EFFICIENCY")]),
        ("SEM_007", {"function": ["OFFICE"]},
         [("USER_NEED", "OFFICE"), ("BUSINESS_VALUE", "WORK_FROM_HOME")]),
    ]
    for rid, pat, claims in sem:
        records.append(rec(
            rid, f"{rid} 语义映射",
            f"pattern {pat} → claims {claims}（SUPPORTED 级，SEGMENT_SCOPE）",
            {"rule_id": rid, "pattern": pat,
             "claims": [{"category": c, "value": v, "status": "SUPPORTED"} for c, v in claims],
             "context_scope": "SEGMENT_SCOPE"},
            ktype="BUSINESS_RULE", conf="MEDIUM"))

    # ---- Negative Rules（V2）----
    neg = [
        ("NR001", {"component": ["TRACK_SOCKET"]}, ["OPERATE_SOCKET"],
         "插座存在 ≠ 正在插电/操作"),
        ("NR002", {"scene_family": ["FACTORY"]}, ["REAL_CUSTOMER_CASE"],
         "工厂场景 ≠ 客户家案例"),
        ("NR004", {"people_presence": ["YES"]}, ["FAMILY_GATHERING"],
         "有人 ≠ 家庭/聚会关系"),
        ("NR005", {"semantic_action_reliability": ["VERY_LOW"]},
         ["FUNCTION_PROOF", "OPERATE_SOCKET", "FAMILY_GATHERING"],
         "semantic_action 不能单独触发"),
    ]
    for rid, cond, block, reason in neg:
        records.append(rec(
            rid, f"{rid} 负规则（V2）",
            f"cond {cond} → block {block}；命中则 claim 置 BLOCKED 并移除",
            {"rule_id": rid, "cond": cond, "block": block, "reason": reason},
            ktype="NEGATIVE_RULE", conf="MEDIUM"))

    # ---- Affinity（候选，非 primary）----
    themes = [
        ("THEME_001", ["SPACE_EFFICIENCY", "GUEST_CAPACITY", "SPACE_DIVISION"], "SPACE_SOLUTION"),
        ("THEME_002", ["FAMILY_GATHERING", "DINING", "GUEST_CAPACITY"], "FAMILY_SCENE"),
        ("THEME_003", ["DECISION_CONFIDENCE", "INSTALLATION_CONFIDENCE", "DURABILITY"], "DECISION_AVOID_PIT"),
        ("THEME_004", ["AESTHETICS", "STYLE_MATCH"], "AESTHETIC_STYLE"),
        ("THEME_005", ["QUALITY_TRUST", "DURABILITY", "CRAFT"], "CRAFT_TRUST"),
    ]
    for rid, needs, theme in themes:
        records.append(rec(
            rid, f"{rid} 母题亲和",
            f"needs {needs} → mother_theme_affinity {theme}（MEDIUM 候选，非 primary）",
            {"rule_id": rid, "needs": needs, "theme": theme, "affinity": "MEDIUM",
             "scope": "CANDIDATE_ONLY"},
            ktype="CONTENT_STRATEGY_RULE", conf="MEDIUM"))

    roles = [
        ("ROLE_001", ["GUEST_CAPACITY", "SPACE_EFFICIENCY", "FAMILY_GATHERING", "CHARGING_POWER"], "CONVERSION"),
        ("ROLE_002", ["DECISION_CONFIDENCE", "STORAGE", "DINING", "SIZE"], "SEARCH"),
        ("ROLE_003", ["QUALITY_TRUST"], "TRUST"),
    ]
    for rid, needs, role in roles:
        records.append(rec(
            rid, f"{rid} 内容角色亲和",
            f"needs {needs} → content_role_affinity {role}（MEDIUM 候选，非 primary）",
            {"rule_id": rid, "needs": needs, "role": role, "affinity": "MEDIUM",
             "scope": "CANDIDATE_ONLY"},
            ktype="CONTENT_STRATEGY_RULE", conf="MEDIUM"))

    records.append(rec(
        "SF001", "Shot Function 候选",
        "needs_values 含 STORAGE_EFFICIENCY/FLEXIBLE_CAPACITY/POWER_CONVENIENCE 且无 semantic_action "
        "→ shot_function_candidates FUNCTION_PROOF（MEDIUM 候选）",
        {"rule_id": "SF001", "needs_vals": ["STORAGE_EFFICIENCY", "FLEXIBLE_CAPACITY", "POWER_CONVENIENCE"],
         "function": "FUNCTION_PROOF", "affinity": "MEDIUM", "scope": "CANDIDATE_ONLY"},
        ktype="CONTENT_STRATEGY_RULE", conf="MEDIUM"))

    doc = {"namespace": "business_rules_v2", "count": len(records), "records": records,
           "source": f"Stage2 Business Cognition V2 规则冻结（Knowledge Snapshot V1.2 之上）",
           "guard": "SEGMENT_SCOPE 仅产出 affinity/candidates；primary 由 Script/Template/Production 决定"}
    json.dump(doc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT, "| records:", len(records))
    print("ktypes:", {r["knowledge_type"] for r in records})


if __name__ == "__main__":
    main()
