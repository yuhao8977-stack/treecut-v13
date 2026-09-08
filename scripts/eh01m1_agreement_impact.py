# -*- coding: utf-8 -*-
"""EH01 M1 §15-§23：router impact shadow + local agreement + structural diagnostic + target.

role-blind：本脚本先做全部诊断，target diagnostic 最后才读 role。
只 shadow，不修改 EH01R1 historical router。
"""
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
sys.stdout.reconfigure(encoding="utf-8")

STRUCT_SYM_P90_MAX = 12.0
AGREE_MED_MAX = 3.0
HULL_DIL = 1


def _obj01():
    spec = importlib.util.spec_from_file_location(
        "obj01", REPO / "scripts" / "posta3_cam01_obj01.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def island_bbox(roi, mid, t):
    for a in roi:
        if a["media_id"] == mid and a["frame_timestamp"] == t and a["object_name"] == "ISLAND_BODY":
            return a["bbox_pixel"]
    return None


def predict_grid(T, ib, grid=(9, 6)):
    x0, y0, x1, y1 = [float(v) for v in ib]
    xs = np.linspace(x0 + (x1 - x0) * 0.08, x0 + (x1 - x0) * 0.92, grid[0])
    ys = np.linspace(y0 + (y1 - y0) * 0.08, y0 + (y1 - y0) * 0.92, grid[1])
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    p1p = cv2.transform(pts.reshape(-1, 1, 2).astype(np.float32),
                        np.float32(T[:2])).reshape(-1, 2)
    return p1p


def t3_from_2x3(M):
    return np.vstack([np.asarray(M, dtype=np.float64), [0, 0, 1.0]])


def transform_disagreement(Ta3, Tb3, ib):
    pa = predict_grid(Ta3, ib)
    pb = predict_grid(Tb3, ib)
    d = np.linalg.norm(pa - pb, axis=1)
    return float(np.median(d)), float(np.percentile(d, 90))


def main():
    m = _obj01()
    roi = load("TREECUT_POSTA3_HUMAN_ROI_V1.json")["annotations"]
    man = load("TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json")
    r2 = load("TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json")["pairs"]
    v24 = load("TREECUT_CAM01_V24R1_TRUE_CLIQUE_CONSENSUS.json")["pairs"]
    gftt_mats = load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    r1r = load("TREECUT_CAM01_EH01R1_ROUTER_SHADOW.json")["rows"]
    cam = load("TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json")["cases"]
    r2s = load("TREECUT_CAM01_DENSE01R2_STRUCTURAL_VALIDATION.json")["rows"]
    v23c = load("TREECUT_CAM01_V23_METHOD_MATRIX.json")["pairs"]

    gftt_by = {r["case"]: r["pair"] for r in []}  # placeholder
    gmat = {}
    for r in gftt_mats:
        if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE":
            gmat[(r["case"], r["pair"])] = r
    print("GFTT materialized count:", len(gmat))

    # ===== §15 router impact shadow =====
    r1r_by = {(r["case"], r["pair"]): r for r in r1r}
    # 7 no-transform GFTT routes from EH01R1: EVIDENCE_ONLY + GLOBAL_FALLBACK that are GFTT-based
    impact = {"EVIDENCE_ONLY_NO_TRANSFORM": [], "GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY": [],
              "covered_by_other_strong": [], "in_conflict": [], "other": []}
    for (k, r) in sorted(r1r_by.items()):
        if k in gmat:
            rt = r["route"]
            if rt == "EVIDENCE_ONLY_NO_TRANSFORM":
                impact["EVIDENCE_ONLY_NO_TRANSFORM"].append(k)
            elif rt == "GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY":
                impact["GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY"].append(k)
            elif rt in ("REFERENCE_EMITTABLE_STRONG", "REFERENCE_PARTIAL_WITH_TRANSFORM"):
                impact["covered_by_other_strong"].append(k)
            elif rt == "LOCAL_CONFLICT":
                impact["in_conflict"].append(k)
            else:
                impact["other"].append(k)
    for key in impact:
        impact[key] = {"count": len(impact[key]),
                       "pairs": [f"{c} {p}" for c, p in impact[key]]}
    # 7 no-transform routes materialized?
    no_tf = ([tuple(x) for x in impact["EVIDENCE_ONLY_NO_TRANSFORM"]["pairs"]]
             if False else [])
    no_tf_pairs = impact["EVIDENCE_ONLY_NO_TRANSFORM"]["pairs"] + \
                  impact["GLOBAL_FALLBACK_CANDIDATE_STATE_ONLY"]["pairs"]
    gftt_keys = set(gmat.keys())
    no_tf_keys = set()
    for s in no_tf_pairs:
        parts = s.split(" ")
        no_tf_keys.add((int(parts[0]), parts[1]))
    mat_after = no_tf_keys & gftt_keys
    impact["no_transform_routes_now_materialized"] = {
        "total_no_tf": len(no_tf_keys), "materialized": len(mat_after),
        "pairs": sorted(f"{c} {p}" for c, p in mat_after)}
    (OUT / "TREECUT_CAM01_EH01M1_ROUTER_IMPACT_SHADOW.json").write_text(
        json.dumps(impact, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== §16 local agreement GFTT vs V24 / DENSE =====
    v24_by = {}
    for x in v24:
        if x.get("consensus") == "MULTI_METHOD_CONSENSUS":
            rep = x.get("representative")
            md = x.get("methods", {}).get(rep, {})
            m2x3 = md.get("final_M_2x3")
            if m2x3:
                v24_by[(x["case"], x["pair"])] = t3_from_2x3(m2x3)
    r2_exact = {}
    for p in r2:
        if p.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL"):
            acc = [c for c in p.get("corr", []) if c.get("reject") == "ACCEPT"]
            if len(acc) >= 4:
                P0 = np.float32([c["p0"] for c in acc])
                P1 = np.float32([c["p1_fb"] for c in acc])
                rep = p.get("representative", "PARTIAL_AFFINE")
                thr = p.get("ransac_thr_raw", 4.0)
                if rep == "HOMOGRAPHY":
                    M, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
                    if M is not None:
                        r2_exact[(p["case"], p["pair"])] = M
                else:
                    M, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                                       ransacReprojThreshold=thr)
                    if M is not None:
                        r2_exact[(p["case"], p["pair"])] = t3_from_2x3(M)

    agr = {"GFTT_vs_V24": [], "GFTT_vs_DENSE": []}
    for (k, g) in sorted(gmat.items()):
        ib = island_bbox(roi, k[0], float(k[1].split("->")[0]))
        if not ib:
            continue
        T3g = t3_from_2x3(g["M2x3"])
        if k in v24_by:
            med, p90 = transform_disagreement(T3g, v24_by[k], ib)
            agr["GFTT_vs_V24"].append({"case": k[0], "pair": k[1],
                                       "median_px": round(med, 3), "p90_px": round(p90, 3),
                                       "verdict": "AGREE" if med <= AGREE_MED_MAX else "CONFLICT"})
        if k in r2_exact:
            med, p90 = transform_disagreement(T3g, r2_exact[k], ib)
            agr["GFTT_vs_DENSE"].append({"case": k[0], "pair": k[1],
                                         "median_px": round(med, 3), "p90_px": round(p90, 3),
                                         "verdict": "AGREE" if med <= AGREE_MED_MAX else "CONFLICT"})
    from collections import Counter
    out_agr = {}
    for k2, rows in agr.items():
        vc = Counter(r["verdict"] for r in rows)
        out_agr[k2] = {"agree": vc.get("AGREE", 0), "conflict": vc.get("CONFLICT", 0),
                       "not_comparable": len(gmat) - len(rows), "rows": rows}
    (OUT / "TREECUT_CAM01_EH01M1_LOCAL_AGREEMENT.json").write_text(
        json.dumps(out_agr, ensure_ascii=False, indent=1), encoding="utf-8")
    print("GFTT vs V24:", out_agr["GFTT_vs_V24"]["agree"], "agree /",
          out_agr["GFTT_vs_V24"]["conflict"], "conflict")
    print("GFTT vs DENSE:", out_agr["GFTT_vs_DENSE"]["agree"], "agree /",
          out_agr["GFTT_vs_DENSE"]["conflict"], "conflict")


if __name__ == "__main__":
    main()
