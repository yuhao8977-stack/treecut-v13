"""Phase 2 Validation Closure — Segment 认知验证报告生成器。

人工审核完成后运行，计算真实 Accuracy/F1/UNKNOWN/Confusion Matrix/
Boundary Metrics/Quality Metrics/Evidence Error Analysis。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from treecut.services.segment_cognition import SegmentCognitionService

# 语义字段
SEM_FIELDS = ("scene", "product", "material", "function", "action", "shot_type", "people_presence")


class SegmentValidationReport:
    """基于 human_annotations + boundary_reviews 生成验证报告。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.svc = SegmentCognitionService(self.db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def semantic_metrics(self) -> dict:
        """L2 vs L3 准确率（仅人工审核过的样本）。"""
        with self._ro() as conn:
            rows = conn.execute("""
                SELECT h.target_id, h.scene, h.product, h.material, h.function,
                       h.action, h.shot_type, h.people_presence,
                       a.scene AS a_scene, a.product AS a_product,
                       a.material AS a_material, a.function AS a_function,
                       a.action AS a_action, a.shot_type AS a_shot_type,
                       a.people_presence AS a_people, a.confidence
                FROM human_annotations h
                JOIN semantic_annotations a ON a.annotation_id = h.annotation_id
            """).fetchall()
        n = len(rows)
        out = {"reviewed": n}
        for field in SEM_FIELDS:
            correct = unknown = 0
            for r in rows:
                human = r[field] or ""
                ai = r[f"a_{field}"] or ""
                if not human:
                    continue
                if ai == "UNKNOWN":
                    unknown += 1
                    continue
                if ai == human:
                    correct += 1
            total_answered = n - unknown
            out[field] = {
                "n": n,
                "correct": correct,
                "accuracy": round(correct / total_answered * 100, 1) if total_answered else 0,
                "unknown": unknown,
                "unknown_rate": round(unknown / n * 100, 1) if n else 0,
                "sample_size_answered": total_answered,
            }
        return out

    def quality_metrics(self) -> dict:
        """人工质量分 vs AI quality_score（MAE/MSE/相关性）。"""
        with self._ro() as conn:
            rows = conn.execute("""
                SELECT h.quality_score AS human_q,
                       a.quality_score AS ai_q
                FROM human_annotations h
                JOIN semantic_annotations a ON a.annotation_id = h.annotation_id
                WHERE h.quality_score > 0
            """).fetchall()
        n = len(rows)
        if n == 0:
            return {"n": 0, "note": "无人工质量评分样本"}
        mae = sum(abs(r["human_q"] - (r["ai_q"] if r["ai_q"] and r["ai_q"] > 0 else r["human_q"]))
                  for r in rows) / n
        # AI 未评（-1）时无法对比，单独统计
        ai_scored = [r for r in rows if r["ai_q"] and r["ai_q"] > 0]
        return {"n": n, "mae_human_vs_ai": round(mae, 2),
                "ai_scored": len(ai_scored),
                "note": "AI quality 多为 -1（Phase2 未实现），MAE 以人工分代偿"}

    def boundary_metrics(self) -> dict:
        """Boundary 审核统计（人工确认后）。"""
        with self._ro() as conn:
            rows = conn.execute("SELECT * FROM segment_boundary_reviews").fetchall()
        n = len(rows)
        if n == 0:
            return {"n": 0, "note": "无 Boundary 审核样本"}
        fields = ("boundary_start_ok", "boundary_end_ok", "action_complete",
                  "semantic_complete", "cut_mid_action", "cut_mid_sentence",
                  "usable_as_edit_unit")
        out = {"n": n}
        for f in fields:
            yes = sum(1 for r in rows if r[f] == 1)
            no = sum(1 for r in rows if r[f] == 0)
            pending = sum(1 for r in rows if r[f] == -1)
            out[f] = {"yes": yes, "no": no, "pending": pending,
                      "yes_rate": round(yes / n * 100, 1) if n else 0}
        return out

    def evidence_error_analysis(self) -> dict:
        """人工错误是否与低 overlap 证据相关（诊断，不修改）。"""
        overlap = json.load(open(
            r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\evidence_overlap_audit.json",
            encoding="utf-8")) if Path(
            r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\evidence_overlap_audit.json").exists() else []
        ov_map = {o["segment_id"]: o["max_overlap_ratio"] for o in overlap}
        with self._ro() as conn:
            rows = conn.execute("""
                SELECT h.target_id, h.function AS hf, a.function AS af
                FROM human_annotations h
                JOIN semantic_annotations a ON a.annotation_id = h.annotation_id
            """).fetchall()
        wrong = [r for r in rows if r["hf"] and r["af"] and r["hf"] != r["af"] and r["af"] != "UNKNOWN"]
        wrong_ratios = [ov_map.get(r["target_id"], None) for r in wrong]
        scored = [x for x in wrong_ratios if x is not None]
        avg = sum(scored) / len(scored) if scored else None
        return {"wrong_samples": len(wrong), "avg_overlap_of_wrong": round(avg, 3) if avg else None,
                "note": "诊断数据；不自动修改阈值"}

    def generate(self) -> dict:
        return {
            "semantic_metrics": self.semantic_metrics(),
            "quality_metrics": self.quality_metrics(),
            "boundary_metrics": self.boundary_metrics(),
            "evidence_error_analysis": self.evidence_error_analysis(),
        }
