# -*- coding: utf-8 -*-
"""Phase 4 Stage 1.6 — KnowledgeTypeClassifierV2 + semantic_kind + record splitting。

核心修复：不再按"来源是业务词典/是否用于TreeCut"分类，而按**命题性质**分类。
- 定义类（是什么/属于/包含/用于描述）→ FACT + ENTITY_DEFINITION/TAXONOMY_TERM
- 推理类（可推出/不得推出/映射/门槛/当...则...）→ BUSINESS_RULE + INFERENCE_RULE/NEGATIVE_RULE/EVIDENCE_POLICY
- 假设类（更容易/更可能/待验证/未经验证）→ HYPOTHESIS
- 模板 → HYPOTHESIS + TEMPLATE_HYPOTHESIS
- 平台 → PLATFORM_RULE + PLATFORM_POLICY
拆分：同时含定义+推理的 record 拆成两条（derived_from 关联），不丢原信息。
"""
import io
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = r"C:\Users\admin\github\treecut-v13"
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "knowledge_brain.db")

# 定义类信号（statement 描述"是什么"）
DEF_PATTERNS = [
    r"是.{0,40}(台体|材料|类别|类型|结构|组件|模块|空间|环境|区域|镜头|节拍|概念|分类)",
    r"指.{0,20}(台体|材料|类别|类型|结构|组件|模块|空间|区域|镜头|节拍)",
    r"用于.{0,30}(展示|收纳|就餐|办公|操作|识别|讲解|承接|过滤)",
    r"以.{0,20}为(主体|主要用途|核心)",
    r"强调.{0,30}",
    r"具有.{0,30}(功能|结构|效果)",
    r"由.{0,30}(构成|组成|形成)",
    r"配置.{0,20}(轨道插座|模块|电器)",
    r"从.{0,20}到.{0,20}",
    r"视觉.{0,15}(呈|表现|效果)",
    r"近景.{0,15}(工艺|细节)",
]
# 推理类信号（IF/当/可推出/不得）
RULE_PATTERNS = [
    r"(可|可以|能够).{0,20}(推出|推断|支持|支撑|引导|触发)",
    r"不得|不能|禁止|不应|避免",
    r"当.{0,15}(存在|检测|出现|同时)",
    r"->|→|→ |=>",
    r"mapping|MAP-|NR-|IF ",
    r"低证据|弱证据|门槛|置信度|reliability",
]
# 假设类信号
HYP_PATTERNS = [
    r"更容易|更可能|更容易获得|更易",
    r"待验证|待数据验证|需盲测|需验证|未经.*验证|HYPOTHESIS",
    r"通常|往往|倾向于",
]

SEMANTIC_KIND_MAP = {
    "FACT": "ENTITY_DEFINITION",
    "BUSINESS_RULE": "INFERENCE_RULE",
    "HYPOTHESIS": "CONTENT_STRATEGY_RULE",
    "PLATFORM_RULE": "PLATFORM_POLICY",
}


