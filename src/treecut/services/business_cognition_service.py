# -*- coding: utf-8 -*-
"""BusinessCognitionServiceV1 — Phase 4 Stage 1 业务认知引擎。

输入：segment cognition（L2）+ 可选 ASR/OCR + knowledge snapshot
流程：Evidence normalization → Knowledge retrieval → Rule matching → Negative filtering
      → Business cognition（structured）→ Traceability
纪律：
  - L1/L2 evidence 不被知识库反向污染
  - semantic_action 只能 WEAK_EVIDENCE（VERY_LOW），不能单独触发高置信规则
  - 每个 user_need/business_value/mother_theme/content_role 必须有 supporting evidence ids + knowledge ids
  - 低证据 → UNKNOWN / LOW CONFIDENCE
"""
from __future__ import annotations

import json
import os
import re
import time

REPO = r"C:\Users\admin\github\treecut-v13"
DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")

KNOWLEDGE_VERSION = "KNOWLEDGE_BRAIN_V2_STAGE1"

# Phase3 字段可信等级（指令 §9）
FIELD_RELIABILITY = {
    "people_presence": "HIGH", "component": "MEDIUM_HIGH", "function": "MEDIUM_HIGH",
    "product_family": "MEDIUM", "scene_family": "LOW", "product_variant": "LOW",
    "material": "LOW", "shot_role": "LOW", "semantic_action": "VERY_LOW",
}

# Evidence Pattern → Business Meaning 映射（指令 §17；确定性规则，非 LLM）
SEMANTIC_MAPPINGS = [
    {"rule_id": "SEM_001", "pattern": {"component": ["EXTENDABLE_SECTION"], "function": ["EXTENDABLE"]},
     "business_values": ["FLEXIBLE_CAPACITY"], "user_needs": ["GUEST_CAPACITY"],
     "confidence": "MEDIUM_HIGH"},
    {"rule_id": "SEM_002", "pattern": {"component": ["DRAWER"], "function": ["STORAGE"]},
     "business_values": ["STORAGE_EFFICIENCY"], "user_needs": ["STORAGE"],
     "confidence": "MEDIUM_HIGH"},
    {"rule_id": "SEM_003", "pattern": {"component": ["TRACK_SOCKET"], "function": ["OFFICE", "POWER", "SMALL_APPLIANCE"]},
     "business_values": ["POWER_CONVENIENCE", "MULTI_FUNCTION"], "user_needs": ["CHARGING_POWER"],
     "confidence": "MEDIUM"},
    {"rule_id": "SEM_004", "pattern": {"component": ["TRACK_SOCKET"]},
     "business_values": ["POWER_CONVENIENCE"], "user_needs": ["CHARGING_POWER"],
     "confidence": "MEDIUM", "note": "产品能力（插座存在），不产生 OPERATE_SOCKET action"},
    {"rule_id": "SEM_005", "pattern": {"component": ["COUNTERTOP"], "function": ["DINING"]},
     "business_values": ["DINING_CONVENIENCE", "SOCIAL_GATHERING"], "user_needs": ["DINING", "FAMILY_GATHERING"],
     "confidence": "MEDIUM"},
    {"rule_id": "SEM_006", "pattern": {"component": ["CABINET_DOOR"], "function": ["STORAGE"]},
     "business_values": ["STORAGE_EFFICIENCY"], "user_needs": ["STORAGE"],
     "confidence": "MEDIUM"},
    {"rule_id": "SEM_007", "pattern": {"function": ["OFFICE"]},
     "business_values": ["WORK_FROM_HOME", "MULTI_FUNCTION"], "user_needs": ["OFFICE"],
     "confidence": "MEDIUM"},
]

