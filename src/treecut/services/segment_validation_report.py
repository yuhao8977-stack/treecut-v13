"""Phase 2 Validation Snapshot — Segment 认知验证报告生成器（完整版）。

人工审核 300 条完成后运行，输出：
  样本/有效/跳过/待定
  各字段 accuracy/precision/recall/F1/UNKNOWN rate/sample_size/confusion matrix
  质量 MAE/mean signed error/median abs error/correlation
  Boundary 各项 rate
  Evidence Error Analysis（ASR/OCR/CLIP/asset_context/overlap 关系）
  TOP 错误类别 + 典型样本
  高置信但错误 / 低置信但正确 / UNKNOWN但人工可判 / 完全冲突
  标记 VALIDATION_SNAPSHOT_V1
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from treecut.services.segment_cognition import SegmentCognitionService

SEM_FIELDS = ("scene", "product", "material", "function", "action", "shot_type", "people_presence")


class SegmentValidationReport:
    """完整验证快照生成器。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.svc = SegmentCognitionService(self.db_path)

    def _ro(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            "file:" + str(self.db_path).replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def _load_reviews(self) -> list[dict]:
        with self._ro() as conn:
            rows = conn.execute("""
                SELECT h.target_id, h.scene, h.product, h.material, h.function,
                       h.action, h.shot_type, h.people_presence, h.quality_score,
                       h.comment, h.operator,
                       a.scene AS a_scene, a.product AS a_product,
                       a.material AS a_material, a.function AS a_function,
                       a.action AS a_action, a.shot_type AS a_shot_type,
                       a.people_presence AS a_people, a.confidence,
                       a.evidence_refs_json, a.algorithm_version
                FROM human_annotations h
                JOIN semantic_annotations a ON a.annotation_id = h.annotation_id
            """).fetchall()
        return [dict(r) for r in rows]

    def _load_boundary(self) -> list[dict]:
        with self._ro() as conn:
            rows = conn.execute("SELECT * FROM segment_boundary_reviews").fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # 1. 样本统计
    # ------------------------------------------------------------------

    def _sample_stats(self, reviews: list[dict]) -> dict:
        total = len(reviews)
        effective = sum(1 for r in reviews if r.get("scene") or r.get("product") or r.get("function"))
        skipped = sum(1 for r in reviews if r.get("comment", "").find("跳过") >= 0)
        pending = sum(1 for r in reviews if not (r.get("scene") or r.get("product") or r.get("function")))
        return {"total": total, "effective": effective, "skipped": skipped, "pending": pending}

    # ------------------------------------------------------------------
    # 2. 各字段指标（accuracy/precision/recall/F1/confusion）
    # ------------------------------------------------------------------

    def _field_metrics(self, reviews: list[dict]) -> dict:
        out = {}
        for field in SEM_FIELDS:
            human_key, ai_key = field, f"a_{field}"
            # 只统计 AI 非 UNKNOWN 且人工有值的样本
            cm = defaultdict(Counter)  # ai -> human count
            unknown_ai = 0
            unknown_human = 0
            for r in reviews:
                ai = r.get(ai_key) or ""
                hu = r.get(human_key) or ""
                if ai == "UNKNOWN":
                    unknown_ai += 1
                    if hu and hu != "UNKNOWN":
                        unknown_human += 1
                    continue
                if not hu:
                    continue
                cm[ai][hu if hu != "UNKNOWN" else "(人工UNKNOWN)"] += 1
            # 计算 per-class precision/recall/F1 + macro avg
            classes = set()
            for ai_map in cm.values():
                classes.update(ai_map.keys())
            classes.update(cm.keys())
            class_metrics = {}
            for cls in sorted(classes):
                tp = cm[cls].get(cls, 0)
                fp = sum(v for k, v in cm[cls].items() if k != cls)
                fn = sum(m.get(cls, 0) for k, m in cm.items() if k != cls)
                prec = tp / (tp + fp) if tp + fp else 0
                rec = tp / (tp + fn) if tp + fn else 0
                f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
                class_metrics[cls] = {"tp": tp, "fp": fp, "fn": fn,
                                      "precision": round(prec, 3), "recall": round(rec, 3),
                                      "f1": round(f1, 3)}
            # 总体
            correct = sum(m.get(k, 0) for k, m in cm.items())
            total_answered = sum(sum(m.values()) for m in cm.values())
            macro_p = sum(c["precision"] for c in class_metrics.values()) / len(class_metrics) if class_metrics else 0
            macro_r = sum(c["recall"] for c in class_metrics.values()) / len(class_metrics) if class_metrics else 0
            macro_f1 = sum(c["f1"] for c in class_metrics.values()) / len(class_metrics) if class_metrics else 0
            out[field] = {
                "n": len(reviews),
                "answered": total_answered,
                "accuracy": round(correct / total_answered * 100, 1) if total_answered else 0,
                "macro_precision": round(macro_p, 3),
                "macro_recall": round(macro_r, 3),
                "macro_f1": round(macro_f1, 3),
                "unknown_ai": unknown_ai,
                "unknown_rate": round(unknown_ai / len(reviews) * 100, 1) if reviews else 0,
                "unknown_but_human_answered": unknown_human,
                "sample_size": total_answered,
                "confusion_matrix": {k: dict(v) for k, v in cm.items()},
            }
        return out

    # ------------------------------------------------------------------
    # 3. 质量评分
    # ------------------------------------------------------------------

    def _quality_metrics(self, reviews: list[dict]) -> dict:
        pairs = [(r.get("quality_score"), r.get("a_confidence")) for r in reviews
                 if r.get("quality_score") and r.get("quality_score") > 0]
        human_q = [p[0] for p in pairs]
        # AI 无 quality（-1），用 confidence 作为 AI 分代理不合适——分开统计
        n = len(pairs)
        if n == 0:
            return {"n": 0, "note": "无人工质量分样本"}
        # 人工质量分布
        avg_h = sum(human_q) / n
        return {
            "n": n,
            "human_quality_avg": round(avg_h, 1),
            "human_quality_median": round(sorted(human_q)[n // 2], 1),
            "human_quality_min": min(human_q),
            "human_quality_max": max(human_q),
            "note": "AI quality 全为 -1（Phase2 未实现），无法计算 AI vs Human MAE；待 Phase 3 技术质量接入",
        }

    # ------------------------------------------------------------------
    # 4. Boundary
    # ------------------------------------------------------------------

    def _boundary_metrics(self, reviews: list[dict]) -> dict:
        rows = self._load_boundary()
        n = len(rows)
        if n == 0:
            return {"n": 0, "note": "无 Boundary 审核"}
        fields = ("boundary_start_ok", "boundary_end_ok", "action_complete",
                  "semantic_complete", "cut_mid_action", "cut_mid_sentence",
                  "usable_as_edit_unit")
        out = {"n": n}
        for f in fields:
            yes = sum(1 for r in rows if r[f] == 1)
            no = sum(1 for r in rows if r[f] == 0)
            pend = sum(1 for r in rows if r[f] == -1)
            out[f] = {"yes": yes, "no": no, "pending": pend,
                      "rate": round(yes / n * 100, 1) if n else 0}
        return out

    # ------------------------------------------------------------------
    # 5-7. Evidence Error Analysis + TOP 错误
    # ------------------------------------------------------------------

    def _load_overlap(self) -> dict:
        p = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\evidence_overlap_audit.json")
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        return {d["segment_id"]: d for d in data}

    def _error_analysis(self, reviews: list[dict]) -> dict:
        """错误分类：TOP 错误类别 + 高置信错误/低置信正确/UNKNOWN可判/完全冲突。"""
        overlap_map = self._load_overlap()
        top_errors = Counter()   # (field, ai, human) 组合
        error_samples = []       # 详细样本
        high_conf_wrong = []
        low_conf_correct = []
        unknown_but_judgeable = []
        conflict = []
        for r in reviews:
            seg_id = r["target_id"]
            ov = overlap_map.get(seg_id, {})
            max_ratio = ov.get("max_overlap_ratio", None)
            conf = r.get("confidence") or 0
            ev = {}
            try:
                ev = json.loads(r.get("evidence_refs_json") or "{}")
            except Exception:
                pass
            has_asr = bool(ev.get("asr_text"))
            has_ocr = bool(ev.get("ocr_text"))
            has_clip = bool(ev.get("clip_tags"))
            # 逐字段判断
            any_wrong = False
            for field in ("scene", "product", "material", "function", "action"):
                ai = r.get(f"a_{field}") or ""
                hu = r.get(field) or ""
                if ai and ai != "UNKNOWN" and hu and hu != "UNKNOWN" and ai != hu:
                    any_wrong = True
                    top_errors[(field, ai, hu)] += 1
                    if len(error_samples) < 30:
                        error_samples.append({
                            "segment_id": seg_id, "field": field,
                            "ai": ai, "human": hu,
                            "confidence": conf, "evidence": ev,
                            "overlap_ratio": max_ratio,
                        })
            # 高置信但错误
            if any_wrong and conf >= 0.8:
                high_conf_wrong.append({"segment_id": seg_id, "confidence": conf,
                                        "ai": {f: r.get(f"a_{f}") for f in ("function", "product", "scene")},
                                        "human": {f: r.get(f) for f in ("function", "product", "scene")}})
            # 低置信但正确
            if not any_wrong and conf < 0.5:
                low_conf_correct.append({"segment_id": seg_id, "confidence": conf})
            # UNKNOWN 但人工可明确判断
            for field in ("scene", "product", "material", "function"):
                ai = r.get(f"a_{field}") or ""
                hu = r.get(field) or ""
                if ai == "UNKNOWN" and hu and hu != "UNKNOWN":
                    unknown_but_judgeable.append({"segment_id": seg_id, "field": field,
                                                  "human": hu, "confidence": conf})
                    break
            # 完全冲突（人工与 AI 在多个字段相反）
            if any_wrong:
                conflict.append({"segment_id": seg_id, "confidence": conf})
        return {
            "top_error_categories": [{"field": f, "ai": a, "human": h, "count": c}
                                     for (f, a, h), c in top_errors.most_common(15)],
            "error_samples": error_samples[:20],
            "high_confidence_wrong": high_conf_wrong[:10],
            "high_confidence_wrong_count": len(high_conf_wrong),
            "low_confidence_correct": low_conf_correct[:10],
            "low_confidence_correct_count": len(low_conf_correct),
            "unknown_but_human_judgeable": unknown_but_judgeable[:10],
            "unknown_but_human_judgeable_count": len(unknown_but_judgeable),
            "conflict_samples": conflict[:10],
            "conflict_count": len(conflict),
        }

    def _evidence_relationship(self, reviews: list[dict]) -> dict:
        """错误与证据类型/overlap 的关系。"""
        overlap_map = self._load_overlap()
        wrong_with_asr = 0
        wrong_with_ocr = 0
        wrong_with_clip = 0
        wrong_total = 0
        wrong_overlaps = []
        for r in reviews:
            ai_f = r.get("a_function") or ""
            hu_f = r.get("function") or ""
            wrong = ai_f and ai_f != "UNKNOWN" and hu_f and hu_f != "UNKNOWN" and ai_f != hu_f
            if not wrong:
                continue
            wrong_total += 1
            ev = {}
            try:
                ev = json.loads(r.get("evidence_refs_json") or "{}")
            except Exception:
                pass
            if ev.get("asr_text"):
                wrong_with_asr += 1
            if ev.get("ocr_text"):
                wrong_with_ocr += 1
            if ev.get("clip_tags"):
                wrong_with_clip += 1
            ov = overlap_map.get(r["target_id"], {})
            mr = ov.get("max_overlap_ratio")
            if mr is not None:
                wrong_overlaps.append(mr)
        return {
            "function_wrong_total": wrong_total,
            "wrong_with_asr": wrong_with_asr,
            "wrong_with_ocr": wrong_with_ocr,
            "wrong_with_clip": wrong_with_clip,
            "avg_overlap_of_wrong": round(sum(wrong_overlaps) / len(wrong_overlaps), 3) if wrong_overlaps else None,
            "note": "诊断数据；不自动修改",
        }

    # ------------------------------------------------------------------

    def generate(self) -> dict:
        reviews = self._load_reviews()
        return {
            "snapshot": "VALIDATION_SNAPSHOT_V1",
            "frozen_git_commit": "5c99564",
            "model": {"name": "rules+clip-v1", "version": "1.0",
                      "algorithm": "segment-cognition-v1"},
            "sample_stats": self._sample_stats(reviews),
            "field_metrics": self._field_metrics(reviews),
            "quality_metrics": self._quality_metrics(reviews),
            "boundary_metrics": self._boundary_metrics(reviews),
            "error_analysis": self._error_analysis(reviews),
            "evidence_relationship": self._evidence_relationship(reviews),
        }
