# -*- coding: utf-8 -*-
"""Stage3 POST-REVIEW — STEP 11/12/13：Multi-label Policy Post-review Audit（新60 DEV）。

用审核前冻结的 SigLIP per-label scores（STAGE3_FINAL_FEATURES）重放冻结策略：
  material=policy_mode v1（阈值0.06）；component/function=v2（Top3+gap0.10+min0.02）；shot_role=v1
仅对 60 条中 features 覆盖的段（49）诊断，称 Stage3 Targeted DEV Diagnostic。
不修改 Policy；product_family 保护对照 V1_1 Holdout 锚点 51.7%（只读引用，不调参）。
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")

MULTI = ["material", "component", "function", "shot_role"]
POLICY = {
    "material": {"mode": "v1", "threshold": 0.06},
    "component": {"mode": "v2", "top_k": 3, "gap": 0.10, "min_score": 0.02},
    "function": {"mode": "v2", "top_k": 3, "gap": 0.10, "min_score": 0.02},
    "shot_role": {"mode": "v1", "threshold": 0.06},
}


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    man_sids = [s["segment_id"] for s in man["segments"]]
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    ph = ",".join("?" * len(man_sids))
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", man_sids)]
    conn.close()

    # 仅 features 覆盖段
    cov = [r for r in rows if r["segment_id"] in feats]
    print(f"60 条中 features 覆盖: {len(cov)}（替换段 11 条无审核前视觉输出，排除）")

    def policy_pred(field, scores):
        if not scores:
            return set()
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        pol = POLICY[field]
        if pol["mode"] == "v1":
            base = max(scores.values())
            return {lab for lab, s in scores.items() if s >= base - pol["threshold"]} or {"UNKNOWN"}
        top1 = ranked[0][1]
        out = []
        for lab, s in ranked[: pol["top_k"]]:
            if s >= top1 - pol["gap"] and s >= pol["min_score"]:
                out.append(lab)
        return set(out) if out else {"UNKNOWN"}

    out = {}
    print("\n=== STEP 11: Multi-label Policy 新60 DEV 诊断 ===")
    for field in MULTI:
        pred_cnt = 0
        human_cnt = 0
        tp = fp = fn = valid = exact = label_in = 0
        macro_p = macro_r = 0
        n_lab = 0
        for r in cov:
            tset = set(jload(r[f"{field}_multi"]))
            if not tset:
                continue
            valid += 1
            pset = policy_pred(field, feats[r["segment_id"]].get(field, {}).get("scores", {}))
            pred_cnt += len(pset)
            human_cnt += len(tset)
            if pset == tset:
                exact += 1
            if pset & tset:
                label_in += 1
            for lab in tset:
                n_lab += 1
                if lab in pset:
                    tp += 1
                else:
                    fn += 1
            for lab in pset - tset:
                fp += 1
            # 逐样本 P/R（macro）
            p_s = tp_s = 0
            # 简化 macro：按样本算
        mp = tp / (tp + fp) if (tp + fp) else 0
        mr = tp / (tp + fn) if (tp + fn) else 0
        res = {"n_valid": valid,
               "pred_avg_labels": round(pred_cnt / valid, 2) if valid else 0,
               "human_avg_labels": round(human_cnt / valid, 2) if valid else 0,
               "micro_precision": round(mp * 100, 1), "micro_recall": round(mr * 100, 1),
               "micro_f1": round(f1(mp, mr) * 100, 1),
               "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
               "label_in": round(label_in / valid * 100, 1) if valid else 0}
        # macro F1（per-sample）
        macro_f1s = []
        for r in cov:
            tset = set(jload(r[f"{field}_multi"]))
            if not tset:
                continue
            pset = policy_pred(field, feats[r["segment_id"]].get(field, {}).get("scores", {}))
            tp_s = len(tset & pset)
            p_s = tp_s / len(pset) if pset else 0
            r_s = tp_s / len(tset) if tset else 0
            if p_s + r_s:
                macro_f1s.append(2 * p_s * r_s / (p_s + r_s))
        res["macro_f1"] = round(sum(macro_f1s) / len(macro_f1s) * 100, 1) if macro_f1s else 0
        out[field] = res
        print(f"[{field}] {POLICY[field]['mode']} n={valid} pred_avg={res['pred_avg_labels']} "
              f"human_avg={res['human_avg_labels']} P={res['micro_precision']} R={res['micro_recall']} "
              f"F1={res['micro_f1']} macroF1={res['macro_f1']} exact={res['exact_set_match']} "
              f"label_in={res['label_in']}")

    # STEP 12: 裁定（只诊断）
    print("\n=== STEP 12: Policy 合理性（新60 DEV，仅诊断不修改）===")
    for field in MULTI:
        r = out[field]
        if r["n_valid"] < 10:
            verdict = "INSUFFICIENT_SAMPLE"
        elif r["micro_f1"] >= 40:
            verdict = "SUPPORTED"
        elif r["micro_f1"] >= 20:
            verdict = "MIXED"
        else:
            verdict = "REGRESSION"
        out[field]["verdict"] = verdict
        print(f"  {field} ({POLICY[field]['mode']}): F1={r['micro_f1']} -> {verdict}")

    # STEP 13: product_family 保护（新60 DEV；V1_1 Holdout 51.7% 只读引用）
    print("\n=== STEP 13: product_family 回归保护（新60 DEV 诊断）===")
    pf_tp = pf_n = 0
    for r in cov:
        t = r.get("product_family")
        if not t or t == "UNKNOWN":
            continue
        pf_n += 1
        p = feats[r["segment_id"]].get("product_family", {}).get("prediction")
        if p == t:
            pf_tp += 1
    pf_acc = round(pf_tp / pf_n * 100, 1) if pf_n else 0
    out["product_family"] = {"n_valid": pf_n, "targeted_dev_accuracy": pf_acc,
                             "note": "V1_1 Fresh Holdout product_family=51.7%（只读锚点，不调参）"}
    print(f"product_family 新60 DEV acc={pf_acc}%（n={pf_n}）；V1_1 Holdout 锚点=51.7%")

    p = os.path.join(DATA_ROOT, "STAGE3_MULTILABEL_POST_REVIEW_EVAL.json")
    json.dump({"manifest": "STAGE3_MULTILABEL_POST_REVIEW_EVAL",
               "scope": "Stage3 Targeted DEV Diagnostic（60 中 features 覆盖 49 段）; NOT generalization",
               "policy_frozen": POLICY, "per_field": out, "product_family": out["product_family"]},
              open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
