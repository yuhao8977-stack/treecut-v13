# -*- coding: utf-8 -*-
"""Phase 3 Stage 1 — Calibration Evaluation（240 段）。

对比：rules+clip-v1（baseline，semantic_annotations 映射到 Schema V2）
     vs Phase3 multimodal candidate（opencv-heuristic-v0.1）。

输出：<data_root>/PHASE3_EVAL_RESULTS.json + 摘要打印。
"""
import json
import os
import sqlite3
import sys
import time
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.schema_v2 import (ACTION_MAP, FUNCTION_MAP, PEOPLE_MAP,
                                        PRODUCT_MAP, SCENE_MAP, SHOT_ROLE_MAP,
                                        SHOT_SCALE_MAP)
from treecut.services.visual_cognition import VisualCognitionPipeline

SINGLE_FIELDS = ["scene", "product", "shot_scale", "people"]
MULTI_FIELDS = ["material", "component", "function", "shot_role"]
ACTION_FIELD = "action"


def map_baseline(field: str, raw: str):
    raw = (raw or "").strip()
    if raw in ("", "UNKNOWN", "未知"):
        return None
    if field == "scene":
        v = SCENE_MAP.get(raw)
        return v[0] if v else None
    if field == "product":
        v = PRODUCT_MAP.get(raw)
        return v[0] if v else None
    if field == "shot_scale":
        return SHOT_SCALE_MAP.get(raw)
    if field == "people":
        return PEOPLE_MAP.get(raw.lower())
    if field == "material":
        return raw if raw in ("岩板", "实木", "奢石", "大理石", "肤感", "不锈钢", "玻璃") else None
    if field == "function":
        v = FUNCTION_MAP.get(raw)
        return v[1] if v else None
    if field == "component":
        v = FUNCTION_MAP.get(raw)
        return v[0] if v else None
    if field == "shot_role":
        return SHOT_ROLE_MAP.get(raw)
    if field == "action":
        v = ACTION_MAP.get(raw)
        return v[1] if v else None
    return None


