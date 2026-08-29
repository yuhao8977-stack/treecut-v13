"""TreeCut Phase 2.5 — Annotation Governance Services。

  AnnotationService  — 标注治理：taxonomy 审计 / 人工可信度 / CALIBRATION eligibility
  ReviewQueueService — 主动学习审核队列（基础）
  CoverageService    — 标注覆盖矩阵
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path


class AnnotationService:
    """标注治理服务。"""

    # 字段 → 概念层（Annotation Schema V2 审计用）
    FIELD_LAYER = {
        "scene": "scene",
        "product": "product_family",
        "material": "material",
        "function": "function",
        "action": "action",
        "shot_type": "shot_type",
        "people_presence": "people_presence",
    }

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Taxonomy Audit（5）
    # ------------------------------------------------------------------

    def taxonomy_audit(self) -> dict:
        """分析人工标签的跨层混用。"""
        with self._ro() as conn:
            rows = conn.execute("""
                SELECT h.function, h.product, h.scene, h.action, h.material
                FROM human_annotations h
            """).fetchall()
        issues = []
        # Object vs Function 混用（function 字段出现部件/物体）
        object_in_function = Counter()
        for r in rows:
            f = r["function"] or ""
            if f in ("抽屉", "柜门", "台面", "插座", "水槽", "轨道"):
                object_in_function[f] += 1
                issues.append({"type": "OBJECT_FUNCTION_MIX", "value": f,
                               "detail": f"function 字段出现部件/物体: {f}"})
        # Parent-child mix（product 字段子类 vs 父类）
        product_vals = Counter(r["product"] or "" for r in rows)
        parent_child = [v for v in product_vals if v in ("伸缩岛台", "悬浮岛台")]
        # Action vs Function mix
        action_func_mix = Counter()
        for r in rows:
            a = r["action"] or ""
            if a in ("收纳", "伸缩", "展示"):
                action_func_mix[a] += 1
                issues.append({"type": "ACTION_FUNCTION_MIX", "value": a,
                               "detail": f"action 字段出现功能词: {a}"})
        return {
            "issues_count": len(issues),
            "object_in_function": dict(object_in_function),
            "action_in_function_words": dict(action_func_mix),
            "product_parent_child_candidates": dict(product_vals),
            "issue_types": [i["type"] for i in issues][:50],
            "note": "仅审计，禁止自动修改历史 Human Label",
        }

    # ------------------------------------------------------------------
    # CALIBRATION eligibility（10）
    # ------------------------------------------------------------------

    def calibration_eligible(self, human_confidence: str = "",
                             review_status: str = "") -> bool:
        """HIGH/MEDIUM + REVIEWED/GOLD → eligible。"""
        conf_ok = human_confidence in ("HIGH", "MEDIUM")
        status_ok = review_status in ("REVIEWED", "GOLD")
        return conf_ok and status_ok

    def eligibility_stats(self) -> dict:
        """当前人工数据的 CALIBRATION 合格率。"""
        with self._ro() as conn:
            total = conn.execute("SELECT COUNT(*) FROM human_annotations").fetchone()[0]
            # v1 无 human_confidence 字段 → 默认视为 MEDIUM/REVIEWED（Phase2.5 前）
        return {"v1_total": total,
                "note": "v1 无可信度字段；Phase2.5 后新审核带 human_confidence"}

    # ------------------------------------------------------------------
    # human_annotation_v2（8）
    # ------------------------------------------------------------------

    def save_v2(self, segment_id: str, v1_annotation_id: int, values: dict,
                human_confidence: str = "MEDIUM",
                review_status: str = "REVIEWED",
                operator: str = "") -> int:
        """二次复核保存（不覆盖 v1）。"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        cur = conn.execute(
            "INSERT OR REPLACE INTO human_annotation_v2(segment_id,v1_annotation_id,"
            "scene,product,material,function,action,shot_type,people_presence,"
            "human_confidence,review_status,comment,operator,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (segment_id, v1_annotation_id,
             values.get("scene", ""), values.get("product", ""),
             values.get("material", ""), values.get("function", ""),
             values.get("action", ""), values.get("shot_type", ""),
             values.get("people_presence", ""),
             human_confidence, review_status, values.get("comment", ""),
             operator, time.time()))
        conn.commit()
        conn.close()
        return int(cur.lastrowid)

    def v2_count(self) -> int:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        n = conn.execute("SELECT COUNT(*) FROM human_annotation_v2").fetchone()[0]
        conn.close()
        return n

    # ------------------------------------------------------------------
    # Stage 2 STEP 0 — 统一保存入口（收敛 Standalone/Main 的 3 份 _persist SQL）
    # ------------------------------------------------------------------

    def save_v3(self, segment_id: str, values: dict, human_confidence: str,
                review_status: str, operator: str = "",
                dictionary_version: str = "ANNOTATION_DICTIONARY_V2_1") -> int:
        """第三次裁决保存（Human V3 → human_annotation_v3）。"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            cur = conn.execute(
                "INSERT OR REPLACE INTO human_annotation_v3(segment_id,scene_family,"
                "scene_subtype,product_family,product_variant,material_multi,"
                "component_multi,function_multi,action_group,action_sequence,"
                "shot_scale,shot_role_multi,people_presence,product_visibility,"
                "quality,human_confidence,review_status,comment,operator,"
                "dictionary_version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (segment_id, values.get("scene_family", ""),
                 values.get("scene_subtype", ""), values.get("product_family", ""),
                 values.get("product_variant", ""),
                 json.dumps(values.get("material", []), ensure_ascii=False),
                 json.dumps(values.get("component", []), ensure_ascii=False),
                 json.dumps(values.get("function", []), ensure_ascii=False),
                 values.get("action_group", ""),
                 json.dumps(values.get("action_sequence", []), ensure_ascii=False),
                 values.get("shot_scale", ""),
                 json.dumps(values.get("shot_role", []), ensure_ascii=False),
                 values.get("people_presence", ""),
                 values.get("product_visibility", ""),
                 values.get("quality"),
                 human_confidence, review_status, values.get("comment", ""),
                 operator, dictionary_version, time.time()))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def save_targeted_review(self, segment_id: str, values: dict,
                             human_confidence: str, review_status: str,
                             selection_reason: str = "", operator: str = "",
                             dictionary_version: str = "ANNOTATION_DICTIONARY_V2_1") -> int:
        """主动学习新样本保存 → targeted_human_review_v1。"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            cur = conn.execute(
                "INSERT OR REPLACE INTO targeted_human_review_v1(segment_id,scene_family,"
                "scene_subtype,product_family,product_variant,material_multi,"
                "component_multi,function_multi,action_group,action_sequence,"
                "shot_scale,shot_role_multi,people_presence,product_visibility,"
                "quality,human_confidence,review_status,comment,operator,"
                "dictionary_version,selection_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (segment_id, values.get("scene_family", ""),
                 values.get("scene_subtype", ""), values.get("product_family", ""),
                 values.get("product_variant", ""),
                 json.dumps(values.get("material", []), ensure_ascii=False),
                 json.dumps(values.get("component", []), ensure_ascii=False),
                 json.dumps(values.get("function", []), ensure_ascii=False),
                 values.get("action_group", ""),
                 json.dumps(values.get("action_sequence", []), ensure_ascii=False),
                 values.get("shot_scale", ""),
                 json.dumps(values.get("shot_role", []), ensure_ascii=False),
                 values.get("people_presence", ""),
                 values.get("product_visibility", ""),
                 values.get("quality"),
                 human_confidence, review_status, values.get("comment", ""),
                 operator, dictionary_version, selection_reason, time.time()))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def save_holdout_review(self, segment_id: str, values: dict, stratum: str,
                            human_confidence: str, review_status: str,
                            operator: str = "",
                            dictionary_version: str = "ANNOTATION_DICTIONARY_V2_1") -> int:
        """Fresh Holdout 盲审保存 → fresh_holdout_human_review_v1（只存人工结果，无 AI 信息）。"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            cur = conn.execute(
                "INSERT OR REPLACE INTO fresh_holdout_human_review_v1(segment_id,stratum,"
                "scene_family,scene_subtype,product_family,product_variant,material_multi,"
                "component_multi,function_multi,action_group,action_sequence,shot_scale,"
                "shot_role_multi,people_presence,product_visibility,quality,human_confidence,"
                "review_status,comment,operator,dictionary_version,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (segment_id, stratum, values.get("scene_family", ""),
                 values.get("scene_subtype", ""), values.get("product_family", ""),
                 values.get("product_variant", ""),
                 json.dumps(values.get("material", []), ensure_ascii=False),
                 json.dumps(values.get("component", []), ensure_ascii=False),
                 json.dumps(values.get("function", []), ensure_ascii=False),
                 values.get("action_group", ""),
                 json.dumps(values.get("action_sequence", []), ensure_ascii=False),
                 values.get("shot_scale", ""),
                 json.dumps(values.get("shot_role", []), ensure_ascii=False),
                 values.get("people_presence", ""),
                 values.get("product_visibility", ""),
                 values.get("quality"), human_confidence, review_status,
                 values.get("comment", ""), operator, dictionary_version, time.time()))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def save_business_cognition_review(self, segment_id: str, challenge_class: str,
                                       values: dict, human_confidence: str,
                                       review_status: str, operator: str = "") -> int:
        """Stage 2 业务认知评审保存 → stage2_business_cognition_review_v1。

        保存独立 Human Truth（完整 taxonomy 勾选 + role/theme 全维度评级），
        不含任何 AI claims/affinity/confidence。BLIND。
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS stage2_business_cognition_review_v1("
                "segment_id TEXT PRIMARY KEY, challenge_class TEXT,"
                "user_needs TEXT, business_values TEXT, decision_factors TEXT,"
                "trust_signals TEXT, search_intents TEXT, shot_functions TEXT,"
                "role_affinity TEXT, theme_affinity TEXT,"
                "overall_unknown TEXT, conflict_observed TEXT, comment TEXT,"
                "human_confidence TEXT, review_status TEXT,"
                "operator TEXT, created_at REAL)")
            cur = conn.execute(
                "INSERT OR REPLACE INTO stage2_business_cognition_review_v1("
                "segment_id,challenge_class,user_needs,business_values,decision_factors,"
                "trust_signals,search_intents,shot_functions,role_affinity,theme_affinity,"
                "overall_unknown,conflict_observed,comment,human_confidence,review_status,"
                "operator,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (segment_id, challenge_class,
                 json.dumps(values.get("user_needs", []), ensure_ascii=False),
                 json.dumps(values.get("business_values", []), ensure_ascii=False),
                 json.dumps(values.get("decision_factors", []), ensure_ascii=False),
                 json.dumps(values.get("trust_signals", []), ensure_ascii=False),
                 json.dumps(values.get("search_intents", []), ensure_ascii=False),
                 json.dumps(values.get("shot_functions", []), ensure_ascii=False),
                 json.dumps(values.get("role_affinity", {}), ensure_ascii=False),
                 json.dumps(values.get("theme_affinity", {}), ensure_ascii=False),
                 values.get("overall_unknown", ""), values.get("conflict_observed", ""),
                 values.get("comment", ""), human_confidence, review_status,
                 operator, time.time()))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def save_business_cognition_adjudication(self, segment_id: str, values: dict,
                                             review_confidence: str,
                                             review_duration_seconds: float,
                                             review_status: str, operator: str = "") -> int:
        """Stage 2 Adjudication V2 保存 → stage2_business_cognition_adjudication_v2。

        独立复核（blind）：不显示 V1/AI/评分；记录 review_confidence（HIGH/MEDIUM/LOW）
        与 review_duration_seconds（仅质量诊断，不决定真值）。
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS stage2_business_cognition_adjudication_v2("
                "segment_id TEXT PRIMARY KEY,"
                "user_needs TEXT, business_values TEXT, decision_factors TEXT,"
                "trust_signals TEXT, search_intents TEXT, shot_functions TEXT,"
                "role_affinity TEXT, theme_affinity TEXT,"
                "overall_unknown TEXT, conflict_observed TEXT, comment TEXT,"
                "review_confidence TEXT, review_duration_seconds REAL,"
                "review_status TEXT, operator TEXT, created_at REAL)")
            cur = conn.execute(
                "INSERT OR REPLACE INTO stage2_business_cognition_adjudication_v2("
                "segment_id,user_needs,business_values,decision_factors,"
                "trust_signals,search_intents,shot_functions,role_affinity,theme_affinity,"
                "overall_unknown,conflict_observed,comment,review_confidence,"
                "review_duration_seconds,review_status,operator,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (segment_id,
                 json.dumps(values.get("user_needs", []), ensure_ascii=False),
                 json.dumps(values.get("business_values", []), ensure_ascii=False),
                 json.dumps(values.get("decision_factors", []), ensure_ascii=False),
                 json.dumps(values.get("trust_signals", []), ensure_ascii=False),
                 json.dumps(values.get("search_intents", []), ensure_ascii=False),
                 json.dumps(values.get("shot_functions", []), ensure_ascii=False),
                 json.dumps(values.get("role_affinity", {}), ensure_ascii=False),
                 json.dumps(values.get("theme_affinity", {}), ensure_ascii=False),
                 values.get("overall_unknown", ""), values.get("conflict_observed", ""),
                 values.get("comment", ""), review_confidence, review_duration_seconds,
                 review_status, operator, time.time()))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def save_business_cognition_adjudication_v2b(
            self, segment_id: str, clearly_needs: list, possible_needs: list,
            clearly_values: list, possible_values: list,
            needs_field_unknown: bool, values_field_unknown: bool,
            evidence_sufficiency: str, conflict_observed: str,
            review_confidence: str, review_duration_seconds: float,
            review_status: str, comment: str = "", operator: str = "") -> int:
        """Adjudication V2b（简化版，四态语义）→ stage2_business_cognition_adjudication_v2b。

        只复核 needs/values/evidence/conflict。
        Human supported truth = clearly_*；possible_* 仅报告不计 SUPPORTED TP。
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS stage2_business_cognition_adjudication_v2b("
                "segment_id TEXT PRIMARY KEY,"
                "clearly_supported_needs TEXT, possible_needs TEXT,"
                "clearly_supported_values TEXT, possible_values TEXT,"
                "needs_field_unknown INTEGER, values_field_unknown INTEGER,"
                "evidence_sufficiency TEXT, conflict_observed TEXT,"
                "review_confidence TEXT, review_duration_seconds REAL,"
                "review_status TEXT, comment TEXT, operator TEXT, created_at REAL)")
            cur = conn.execute(
                "INSERT OR REPLACE INTO stage2_business_cognition_adjudication_v2b("
                "segment_id,clearly_supported_needs,possible_needs,"
                "clearly_supported_values,possible_values,"
                "needs_field_unknown,values_field_unknown,"
                "evidence_sufficiency,conflict_observed,"
                "review_confidence,review_duration_seconds,"
                "review_status,comment,operator,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (segment_id,
                 json.dumps(clearly_needs, ensure_ascii=False),
                 json.dumps(possible_needs, ensure_ascii=False),
                 json.dumps(clearly_values, ensure_ascii=False),
                 json.dumps(possible_values, ensure_ascii=False),
                 1 if needs_field_unknown else 0,
                 1 if values_field_unknown else 0,
                 evidence_sufficiency, conflict_observed,
                 review_confidence, review_duration_seconds,
                 review_status, comment, operator, time.time()))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


