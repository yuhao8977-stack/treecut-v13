# -*- coding: utf-8 -*-
"""Stage 2 — FRESH_HOLDOUT_V1 FINAL SCORING & GENERALIZATION AUDIT。

输出：HUMAN_LOCK / METRICS / ERROR_CASES json。
严格 segment_id JOIN；分层 RANDOM/HARD/GAP/ALL；正确 n_valid 口径。
"""
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

SINGLE = ["scene_family", "scene_subtype", "product_family", "product_variant",
          "shot_scale", "people_presence", "product_visibility"]
MULTI = ["material", "component", "function", "shot_role"]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    # ---- 三方数据 ----
    hl = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    stratum_of = {s["segment_id"]: s["stratum"] for s in hl["strata"]}
    pred = json.load(open(os.path.join(DATA_ROOT, "HOLDOUT_AI_PREDICTIONS_V1.json"), encoding="utf-8"))
    ai = {s["segment_id"]: s for s in pred["segments"]}
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    hum = {r["segment_id"]: r for r in conn.execute("SELECT * FROM fresh_holdout_human_review_v1")}
    conn.close()
    sids = sorted(ai.keys() & hum.keys() & set(stratum_of))
    assert len(sids) == 30

    # ---- STEP 1 Human Lock ----
    human_lock_payload = json.dumps(
        {sid: {k: (hum[sid][k] if k not in ("material_multi", "component_multi", "function_multi", "shot_role_multi", "action_sequence")
                  else jload(hum[sid][k]))
               for k in ("scene_family", "scene_subtype", "product_family", "product_variant",
                         "material_multi", "component_multi", "function_multi", "action_group",
                         "action_sequence", "shot_scale", "shot_role_multi", "people_presence",
                         "product_visibility", "human_confidence", "review_status")}
         for sid in sids}, ensure_ascii=False, sort_keys=True)
    human_truth_sha = hashlib.sha256(human_lock_payload.encode()).hexdigest()[:16]
    human_lock = {"manifest_version": "FRESH_HOLDOUT_V1_HUMAN_LOCK",
                  "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                  "count": len(sids), "human_truth_sha256": human_truth_sha,
                  "confidence_dist": dict(Counter(hum[s]["human_confidence"] for s in sids)),
                  "status_dist": dict(Counter(hum[s]["review_status"] for s in sids)),
                  "segments": [{"segment_id": s, "stratum": stratum_of[s],
                                "human_confidence": hum[s]["human_confidence"],
                                "review_status": hum[s]["review_status"]} for s in sids]}
    json.dump(human_lock, open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_HUMAN_LOCK.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("HUMAN_LOCK:", len(sids), "| human_truth_sha256:", human_truth_sha)

    def layer(sid_list):
        return [s for s in sids if stratum_of[s] in sid_list]

    LAYERS = {"ALL": sids, "RANDOM": layer(["RANDOM"]), "HARD": layer(["HARD"]), "GAP": layer(["GAP"])}

    # ---- 单标签评分 ----
    def ai_final(sid, field):
        f = ai[sid]["fields"].get(field, {})
        if isinstance(f, dict):
            return f.get("final")
        return None

    single_metrics = {}
    for field in SINGLE:
        per_layer = {}
        for lname, lsids in LAYERS.items():
            tp = fp = unk = 0
            for sid in lsids:
                truth = hum[sid][field]
                if truth in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                    continue
                p = ai_final(sid, field)
                if p in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                    unk += 1
                elif p == truth:
                    tp += 1
                else:
                    fp += 1
            nv = tp + fp + unk
            per_layer[lname] = {
                "n_valid": nv, "correct": tp,
                "accuracy": round(tp / nv * 100, 1) if nv else 0,
                "coverage": round((tp + fp) / nv * 100, 1) if nv else 0,
                "conditional_accuracy": round(tp / (tp + fp) * 100, 1) if (tp + fp) else 0,
                "unknown_rate": round(unk / nv * 100, 1) if nv else 0,
                "macro_f1": round(f1(tp / (tp + fp) if (tp + fp) else 0,
                                     tp / nv if nv else 0) * 100, 1)}
        single_metrics[field] = per_layer

    # ---- 多标签评分 ----
    multi_metrics = {}
    for field in MULTI:
        per_layer = {}
        for lname, lsids in LAYERS.items():
            tp = fp = fn = exact = valid = label_in = 0
            per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
            for sid in lsids:
                # 盲审表只有 _multi JSON 列（无单值列）
                truth_set = set(jload(hum[sid][f"{field}_multi"]))
                pred_set = set(ai_final(sid, field) or [])
                if not truth_set:
                    continue
                valid += 1
                if pred_set == truth_set:
                    exact += 1
                if pred_set & truth_set:
                    label_in += 1
                for lab in truth_set:
                    if lab in pred_set:
                        tp += 1
                        per[lab]["tp"] += 1
                    else:
                        fn += 1
                        per[lab]["fn"] += 1
                for lab in pred_set - truth_set:
                    fp += 1
                    per[lab]["fp"] += 1
            mp = tp / (tp + fp) if (tp + fp) else 0
            mr = tp / (tp + fn) if (tp + fn) else 0
            per_layer[lname] = {
                "n_segments": valid, "micro_precision": round(mp * 100, 1),
                "micro_recall": round(mr * 100, 1), "micro_f1": round(f1(mp, mr) * 100, 1),
                "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
                "label_in_set_accuracy": round(label_in / valid * 100, 1) if valid else 0}
        multi_metrics[field] = per_layer

    # ---- Action ----
    action_metrics = {}
    for lname, lsids in LAYERS.items():
        tg = tp_g = 0
        seq_exact = seq_n = 0
        for sid in lsids:
            truth_g = hum[sid]["action_group"]
            truth_seq = jload(hum[sid]["action_sequence"])
            if truth_g not in ("", "UNKNOWN"):
                tg += 1
                if ai_final(sid, "action_group") == truth_g:
                    tp_g += 1
            if truth_seq:
                seq_n += 1
                if ai_final(sid, "action_sequence") == truth_seq:
                    seq_exact += 1
        action_metrics[lname] = {
            "group_accuracy": round(tp_g / tg * 100, 1) if tg else 0, "group_n": tg,
            "sequence_exact_match": round(seq_exact / seq_n * 100, 1) if seq_n else 0, "seq_n": seq_n}

    # ---- Trivial baseline（Holdout 事后，仅 human truth）----
    trivial = {}
    for field in SINGLE:
        dist = Counter(hum[s][field] for s in sids if hum[s][field] not in ("", "UNKNOWN", "NOT_APPLICABLE", None))
        if dist:
            trivial[field] = {"majority": dist.most_common(1)[0][0],
                              "accuracy": round(dist.most_common(1)[0][1] / sum(dist.values()) * 100, 1)}

    # ---- Dev vs Holdout ----
    dev_map = {"scene": 37.9, "product": 52.7, "shot_scale": 35.3, "people": 8.5,
               "material": 22.1, "component": 24.4, "function": 21.5, "shot_role": 19.9}
    dev_holdout = {}
    for dev_f, hold_f in (("scene", "scene_family"), ("product", "product_family"),
                          ("shot_scale", "shot_scale"), ("people", "people_presence"),
                          ("material", "material"), ("component", "component"),
                          ("function", "function"), ("shot_role", "shot_role")):
        if hold_f in single_metrics:
            ho = single_metrics[hold_f]["ALL"]["accuracy"]
        else:
            ho = multi_metrics[hold_f]["ALL"]["micro_f1"]
        dev_holdout[dev_f] = {"dev": dev_map[dev_f], "holdout": ho,
                              "delta": round(ho - dev_map[dev_f], 1)}

    # ---- 错误案例 ----
    error_cases = []
    for sid in sids:
        errs = []
        for field in SINGLE:
            truth = hum[sid][field]
            if truth in ("", "UNKNOWN", "NOT_APPLICABLE", None):
                continue
            p = ai_final(sid, field)
            if p not in ("", "UNKNOWN", "NOT_APPLICABLE", None) and p != truth:
                errs.append({"field": field, "truth": truth, "prediction": p,
                             "error_type": "VISION_CONFUSION" if p != "UNKNOWN" else "UNKNOWN_OVERUSE"})
        for field in MULTI:
            truth_set = set(jload(hum[sid][f"{field}_multi"]))
            pred_set = set(ai_final(sid, field) or [])
            if truth_set and not (pred_set & truth_set):
                errs.append({"field": field, "truth": list(truth_set), "prediction": list(pred_set),
                             "error_type": "VISION_CONFUSION"})
        if errs:
            error_cases.append({"segment_id": sid, "stratum": stratum_of[sid],
                                "provider_used": ai[sid]["fields"].get("product_family", {}).get("provider", ""),
                                "errors": errs})
    error_cases.sort(key=lambda c: -len(c["errors"]))

    metrics = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
               "human_truth_sha256": human_truth_sha,
               "prediction_sha256": "f5c7c5e70c0fa299",
               "bundle_lock_sha256": "6c2ce081b9d2a1be",
               "holdout_manifest_sha256": "31ae951d99f0e792",
               "layers": {k: len(v) for k, v in LAYERS.items()},
               "single": single_metrics, "multi": multi_metrics, "action": action_metrics,
               "trivial_baseline": trivial, "dev_vs_holdout": dev_holdout,
               "error_case_count": len(error_cases)}
    json.dump(metrics, open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_METRICS.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(error_cases, open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_ERROR_CASES.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("\n== ALL_30 单标签 ==")
    for f in SINGLE:
        a = single_metrics[f]["ALL"]
        t = trivial.get(f, {})
        print(f"  {f:18s} acc={a['accuracy']}% cov={a['coverage']}% unk={a['unknown_rate']}% n={a['n_valid']} | trivial={t.get('accuracy','-')}%({t.get('majority','-')})")
    print("== ALL_30 多标签 ==")
    for f in MULTI:
        a = multi_metrics[f]["ALL"]
        print(f"  {f:12s} microF1={a['micro_f1']}% label-in={a['label_in_set_accuracy']}% exact={a['exact_set_match']}% n={a['n_segments']}")
    print("== Action ==")
    for l in ("RANDOM", "HARD", "GAP", "ALL"):
        print(f"  {l:6s}", action_metrics[l])
    print("== 分层（scene）==")
    for l in ("RANDOM", "HARD", "GAP", "ALL"):
        print(f"  {l:6s}", single_metrics["scene_family"][l])
    print("== Dev vs Holdout ==")
    for f, v in dev_holdout.items():
        gap = "GENERALIZATION_GAP" if v["delta"] < -10 else ("STABLE" if abs(v["delta"]) <= 10 else "HOLDOUT_BETTER")
        print(f"  {f:10s} dev={v['dev']} holdout={v['holdout']} delta={v['delta']} {gap}")
    print("== 错误案例数:", len(error_cases))


if __name__ == "__main__":
    main()
