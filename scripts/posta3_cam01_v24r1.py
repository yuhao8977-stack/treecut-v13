#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.4 R1 — 共识真 pairwise clique 修正 + 指标分口径。

从 V2.4 CASE_MATRIX（真实 5 方法 per-pair 结果）重算，不重跑 detector：
- 登记 CAM01_V24_DEFECT_STAR_CLUSTER_01（旧=星形簇，非 pairwise clique）。
- 真 clique：agreement edge = 固定 island grid 上 median transform disagreement<=3.0px；
  穷举最大 clique（≤5 方法）；多同 size 按预置规则（成员 pooled median 最大→P90 最大→成员名 tuple 最小）。
- 代表：clique 内 pooled median 最低→P90→固定 TIE_ORDER。
- 拆口径：MULTI_CONSENSUS_ONLY vs SINGLE_SOURCE_ONLY；候选语义 candidate=null unless PROMISING。
- 不用动作 GT；不读 A3；不动阈值。
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.stdout.reconfigure(encoding="utf-8")
AGREE_PX = 3.0
GRID_N = 6
TIE_ORDER = ["GFTT_LK_LOCAL", "AKAZE_CLAHE", "AKAZE_BASELINE", "SIFT_GRID_BALANCED", "SIFT_BASELINE"]
METHODS = ["AKAZE_BASELINE", "AKAZE_CLAHE", "SIFT_BASELINE", "SIFT_GRID_BALANCED", "GFTT_LK_LOCAL"]


def island_grid(ib, others, n=GRID_N):
    x1, y1, x2, y2 = [float(v) for v in ib]
    pts = []
    for i in range(n):
        for j in range(n):
            px = x1 + (i + 0.5) * (x2 - x1) / n
            py = y1 + (j + 0.5) * (y2 - y1) / n
            if not any(ob[0] <= px <= ob[2] and ob[1] <= py <= ob[3] for ob in others):
                pts.append([px, py])
    return np.float32(pts).reshape(-1, 2) if pts else None


def pairwise_disagreement(pr, methods):
    g = island_grid(pr["ib0_bbox"], pr.get("fg_others0", []))
    if g is None or len(g) < 4:
        return {}
    out = {}
    for a in methods:
        Ma = np.asarray(pr["methods"][a].get("final_M_2x3"), dtype=np.float64)
        if Ma is None or Ma.shape != (2, 3):
            continue
        pa = cv2.transform(g.reshape(-1, 1, 2), Ma).reshape(-1, 2)
        for b in methods:
            if b <= a:
                continue
            Mb = np.asarray(pr["methods"][b].get("final_M_2x3"), dtype=np.float64)
            if Mb is None or Mb.shape != (2, 3):
                continue
            pb = cv2.transform(g.reshape(-1, 1, 2), Mb).reshape(-1, 2)
            d = np.linalg.norm(pa - pb, axis=1)
            out[(a, b)] = {"median": float(np.median(d)), "p90": float(np.percentile(d, 90))}
    return out