def main():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    segs = conn.execute(
        "SELECT s.segment_id, s.asset_id, s.start_ms, s.end_ms FROM segments s "
        "JOIN canonical_human_truth t ON t.segment_id=s.segment_id "
        "WHERE t.truth_source IN ('SINGLE_REVIEW','DOUBLE_REVIEW_AGREED','DOUBLE_REVIEW_HIERARCHICAL') "
        "AND s.segment_id IN (SELECT segment_id FROM segment_boundary_reviews WHERE usable_as_edit_unit=1)"
    ).fetchall()
    truth_map = {r["segment_id"]: r for r in conn.execute(
        "SELECT * FROM canonical_human_truth")}
    baseline_map = {r["target_id"]: r for r in conn.execute(
        "SELECT * FROM semantic_annotations WHERE status='candidate'")}
    print(f"评估段数: {len(segs)}", flush=True)

    pipe = VisualCognitionPipeline(DB)
    t0 = time.time()
    rows = []
    for i, s in enumerate(segs):
        sid = s["segment_id"]
        res = pipe.analyze(sid, s["asset_id"], s["start_ms"], s["end_ms"])
        pf = res["fused"]["per_field"]
        cand = {
            "scene": pf["scene"].get("prediction", "UNKNOWN"),
            "product": pf["product"].get("prediction", "UNKNOWN"),
            "shot_scale": pf["shot_scale"].get("prediction", "UNKNOWN"),
            "people": pf["people"].get("prediction", "UNKNOWN"),
            "material": pf["material"].get("labels", []),
            "component": pf["component"].get("labels", []),
            "function": pf["function"].get("labels", []),
            "shot_role": pf["shot_role"].get("labels", []),
            "action_group": pf["action"].get("action_group", "UNKNOWN"),
            "action_sequence": pf["action"].get("action_sequence", []),
            "scores": {k: pf[k].get("score", 0.0) for k in pf},
            "gates": {k: v["evidence_sufficiency"] for k, v in res["gates"].items()},
        }
        bl = baseline_map.get(sid)
        RAW_KEYS = {"scene": "scene", "product": "product", "material": "material",
                    "function": "function", "component": "function",
                    "shot_scale": "shot_type", "shot_role": "shot_type",
                    "people": "people_presence", "action": "action"}
        baseline = {}
        for f in SINGLE_FIELDS + ["material", "function", "component", "shot_role"]:
            baseline[f] = map_baseline(f, bl[RAW_KEYS[f]]) if bl else None
        baseline["action"] = map_baseline("action", bl["action"]) if bl else None
        t = truth_map[sid]
        rows.append({
            "segment_id": sid,
            "truth": {f: t[f] for f in ("scene_family", "product_family", "shot_scale",
                                        "people_presence", "material", "component",
                                        "function", "shot_role", "action_group",
                                        "atomic_action")},
            "baseline": baseline,
            "candidate": cand,
            "technical": res["technical_v2"],
        })
        if (i + 1) % 60 == 0:
            print(f"  {i+1}/{len(segs)}  elapsed {time.time()-t0:.0f}s", flush=True)
    dt = time.time() - t0
    print(f"管线总耗时 {dt:.1f}s, 平均 {dt/len(segs):.2f}s/段", flush=True)

    # ---------------- metrics ----------------
    TRUTH_KEY = {"scene": "scene_family", "product": "product_family",
                 "shot_scale": "shot_scale", "people": "people_presence",
                 "material": "material", "component": "component",
                 "function": "function", "shot_role": "shot_role"}

    def norm_single(v):
        return v if v not in ("", "UNKNOWN", None, "NOT_APPLICABLE") else None

    def f1(p, r):
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def eval_single(rows, which, field):
        """单值字段：coverage / conditional / effective / macro F1 / UNKNOWN rate。"""
        key = TRUTH_KEY[field]
        tp = fp = fn = 0
        unknown_n = 0
        for r in rows:
            truth = norm_single(r["truth"][key])
            if truth is None:
                continue
            pred = norm_single(r[which].get(field, None))
            if pred is None:
                unknown_n += 1
                fn += 1
                continue
            if pred == truth:
                tp += 1
            else:
                fp += 1
                fn += 1
        human_valid = tp + fp + fn
        answered = tp + fp
        coverage = answered / human_valid if human_valid else 0.0
        conditional = tp / answered if answered else 0.0
        effective = tp / human_valid if human_valid else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        return {"coverage": round(coverage * 100, 1), "conditional_accuracy": round(conditional * 100, 1),
                "effective_correct_rate": round(effective * 100, 1), "macro_f1": round(f1(prec, rec) * 100, 1),
                "unknown_rate": round(unknown_n / human_valid * 100, 1) if human_valid else 0.0,
                "n": human_valid}

    def eval_multi(rows, which, field):
        """多标签字段：micro P/R/F1、macro F1、exact set match、标签覆盖率。"""
        key = TRUTH_KEY[field]
        tp = fp = fn = 0
        exact_ok = 0
        valid = 0
        per_label = {}
        for r in rows:
            tval = r["truth"][key]
            truth_set = {tval} if tval not in ("", "UNKNOWN", "NOT_APPLICABLE", None) else set()
            if not truth_set:
                continue
            valid += 1
            pred_set = set(r[which].get(field, []) or [])
            if pred_set == truth_set:
                exact_ok += 1
            for lab in truth_set:
                if lab in pred_set:
                    tp += 1
                else:
                    fn += 1
                    per_label.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})
                    per_label[lab]["fn"] += 1
            for lab in pred_set - truth_set:
                fp += 1
                per_label.setdefault(lab, {"tp": 0, "fp": 0, "fn": 0})
                per_label[lab]["fp"] += 1
        micro_p = tp / (tp + fp) if (tp + fp) else 0.0
        micro_r = tp / (tp + fn) if (tp + fn) else 0.0
        f1s = []
        for v in per_label.values():
            p_ = v["tp"] / (v["tp"] + v["fp"]) if (v["tp"] + v["fp"]) else 0.0
            r_ = v["tp"] / (v["tp"] + v["fn"]) if (v["tp"] + v["fn"]) else 0.0
            f1s.append(f1(p_, r_))
        macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
        return {"micro_precision": round(micro_p * 100, 1), "micro_recall": round(micro_r * 100, 1),
                "micro_f1": round(f1(micro_p, micro_r) * 100, 1), "macro_f1": round(macro_f1 * 100, 1),
                "exact_set_match": round(exact_ok / valid * 100, 1) if valid else 0.0,
                "n": valid}

    def eval_action(rows, which):
        """action：sequence exact match、group accuracy、edit distance。"""
        seq_ok = group_ok = 0
        dist_sum = 0
        valid = 0
        for r in rows:
            truth_seq = [a for a in (r["truth"]["atomic_action"] or "").split(",")
                         if a and a != "UNKNOWN"]
            truth_group = r["truth"]["action_group"]
            if not truth_seq and truth_group in ("", "UNKNOWN"):
                continue
            valid += 1
            if which == "candidate":
                cand_seq = r["candidate"]["action_sequence"] or []
                cand_group = r["candidate"]["action_group"]
            else:
                # baseline 无 sequence → 单原子
                cand_seq = [r["baseline"]["action"]] if r["baseline"]["action"] else []
                cand_group = "UNKNOWN"
            d = 0
            for i in range(max(len(truth_seq), len(cand_seq))):
                a = truth_seq[i] if i < len(truth_seq) else ""
                b = cand_seq[i] if i < len(cand_seq) else ""
                d += 0 if a == b else 1
            dist_sum += d
            if cand_seq == truth_seq:
                seq_ok += 1
            if cand_group == truth_group:
                group_ok += 1
        return {"sequence_exact_match": round(seq_ok / valid * 100, 1) if valid else 0.0,
                "group_accuracy": round(group_ok / valid * 100, 1) if valid else 0.0,
                "mean_edit_distance": round(dist_sum / valid, 2) if valid else 0.0,
                "n": valid}

    metrics = {}
    for f in SINGLE_FIELDS:
        metrics[f] = {"baseline": eval_single(rows, "baseline", f),
                      "candidate": eval_single(rows, "candidate", f)}
    for f in MULTI_FIELDS:
        metrics[f] = {"baseline": eval_multi(rows, "baseline", f),
                      "candidate": eval_multi(rows, "candidate", f)}
    metrics["action"] = {"baseline": eval_action(rows, "baseline"),
                         "candidate": eval_action(rows, "candidate")}
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M"),
           "n_segments": len(rows),
           "pipeline_avg_seconds": round(dt / len(segs), 2),
           "metrics": metrics,
           "rows": rows,
           "note": ("240 为 CALIBRATION_CORPUS_V1（非 holdout，非 generalization accuracy）；"
                    "candidate 为 opencv-heuristic-v0.1 原型"),
           }
    with open(os.path.join(DATA_ROOT, "PHASE3_EVAL_RESULTS.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n== Metrics (baseline rules+clip-v1 vs Phase3 candidate) ==")
    for f, m in metrics.items():
        b, c = m["baseline"], m["candidate"]
        if f in SINGLE_FIELDS:
            print(f"{f:12s} base eff={b['effective_correct_rate']}% cond={b['conditional_accuracy']}% cov={b['coverage']}% | cand eff={c['effective_correct_rate']}% cond={c['conditional_accuracy']}% cov={c['coverage']}% unk={c['unknown_rate']}%")
        elif f == "action":
            print(f"{f:12s} base group={b.get('group_accuracy')}% | cand group={c['group_accuracy']}% seq={c['sequence_exact_match']}% edit={c['mean_edit_distance']}")
        else:
            print(f"{f:12s} base microF1={b['micro_f1']}% | cand microF1={c['micro_f1']}% exact={c['exact_set_match']}%")


if __name__ == "__main__":
    main()
