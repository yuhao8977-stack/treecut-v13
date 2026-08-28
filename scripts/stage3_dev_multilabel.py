# -*- coding: utf-8 -*-
"""Stage3 TRACK A — A6/A7/A8/A9：Multi-label 合并评估 + ShotRole V3 + Product Family guard。

A6：component/function Policy V2 在 Cal333+Stage3 合并 DEV 的 microP/R/F1/macroF1/avg/exact。
A7：material V1 保持（FALLBACK/EXPERIMENTAL 标注）。
A8：ShotRole Policy V3 候选：在 333+60 上网格压缩标签数（top_k/gap/min），目标减少 label 同时 F1 不明显下降。
A9：product_family 回归保护（Cal DEV + Stage3 DEV；Fresh Holdout V1 仅 KNOWN BENCHMARK 参考）。
全部用审核前冻结 SigLIP scores（STAGE3_FINAL_FEATURES）。
"""
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def multi_metrics(rows, field, pred_fn):
    tp = fp = fn = valid = exact = label_in = 0
    pred_cnt = human_cnt = 0
    macro_f1s = []
    for r in rows:
        tset = set(jload(r.get(f"{field}_multi")))
        if not tset:
            continue
        valid += 1
        pset = pred_fn(r)
        pred_cnt += len(pset)
        human_cnt += len(tset)
        if pset == tset:
            exact += 1
        if pset & tset:
            label_in += 1
        tp += len(tset & pset)
        fn += len(tset - pset)
        fp += len(pset - tset)
        p_s = len(tset & pset) / len(pset) if pset else 0
        r_s = len(tset & pset) / len(tset) if tset else 0
        if p_s + r_s:
            macro_f1s.append(2 * p_s * r_s / (p_s + r_s))
    mp = tp / (tp + fp) if (tp + fp) else 0
    mr = tp / (tp + fn) if (tp + fn) else 0
    return {"n_valid": valid, "pred_avg": round(pred_cnt / valid, 2) if valid else 0,
            "human_avg": round(human_cnt / valid, 2) if valid else 0,
            "micro_precision": round(mp * 100, 1), "micro_recall": round(mr * 100, 1),
            "micro_f1": round(f1(mp, mr) * 100, 1),
            "macro_f1": round(sum(macro_f1s) / len(macro_f1s) * 100, 1) if macro_f1s else 0,
            "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
            "label_in": round(label_in / valid * 100, 1) if valid else 0}


