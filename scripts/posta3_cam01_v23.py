#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.3 — Local Anchor Feature Bakeoff + R1 诊断修正。

修正: ① 象限 TL/TR/BL/BR（原 LT/LB/RT/RB bug）；② target-neighborhood residual 只用
      2-fold holdout 点（禁止 all-match fit residual）。
方法(同 region/同 gate/同 2-fold, 参数预冻结见 CONFIG):
  AKAZE_BASELINE / AKAZE_CLAHE / SIFT_BASELINE / SIFT_GRID_BALANCED / GFTT_LK_LOCAL
Gate 不变: fit inlier>=0.45, holdout>=8, holdout median<=3.0, spatial 2-fold(grid=40)。
不用动作 GT 选方法。不读 A3。
"""
import cv2
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
WMAX = 960
CELL = 40
CONFIG = {
    "analysis_width_max": WMAX, "grid_cell": CELL,
    "ratio": 0.8, "ransac_thr": 3.0,
    "fit_inlier_min": 0.45, "holdout_min": 8, "holdout_median_max_px": 3.0,
    "akaze": {"default": True},
    "clahe": {"clipLimit": 2.0, "tileGridSize": [8, 8]},
    "sift": {"nfeatures": 2000, "contrastThreshold": 0.04},
    "sift_grid": {"cap_per_cell": 6},
    "gftt": {"maxCorners": 300, "qualityLevel": 0.02, "minDistance": 6,
             "lk_win": 21, "lk_maxLevel": 3, "fb_max_px": 3.0},
}
CRIT = (CONFIG["fit_inlier_min"], CONFIG["holdout_min"], CONFIG["holdout_median_max_px"])


class Video:
    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        self.cache = {}
        self.ok = self.cap.isOpened()

    def frame(self, ts):
        key = round(ts, 3)
        if key in self.cache:
            return self.cache[key]
        if not self.ok:
            return None
        self.cap.set(cv2.CAP_PROP_POS_MSEC, key * 1000.0)
        ok, fr = self.cap.read()
        fr = None if not ok else fr
        if fr is not None:
            h, w = fr.shape[:2]
            if w > WMAX:
                fr = cv2.resize(fr, (WMAX, int(h * WMAX / w)), interpolation=cv2.INTER_AREA)
        self.cache[key] = fr
        return fr

    def close(self):
        if self.cap:
            self.cap.release()


def island_mask(shape, ib, others):
    m = np.zeros(shape, dtype=bool)
    x1, y1, x2, y2 = [int(v) for v in ib]
    x1 = max(0, x1); y1 = max(0, y1); x2 = min(shape[1], x2); y2 = min(shape[0], y2)
    m[y1:y2, x1:x2] = True
    for ob in others:
        ox1, oy1, ox2, oy2 = [int(v) for v in ob]
        oy1 = max(0, oy1); oy2 = min(shape[0], oy2)
        ox1 = max(0, ox1); ox2 = min(shape[1], ox2)
        m[oy1:oy2, ox1:ox2] = False
    return m


def fold_split(p0):
    gx = np.floor(p0[:, 0] / CELL).astype(int)
    gy = np.floor(p0[:, 1] / CELL).astype(int)
    return (gx + gy) % 2


def holdout_stats(errs):
    e = np.asarray(errs)
    if len(e) == 0:
        return None
    return {"n": int(len(e)), "median_px": round(float(np.median(e)), 3),
            "p90_px": round(float(np.percentile(e, 90)), 3),
            "gt3": round(float((e > 3).mean()), 3),
            "gt5": round(float((e > 5).mean()), 3),
            "gt10": round(float((e > 10).mean()), 3)}


def validate_pairs(p0, p1):
    """统一 2-fold（fit/val 空间分离）。返回 state + folds + merged holdout(p0,err)。"""
    fold = fold_split(p0)
    res = {"folds": {}}
    hold_pts = []
    for fitf, valf in ((0, 1), (1, 0)):
        fi = fold == fitf
        vi = fold == valf
        rec = {"fit_n": int(fi.sum()), "holdout_n": int(vi.sum())}
        if int(fi.sum()) < 6 or int(vi.sum()) < CRIT[1]:
            rec["state"] = "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"
            res["folds"][f"fit{fitf}val{valf}"] = rec
            continue
        M, inl = cv2.estimateAffinePartial2D(p0[fi], p1[fi], method=cv2.RANSAC,
                                             ransacReprojThreshold=CONFIG["ransac_thr"])
        if M is None or inl is None:
            rec["state"] = "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"
            res["folds"][f"fit{fitf}val{valf}"] = rec
            continue
        ii = inl.ravel() == 1
        fit_inl = float(ii.mean())
        p1p = cv2.transform(p0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        err = np.linalg.norm(p1p - p1[vi], axis=1)
        hs = holdout_stats(err)
        for k, v in hs.items():
            rec[k] = v
        rec["fit_inlier_ratio"] = round(fit_inl, 3)
        rec["state"] = "VALIDATED" if (rec["holdout_n"] >= CRIT[1] and fit_inl >= CRIT[0]
                                       and hs["median_px"] <= CRIT[2]) else "NOT_VALIDATED"
        res["folds"][f"fit{fitf}val{valf}"] = rec
        for i in range(len(err)):
            hold_pts.append((float(p0[vi][i][0]), float(p0[vi][i][1]), float(err[i])))
    sts = [v["state"] for v in res["folds"].values()]
    if len(sts) == 2 and all(s == "VALIDATED" for s in sts):
        res["pair_state"] = "LOCAL_ANCHOR_VALIDATED"
    elif len(sts) == 2 and any(s == "VALIDATED" for s in sts):
        res["pair_state"] = "LOCAL_ANCHOR_PARTIAL"
    elif len(sts) == 2 and all(s == "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT" for s in sts):
        res["pair_state"] = "LOCAL_ANCHOR_INSUFFICIENT"
    else:
        res["pair_state"] = "LOCAL_ANCHOR_NOT_VALIDATED"
    return res, hold_pts


def matches_for(method, g0, g1, mask0, mask1):
    """返回 (p0, p1) good matches/tracks 或 None。"""
    if method in ("AKAZE_BASELINE", "AKAZE_CLAHE"):
        g0u = g0 if method == "AKAZE_BASELINE" else cv2.createCLAHE(
            clipLimit=CONFIG["clahe"]["clipLimit"],
            tileGridSize=tuple(CONFIG["clahe"]["tileGridSize"])).apply(g0)
        g1u = g1 if method == "AKAZE_BASELINE" else cv2.createCLAHE(
            clipLimit=CONFIG["clahe"]["clipLimit"],
            tileGridSize=tuple(CONFIG["clahe"]["tileGridSize"])).apply(g1)
        det = cv2.AKAZE_create()
        k0, d0 = det.detectAndCompute(g0u, mask=(mask0.astype(np.uint8)) * 255)
        k1, d1 = det.detectAndCompute(g1u, mask=(mask1.astype(np.uint8)) * 255)
        if d0 is None or d1 is None:
            return None
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        good = []
        for pr in bf.knnMatch(d0, d1, k=2):
            if len(pr) < 2:
                continue
            m, n = pr
            if m.distance < CONFIG["ratio"] * n.distance:
                good.append(m)
        if len(good) < 12:
            return None
        return (np.float32([k0[m.queryIdx].pt for m in good]).reshape(-1, 2),
                np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 2))
    if method in ("SIFT_BASELINE", "SIFT_GRID_BALANCED"):
        if not hasattr(cv2, "SIFT_create"):
            return "SIFT_UNAVAILABLE"
        sift = cv2.SIFT_create(nfeatures=CONFIG["sift"]["nfeatures"],
                               contrastThreshold=CONFIG["sift"]["contrastThreshold"])
        k0, d0 = sift.detectAndCompute(g0, mask=(mask0.astype(np.uint8)) * 255)
        k1, d1 = sift.detectAndCompute(g1, mask=(mask1.astype(np.uint8)) * 255)
        if d0 is None or d1 is None:
            return None
        bf = cv2.BFMatcher(cv2.NORM_L2)
        good = []
        for pr in bf.knnMatch(d0, d1, k=2):
            if len(pr) < 2:
                continue
            m, n = pr
            if m.distance < CONFIG["ratio"] * n.distance:
                good.append(m)
        if method == "SIFT_GRID_BALANCED":
            cap = CONFIG["sift_grid"]["cap_per_cell"]
            bycell = {}
            picked = []
            for m in sorted(good, key=lambda x: x.distance):
                cx = int(k0[m.queryIdx].pt[0] // CELL)
                cy = int(k0[m.queryIdx].pt[1] // CELL)
                keyc = (cx, cy)
                if bycell.get(keyc, 0) >= cap:
                    continue
                bycell[keyc] = bycell.get(keyc, 0) + 1
                picked.append(m)
                if len(picked) >= 500:
                    break
            good = picked
        if len(good) < 12:
            return None
        return (np.float32([k0[m.queryIdx].pt for m in good]).reshape(-1, 2),
                np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 2))
    if method == "GFTT_LK_LOCAL":
        pts = cv2.goodFeaturesToTrack(g0, mask=(mask0.astype(np.uint8)) * 255,
                                      maxCorners=CONFIG["gftt"]["maxCorners"],
                                      qualityLevel=CONFIG["gftt"]["qualityLevel"],
                                      minDistance=CONFIG["gftt"]["minDistance"], blockSize=7)
        if pts is None or len(pts) < 12:
            return None
        p1t, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts, None,
                                              winSize=(CONFIG["gftt"]["lk_win"], CONFIG["gftt"]["lk_win"]),
                                              maxLevel=CONFIG["gftt"]["lk_maxLevel"])
        p0b, stb, _ = cv2.calcOpticalFlowPyrLK(g1, g0, p1t, None,
                                               winSize=(CONFIG["gftt"]["lk_win"], CONFIG["gftt"]["lk_win"]),
                                               maxLevel=CONFIG["gftt"]["lk_maxLevel"])
        ok = (st.ravel() == 1) & (stb.ravel() == 1)
        if ok.any():
            d = np.linalg.norm(p0b[ok].reshape(-1, 2) - pts[ok].reshape(-1, 2), axis=1)
            ok = ok.copy()
            ok[ok] = d <= CONFIG["gftt"]["fb_max_px"]
        if ok.sum() < 12:
            return None
        return (pts[ok].reshape(-1, 2).astype(np.float32),
                p1t[ok].reshape(-1, 2).astype(np.float32))
    raise ValueError(method)


def quadrant_counts(p0, ib):
    icx = (ib[0] + ib[2]) / 2
    icy = (ib[1] + ib[3]) / 2
    q = {"TL": 0, "TR": 0, "BL": 0, "BR": 0}
    for pt in p0:
        key = ("R" if pt[0] >= icx else "L") + ("B" if pt[1] >= icy else "T")
        name = {"LT": "TL", "LB": "BL", "RT": "TR", "RB": "BR"}[key]
        q[name] += 1
    return q


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cv2.setRNGSeed(0)
    METHODS = ["AKAZE_BASELINE", "AKAZE_CLAHE", "SIFT_BASELINE", "SIFT_GRID_BALANCED", "GFTT_LK_LOCAL"]
    (OUT / "TREECUT_CAM01_V23_METHOD_CONFIG.json").write_text(
        json.dumps({"experiment": "CAM01_V23_METHOD_CONFIG", "config": CONFIG,
                    "methods": METHODS}, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = []
    for c in man["cases"]:
        mid = c["media_id"]
        row = cur.execute("select source_id, relative_path from media_files where id=?", (mid,)).fetchone()
        v = Video(ROOTS.get(row[0]) + "\\" + row[1])
        if not v.ok:
            continue
        A_w = c["frames"][0]["width"]
        A_h = c["frames"][0]["height"]
        ts = [f["t_s"] for f in c["frames"]]
        roi_by_t = {}
        for a in roi:
            if a["media_id"] == mid:
                roi_by_t.setdefault(a["frame_timestamp"], []).append(a)
        for t in ts:
            v.frame(t)
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            fa, fb = v.frame(t0), v.frame(t1)
            if fa is None or fb is None:
                continue
            h, w = fa.shape[:2]
            sx = w / float(A_w)
            sy = h / float(A_h)
            ga = cv2.cvtColor(fa, cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(fb, cv2.COLOR_BGR2GRAY)
            shape = ga.shape

            def ann(t):
                return [(a["object_name"], [a["bbox_pixel"][0] * sx, a["bbox_pixel"][1] * sy,
                                            a["bbox_pixel"][2] * sx, a["bbox_pixel"][3] * sy])
                        for a in roi_by_t.get(t, [])]
            a0, a1 = ann(t0), ann(t1)
            ib0 = [b for n, b in a0 if n == "ISLAND_BODY"]
            ib1 = [b for n, b in a1 if n == "ISLAND_BODY"]
            rec = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                   "island_present": bool(len(ib0) == 1 and len(ib1) == 1), "methods": {}}
            if len(ib0) == 1 and len(ib1) == 1:
                o0 = [b for n, b in a0 if n != "ISLAND_BODY"]
                o1 = [b for n, b in a1 if n != "ISLAND_BODY"]
                mA0 = island_mask(shape, ib0[0], o0)
                mA1 = island_mask(shape, ib1[0], o1)
                tt0 = [b for n, b in a0 if n in ("EXTENSION_TABLETOP", "TABLETOP")]
                tt1 = [b for n, b in a1 if n in ("EXTENSION_TABLETOP", "TABLETOP")]
                iw = max(1, ib0[0][2] - ib0[0][0])
                ih = max(1, ib0[0][3] - ib0[0][1])
                tgt_c = None
                if len(tt0) == 1:
                    tgt_c = [(tt0[0][0] + tt0[0][2]) / 2, (tt0[0][1] + tt0[0][3]) / 2]
                for mth in METHODS:
                    t0m = time.time()
                    mm = matches_for(mth, ga, gb, mA0, mA1)
                    mr = {"runtime_s": 0.0}
                    if mm == "SIFT_UNAVAILABLE":
                        mr.update({"state": "SIFT_UNAVAILABLE"})
                        rec["methods"][mth] = mr
                        continue
                    if mm is None:
                        mr.update({"state": "INSUFFICIENT"})
                        rec["methods"][mth] = mr
                        continue
                    p0, p1 = mm
                    resv, hold_pts = validate_pairs(p0, p1)
                    mr.update(resv)
                    # spatial
                    hull = float(cv2.contourArea(cv2.convexHull(p0.astype(np.int32)))) if len(p0) >= 4 else 0.0
                    island_area = (ib0[0][2] - ib0[0][0]) * (ib0[0][3] - ib0[0][1])
                    cells = len(set(zip((p0[:, 0] / CELL).astype(int), (p0[:, 1] / CELL).astype(int))))
                    mr["spatial"] = {"matches": int(len(p0)),
                                     "hull_island_ratio": round(hull / max(1, island_area), 3),
                                     "occupied_cells": int(cells),
                                     "quadrants": quadrant_counts(p0, ib0[0])}
                    # target neighborhood（仅 holdout 点残差）
                    if tgt_c is not None and hold_pts:
                        norm = 0.5 * (iw + ih)
                        dists = np.linalg.norm(np.array([[x, y] for x, y, _ in hold_pts]) -
                                               np.array(tgt_c), axis=1) / max(1.0, norm)
                        e_arr = np.array([e for _, _, e in hold_pts])
                        nb = {}
                        for bk, cond in (("NEAR", dists < 0.15), ("MID", (dists >= 0.15) & (dists < 0.45)),
                                         ("FAR", dists >= 0.45)):
                            if cond.sum() == 0:
                                continue
                            e = e_arr[cond]
                            nb[bk] = {"count": int(cond.sum()),
                                      "median_px": round(float(np.median(e)), 3),
                                      "p90_px": round(float(np.percentile(e, 90)), 3)}
                        mr["target_neighborhood"] = nb
                    mr["runtime_s"] = round(time.time() - t0m, 2)
                    rec["methods"][mth] = mr
            rows.append(rec)
        v.close()
        print("case done", mid, c["role"], flush=True)
    # 汇总
    from collections import Counter
    summ = {}
    for mth in METHODS:
        cnt = Counter()
        for r in rows:
            m = r["methods"].get(mth, {})
            st = m.get("pair_state", m.get("state", "NO_ISLAND") if not r.get("island_present") else "UNKNOWN")
            cnt[st] += 1
        validated = cnt.get("LOCAL_ANCHOR_VALIDATED", 0)
        cases_ok = len({r["case"] for r in rows
                        if r["methods"].get(mth, {}).get("pair_state") == "LOCAL_ANCHOR_VALIDATED"})
        meds = [r["methods"][mth]["folds"][k]["median_px"] for r in rows
                for k in r["methods"].get(mth, {}).get("folds", {})
                if r["methods"][mth]["folds"][k].get("median_px") is not None]
        p90s = [r["methods"][mth]["folds"][k]["p90_px"] for r in rows
                for k in r["methods"].get(mth, {}).get("folds", {})
                if r["methods"][mth]["folds"][k].get("p90_px") is not None]
        heavy = sum(1 for r in rows
                    if r["methods"].get(mth, {}).get("pair_state") == "LOCAL_ANCHOR_VALIDATED"
                    and any(r["methods"][mth]["folds"][k].get("gt10", 0) > 0.02
                            for k in r["methods"][mth].get("folds", {})))
        hulls = [r["methods"][mth]["spatial"]["hull_island_ratio"] for r in rows
                 if "spatial" in r["methods"].get(mth, {})]
        summ[mth] = {"states": dict(cnt), "validated": validated,
                     "validated_case_coverage": cases_ok,
                     "median_holdout_residual": round(float(np.median(meds)), 3) if meds else None,
                     "p90_holdout_residual": round(float(np.median(p90s)), 3) if p90s else None,
                     "heavy_tail_validated": heavy,
                     "median_hull_ratio": round(float(np.median(hulls)), 3) if hulls else None}
        print(mth, dict(cnt), "| validated", validated, "cases", cases_ok)
    matrix = {"experiment": "CAM01_V23_METHOD_MATRIX", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "summary": summ, "pairs": rows}
    (OUT / "TREECUT_CAM01_V23_METHOD_MATRIX.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=1), encoding="utf-8")
    # winner
    base = summ.get("AKAZE_BASELINE", {}).get("validated", 0)
    best = max(METHODS, key=lambda m: summ[m].get("validated", 0))
    bv = summ[best]["validated"]
    cls = ("NO_MEANINGFUL_IMPROVEMENT" if bv < 18
           else ("STRONG_IMPROVEMENT" if (bv >= 24 and summ[best].get("validated_case_coverage", 0) >= 7
                                          and summ[best].get("heavy_tail_validated", 99) <=
                                          summ["AKAZE_BASELINE"].get("heavy_tail_validated", 0))
                 else "MODERATE_IMPROVEMENT"))
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    winner = {"experiment": "CAM01_V23_WINNER", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "akaze_baseline_validated": base, "best_method": best,
              "best_validated": bv, "improvement_class": cls,
              "candidate": ({"method": best, "config": CONFIG, "metrics": summ[best],
                             "code_sha256_prefix": code_hash}
                            if cls in ("STRONG_IMPROVEMENT", "MODERATE_IMPROVEMENT") else None),
              "status": ("LOCAL_ANCHOR_FEATURE_BAKEOFF_FAILED"
                         if cls == "NO_MEANINGFUL_IMPROVEMENT" else "CAM01_LOCAL_ANCHOR_CANDIDATE_V1_SHADOW")}
    (OUT / "TREECUT_CAM01_V23_WINNER.json").write_text(
        json.dumps(winner, ensure_ascii=False, indent=1), encoding="utf-8")
    print("winner:", best, bv, cls)
    # case diagnostic + spatial validation jsons
    cd = {}
    for mid in (1641, 10000, 2543, 21674, 27433, 12095, 3571, 9697, 25894):
        cd[str(mid)] = {mth: summ[mth]["states"] for mth in METHODS}
        rows_c = [r for r in rows if r["case"] == mid]
        cd[str(mid)]["pairs"] = [{"pair": r["pair"], "methods": {m: r["methods"][m].get("pair_state",
                                      r["methods"][m].get("state")) for m in r["methods"]}}
                                 for r in rows_c]
    (OUT / "TREECUT_CAM01_V23_CASE_DIAGNOSTIC.json").write_text(
        json.dumps(cd, ensure_ascii=False, indent=1), encoding="utf-8")
    # NEG target control availability（最佳方法）
    neg_ok = []
    for c in man["cases"]:
        if c["role"] != "NEG":
            continue
        okpairs = [r for r in rows if r["case"] == c["media_id"]
                   and r["methods"].get(best, {}).get("pair_state") == "LOCAL_ANCHOR_VALIDATED"
                   and "target_neighborhood" in r["methods"].get(best, {})]
        if okpairs:
            neg_ok.append({"case": c["media_id"], "validated_with_target_pairs": len(okpairs)})
    sv = {"experiment": "CAM01_V23_SPATIAL_VALIDATION",
          "summary": summ, "neg_target_control_available_cases": neg_ok,
          "note": "quadrant TL/TR/BL/BR 已修正；target_neighborhood 用 holdout 残差"}
    (OUT / "TREECUT_CAM01_V23_SPATIAL_VALIDATION.json").write_text(
        json.dumps(sv, ensure_ascii=False, indent=1), encoding="utf-8")
    print("NEG control available:", neg_ok if neg_ok else "STILL_MISSING")
    con.close()


if __name__ == "__main__":
    main()