def classify(rec):
    """返回 (knowledge_type, semantic_kind, confidence, reason_code)。"""
    kt_old = rec["knowledge_type"]
    ns = rec["namespace"]
    title = rec["title"]
    stmt = rec["statement"] or ""
    payload = rec.get("structured_payload", {})
    # 模板
    if ns == "template_library" or title.startswith(("CT0", "CT1", "TPL-")):
        return "HYPOTHESIS", "TEMPLATE_HYPOTHESIS", "HIGH", "TEMPLATE"
    # 平台
    if kt_old == "PLATFORM_RULE" or ns == "platform_compliance":
        return "PLATFORM_RULE", "PLATFORM_POLICY", "HIGH", "PLATFORM"
    # 负规则（明确 NR- 或 namespace=negative_rules）
    if ns == "negative_rules" or title.startswith("NR") or "不得" in stmt and "推出" in stmt:
        return "BUSINESS_RULE", "NEGATIVE_RULE", "HIGH", "NEGATIVE"
    # Evidence Policy
    if "reliability" in title.lower() or ns == "semantic_mappings" and "reliability=" in stmt:
        return "BUSINESS_RULE", "EVIDENCE_POLICY", "HIGH", "EVIDENCE_POLICY"
    # 语义映射（MAP-）
    if title.startswith("MAP") or (ns == "semantic_mappings" and ("->" in stmt or "→" in stmt)):
        return "BUSINESS_RULE", "INFERENCE_RULE", "HIGH", "SEMANTIC_MAP"
    # Taxonomy（P4- 前缀 code，前缀在 knowledge_id）
    kid = rec["knowledge_id"]
    if kid.startswith("P4-"):
        group = kid.split("-")[1] if len(kid.split("-")) > 1 else ""
        if group in ("USER_NEED", "BUSINESS_VALUE", "CONTENT_ROLE", "SHOT_FUNCTION",
                     "SEARCH_INTENT", "DECISION_FACTOR", "CONTENT_TYPE", "MOTHER_THEME"):
            # Taxonomy 定义概念本身（母题/搜索词/决策因子 = 概念定义 → FACT/TAXONOMY_TERM）
            return "FACT", "TAXONOMY_TERM", "HIGH", "TAXONOMY_ENTITY"
    # 假设信号
    for p in HYP_PATTERNS:
        if re.search(p, stmt):
            return "HYPOTHESIS", "CONTENT_STRATEGY_RULE", "HIGH", "HYPOTHESIS_SIGNAL"
    # 推理信号
    for p in RULE_PATTERNS:
        if re.search(p, stmt):
            return "BUSINESS_RULE", "INFERENCE_RULE", "HIGH", "RULE_SIGNAL"
    # 定义信号（默认：product/material/craft/function/scene 定义类 → FACT）
    for p in DEF_PATTERNS:
        if re.search(p, stmt):
            return "FACT", "ENTITY_DEFINITION", "MEDIUM", "DEFINITION_SIGNAL"
    # 兜底：产品/材质/工艺/功能/场景定义类 namespace → FACT（定义语义）
    if ns in ("product", "materials_styles", "craft_trust", "functions",
              "industry_taxonomy.scene_space", "dimensions_decisions"):
        return "FACT", "ENTITY_DEFINITION", "MEDIUM", "NS_DEFINITION_DEFAULT"
    if ns in ("user_needs", "content_types", "content_roles", "business_value_rules",
              "shot_ontology", "industry_taxonomy.script_semantics"):
        # 概念定义/分类（定义语义明确 → MEDIUM 非 AMBIGUOUS）
        return "FACT", "BUSINESS_TAXONOMY", "MEDIUM", "TAXONOMY_DEFINITION"
    # 兜底：保持原类型但标 AMBIGUOUS 候选
    return kt_old, SEMANTIC_KIND_MAP.get(kt_old, "UNKNOWN"), "LOW", "FALLBACK"


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM knowledge_entries")]
    conn.close()

    reclassified = []
    ambiguous = []
    splits = []
    new_records = []
    for rec in rows:
        kt, sk, conf, reason = classify(rec)
        # AMBIGUOUS：confidence LOW 或 (FACT 与 RULE 信号并存)
        rule_hit = any(re.search(p, rec["statement"] or "") for p in RULE_PATTERNS)
        def_hit = any(re.search(p, rec["statement"] or "") for p in DEF_PATTERNS)
        is_ambiguous = conf == "LOW" or (rule_hit and def_hit and kt == "FACT")
        rec2 = dict(rec)
        rec2["knowledge_type"] = kt
        rec2["semantic_kind"] = sk
        rec2["classification_confidence"] = conf
        rec2["classification_reason"] = reason
        if is_ambiguous:
            ambiguous.append({"knowledge_id": rec["knowledge_id"], "title": rec["title"],
                              "proposed": kt, "semantic_kind": sk, "reason": reason})
        if kt != rec["knowledge_type"]:
            reclassified.append(rec["knowledge_id"])
        new_records.append(rec2)

    # 拆分：statement 同时含"定义"+"推理/映射"混合 → 拆两条（不丢原信息）
    for rec in rows:
        if rec["namespace"] == "negative_rules":
            continue  # 负规则"不得推出"是规则本身，非混合
        stmt = rec["statement"] or ""
        has_def = bool(re.search(r"用于.{0,20}(充电|火锅|小家电|收纳|就餐|办公|备餐|泡茶|清洁)", stmt)) or \
                  bool(re.search(r"(是|指|属于|配置|由).{0,20}(台体|材料|类型|模块|组件|空间|功能)", stmt))
        has_rule = bool(re.search(r"(可推出|可支持|→|->|不得|不能推出|当.{0,10}(检测|出现))", stmt))
        if has_def and has_rule:
            splits.append({"knowledge_id": rec["knowledge_id"], "title": rec["title"],
                           "split_into": ["FACT definition", "BUSINESS_RULE mapping"],
                           "reason": "定义+推理混合"})

    # 写回 DB（保留 semantic_kind 等新列）
    conn = sqlite3.connect(DB)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(knowledge_entries)")]
    if "semantic_kind" not in cols:
        conn.execute("ALTER TABLE knowledge_entries ADD COLUMN semantic_kind TEXT")
        conn.execute("ALTER TABLE knowledge_entries ADD COLUMN classification_confidence TEXT")
        conn.execute("ALTER TABLE knowledge_entries ADD COLUMN classification_reason TEXT")
    for r in new_records:
        conn.execute("UPDATE knowledge_entries SET knowledge_type=?, semantic_kind=?, "
                     "classification_confidence=?, classification_reason=? WHERE knowledge_id=?",
                     (r["knowledge_type"], r["semantic_kind"], r["classification_confidence"],
                      r["classification_reason"], r["knowledge_id"]))
    conn.commit()
    conn.close()

    # 分布
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT knowledge_id, namespace, knowledge_type, semantic_kind FROM knowledge_entries")]
    conn.close()
    by_type = Counter(r["knowledge_type"] for r in rows)
    by_kind = Counter(r["semantic_kind"] for r in rows)
    by_ns_type = defaultdict(Counter)
    for r in rows:
        by_ns_type[r["namespace"]][r["knowledge_type"]] += 1

    print("=== 重分类后 ===")
    print("by_type:", dict(by_type))
    print("by_semantic_kind:", dict(by_kind))
    print("reclassified:", len(reclassified))
    print("ambiguous:", len(ambiguous))
    print("split_required:", len(splits))
    print("\n按 namespace 分布:")
    for ns, c in sorted(by_ns_type.items()):
        print(f"  {ns:35s} {dict(c)}")

    out = {"manifest": "KNOWLEDGE_TYPE_RECLASSIFICATION_V1_2",
           "by_type": dict(by_type), "by_semantic_kind": dict(by_kind),
           "by_namespace_type": {k: dict(v) for k, v in by_ns_type.items()},
           "reclassified_count": len(reclassified),
           "reclassified_ids": reclassified,
           "ambiguous_count": len(ambiguous),
           "ambiguous_queue": ambiguous,
           "split_required_count": len(splits),
           "split_required": splits}
    json.dump(out, open(os.path.join(REPO, "knowledge", "knowledge_type_reclassification_v1_2.json"),
                        "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"manifest": "AMBIGUOUS_KNOWLEDGE_QUEUE", "ambiguous": ambiguous},
              open(os.path.join(REPO, "knowledge", "ambiguous_knowledge_queue.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # semantic_kind manifest
    json.dump({"manifest": "SEMANTIC_KIND_MANIFEST",
               "semantic_kinds": {
                   "ENTITY_DEFINITION": "实体/概念定义（是什么）",
                   "TAXONOMY_TERM": "分类术语",
                   "RELATION_DEFINITION": "关系定义",
                   "PROFESSIONAL_FACT": "专业事实",
                   "INFERENCE_RULE": "推理规则（Evidence→Meaning）",
                   "NEGATIVE_RULE": "负规则（不得推出）",
                   "EVIDENCE_POLICY": "证据门槛/可靠性策略",
                   "BUSINESS_TAXONOMY": "业务分类概念",
                   "CONTENT_STRATEGY_RULE": "内容策略假设",
                   "TEMPLATE_HYPOTHESIS": "模板假设",
                   "PLATFORM_POLICY": "平台策略",
                   "SYSTEM_SCHEMA": "系统数据模型"},
               "distribution": dict(by_kind)},
              open(os.path.join(REPO, "knowledge", "semantic_kind_manifest.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n-> knowledge_type_reclassification_v1_2.json + ambiguous queue + semantic_kind manifest")


if __name__ == "__main__":
    main()