def main():
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = {s["segment_id"] for s in man["segments"]}
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    t_sids = [s["segment_id"] for s in tman["segments"]]
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))["segments"]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = []
    for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1"):
        if r["segment_id"] in cal_sids:
            rows.append(dict(r))
    ph = ",".join("?" * len(t_sids))
    for r in conn.execute(f"SELECT * FROM targeted_human_review_v1 WHERE segment_id IN ({ph})", t_sids):
        if r["review_status"] != "EXCLUDED":
            rows.append(dict(r))
    conn.close()

    # 仅 features 覆盖段
    cov = [r for r in rows if r["segment_id"] in feats]
    print(f"合并 DEV 段（features 覆盖）: {len(cov)}（Cal333+Stage3）")

    # ---- A6: component/function Policy V2 ----
    def v2_pred(field, top_k=3, gap=0.10, min_score=0.02):
        def f(r):
            sc = feats[r["segment_id"]].get(field, {}).get("scores", {})
            if not sc:
                return set()
            ranked = sorted(sc.items(), key=lambda x: -x[1])
            top1 = ranked[0][1]
            out = []
            for lab, s in ranked[:top_k]:
                if s >= top1 - gap and s >= min_score:
                    out.append(lab)
            return set(out) if out else {"UNKNOWN"}
        return f

    a6 = {}
    for fld in ("component", "function"):
        m = multi_metrics(cov, fld, v2_pred(fld))
        a6[fld] = m
        print(f"[A6 {fld} V2] n={m['n_valid']} pred_avg={m['pred_avg']} human_avg={m['human_avg']} "
              f"P={m['micro_precision']} R={m['micro_recall']} F1={m['micro_f1']} "
              f"macroF1={m['macro_f1']} exact={m['exact_set_match']} label_in={m['label_in']}")

    # ---- A7: material V1（FALLBACK 标注）----
    def v1_pred(field, threshold=0.06):
        def f(r):
            sc = feats[r["segment_id"]].get(field, {}).get("scores", {})
            if not sc:
                return set()
            base = max(sc.values())
            return {lab for lab, s in sc.items() if s >= base - threshold} or {"UNKNOWN"}
        return f

    mat_v1 = multi_metrics(cov, "material", v1_pred("material"))
    print(f"[A7 material V1] n={mat_v1['n_valid']} pred_avg={mat_v1['pred_avg']} human_avg={mat_v1['human_avg']} "
          f"P={mat_v1['micro_precision']} R={mat_v1['micro_recall']} F1={mat_v1['micro_f1']}")
    a7 = {"material_v1": mat_v1, "status": "FALLBACK/EXPERIMENTAL（MIXED 弱）",
          "note": "material 保持 V1；不因 Stage3 强行升级 V2"}

    # ---- A8: ShotRole Policy V3 网格 ----
    print("\n[A8 ShotRole V3 网格]")
    sr_v1 = multi_metrics(cov, "shot_role", v1_pred("shot_role"))
    print(f"  V1: pred_avg={sr_v1['pred_avg']} human_avg={sr_v1['human_avg']} F1={sr_v1['micro_f1']} "
          f"P={sr_v1['micro_precision']} R={sr_v1['micro_recall']}")
    sr_grid = {"v1_threshold0.06": sr_v1}
    for top_k in (3, 4, 5):
        for gap in (0.08, 0.10, 0.15):
            m = multi_metrics(cov, "shot_role", v2_pred("shot_role", top_k=top_k, gap=gap, min_score=0.02))
            key = f"v3_top{top_k}_gap{gap}"
            sr_grid[key] = m
            print(f"  {key}: pred_avg={m['pred_avg']} F1={m['micro_f1']} P={m['micro_precision']} "
                  f"R={m['micro_recall']} macroF1={m['macro_f1']}")
    # 选 F1 不降 >2pt 且 pred_avg 最低者
    best = None
    for k, m in sr_grid.items():
        if k == "v1_threshold0.06":
            continue
        if m["micro_f1"] >= sr_v1["micro_f1"] - 2.0:
            if best is None or m["pred_avg"] < sr_grid[best]["pred_avg"]:
                best = k
    a8 = {"v1": sr_v1, "grid": sr_grid,
          "selected": best if best else "keep_v1",
          "note": "目标：显著减 label 且 F1 不降 >2pt；做不到则保留 V1 标 EXPERIMENTAL"}

    # ---- A9: product_family guard ----
    pf_cal = pf_s3 = pf_n_cal = pf_n_s3 = 0
    for r in cov:
        t = r.get("product_family")
        if not t or t == "UNKNOWN":
            continue
        p = feats[r["segment_id"]].get("product_family", {}).get("prediction")
        if p != t:
            continue
        if r["segment_id"] in cal_sids:
            pf_cal += 1
            pf_n_cal += 1
        else:
            pf_s3 += 1
            pf_n_s3 += 1
    # 修正计数（上面逻辑 p!=t continue 后 +1 只算正确；分母需另算）
    pf_cal = sum(1 for r in cov if r["segment_id"] in cal_sids
                 and r.get("product_family") not in ("UNKNOWN", "")
                 and feats[r["segment_id"]].get("product_family", {}).get("prediction") == r["product_family"])
    pf_n_cal = sum(1 for r in cov if r["segment_id"] in cal_sids
                   and r.get("product_family") not in ("UNKNOWN", ""))
    pf_s3 = sum(1 for r in cov if r["segment_id"] not in cal_sids
                and r.get("product_family") not in ("UNKNOWN", "")
                and feats[r["segment_id"]].get("product_family", {}).get("prediction") == r["product_family"])
    pf_n_s3 = sum(1 for r in cov if r["segment_id"] not in cal_sids
                  and r.get("product_family") not in ("UNKNOWN", ""))
    a9 = {"cal333": {"acc": round(pf_cal / pf_n_cal * 100, 1) if pf_n_cal else 0, "n": pf_n_cal},
          "stage3_dev": {"acc": round(pf_s3 / pf_n_s3 * 100, 1) if pf_n_s3 else 0, "n": pf_n_s3},
          "v1_1_holdout_benchmark": 51.7,
          "note": "Fresh Holdout V1 仅 KNOWN BENCHMARK 参考，不用于选择方案"}
    print(f"\n[A9 product_family] Cal333={a9['cal333']} Stage3DEV={a9['stage3_dev']} (Holdout 锚点 51.7%)")

    out = {"manifest": "MULTILABEL_STAGE3_DEV_EVAL",
           "scope": "Cal333+Stage3 合并 DEV（features 覆盖段）",
           "a6_component_function_v2": a6, "a7_material_v1": a7,
           "a8_shotrole_v3": a8, "a9_product_family": a9}
    p = os.path.join(DATA_ROOT, "MULTILABEL_STAGE3_DEV_EVAL.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