def main():
    case_mat = json.loads((OUT / "TREECUT_CAM01_V24_CASE_MATRIX.json").read_text(encoding="utf-8"))["pairs"]
    island_pairs = [pr for pr in case_mat if pr.get("island_present")]
    true_multi = single = conflict = none_ = 0
    multi_rows = []
    single_rows = []
    affected = []
    cons_med = []
    cons_p90 = []
    cons_rep_dist = {}
    sing_med = []
    sing_p90 = []
    sing_rep_dist = {}
    for pr in island_pairs:
        val = [m for m in METHODS
               if pr["methods"].get(m, {}).get("pair_state") == "LOCAL_ANCHOR_VALIDATED"]
        pr["validated_method_count"] = len(val)
        if len(val) == 0:
            none_ += 1
            pr["r1_consensus"] = "NO_VALID_ANCHOR"
            continue
        if len(val) == 1:
            single += 1
            pr["r1_consensus"] = "SINGLE_METHOD_VALIDATED"
            pr["r1_representative"] = val[0]
            m = pr["methods"][val[0]]
            sing_rep_dist[val[0]] = sing_rep_dist.get(val[0], 0) + 1
            if m.get("pooled_holdout_median") is not None:
                sing_med.append(m["pooled_holdout_median"])
                sing_p90.append(m["pooled_holdout_p90"])
            single_rows.append(pr)
            continue
        # ≥2 validated → pairwise disagreement + true clique（穷举）
        dis = pairwise_disagreement(pr, val)
        edges = {(a, b) for (a, b), d in dis.items() if d["median"] <= AGREE_PX}
        cliques = []
        n = len(val)
        for mask in range(1 << n):
            if bin(mask).count("1") < 2:
                continue
            members = [val[i] for i in range(n) if mask >> i & 1]
            ok = all((a, b) in edges or (b, a) in edges
                     for a in members for b in members if b > a)
            if ok:
                cliques.append(members)
        if not cliques:
            conflict += 1
            pr["r1_consensus"] = "METHOD_CONFLICT"
            pr["r1_representative"] = None
            continue
        # 最大 clique；同 size 预置规则
        maxsz = max(len(c) for c in cliques)
        best_c = None
        best_key = None
        for c in cliques:
            if len(c) != maxsz:
                continue
            meds = [pr["methods"][m].get("pooled_holdout_median") or 99 for m in c]
            p90s = [pr["methods"][m].get("pooled_holdout_p90") or 999 for m in c]
            key = (max(meds), max(p90s), tuple(sorted(c)))
            if best_key is None or key < best_key:
                best_key = key
                best_c = c
        # 代表：clique 内 pooled median 最低→P90→TIE_ORDER
        def repkey(m):
            d = pr["methods"][m]
            return (d.get("pooled_holdout_median") if d.get("pooled_holdout_median") is not None else 99,
                    d.get("pooled_holdout_p90") if d.get("pooled_holdout_p90") is not None else 999,
                    TIE_ORDER.index(m) if m in TIE_ORDER else 99)
        rep = min(best_c, key=repkey)
        true_multi += 1
        pr["r1_consensus"] = "MULTI_METHOD_CONSENSUS"
        pr["r1_clique"] = best_c
        pr["r1_representative"] = rep
        m = pr["methods"][rep]
        cons_rep_dist[rep] = cons_rep_dist.get(rep, 0) + 1
        if m.get("pooled_holdout_median") is not None:
            cons_med.append(m["pooled_holdout_median"])
            cons_p90.append(m["pooled_holdout_p90"])
        pair_med = [d["median"] for (a, b), d in dis.items()
                    if a in best_c and b in best_c]
        pair_p90 = [d["p90"] for (a, b), d in dis.items()
                    if a in best_c and b in best_c]
        pr["r1_disagreement"] = {"clique_size": maxsz,
                                 "max_pairwise_median": round(max(pair_med), 3) if pair_med else None,
                                 "max_pairwise_p90": round(max(pair_p90), 3) if pair_p90 else None,
                                 "pairwise": {f"{a}|{b}": round(d["median"], 3)
                                              for (a, b), d in dis.items()}}
        # 受影响的旧星形簇对比（v24 存的 consensus_cluster）
        old = pr.get("consensus_cluster") or []
        removed = [m for m in old if m not in best_c]
        if len(old) >= 3 and removed:
            affected.append({"case": pr["case"], "pair": pr["pair"],
                             "old_cluster": old, "true_clique": best_c,
                             "removed_methods": removed,
                             "old_representative": pr.get("representative"),
                             "new_representative": rep})
        multi_rows.append(pr)
    # 汇总
    union = sum(1 for pr in island_pairs if pr.get("validated_method_count", 0) >= 1)
    union_cases = len({pr["case"] for pr in island_pairs if pr.get("validated_method_count", 0) >= 1})
    cons_cases = len({pr["case"] for pr in island_pairs
                      if pr.get("r1_consensus") == "MULTI_METHOD_CONSENSUS"})
    akaze_base = sum(1 for pr in island_pairs
                     if pr["methods"].get("AKAZE_BASELINE", {}).get("pair_state") == "LOCAL_ANCHOR_VALIDATED")
    metrics = {"island_present": len(island_pairs),
               "oracle_union": union, "union_case_coverage": union_cases,
               "TRUE_MULTI_METHOD_CONSENSUS": true_multi,
               "consensus_case_coverage": cons_cases,
               "SINGLE_METHOD_VALIDATED": single,
               "METHOD_CONFLICT": conflict,
               "NO_VALID_ANCHOR": none_,
               "consensus_only_pooled_holdout_median": round(float(np.median(cons_med)), 3) if cons_med else None,
               "consensus_only_pooled_holdout_p90": round(float(np.median(cons_p90)), 3) if cons_p90 else None,
               "consensus_only_representative_distribution": dict(sorted(cons_rep_dist.items(),
                                                                         key=lambda kv: -kv[1])),
               "single_source_pooled_holdout_median": round(float(np.median(sing_med)), 3) if sing_med else None,
               "single_source_pooled_holdout_p90": round(float(np.median(sing_p90)), 3) if sing_p90 else None,
               "single_source_representative_distribution": dict(sorted(sing_rep_dist.items(),
                                                                        key=lambda kv: -kv[1])),
               "consensus_count_unchanged": (true_multi == 12)}
    # NEG control（严格 contract，按 true consensus / single 分）
    neg = {"TRUE_MULTI_METHOD_CONSENSUS": [], "SINGLE_SOURCE": []}
    for pr in island_pairs:
        if pr["role"] != "NEG" or not (pr.get("target_t0_valid") and pr.get("target_t1_valid")):
            continue
        if pr.get("r1_consensus") == "MULTI_METHOD_CONSENSUS":
            neg["TRUE_MULTI_METHOD_CONSENSUS"].append({"case": pr["case"], "pair": pr["pair"]})
        elif pr.get("r1_consensus") == "SINGLE_METHOD_VALIDATED":
            neg["SINGLE_SOURCE"].append({"case": pr["case"], "pair": pr["pair"]})
    neg_meta = {"TRUE_MULTI_METHOD_CONSENSUS_cases": len({x["case"] for x in neg["TRUE_MULTI_METHOD_CONSENSUS"]}),
                "SINGLE_SOURCE_cases": len({x["case"] for x in neg["SINGLE_SOURCE"]}),
                "TRUE_MULTI_METHOD_CONSENSUS_pairs": neg["TRUE_MULTI_METHOD_CONSENSUS"],
                "SINGLE_SOURCE_pairs": neg["SINGLE_SOURCE"]}
    # status（沿用 V2.4 预置规则）
    if true_multi >= 18 and conflict <= 4 and cons_cases >= 7 and true_multi > akaze_base + 4:
        status = "CONSENSUS_PROMISING"
    else:
        status = "CONSENSUS_PARTIAL"
    candidate = {"candidate": None, "candidate_frozen": False,
                 "diagnostic_recipe": {"methods": METHODS,
                                       "consensus_rule": "true pairwise clique (edge = island-grid median disagreement<=3.0px); max size; tie: max member pooled median -> max pooled P90 -> lexicographic",
                                       "representative_rule": "member lowest pooled median -> P90 -> TIE_ORDER",
                                       "agreement_px": AGREE_PX,
                                       "v24r1_metrics": metrics},
                 "status": status}
    (OUT / "TREECUT_CAM01_V24R1_METHOD_CORRECTION.json").write_text(
        json.dumps({"experiment": "CAM01_V24R1_METHOD_CORRECTION",
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "defect": "CAM01_V24_DEFECT_STAR_CLUSTER_01",
                    "old_cluster_semantics": "star: 以某方法为中心收拢 <=3px 方法（非 pairwise clique）",
                    "fixed_to": "true pairwise clique (穷举, edge<=3.0px)",
                    "affected_pairs": affected,
                    "v24_consensus_was": 12}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24R1_TRUE_CLIQUE_CONSENSUS.json").write_text(
        json.dumps({"metrics": metrics, "pairs": multi_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24R1_METRICS_SEPARATED.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24R1_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24R1_CANDIDATE.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("affected:", json.dumps(affected, ensure_ascii=False))
    print("status:", status, "| NEXT_BLOCKER:", "ANCHOR_REGION_OR_OBJECT_REPRESENTATION")


if __name__ == "__main__":
    main()