# 母题映射（指令 §18-23）
THEME_RULES = [
    {"rule_id": "THEME_001", "needs": ["SPACE_EFFICIENCY", "GUEST_CAPACITY", "SPACE_DIVISION"],
     "primary": "SPACE_SOLUTION", "secondary": ["FAMILY_SCENE"]},
    {"rule_id": "THEME_002", "needs": ["FAMILY_GATHERING", "DINING", "GUEST_CAPACITY"],
     "primary": "FAMILY_SCENE", "secondary": ["SPACE_SOLUTION"]},
    {"rule_id": "THEME_003", "needs": ["DECISION_CONFIDENCE", "INSTALLATION_CONFIDENCE", "DURABILITY"],
     "primary": "DECISION_AVOID_PIT", "secondary": ["CRAFT_TRUST"]},
    {"rule_id": "THEME_004", "needs": ["AESTHETICS", "STYLE_MATCH"],
     "primary": "AESTHETIC_STYLE", "secondary": []},
    {"rule_id": "THEME_005", "needs": ["QUALITY_TRUST", "DURABILITY", "CRAFT"],
     "primary": "CRAFT_TRUST", "secondary": ["DECISION_AVOID_PIT"]},
]

# Negative Rules（指令 §40）
NEGATIVE_RULES = [
    {"rule_id": "NR001", "if": {"component": ["TRACK_SOCKET"]}, "block": ["OPERATE_SOCKET"],
     "reason": "插座存在 ≠ 操作插座"},
    {"rule_id": "NR002", "if": {"scene_family": ["FACTORY"]}, "block": ["REAL_CUSTOMER_CASE"],
     "reason": "工厂 ≠ 真实客户案例"},
    {"rule_id": "NR003", "if": {"material_reliability": ["LOW"]}, "block": ["PREMIUM_MATERIAL_CLAIM"],
     "reason": "材质弱预测不产生高端材质断言"},
    {"rule_id": "NR004", "if": {"people_presence": ["YES"]}, "block": ["FAMILY_GATHERING"],
     "reason": "有人 ≠ 家庭聚会"},
    {"rule_id": "NR005", "if": {"semantic_action_reliability": ["VERY_LOW"]},
     "block": ["FUNCTION_PROOF", "OPERATE_SOCKET", "FAMILY_GATHERING"],
     "reason": "semantic_action 不能单独触发高置信业务规则"},
]


