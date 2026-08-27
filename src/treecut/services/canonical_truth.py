# -*- coding: utf-8 -*-
"""TreeCut Phase 2.5.1 — Canonical Human Truth 解析服务。

职责：
  1. 每个 segment_id 只产生 1 条 canonical_human_truth（生产单位口径）；
  2. v1/v2 历史标注映射到 ANNOTATION_DICTIONARY_V2 枚举后做 Truth Resolution；
  3. 保留全部历史（v1/v2 表不动），canonical truth 是只增的裁决产物。

Truth Resolution Policy（架构监工冻结）：
  SINGLE_REVIEW              — 仅一次有效人工审核
  DOUBLE_REVIEW_AGREED       — 两次审核 Schema V2 口径全一致
  DOUBLE_REVIEW_HIERARCHICAL — 两次审核仅在族/变体层级兼容（取更具体值）
  NEEDS_ADJUDICATION         — 存在字段级真冲突 → 不进入训练，等第三次裁决
  EXCLUDED                   — 无有效人工真值（空提交/视频无法播放）
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from pathlib import Path

from treecut.services.schema_v2 import (
    ACTION_MAP, DICTIONARY_VERSION, FUNCTION_MAP, PEOPLE_MAP, PRODUCT_MAP,
    SCENE_MAP, SHOT_ROLE_MAP, SHOT_SCALE_MAP, TRUTH_FIELDS, freeze_schema,
)


class CanonicalTruthService:
    """Canonical Human Truth 解析服务。"""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from treecut.platform.paths import RuntimePaths
            db_path = RuntimePaths.discover().databases / "materials.db"
        self.db_path = Path(db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _write(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=30)

    # ------------------------------------------------------------------

    @staticmethod
    def _complete(r) -> bool:
        keys = ("scene", "product", "material", "function", "action",
                "shot_type", "people_presence")
        return all((r[k] or "").strip() not in ("", "UNKNOWN", "未知") for k in keys)

    def map_record_to_v2(self, r) -> dict:
        """把一条 v1/v2 记录映射为 Schema V2 字段。"""
        scene = (r["scene"] or "UNKNOWN").strip()
        product = (r["product"] or "UNKNOWN").strip()
        function = (r["function"] or "UNKNOWN").strip()
        action = (r["action"] or "UNKNOWN").strip()
        shot_type = (r["shot_type"] or "UNKNOWN").strip()
        material = (r["material"] or "UNKNOWN").strip()
        people = (r["people_presence"] or "").strip().lower()
        sf, ss = SCENE_MAP.get(scene, ("UNKNOWN", "UNKNOWN"))
        pf, pv_ = PRODUCT_MAP.get(product, ("UNKNOWN", "UNKNOWN"))
        cp, fn = FUNCTION_MAP.get(function, ("UNKNOWN", "UNKNOWN"))
        ag, aa = ACTION_MAP.get(action, ("UNKNOWN", "UNKNOWN"))
        m = material if material in (
            "岩板", "实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃", "其他") else "UNKNOWN"
        pv = r["product_visibility"] if "product_visibility" in r.keys() else -1.0
        if isinstance(pv, (int, float)):
            vis = "UNKNOWN" if pv in (-1, -1.0) else str(pv)
        else:
            vis = (pv or "UNKNOWN").strip()
        q = r["quality_score"] if "quality_score" in r.keys() else None
        return {
            "scene_family": sf, "scene_subtype": ss,
            "product_family": pf, "product_variant": pv_,
            "material": m, "component": cp, "function": fn,
            "action_group": ag, "atomic_action": aa,
            "shot_scale": SHOT_SCALE_MAP.get(shot_type, "UNKNOWN"),
            "shot_role": SHOT_ROLE_MAP.get(shot_type, "UNKNOWN"),
            "people_presence": PEOPLE_MAP.get(people, "UNKNOWN"),
            "product_visibility": vis,
            "quality": q,
        }

    # ------------------------------------------------------------------

    def _merge_fields(self, a: dict, b: dict) -> tuple[dict, list[str], bool]:
        """合并两个 Schema V2 映射。返回 (合并真值, 冲突字段, 是否层级补全)。"""
        merged = {}
        conflicts = []
        hierarchical = False
        for f in TRUTH_FIELDS:
            va, vb = a[f], b[f]
            if f == "quality":
                merged[f] = va if va is not None else vb
                continue
            if va == vb:
                merged[f] = va
                continue
            # 一方是 UNKNOWN / NOT_APPLICABLE / 空 → 用有值方（层级补全）
            if va in ("UNKNOWN", "NOT_APPLICABLE", ""):
                if vb not in ("UNKNOWN", "NOT_APPLICABLE", ""):
                    hierarchical = True
                merged[f] = vb
                continue
            if vb in ("UNKNOWN", "NOT_APPLICABLE", ""):
                if va not in ("UNKNOWN", "NOT_APPLICABLE", ""):
                    hierarchical = True
                merged[f] = va
                continue
            # 族/变体层级兼容：family 相同，variant 一方未知 → 取更具体
            if f == "product_variant" and a["product_family"] == b["product_family"]:
                hierarchical = True
                merged[f] = vb  # v2 变体更具体（审计假设：v2 优先）
                continue
            if f == "scene_subtype" and a["scene_family"] == b["scene_family"]:
                hierarchical = True
                merged[f] = vb
                continue
            conflicts.append(f)
            merged[f] = va  # 保留 v1 值作参考，段标记 NEEDS_ADJUDICATION
        return merged, conflicts, hierarchical

    def resolve_segment(self, v1: dict | None, v2: dict | None,
                        v1_row: dict | None = None,
                        v2_row: dict | None = None) -> dict:
        """单段 Truth Resolution。v1/v2 为已映射的 Schema V2 dict。"""
        now = time.time()
        base = {
            "truth_source": "SINGLE_REVIEW", "agreement_level": "single",
            "human_evidence_count": 0, "human_confidence": "MEDIUM",
            "review_status": "REVIEWED", "dictionary_version": DICTIONARY_VERSION,
            "v1_record_id": None, "v2_record_id": None,
            "created_at": now, "updated_at": now,
        }
        if v1 is None and v2 is None:
            base["truth_source"] = "EXCLUDED"
            base["agreement_level"] = "none"
            base["review_status"] = "EXCLUDED"
            return base
        if v1 is not None and v2 is not None:
            merged, conflicts, hierarchical = self._merge_fields(v1, v2)
            base["human_evidence_count"] = 2
            base.update({f: merged.get(f) for f in TRUTH_FIELDS})
            if v2_row is not None:
                base["human_confidence"] = v2_row.get("human_confidence") or "MEDIUM"
                base["v2_record_id"] = v2_row.get("v2_id")
            if v1_row is not None:
                base["v1_record_id"] = v1_row.get("adjudication_id")
            if conflicts:
                base["truth_source"] = "NEEDS_ADJUDICATION"
                base["agreement_level"] = "conflict"
                base["review_status"] = "NEEDS_SECOND_REVIEW"
                base["conflicts"] = conflicts
            elif hierarchical:
                base["truth_source"] = "DOUBLE_REVIEW_HIERARCHICAL"
                base["agreement_level"] = "hierarchical"
                base["review_status"] = "GOLD"
            else:
                base["truth_source"] = "DOUBLE_REVIEW_AGREED"
                base["agreement_level"] = "exact"
                base["review_status"] = "GOLD"
            return base
        src = v1 if v1 is not None else v2
        row = v1_row if v1 is not None else v2_row
        base["human_evidence_count"] = 1
        base.update({f: src.get(f) for f in TRUTH_FIELDS})
        if row is not None:
            base["human_confidence"] = row.get("human_confidence") or "MEDIUM"
            if v1 is not None:
                base["v1_record_id"] = row.get("adjudication_id")
            else:
                base["v2_record_id"] = row.get("v2_id")
        return base

    # ------------------------------------------------------------------

    def resolve_all(self, persist: bool = True) -> dict:
        """全量解析 300 段并写入 canonical_human_truth（只增不覆盖历史）。"""
        with self._ro() as conn:
            v1_rows = {r["target_id"]: r for r in conn.execute(
                "SELECT * FROM human_annotations")}
            v2_rows = {r["segment_id"]: r for r in conn.execute(
                "SELECT * FROM human_annotation_v2")}
            all_sids = sorted(set(v1_rows) | set(v2_rows))

        results = []
        for sid in all_sids:
            v1r = v1_rows.get(sid)
            v2r = v2_rows.get(sid)
            v1_map = self.map_record_to_v2(v1r) if v1r is not None else None
            v2_map = self.map_record_to_v2(v2r) if v2r is not None else None
            # 空提交（v2 无有效字段）视为无 v2
            if v2r is not None and not self._complete(v2r):
                v2_map = None
            if v1r is not None and not self._complete(v1r):
                v1_map = None
            res = self.resolve_segment(v1_map, v2_map,
                                       v1_row=dict(v1r) if v1r is not None else None,
                                       v2_row=dict(v2r) if v2r is not None else None)
            res["segment_id"] = sid
            res.pop("conflicts", None)
            results.append(res)

        if persist:
            self._upsert(results)

        stats = {
            "total_segments": len(results),
            "by_source": dict(Counter(r["truth_source"] for r in results)),
            "by_agreement": dict(Counter(r["agreement_level"] for r in results)),
            "needs_adjudication": [r["segment_id"] for r in results
                                   if r["truth_source"] == "NEEDS_ADJUDICATION"],
            "excluded": [r["segment_id"] for r in results
                         if r["truth_source"] == "EXCLUDED"],
        }
        return {"stats": stats, "rows": results}

    def _upsert(self, rows: list[dict]) -> None:
        conn = self._write()
        try:
            for r in rows:
                conn.execute(
                    "INSERT OR REPLACE INTO canonical_human_truth("
                    "segment_id,scene_family,scene_subtype,product_family,"
                    "product_variant,material,component,function,action_group,"
                    "atomic_action,shot_scale,shot_role,people_presence,"
                    "product_visibility,quality,truth_source,agreement_level,"
                    "human_evidence_count,human_confidence,review_status,"
                    "dictionary_version,v1_record_id,v2_record_id,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["segment_id"], r.get("scene_family", "UNKNOWN"),
                     r.get("scene_subtype", "UNKNOWN"),
                     r.get("product_family", "UNKNOWN"),
                     r.get("product_variant", "UNKNOWN"),
                     r.get("material", "UNKNOWN"),
                     r.get("component", "UNKNOWN"),
                     r.get("function", "UNKNOWN"),
                     r.get("action_group", "UNKNOWN"),
                     r.get("atomic_action", "UNKNOWN"),
                     r.get("shot_scale", "UNKNOWN"),
                     r.get("shot_role", "UNKNOWN"),
                     r.get("people_presence", "UNKNOWN"),
                     r.get("product_visibility", "UNKNOWN"),
                     r.get("quality"),
                     r["truth_source"], r["agreement_level"],
                     r["human_evidence_count"], r["human_confidence"],
                     r["review_status"], r["dictionary_version"],
                     r.get("v1_record_id"), r.get("v2_record_id"),
                     r["created_at"], r["updated_at"]))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------

    def freeze_dictionary(self) -> int:
        """把 ANNOTATION_DICTIONARY_V2 写入 annotation_dictionary 表。"""
        import subprocess
        repo = Path(__file__).resolve().parents[3]
        try:
            commit = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            commit = ""
        payload = json.dumps(freeze_schema(), ensure_ascii=False)
        conn = self._write()
        try:
            cur = conn.execute(
                "INSERT OR REPLACE INTO annotation_dictionary(version,schema_json,"
                "frozen_at,git_commit,notes) VALUES(?,?,?,?,?)",
                (DICTIONARY_VERSION, payload, time.time(), commit,
                 "Phase 2.5.1 架构监工冻结"))
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()
