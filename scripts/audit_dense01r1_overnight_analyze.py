# -*- coding: utf-8 -*-
"""DENSE01R1 OVERNIGHT — INDEPENDENT METRIC RECOMPUTATION & FAILURE MAP (audit-only).

§2/§12/§13/§14/§15/§16/§17/§18/§19：不信任原报告数字，从 overnight replay raw records
独立重算全部指标、逐 pair/model/fold failure taxonomy、holdout residual 分位数、
DINO_ONLY vs DINO_LK、RANSAC stride 单位审计、fold 独立性、coverage 判定审计、
true-pooled 数学。role-blind：不读 POS/NEG，仅最后按 media_id 透视由调用方决定。

输入：TREECUT_DENSE01R1_OVERNIGHT_REPLAY_{tag}.json（audit runner 产物）。
输出：多份 §31 JSON（新文件名）。
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.stdout.reconfigure(encoding="utf-8")

CFG = {"model": "dinov2_vits14_reg", "input": 518, "stride": 14,
       "top_k": 256, "min_mnn": 12, "fit_min": 8, "inlier_min": 0.45,
       "holdout_min": 8, "holdout_med_max": 3.0, "holdout_p90_max": 8.0,
       "bins_min": 4, "quads_min": 2, "agree_px": 3.0, "T": 1.0,
       "lk": {"win": 21, "maxLevel": 3, "fb_max": 3.0}}


def pct(a, q):
    a = np.asarray(a, dtype=np.float64)
    return round(float(np.percentile(a, q)), 3) if len(a) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="replay1")
    args = ap.parse_args()
    raw = json.loads((OUT / f"TREECUT_DENSE01R1_OVERNIGHT_REPLAY_{args.tag}.json")
                     .read_text(encoding="utf-8"))
    pairs = raw["pairs"]
    prod = json.loads((OUT / "TREECUT_CAM01_DENSE01R1_MATCH_MATRIX.json")
                      .read_text(encoding="utf-8"))["pairs"]
    v1 = json.loads((OUT / "TREECUT_CAM01_DENSE01_MATCH_MATRIX.json")
                    .read_text(encoding="utf-8"))["pairs"]
    v1_mnn = {(p["case"], p["pair"]): p.get("mnn_count", 0) for p in v1}
    prod_by = {(p["case"], p["pair"]): p for p in prod}
    n = len(pairs)

    # ---------- §2 指标独立重算 ----------
    old_mnn_suff = sum(1 for p in pairs if (v1_mnn.get((p["case"], p["pair"])) or 0) >= 12)
    corr_mnn_suff = sum(1 for p in pairs if p.get("valid_mnn", 0) >= 12)
    lk_attempted = sum(p.get("lk_attempted", 0) for p in pairs)
    lk_accepted = sum(p.get("lk_accepted_prod_semantics", 0) for p in pairs)
    lk_fb3 = sum(p.get("lk_accepted_fb3", 0) for p in pairs)

    def pipe_valid(pipe):
        aff = sum(1 for p in pairs
                  if p.get("models", {}).get(pipe, {}).get("PARTIAL_AFFINE", {}).get("validated"))
        hom = sum(1 for p in pairs
                  if p.get("models", {}).get(pipe, {}).get("HOMOGRAPHY", {}).get("validated"))
        return aff, hom

    aff_do, hom_do = pipe_valid("DINO_ONLY")
    aff_lk, hom_lk = pipe_valid("DINO_LK")
    cnt = Counter(p.get("state") for p in pairs)
    union = cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0) + cnt.get("DENSE_SINGLE_MODEL", 0)
    case9 = len({p["case"] for p in pairs
                 if p.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")})
    mnn_mismatch = [{"case": p["case"], "pair": p["pair"],
                     "audit": p.get("valid_mnn"), "prod": p.get("prod_valid_mnn")}
                    for p in pairs if p.get("mnn_matches_prod") is not True]

    metrics = {"pairs": n,
               "old_mnn_sufficient": old_mnn_suff,
               "corrected_mnn_sufficient": corr_mnn_suff,
               "lk_attempted_total": lk_attempted,
               "lk_accepted_prod_semantics_total": lk_accepted,
               "lk_accepted_fb3_total": lk_fb3,
               "DINO_ONLY": {"AFFINE": aff_do, "HOMOGRAPHY": hom_do},
               "DINO_LK": {"AFFINE": aff_lk, "HOMOGRAPHY": hom_lk,
                           "MULTI": cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0),
                           "SINGLE": cnt.get("DENSE_SINGLE_MODEL", 0),
                           "CONFLICT": cnt.get("DENSE_MODEL_CONFLICT", 0),
                           "NO": cnt.get("DENSE_NO_ANCHOR", 0) +
                                 cnt.get("DENSE_MATCH_INSUFFICIENT", 0) +
                                 cnt.get("DENSE_SUPPORT_TOO_LOCALIZED", 0) + cnt.get("ERROR", 0),
                           "union": union,
                           "case_coverage_9": case9},
               "state_counts": dict(cnt),
               "mnn_mismatch_vs_prod": mnn_mismatch}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_METRICS_RECOMPUTED.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §12 failure taxonomy（36 × AFFINE/HOM × 2 folds） ----------
    fm = []
    for p in pairs:
        row = {"case": p["case"], "pair": p["pair"], "state": p.get("state")}
        for pipe in ("DINO_ONLY", "DINO_LK"):
            for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                md = p.get("models", {}).get(pipe, {}).get(mdl)
                if md is None:
                    row[f"{pipe}.{mdl}"] = {"m": "NO_MODEL", "folds": None}
                    continue
                if "reason" in md:
                    row[f"{pipe}.{mdl}"] = {"m": md["reason"], "folds": None}
                    continue
                folds = {}
                for fk, fv in md["folds"].items():
                    folds[fk] = {"state": fv["state"],
                                 "fit": fv["fit"], "hold": fv["hold"],
                                 "med": fv.get("med"), "p90": fv.get("p90"),
                                 "inlier": fv.get("inlier_ratio")}
                row[f"{pipe}.{mdl}"] = {"m": "VALIDATED" if md["validated"] else "NOT_VALIDATED",
                                        "folds": folds}
        fm.append(row)
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_FAILURE_MAP.json").write_text(
        json.dumps({"rows": fm}, ensure_ascii=False, indent=1), encoding="utf-8")

    # failure cause 汇总（fold 级 failure reason）
    cause = Counter()
    for p in pairs:
        for pipe in ("DINO_ONLY", "DINO_LK"):
            for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                md = p.get("models", {}).get(pipe, {}).get(mdl)
                if md is None:
                    cause["NO_MODEL"] += 1
                    continue
                if "reason" in md:
                    cause[md["reason"]] += 1
                    continue
                for fk, fv in md["folds"].items():
                    if fv["state"] in ("VALIDATED", "NOT_VALIDATED"):
                        med = fv["med"]; p90 = fv["p90"]
                        if med is not None and p90 is not None:
                            mf = med > CFG["holdout_med_max"]
                            pf = p90 > CFG["holdout_p90_max"]
                            cause[("MED_AND_P90_FAIL" if (mf and pf)
                                   else "HOLDOUT_MEDIAN_FAIL_ONLY" if mf
                                   else "HOLDOUT_P90_FAIL_ONLY" if pf
                                   else "HOLDOUT_PASS")] += 1
                        else:
                            cause["NO_RESIDUALS"] += 1
                    else:
                        cause[fv["state"]] += 1  # INSUFFICIENT/NO_FIT/LOW_INLIER
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_FAILURE_CAUSES.json").write_text(
        json.dumps({"cause_counts": dict(cause)}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    # ---------- §13 holdout residual 全数据分位数 ----------
    resid = {"DINO_ONLY": [], "DINO_LK": []}
    pair_resid = []
    for p in pairs:
        pr_ = {"case": p["case"], "pair": p["pair"]}
        for pipe in ("DINO_ONLY", "DINO_LK"):
            allr = []
            best = {}
            for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                md = p.get("models", {}).get(pipe, {}).get(mdl)
                if md and "folds" in md and not ("reason" in md):
                    for fk, fv in md["folds"].items():
                        rr = fv.get("residuals") or []
                        resid[pipe].extend(rr)
                        allr.extend(rr)
                        if rr:
                            best.setdefault(mdl, {})[fk] = {"med": fv.get("med"),
                                                            "p90": fv.get("p90"),
                                                            "n": len(rr)}
            pr_[pipe] = {"n": len(allr),
                         "median": pct(allr, 50), "p75": pct(allr, 75),
                         "p90": pct(allr, 90), "p95": pct(allr, 95),
                         "p99": pct(allr, 99), "max": (round(float(np.max(allr)), 3)
                                                       if allr else None)}
            pr_[pipe + "_by_model"] = best
        pair_resid.append(pr_)
    hold = {"global": {k: {"n": len(v),
                           "median": pct(v, 50), "p75": pct(v, 75), "p90": pct(v, 90),
                           "p95": pct(v, 95), "p99": pct(v, 99),
                           "max": (round(float(np.max(v)), 3) if v else None)}
                       for k, v in resid.items()},
            "per_pair": pair_resid}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_HOLDOUT_ANALYSIS.json").write_text(
        json.dumps(hold, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §14 DINO_ONLY vs DINO_LK ----------
    delta = []
    for p in pairs:
        d = {"case": p["case"], "pair": p["pair"]}
        for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
            fo = p.get("models", {}).get("DINO_ONLY", {}).get(mdl, {}).get("folds", {})
            fl = p.get("models", {}).get("DINO_LK", {}).get(mdl, {}).get("folds", {})
            # best-fold median 对比（取两 fold 中较小 median 作为 best）
            def bestmed(fd):
                ms = [fv["med"] for fv in fd.values() if fv.get("med") is not None]
                return min(ms) if ms else None
            def bestp90(fd):
                ps = [fv["p90"] for fv in fd.values() if fv.get("p90") is not None]
                return min(ps) if ps else None
            mo, ml = bestmed(fo), bestmed(fl)
            po, pl = bestp90(fo), bestp90(fl)
            if mo is None or ml is None:
                d[mdl] = {"class": "LK_NA"}
                continue
            dmed = ml - mo
            cls = ("LK_HELPED" if dmed < -0.3 else "LK_HURT" if dmed > 0.3 else "LK_NEUTRAL")
            d[mdl] = {"dino_med": mo, "lk_med": ml, "delta_med": round(dmed, 3),
                      "dino_p90": po, "lk_p90": pl, "class": cls}
        delta.append(d)
    cls_cnt = Counter()
    for d in delta:
        for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
            cls_cnt[d[mdl]["class"]] += 1
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_DINO_VS_LK.json").write_text(
        json.dumps({"per_pair": delta, "class_counts": dict(cls_cnt)},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §15 RANSAC stride ----------
    stride_rows = [{"case": p["case"], "pair": p["pair"],
                    "s0": p.get("scale", {}).get("s0"),
                    "s1": p.get("scale", {}).get("s1"),
                    "ransac_thr_raw_px": p.get("ransac_thr"),
                    "patch_raw_px0": round(14 / p["scale"]["s0"], 3) if p.get("scale") else None,
                    "patch_raw_px1": round(14 / p["scale"]["s1"], 3) if p.get("scale") else None}
                   for p in pairs if p.get("scale")]
    unit_ok = all(abs(r["ransac_thr_raw_px"] - max(r["patch_raw_px0"], r["patch_raw_px1"])) < 1e-3
                  for r in stride_rows)
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_RANSAC_STRIDE.json").write_text(
        json.dumps({"rows": stride_rows, "unit_raw_px": True,
                    "thr_equals_max_patch_over_scale": unit_ok},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §16 fold 独立性 ----------
    fold_rows = []
    for p in pairs:
        f0 = p.get("fold_ids", {}).get("fold0", [])
        f1 = p.get("fold_ids", {}).get("fold1", [])
        inter = len(set(f0) & set(f1))
        alln = len(f0) + len(f1)
        fold_rows.append({"case": p["case"], "pair": p["pair"],
                          "fit0_hold1": len(f0), "fit1_hold0": len(f1),
                          "intersection": inter, "total_corr": alln,
                          "disjoint": inter == 0})
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_FOLD_INDEPENDENCE.json").write_text(
        json.dumps({"rows": fold_rows,
                    "all_disjoint": all(r["disjoint"] for r in fold_rows)},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §17 coverage：全量 vs accepted ----------
    cov_rows = []
    for p in pairs:
        ca = p.get("coverage") or {}
        caa = p.get("coverage_accepted") or {}
        cov_rows.append({"case": p["case"], "pair": p["pair"],
                         "all_mnn_bins": ca.get("bins"), "all_mnn_quads": ca.get("quads"),
                         "accepted_bins": caa.get("bins") if isinstance(caa, dict) else None,
                         "accepted_quads": caa.get("quads") if isinstance(caa, dict) else None,
                         "state": p.get("state"),
                         "state_under_accepted_cov": p.get("state_under_accepted_coverage")})
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_SPATIAL_COVERAGE.json").write_text(
        json.dumps({"rows": cov_rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- §19 true pooled math（从 validated residuals；若 0 validated 为 null） ----------
    pooled = []
    for p in pairs:
        if p.get("state") not in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL"):
            continue
        rp = p.get("representative")
        for fk in p.get("models", {}).get("DINO_LK", {}).get(rp, {}).get("folds", {}).values():
            pooled.extend(fk.get("residuals") or [])
    pooled = np.array(pooled, dtype=np.float64)
    tp = {"n": int(len(pooled)),
          "median": pct(pooled, 50), "p90": pct(pooled, 90), "p95": pct(pooled, 95)} \
        if len(pooled) else {"n": 0, "median": None, "p90": None, "p95": None}
    (OUT / "TREECUT_DENSE01R1_OVERNIGHT_TRUE_POOLED.json").write_text(
        json.dumps(tp, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({"recomputed": metrics, "holdout_global": hold["global"],
                      "dino_vs_lk_classes": dict(cls_cnt),
                      "fold_all_disjoint": all(r["disjoint"] for r in fold_rows),
                      "true_pooled": tp}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
