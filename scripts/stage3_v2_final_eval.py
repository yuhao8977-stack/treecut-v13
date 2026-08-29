# -*- coding: utf-8 -*-
"""FRESH_HOLDOUT_V2 FINAL EVAL — STEP 2-16：完整评分 + 四层 + 错误归因 + V1/V2 对比。

使用：FRESH_HOLDOUT_V2_HUMAN_LOCK（人工真值）+ HOLDOUT_V2_AI_PREDICTIONS_V1（AI 交卷）。
纪律：不改 prediction / 不重新预测 / 不修改 Bundle。
"""
import io
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"

SINGLE_FIELDS = ["people_presence", "product_family", "product_variant",
                 "scene_family", "scene_subtype", "shot_scale", "product_visibility"]
MULTI_FIELDS = ["material", "component", "function", "shot_role"]


def jload(s):
    """兼容 str-JSON 与 list：HUMAN_LOCK 中 multi 字段已是 list。"""
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0, center - half) * 100, 1), round(min(1, center + half) * 100, 1))


def single_metrics(truth_val, pred_val):
    if pred_val == truth_val:
        return True
    return False


def main():
    lock = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_HUMAN_LOCK.json"), encoding="utf-8"))
    truth = {s["segment_id"]: s for s in lock["segments"]}
    pred = json.load(open(os.path.join(DATA_ROOT, "HOLDOUT_V2_AI_PREDICTIONS_V1.json"), encoding="utf-8"))
    pred_map = {r["segment_id"]: r for r in pred["results"]}
    assert set(truth) == set(pred_map), "AI pred 与 Human truth segment 不一致！"

    strata = {s["segment_id"]: s["stratum"] for s in lock["segments"]}
    layers = {"RANDOM": [], "HARD": [], "GAP": [], "ALL": []}
    for sid in truth:
        layers[strata[sid]].append(sid)
        layers["ALL"].append(sid)
    print("分层:", {k: len(v) for k, v in layers.items()})

    # ---------- STEP 5: single-label ----------
    # exam 脚本缺陷：single 字段（product_family/scene_family/product_variant）误用
    # scores key（SigLIP single 返回 all_scores 非 scores）→ prediction 全 UNKNOWN 且 raw 未存真实值。
    # 这 3 字段的 V2 评分 INVALID（不可当模型真实表现）；people/shot_scale 等不受影响。
    EXAM_BUG_SINGLE = {"product_family", "scene_family", "product_variant"}
    single_out = {}
    for f in SINGLE_FIELDS:
        per_layer = {}
        for layer, sids in layers.items():
            n_valid = correct = unknown = missing = 0
            for sid in sids:
                t = truth[sid].get(f)
                if t in ("", "UNKNOWN", None):
                    continue
                n_valid += 1
                if f not in pred_map[sid]["final_routed_prediction"]:
                    missing += 1
                    continue
                p = pred_map[sid]["final_routed_prediction"].get(f)
                if p in ("", "UNKNOWN", None):
                    unknown += 1
                    continue
                if p == t:
                    correct += 1
            denom = n_valid - missing
            cov = (denom - unknown) / denom if denom else 0
            cond_acc = correct / (denom - unknown) if (denom - unknown) else 0
            valid_flag = "OK"
            if f in EXAM_BUG_SINGLE and unknown == n_valid:
                valid_flag = "INVALID_EXAM_BUG（SigLIP single scores 未保存；不可当模型真实表现）"
            per_layer[layer] = {"n_valid": n_valid, "correct": correct, "unknown": unknown,
                                "missing_from_prediction": missing, "validity": valid_flag,
                                "accuracy": round(correct / n_valid * 100, 1) if n_valid else 0,
                                "coverage": round(cov * 100, 1),
                                "conditional_accuracy": round(cond_acc * 100, 1),
                                "effective_correct_rate": round(correct / n_valid * 100, 1) if n_valid else 0,
                                "unknown_rate": round(unknown / n_valid * 100, 1) if n_valid else 0,
                                "wilson_ci": wilson_ci(correct, n_valid)}
        single_out[f] = per_layer
        print(f"\n[{f}]")
        for layer in ("RANDOM", "HARD", "GAP", "ALL"):
            r = per_layer[layer]
            print(f"  {layer:6s} n={r['n_valid']:2d} correct={r['correct']:2d} acc={r['accuracy']:5.1f}% "
                  f"cond={r['conditional_accuracy']:5.1f}% unk={r['unknown_rate']:4.1f}% "
                  f"miss={r['missing_from_prediction']:2d} CI={r['wilson_ci']} [{r['validity'][:12]}]")

    # ---------- STEP 6: multi-label ----------
    multi_out = {}
    for f in MULTI_FIELDS:
        per_layer = {}
        for layer, sids in layers.items():
            tp = fp = fn = valid = exact = 0
            pred_cnt = human_cnt = 0
            macro_f1s = []
            per_class = defaultdict(lambda: {"support": 0, "tp": 0, "fp": 0, "fn": 0})
            for sid in sids:
                tset = set(jload(truth[sid].get(f, "")))
                if not tset:
                    continue
                valid += 1
                pset = set(pred_map[sid]["final_routed_prediction"].get(f, []))
                pred_cnt += len(pset)
                human_cnt += len(tset)
                if pset == tset:
                    exact += 1
                for lab in tset:
                    per_class[lab]["support"] += 1
                    if lab in pset:
                        per_class[lab]["tp"] += 1
                    else:
                        per_class[lab]["fn"] += 1
                for lab in pset:
                    if lab not in tset:
                        per_class[lab]["fp"] += 1
                tp += len(tset & pset)
                fn += len(tset - pset)
                fp += len(pset - tset)
                p_s = len(tset & pset) / len(pset) if pset else 0
                r_s = len(tset & pset) / len(tset) if tset else 0
                if p_s + r_s:
                    macro_f1s.append(2 * p_s * r_s / (p_s + r_s))
            mp = tp / (tp + fp) if (tp + fp) else 0
            mr = tp / (tp + fn) if (tp + fn) else 0
            pc = {}
            for lab, s in per_class.items():
                P = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0
                R = s["tp"] / s["n"] if False else (s["tp"] / s["support"] if s["support"] else 0)
                pc[lab] = {"support": s["support"], "tp": s["tp"], "fp": s["fp"], "fn": s["fn"],
                           "precision": round(P * 100, 1), "recall": round(R * 100, 1),
                           "f1": round(f1(P, R) * 100, 1),
                           "status": ("INSUFFICIENT_SAMPLE" if s["support"] < 5 else "OK")}
            per_layer[layer] = {"n_segments": valid,
                                "micro_precision": round(mp * 100, 1), "micro_recall": round(mr * 100, 1),
                                "micro_f1": round(f1(mp, mr) * 100, 1),
                                "macro_f1": round(sum(macro_f1s) / len(macro_f1s) * 100, 1) if macro_f1s else 0,
                                "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
                                "pred_avg_labels": round(pred_cnt / valid, 2) if valid else 0,
                                "human_avg_labels": round(human_cnt / valid, 2) if valid else 0,
                                "per_class": pc}
        multi_out[f] = per_layer
        a = per_layer["ALL"]
        print(f"\n[{f}] ALL: n={a['n_segments']} P={a['micro_precision']} R={a['micro_recall']} "
              f"F1={a['micro_f1']} macroF1={a['macro_f1']} exact={a['exact_set_match']} "
              f"pred_avg={a['pred_avg_labels']} human_avg={a['human_avg_labels']}")
        for lab, c in sorted(a["per_class"].items(), key=lambda x: -x[1]["support"]):
            print(f"  {lab:20s} sup={c['support']:2d} P={c['precision']:5.1f} R={c['recall']:5.1f} "
                  f"F1={c['f1']:5.1f} {c['status']}")

    # ---------- STEP 7: People 重点 ----------
    pp = single_out["people_presence"]["ALL"]
    # 混淆矩阵（从 raw evidence）
    tp = fp = tn = fn = 0
    yolo_provider = tech_fb = normal_no_viol = 0
    for sid in truth:
        t = truth[sid]["people_presence"]
        p = pred_map[sid]["final_routed_prediction"].get("people_presence")
        pe = pred_map[sid]["raw_provider_evidence"].get("people", {})
        if pe.get("provider") == "yolo":
            yolo_provider += 1
            if p == "NO" and pe.get("fallback_used") is True:
                normal_no_viol += 1
        if pe.get("provider") == "siglip_fallback":
            tech_fb += 1
        if t in ("", "UNKNOWN"):
            continue
        t_yes = t == "YES"
        p_yes = p == "YES"
        if p_yes and t_yes:
            tp += 1
        elif p_yes and not t_yes:
            fp += 1
        elif not p_yes and not t_yes:
            tn += 1
        else:
            fn += 1
    P = tp / (tp + fp) if (tp + fp) else 0
    R = tp / (tp + fn) if (tp + fn) else 0
    Sp = tn / (tn + fp) if (tn + fp) else 0
    acc = (tp + tn) / (tp + fp + tn + fn)
    ba = (R + Sp) / 2
    people_out = {"tp": tp, "fp": fp, "tn": tn, "fn": fn,
                  "precision": round(P * 100, 1), "recall": round(R * 100, 1),
                  "specificity": round(Sp * 100, 1), "f1": round(f1(P, R) * 100, 1),
                  "accuracy": round(acc * 100, 1), "balanced_accuracy": round(ba * 100, 1),
                  "yolo_provider_count": yolo_provider, "technical_fallback_count": tech_fb,
                  "NORMAL_NO_FALLBACK_VIOLATIONS": normal_no_viol}
    print(f"\n[People ALL] TP/FP/TN/FN={tp}/{fp}/{tn}/{fn} P={people_out['precision']} "
          f"R={people_out['recall']} F1={people_out['f1']} bacc={people_out['balanced_accuracy']} "
          f"viol={normal_no_viol}")

    # ---------- STEP 11: Semantic Action ----------
    router = json.load(open(os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V2_LOCK.json"), encoding="utf-8"))["semantic_action_router"]
    sa_out = {}
    sa_atoms = ["PERSON_SPEAKING", "PULL_OUT", "RETRACT", "OPEN_DRAWER", "CLOSE_DRAWER",
                "OPEN_CABINET", "CLOSE_CABINET", "OPERATE_SOCKET", "OPEN_SINK_COVER",
                "STATIC_DISPLAY", "OTHER"]
    per_atom = defaultdict(lambda: {"support": 0, "tp": 0, "fp": 0, "fn": 0})
    false_claims = []
    abstain_ok = 0
    abstain_wrong = 0
    for sid in truth:
        tseq = set(jload(truth[sid].get("action_sequence", "")))
        pseq = set(pred_map[sid]["final_routed_prediction"].get("action_sequence", []))
        for a in sa_atoms:
            t_hit, p_hit = a in tseq, a in pseq
            if t_hit:
                per_atom[a]["support"] += 1
            if p_hit and t_hit:
                per_atom[a]["tp"] += 1
            elif p_hit and not t_hit:
                per_atom[a]["fp"] += 1
                false_claims.append((sid, a))
            elif t_hit and not p_hit:
                per_atom[a]["fn"] += 1
        # abstain 判定：NO_CLAIM/INSUFFICIENT 动作人工有但系统 abstain = correct abstention
        for a in ("OPEN_CABINET", "RETRACT", "OPERATE_SOCKET", "OPEN_SINK_COVER"):
            spec = router.get(a, {})
            if spec.get("provider") in ("NO_CLAIM", "INSUFFICIENT_SAMPLE"):
                if a in tseq and a not in pseq:
                    abstain_ok += 1
                elif a in pseq:
                    abstain_wrong += 1  # 违规输出
    for a in sa_atoms:
        s = per_atom[a]
        P = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 0
        R = s["tp"] / s["support"] if s["support"] else 0
        sa_out[a] = {"support": s["support"], "tp": s["tp"], "fp": s["fp"], "fn": s["fn"],
                     "precision": round(P * 100, 1), "recall": round(R * 100, 1),
                     "f1": round(f1(P, R) * 100, 1),
                     "router": router.get(a, {}).get("provider", "?")}
        print(f"[SA {a:16s}] sup={s['support']:2d} TP={s['tp']:2d} FP={s['fp']:2d} FN={s['fn']:2d} "
              f"P={sa_out[a]['precision']:5.1f} R={sa_out[a]['recall']:5.1f} F1={sa_out[a]['f1']:5.1f} "
              f"({sa_out[a]['router']})")
    print(f"\n[SA] correct_abstention={abstain_ok} false_claim_count={len(false_claims)} "
          f"abstain_violations={abstain_wrong}")
    sa_summary = {"per_atom": sa_out, "correct_abstention": abstain_ok,
                  "false_claims": false_claims, "abstain_violations": abstain_wrong,
                  "semantic_coverage": sum(1 for a in sa_out if sa_out[a]["support"] > 0)}

    out = {"manifest": "FRESH_HOLDOUT_V2_METRICS",
           "layers": {k: len(v) for k, v in layers.items()},
           "single_label": single_out, "multi_label": multi_out,
           "people": people_out, "semantic_action": sa_summary,
           "note": "Fresh Unseen Stratified Holdout V2 Performance；n<=30，small-n warning；"
                   "禁止称全库泛化；Wilson 95% CI 见 single_label"}
    p = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_METRICS.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