class ReviewQueueService:
    """主动学习审核队列（基础，11）。"""

    REASONS = ("LOW_CONFIDENCE", "UNKNOWN", "MULTIMODAL_CONFLICT",
               "NEW_VISUAL_CLUSTER", "NEW_PRODUCT", "NEW_MATERIAL",
               "NEW_FUNCTION", "PRODUCTION_REJECTED", "HIGH_VALUE_CANDIDATE",
               "RANDOM_AUDIT")

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def enqueue(self, segment_id: str, reason: str = "RANDOM_AUDIT",
                priority: int = 50, source: str = "system") -> int:
        if reason not in self.REASONS:
            reason = "RANDOM_AUDIT"
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        cur = conn.execute(
            "INSERT INTO review_queue(segment_id,reason,priority,source,status,created_at) "
            "VALUES(?,?,?,?, 'pending', ?)",
            (segment_id, reason, priority, source, time.time()))
        conn.commit()
        conn.close()
        return int(cur.lastrowid)

    def next_pending(self, limit: int = 10) -> list[dict]:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM review_queue WHERE status='pending' "
            "ORDER BY priority DESC, created_at LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def mark_reviewed(self, queue_id: int) -> None:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.execute("UPDATE review_queue SET status='reviewed', reviewed_at=? WHERE queue_id=?",
                     (time.time(), queue_id))
        conn.commit()
        conn.close()

    def stats(self) -> dict:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        by_status = {r[0]: r[1] for r in conn.execute(
            "SELECT status, COUNT(*) FROM review_queue GROUP BY status")}
        by_reason = {r[0]: r[1] for r in conn.execute(
            "SELECT reason, COUNT(*) FROM review_queue GROUP BY reason")}
        conn.close()
        return {"by_status": by_status, "by_reason": by_reason}


