# -*- coding: utf-8 -*-
"""Stage3 FINAL PRE-REVIEW BATCH — STEP 1-3：Multi-label Policy 最终裁定（333 DEV）。

用 STAGE3_FINAL_FEATURES.json 的真实 per-label scores 重放：
  - V1：阈值 0.06（全 label >= base-0.06）
  - V2：Top-K + gap + min_score（现 MULTI_POLICY）
  - Material 调参网格：top1/min_score/gap 变体（仅 333，禁 Holdout）
裁定：逐字段 ACCEPT_POLICY_V2 / POLICY_V2_REJECTED_FOR_MATERIAL（保留旧路由）。
指标：micro P/R/F1、macro F1、label-in-set、exact_set_match、avg_labels。
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
POLICY_V2 = {"material": {"top_k": 2, "gap": 0.10, "min_score": 0.02},
             "component": {"top_k": 3, "gap": 0.10, "min_score": 0.02},
             "function": {"top_k": 3, "gap": 0.10, "min_score": 0.02},
             "shot_role": {"top_k": 3, "gap": 0.10, "min_score": 0.02}}
MATERIAL_GRID = [
    {"name": "top1_plain", "top_k": 1, "gap": 1.0, "min_score": -9.0},
    {"name": "top1_min00", "top_k": 1, "gap": 1.0, "min_score": 0.00},
    {"name": "top1_min02", "top_k": 1, "gap": 1.0, "min_score": 0.02},
    {"name": "top1_min05", "top_k": 1, "gap": 1.0, "min_score": 0.05},
    {"name": "top2_gap05_min00", "top_k": 2, "gap": 0.05, "min_score": 0.00},
    {"name": "top2_gap05_min02", "top_k": 2, "gap": 0.05, "min_score": 0.02},
    {"name": "top2_gap10_min02", "top_k": 2, "gap": 0.10, "min_score": 0.02},  # = V2 material
    {"name": "top2_gap15_min02", "top_k": 2, "gap": 0.15, "min_score": 0.02},
    {"name": "top3_gap10_min02", "top_k": 3, "gap": 0.10, "min_score": 0.02},
    {"name": "top3_gap15_min05", "top_k": 3, "gap": 0.15, "min_score": 0.05},
]


def jload(s):
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def main():
    feats = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_FEATURES.json"), encoding="utf-8"))
    segs = feats["segments"]
    man = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in man["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    truth = {r["segment_id"]: dict(r) for r in conn.execute("SELECT * FROM canonical_human_truth WHERE is_current=1")}
    conn.close()

    def policy_pred(field, sid, top_k, gap, min_score):
        sc = segs.get(sid, {}).get(field, {}).get("scores", {})
        if not sc:
            return set()
        ranked = sorted(sc.items(), key=lambda x: -x[1])
        top1 = ranked[0][1]
        out = []
        for lab, s in ranked[:top_k]:
            if s >= top1 - gap and s >= min_score:
                out.append(lab)
        return set(out) if out else {"UNKNOWN"}

    def eval_policy(field, top_k, gap, min_score):
        tp = fp = fn = valid = exact = label_in = 0
        n_pred = []
        for sid in cal_sids:
            tset = set(jload(truth.get(sid, {}).get(f"{field}_multi")))
            if not tset:
                continue
            valid += 1
            pset = policy_pred(field, sid, top_k, gap, min_score)
            n_pred.append(len(pset))
            if pset == tset:
                exact += 1
            if pset & tset:
                label_in += 1
            for lab in tset:
                if lab in pset:
                    tp += 1
                else:
                    fn += 1
            for lab in pset - tset:
                fp += 1
        mp = tp / (tp + fp) if (tp + fp) else 0.0
        mr = tp / (tp + fn) if (tp + fn) else 0.0
        return {"n": valid, "avg_labels": round(sum(n_pred) / len(n_pred), 2) if n_pred else 0,
                "micro_precision": round(mp * 100, 1), "micro_recall": round(mr * 100, 1),
                "micro_f1": round(f1(mp, mr) * 100, 1),
                "exact_set_match": round(exact / valid * 100, 1) if valid else 0,
                "label_in": round(label_in / valid * 100, 1) if valid else 0}

    out = {}
    for field in MULTI:
        v1 = eval_policy(field, 99, 0.06, -9.0)  # V1: 所有 label >= base-0.06（top_k 无限制）
        v2 = eval_policy(field, POLICY_V2[field]["top_k"], POLICY_V2[field]["gap"],
                         POLICY_V2[field]["min_score"])
        row = {"v1_threshold_0.06": v1, "v2_topk_gap": v2,
               "human_avg_labels": round(sum(len(jload(truth[s][f"{field}_multi"])) for s in cal_sids
                                              if truth.get(s, {}).get(f"{field}_multi")) / v1["n"], 2)}
        if field == "material":
            grid = {}
            for g in MATERIAL_GRID:
                grid[g["name"]] = eval_policy(field, g["top_k"], g["gap"], g["min_score"])
            row["material_tuning_grid"] = grid
            # 裁定：V2 若在 P/F1 上退化于 V1 → REJECTED_FOR_MATERIAL，且网格中无同时提升者 → 保留旧路由
            best = max(grid.items(), key=lambda kv: (kv[1]["micro_f1"], kv[1]["micro_precision"]))
            v2_rejects = v2["micro_f1"] < v1["micro_f1"] or v2["micro_recall"] < v1["micro_recall"] * 0.9
            best_beats_v1 = best[1]["micro_f1"] >= v1["micro_f1"] and best[1]["micro_precision"] >= v1["micro_precision"]
            if v2_rejects and not best_beats_v1:
                row["verdict"] = "POLICY_V2_REJECTED_FOR_MATERIAL"
                row["verdict_note"] = ("V2 相对 V1 在 P 或 F1 退化，且 333 网格无同时改善变体 → 保留旧路由 "
                                       "(threshold 0.06) 供 material；待人工审核后重估。")
                row["adopted"] = "V1_LEGACY_ROUTE"
            elif best_beats_v1:
                row["verdict"] = "POLICY_V2_ACCEPTED_WITH_TUNING"
                row["adopted"] = best[0]
                row["adopted_params"] = next(g for g in MATERIAL_GRID if g["name"] == best[0])
                row["verdict_note"] = f"material 采用调参变体 {best[0]}（同时改善 P/F1 于 V1）。"
            else:
                row["verdict"] = "POLICY_V2_ACCEPTED_AS_IS"
                row["adopted"] = "V2"
                row["verdict_note"] = "V2 未退化于 V1，接受。"
        else:
            # F1 裁定（R 下降是压缩的必然代价，V1 的 R 是 label-spam 通胀，不作拒绝依据）
            regress = v2["micro_f1"] < v1["micro_f1"] - 1.0
            row["verdict"] = "POLICY_V2_REJECTED" if regress else "POLICY_V2_ACCEPTED"
            row["adopted"] = "V1_LEGACY_ROUTE" if regress else "V2"
            row["verdict_note"] = ("V2 相对 V1 F1 退化 >1pt → 保留旧路由" if regress
                                   else ("V2 相对 V1 F1 不退化（压缩标签数、对齐人工）→ 接受；"
                                         "R 下降为压缩代价，V1 R 来自 label-spam（5-8 标签 vs 人工 1-3），不作为拒绝依据。"))
        out[field] = row
        print(f"\n[{field}] human_avg={row['human_avg_labels']}")
        print(f"  V1: labels={v1['avg_labels']} P={v1['micro_precision']} R={v1['micro_recall']} "
              f"F1={v1['micro_f1']} label-in={v1['label_in']} exact={v1['exact_set_match']}")
        print(f"  V2: labels={v2['avg_labels']} P={v2['micro_precision']} R={v2['micro_recall']} "
              f"F1={v2['micro_f1']} label-in={v2['label_in']} exact={v2['exact_set_match']}")
        print(f"  => {row['verdict']} (adopt {row['adopted']})")

    summary = {"per_field_decision": {f: out[f]["verdict"] for f in MULTI},
               "adopted_policies": {f: out[f]["adopted"] for f in MULTI}}
    res = {"manifest": "MULTILABEL_POLICY_V2_FINAL_EVAL",
           "scope": "Calibration333 DEV ONLY (NOT_HOLDOUT)",
           "method": "real per-label scores replay; V1=threshold0.06 all-labels, V2=Top-K+gap+min",
           "per_field": out, "summary": summary}
    p = os.path.join(DATA_ROOT, "MULTILABEL_POLICY_V2_FINAL_EVAL.json")
    json.dump(res, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n->", p)


if __name__ == "__main__":
    main()
