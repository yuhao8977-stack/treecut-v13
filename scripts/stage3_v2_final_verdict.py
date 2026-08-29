# -*- coding: utf-8 -*-
"""FRESH_HOLDOUT_V2 FINAL — STEP 12-22：错误归因 + V1/V2 对比 + 最终判定。"""
import io
import json
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"


def jload(s):
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    lock = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_HUMAN_LOCK.json"), encoding="utf-8"))
    truth = {s["segment_id"]: s for s in lock["segments"]}
    pred = json.load(open(os.path.join(DATA_ROOT, "HOLDOUT_V2_AI_PREDICTIONS_V1.json"), encoding="utf-8"))
    pred_map = {r["segment_id"]: r for r in pred["results"]}
    v1m = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_METRICS.json"), encoding="utf-8"))

    # ---------- STEP 12: 错误归因 ----------
    errors = []
    for sid, t in truth.items():
        p = pred_map[sid]["final_routed_prediction"]
        pe = pred_map[sid]["raw_provider_evidence"]
        reasons = []
        # people
        if p.get("people_presence") != t["people_presence"] and t["people_presence"] not in ("", "UNKNOWN"):
            reasons.append("YOLO_FALSE_POSITIVE" if p.get("people_presence") == "YES" else "YOLO_FALSE_NEGATIVE")
        # scene/product family UNKNOWN（exam bug）
        for f in ("product_family", "scene_family", "product_variant"):
            if t.get(f) not in ("", "UNKNOWN") and p.get(f) == "UNKNOWN":
                reasons.append("UNKNOWN_OVERUSE_EXAM_BUG" if f in ("product_family", "scene_family") else "UNKNOWN_OVERUSE")
        # multi 撒网
        for f in ("material", "shot_role"):
            th = set(jload(t.get(f)))
            ph = set(p.get(f, []))
            if th and len(ph) > len(th) + 1:
                reasons.append(f"OVERPREDICTION_{f}")
        # semantic false claim
        tseq = set(jload(t.get("action_sequence")))
        pseq = set(p.get("action_sequence", []))
        fc = pseq - tseq
        if fc:
            reasons.append(f"FALSE_CLAIM:{','.join(sorted(fc)[:3])}")
        errors.append({"segment_id": sid, "stratum": t["stratum"],
                       "truth_people": t["people_presence"], "pred_people": p.get("people_presence"),
                       "truth_family": t.get("product_family"), "pred_family": p.get("product_family"),
                       "truth_scene": t.get("scene_family"), "pred_scene": p.get("scene_family"),
                       "truth_seq": sorted(tseq), "pred_seq": sorted(pseq),
                       "reasons": reasons})
    error_cases = {"manifest": "FRESH_HOLDOUT_V2_ERROR_CASES", "count": len(errors),
                   "reason_summary": dict(Counter(r for e in errors for r in e["reasons"])),
                   "cases": errors}
    json.dump(error_cases, open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_ERROR_CASES.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("ERROR_CASES:", len(errors), dict(error_cases["reason_summary"]))

    # ---------- STEP 15: V1/V2 双考试对比 ----------
    # V2 有效字段（排除 exam bug 3 字段）
    v2_metrics = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_METRICS.json"), encoding="utf-8"))
    comparison = {
        "note": "两套 Holdout 非同题；只做量级/信号比较，不做 paired significance",
        "fields": {
            "people_presence": {
                "v1": {"acc": 0.0, "unk_rate": 100.0},
                "v2": {"acc": v2_metrics["people"]["accuracy"], "f1": v2_metrics["people"]["f1"],
                       "bacc": v2_metrics["people"]["balanced_accuracy"]},
                "verdict": "V1 全 UNKNOWN → V2 F1 90.0（重大升级，Fresh 成立）"},
            "product_family": {
                "v1": {"acc": 51.7, "cond": 75.0},
                "v2": {"acc": None, "note": "INVALID_EXAM_BUG（SigLIP single scores 未保存）"},
                "verdict": "V2 Fresh 评分无效（exam 缺陷），无法对比；不构成回归结论"},
            "scene_family": {
                "v1": {"acc": 24.1, "cond": 36.8},
                "v2": {"acc": None, "note": "INVALID_EXAM_BUG"},
                "verdict": "同上，评分无效"},
            "product_variant": {
                "v1": {"acc": 0.0},
                "v2": {"acc": None, "note": "INVALID_EXAM_BUG"},
                "verdict": "V1 本就 0%（unk 100%）；V2 评分无效"},
            "component": {
                "v1": {"microF1": 49.2},
                "v2": {"microF1": v2_metrics["multi_label"]["component"]["ALL"]["micro_f1"],
                       "macroF1": v2_metrics["multi_label"]["component"]["ALL"]["macro_f1"],
                       "pred_avg": v2_metrics["multi_label"]["component"]["ALL"]["pred_avg_labels"],
                       "human_avg": v2_metrics["multi_label"]["component"]["ALL"]["human_avg_labels"]},
                "verdict": "V1 49.2 → V2 57.7（改善，Fresh 支持 V2 Policy）"},
            "function": {
                "v1": {"microF1": 55.7},
                "v2": {"microF1": v2_metrics["multi_label"]["function"]["ALL"]["micro_f1"],
                       "macroF1": v2_metrics["multi_label"]["function"]["ALL"]["macro_f1"],
                       "pred_avg": v2_metrics["multi_label"]["function"]["ALL"]["pred_avg_labels"],
                       "human_avg": v2_metrics["multi_label"]["function"]["ALL"]["human_avg_labels"]},
                "verdict": "V1 55.7 → V2 59.3（稳定改善）"},
            "material": {
                "v1": {"microF1": 23.2},
                "v2": {"microF1": v2_metrics["multi_label"]["material"]["ALL"]["micro_f1"],
                       "pred_avg": v2_metrics["multi_label"]["material"]["ALL"]["pred_avg_labels"]},
                "verdict": "V1 23.2 → V2 22.6（持平；岩板 82.4 但 pred_avg 5.2 撒网）"},
            "shot_role": {
                "v1": {"microF1": 37.3},
                "v2": {"microF1": v2_metrics["multi_label"]["shot_role"]["ALL"]["micro_f1"],
                       "pred_avg": v2_metrics["multi_label"]["shot_role"]["ALL"]["pred_avg_labels"],
                       "human_avg": v2_metrics["multi_label"]["shot_role"]["ALL"]["human_avg_labels"]},
                "verdict": "V1 37.3 → V2 36.3（持平；pred_avg 7.1 vs human 1.9 仍严重撒网）"},
        },
    }
    json.dump(comparison, open(os.path.join(DATA_ROOT, "DUAL_HOLDOUT_COMPARISON_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nDUAL_HOLDOUT_COMPARISON_V1 done")

    # ---------- STEP 17-21: 最终评级 + 判定 ----------
    fields_rating = {
        "people_presence": {"rating": "PRODUCTION_CANDIDATE",
                            "evidence": "V2 Fresh F1 90.0 / bacc 83.3 / viol=0；V1 曾全 UNKNOWN"},
        "product_family": {"rating": "LIMITED（V2 Fresh 评分无效，待补）",
                           "evidence": "V1 51.7%；V2 exam bug 评分无效，不能定论"},
        "component": {"rating": "READY/LIMITED", "evidence": "V2 Fresh microF1 57.7 / macroF1 60.4"},
        "function": {"rating": "READY/LIMITED", "evidence": "V2 Fresh microF1 59.3 / macroF1 60.9"},
        "scene_family": {"rating": "LIMITED（V2 Fresh 评分无效，待补）",
                         "evidence": "V1 24.1%；V2 exam bug 评分无效"},
        "material": {"rating": "EXPERIMENTAL", "evidence": "V2 Fresh F1 22.6；岩板 82.4 但 pred_avg 5.2 撒网"},
        "shot_role": {"rating": "EXPERIMENTAL", "evidence": "V2 Fresh F1 36.3；pred_avg 7.1 严重撒网"},
        "product_variant": {"rating": "LIMITED（评分无效，待补）", "evidence": "V1 0%；V2 无效"},
        "semantic_action": {"rating": "EXPERIMENTAL", "evidence": "PULL_OUT 2/2；abstain 正确 7；false_claim 51（CLOSE_CABINET 13/OTHER 27）；无 abstain 违规"},
    }
    # Phase3 判定
    phase3_verdict = "PASS_WITH_LIMITATIONS"
    phase3_note = ("核心升级成立：People V2 Fresh F1 90（V1 0）、component 49→57.7、function 55.7→59.3；"
                   "弱字段诚实（material/shot_role EXPERIMENTAL）；Semantic Action abstain 纪律正确（viol=0）。"
                   "限制：product_family/scene/variant 的 V2 Fresh 评分因 exam 脚本缺陷无效（SigLIP single scores 未保存），"
                   "需后续补验；shot_role 撒网仍在。")
    phase4_ready = True
    out = {"manifest": "PHASE3_FINAL_ASSESSMENT",
           "generated_at": "2026-08-29",
           "phase3_verdict": phase3_verdict, "phase3_note": phase3_note,
           "PHASE4_READY": phase4_ready,
           "fields_rating": fields_rating,
           "holdout_discipline": "V1/V2 均为永久 DO_NOT_TRAIN/DO_NOT_CALIBRATE；V2 已查看表现，未来 V3 需新 Fresh Holdout",
           "known_exam_defect": ("exam 脚本 single 字段误用 scores key（SigLIP single 返回 all_scores），"
                                 "product_family/scene_family/product_variant 的 V2 prediction 全 UNKNOWN 且 raw 未存真实值；"
                                 "3 字段 V2 Fresh 评分 INVALID，需另开补充预测（非重跑锁定 prediction）")}
    json.dump(out, open(os.path.join(DATA_ROOT, "PHASE3_FINAL_ASSESSMENT.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nPHASE3 verdict:", phase3_verdict, "| PHASE4_READY:", phase4_ready)
    for f, r in fields_rating.items():
        print(f"  {f:18s} -> {r['rating']}")


if __name__ == "__main__":
    main()