class CoverageService:
    """标注覆盖矩阵（13）。"""

    THRESHOLDS = {"EMPTY": 0, "LOW": 5, "MEDIUM": 20, "GOOD": 50}  # 配置化阈值

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _state(self, n: int) -> str:
        if n >= self.THRESHOLDS["GOOD"]:
            return "GOOD"
        if n >= self.THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        if n >= self.THRESHOLDS["LOW"]:
            return "LOW"
        return "EMPTY"

    def compute(self, dim1: str, dim2: str = "") -> list[dict]:
        """按 (dim1 × dim2) 统计覆盖。dim1/dim2 ∈ scene/product/material/function/action。"""
        with self._ro() as conn:
            if dim2:
                rows = conn.execute(
                    f"SELECT {dim1} AS d1, {dim2} AS d2, COUNT(*) n "
                    f"FROM human_annotations WHERE {dim1}!='' AND {dim2}!='' "
                    f"GROUP BY {dim1}, {dim2}").fetchall()
                return [{"dim1_value": r["d1"], "dim2_value": r["d2"],
                         "sample_count": r["n"], "coverage_state": self._state(r["n"])}
                        for r in rows]
            rows = conn.execute(
                f"SELECT {dim1} AS d1, COUNT(*) n FROM human_annotations "
                f"WHERE {dim1}!='' GROUP BY {dim1}").fetchall()
            return [{"dim1_value": r["d1"], "sample_count": r["n"],
                     "coverage_state": self._state(r["n"])} for r in rows]

    def coverage_gaps(self, dim1: str = "product", dim2: str = "scene",
                      limit: int = 10) -> list[dict]:
        """覆盖不足的组合（LOW/EMPTY）Top N。"""
        combos = self.compute(dim1, dim2)
        gaps = [c for c in combos if c["coverage_state"] in ("EMPTY", "LOW")]
        gaps.sort(key=lambda c: c["sample_count"])
        return gaps[:limit]

    def persist(self) -> int:
        """写入 annotation_coverage 表。"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        n = 0
        for dim1 in ("scene", "product", "material", "function", "action"):
            for row in self.compute(dim1):
                conn.execute(
                    "INSERT OR REPLACE INTO annotation_coverage(dim1,dim1_value,dim2,"
                    "dim2_value,sample_count,high_conf_count,coverage_state,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (dim1, row["dim1_value"], "", "", row["sample_count"], 0,
                     row["coverage_state"], time.time()))
                n += 1
        conn.commit()
        conn.close()
        return n