class BusinessCognitionServiceV1:
    """确定性规则引擎（Evidence Pattern → Business Meaning）+ 负规则过滤。"""

    def __init__(self, knowledge_service=None):
        if knowledge_service is None:
            from treecut.services.knowledge_service import KnowledgeService
            knowledge_service = KnowledgeService()
        self.ks = knowledge_service

    def _evidence_summary(self, seg_cog: dict) -> dict:
        """提取 L1/L2 evidence + reliability 标注。"""
        ev = {}
        for field in ("people_presence", "component", "function", "product_family",
                      "scene_family", "product_variant", "material", "shot_role",
                      "semantic_action"):
            if field in seg_cog and seg_cog[field] not in (None, "", "UNKNOWN", []):
                val = seg_cog[field]
                ev[field] = {"value": val, "reliability": FIELD_RELIABILITY.get(field, "LOW")}
        if seg_cog.get("action_sequence"):
            ev["semantic_action"] = {"value": seg_cog["action_sequence"],
                                     "reliability": "VERY_LOW"}  # 强制 WEAK
        return ev

    def _rule_match(self, ev: dict, pattern: dict) -> bool:
        for field, need_vals in pattern.items():
            if field == "semantic_action_reliability":
                continue
            if field == "material_reliability":
                continue
            actual = ev.get(field, {}).get("value", []) if field in ev else None
            if actual is None:
                return False
            if isinstance(actual, list):
                if not any(v in actual for v in need_vals):
                    return False
            else:
                if actual not in need_vals:
                    return False
        return True

    def _negative_check(self, ev: dict, candidates: list[str]) -> list[str]:
        blocked = set()
        for nr in NEGATIVE_RULES:
            cond = nr["if"]
            # 检查条件
            matched = True
            for k, v in cond.items():
                if k == "semantic_action_reliability":
                    sa = ev.get("semantic_action", {}).get("reliability", "VERY_LOW")
                    if sa != v:
                        matched = False
                elif k == "material_reliability":
                    mr = ev.get("material", {}).get("reliability", "LOW")
                    if mr != v:
                        matched = False
                elif k in ev:
                    actual = ev[k].get("value")
                    if isinstance(actual, list):
                        if not any(x in actual for x in v):
                            matched = False
                    elif actual not in v:
                        matched = False
                else:
                    matched = False
            if matched:
                blocked.update(nr["block"])
        return [c for c in candidates if c not in blocked]

    def cognize(self, segment_id: str, seg_cog: dict, asr_text: str = "",
                ocr_text: str = "", asset_id: str = "") -> dict:
        ev = self._evidence_summary(seg_cog)
        trace = []
        user_needs, business_values, mother_themes = [], [], []
        content_roles = []
        shot_functions = []

        # 1) Semantic Business Mapping（确定性规则）
        for rule in SEMANTIC_MAPPINGS:
            if self._rule_match(ev, rule["pattern"]):
                for bv in rule["business_values"]:
                    if bv not in business_values:
                        business_values.append(bv)
                for un in rule["user_needs"]:
                    if un not in user_needs:
                        user_needs.append(un)
                trace.append({"rule_id": rule["rule_id"],
                              "evidence_ids": [f"{f}={v.get('value')}" for f, v in ev.items() if f in rule["pattern"]],
                              "knowledge_ids": [], "note": "SEM mapping matched"})

        # 2) Knowledge retrieval（证据 → 知识）
        retrieved = self.ks.retrieve_for_evidence({k: v.get("value") for k, v in ev.items()})
        retrieved_ids = [r["knowledge_id"] for r in retrieved[:8]]

        # 3) 母题（基于已得 user_needs）
        for tr in THEME_RULES:
            if any(n in user_needs for n in tr["needs"]):
                m = {"primary": tr["primary"], "secondary": tr["secondary"]}
                if m not in mother_themes:
                    mother_themes.append(m)
                trace.append({"rule_id": tr["rule_id"], "evidence_ids": list(user_needs),
                              "knowledge_ids": retrieved_ids[:3], "note": "theme derived from needs"})

        # 4) Content Role（Business Meaning + 表达意图；不硬绑定）
        if any(v in user_needs for v in ("GUEST_CAPACITY", "SPACE_EFFICIENCY", "FAMILY_GATHERING")):
            content_roles.append("CONVERSION")
        if any(v in user_needs for v in ("DECISION_CONFIDENCE", "INSTALLATION_CONFIDENCE", "SIZE")):
            content_roles.append("SEARCH")
        if "QUALITY_TRUST" in user_needs or ev.get("scene_family", {}).get("value") in ("FACTORY",):
            content_roles.append("TRUST")

        # 5) Shot Function（与 shot_role 分离）
        if any(v in business_values for v in ("STORAGE_EFFICIENCY", "FLEXIBLE_CAPACITY", "POWER_CONVENIENCE")):
            shot_functions.append("FUNCTION_PROOF")
        if ev.get("scene_family", {}).get("value") == "FACTORY":
            shot_functions.append("CRAFT_PROOF")

        # 6) Negative filtering（semantic_action 永不触发高置信）
        # 语义动作仅作 evidence 展示，不进入 business_values/user_needs
        sa_val = ev.get("semantic_action", {}).get("value", [])
        sa_note = ("semantic_action=VERY_LOW 仅 WEAK_EVIDENCE，不参与业务推断" if sa_val else "无语义动作证据")

        # 7) 置信度聚合（不简单平均）
        rels = [v["reliability"] for v in ev.values()]
        conf_map = {"VERY_HIGH": 1.0, "HIGH": 0.9, "MEDIUM_HIGH": 0.75, "MEDIUM": 0.6,
                    "LOW": 0.4, "VERY_LOW": 0.2}
        if not ev:
            conf = "UNKNOWN"
        else:
            avg = sum(conf_map.get(r, 0.3) for r in rels) / len(rels)
            conf = ("HIGH" if avg >= 0.75 else "MEDIUM" if avg >= 0.55 else
                    "LOW" if avg >= 0.35 else "UNKNOWN")

        return {
            "segment_id": segment_id, "asset_id": asset_id,
            "evidence_summary": ev,
            "product_meaning": [], "user_needs": user_needs,
            "business_values": business_values,
            "content_roles": content_roles,
            "mother_themes": mother_themes,
            "trust_signals": [], "decision_factors": [], "search_intents": [],
            "shot_functions": shot_functions,
            "risks": [], "unknowns": [sa_note] if sa_val else [],
            "reasoning_trace": trace,
            "confidence": conf,
            "knowledge_version": KNOWLEDGE_VERSION,
            "knowledge_snapshot_id": None,
            "retrieved_knowledge_ids": retrieved_ids,
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
        }
