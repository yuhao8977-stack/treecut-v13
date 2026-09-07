#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.4 — Multi-method Local Anchor Consensus + V2.3 report corrections。

修正: state 汇总不用 UNKNOWN 吞 INSUFFICIENT；case 统计按本 case 4 pairs；
      pooled holdout median/P90（真残差数组）；NEG target control 严格 t0/t1 contract。
方法: AKAZE_BASELINE/CLAHE/SIFT/SIFT_GRID/GFTT_LK（参数冻结同 V2.3），逐 pair 存 final 2x3 变换、
      2-fold 证据、holdout 残差数组。
共识: 同一 pair ≥2 方法 VALIDATED 时，在岛台固定 6×6 网格(排除前景)比两两变换分歧；
      主分歧≤3px(沿用既有尺度, 非新调参) 的最大方法簇 → MULTI_METHOD_CONSENSUS；有≥2 但不成簇→METHOD_CONFLICT；
      单方法→SINGLE_METHOD_VALIDATED；0→NO_VALID_ANCHOR。
不读 A3；方法/共识/代表选择不用动作 GT。
"""
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import cv2
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
CONFIG = {"analysis_width_max": WMAX, "grid_cell": CELL, "ratio": 0.8, "ransac_thr": 3.0,
          "fit_inlier_min": 0.45, "holdout_min": 8, "holdout_median_max_px": 3.0,
          "clahe": {"clipLimit": 2.0, "tileGridSize": [8, 8]},
          "sift": {"nfeatures": 2000, "contrastThreshold": 0.04},
          "sift_grid": {"cap_per_cell": 6},
          "gftt": {"maxCorners": 300, "qualityLevel": 0.02, "minDistance": 6,
                   "lk_win": 21, "lk_maxLevel": 3, "fb_max_px": 3.0}}
AGREE_PX = 3.0
GRID_N = 6
METHODS = ["AKAZE_BASELINE", "AKAZE_CLAHE", "SIFT_BASELINE", "SIFT_GRID_BALANCED", "GFTT_LK_LOCAL"]
TIE_ORDER = ["GFTT_LK_LOCAL", "AKAZE_CLAHE", "AKAZE_BASELINE", "SIFT_GRID_BALANCED", "SIFT_BASELINE"]


def state_of(pr, mth):
    m = pr["methods"].get(mth, {})
    return m.get("pair_state", m.get("state", "NO_RESULT"))


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


def matches_for(method, g0, g1, mask0, mask1):
    if method in ("AKAZE_BASELINE", "AKAZE_CLAHE"):
        if method == "AKAZE_CLAHE":
            clahe = cv2.createCLAHE(clipLimit=CONFIG["clahe"]["clipLimit"],
                                    tileGridSize=tuple(CONFIG["clahe"]["tileGridSize"]))
            g0, g1 = clahe.apply(g0), clahe.apply(g1)
        det = cv2.AKAZE_create()
        k0, d0 = det.detectAndCompute(g0, mask=(mask0.astype(np.uint8)) * 255)
        k1, d1 = det.detectAndCompute(g1, mask=(mask1.astype(np.uint8)) * 255)
        if d0 is None or d1 is None:
            return None
        good = []
        for pr in cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d0, d1, k=2):
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
        good = []
        for pr in cv2.BFMatcher(cv2.NORM_L2).knnMatch(d0, d1, k=2):
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
                keyc = (int(k0[m.queryIdx].pt[0] // CELL), int(k0[m.queryIdx].pt[1] // CELL))
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


def run_method_full(p0, p1):
    """2-fold（fit/val 分离）→ dict incl 残差数组；返回 (rec, pooled_holdout_errs)。"""
    fold = (np.floor(p0[:, 0] / CELL).astype(int) + np.floor(p0[:, 1] / CELL).astype(int)) % 2
    rec = {"folds": {}}
    pooled = []
    for fitf, valf in ((0, 1), (1, 0)):
        fi, vi = fold == fitf, fold == valf
        fr = {"fit_n": int(fi.sum()), "holdout_n": int(vi.sum())}
        if int(fi.sum()) < 6 or int(vi.sum()) < 8:
            fr["state"] = "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"
            rec["folds"][f"fit{fitf}val{valf}"] = fr
            continue
        M, inl = cv2.estimateAffinePartial2D(p0[fi], p1[fi], method=cv2.RANSAC,
                                             ransacReprojThreshold=CONFIG["ransac_thr"])
        if M is None or inl is None:
            fr["state"] = "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"
            rec["folds"][f"fit{fitf}val{valf}"] = fr
            continue
        fit_inl = float((inl.ravel() == 1).mean())
        p1p = cv2.transform(p0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        err = np.linalg.norm(p1p - p1[vi], axis=1)
        pooled.extend(err.tolist())
        fr.update({"state": "VALIDATED" if (fr["holdout_n"] >= 8 and fit_inl >= 0.45
                                            and float(np.median(err)) <= 3.0) else "NOT_VALIDATED",
                   "fit_inlier_ratio": round(fit_inl, 3),
                   "holdout_median_px": round(float(np.median(err)), 3),
                   "holdout_p90_px": round(float(np.percentile(err, 90)), 3),
                   "holdout_residuals": [round(float(x), 3) for x in err]})
        rec["folds"][f"fit{fitf}val{valf}"] = fr
    sts = [v["state"] for v in rec["folds"].values()]
    if len(sts) == 2 and all(s == "VALIDATED" for s in sts):
        rec["pair_state"] = "LOCAL_ANCHOR_VALIDATED"
    elif len(sts) == 2 and any(s == "VALIDATED" for s in sts):
        rec["pair_state"] = "LOCAL_ANCHOR_PARTIAL"
    elif len(sts) == 2 and all(s == "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT" for s in sts):
        rec["pair_state"] = "LOCAL_ANCHOR_INSUFFICIENT"
    else:
        rec["pair_state"] = "LOCAL_ANCHOR_NOT_VALIDATED"
    return rec, pooled


def island_grid(ib, others, n=GRID_N):
    """岛台内 n×n 网格中心点，排除前景框内点。"""
    x1, y1, x2, y2 = [float(v) for v in ib]
    pts = []
    for i in range(n):
        for j in range(n):
            px = x1 + (i + 0.5) * (x2 - x1) / n
            py = y1 + (j + 0.5) * (y2 - y1) / n
            inside_fg = False
            for ob in others:
                if ob[0] <= px <= ob[2] and ob[1] <= py <= ob[3]:
                    inside_fg = True
                    break
            if not inside_fg:
                pts.append([px, py])
    return np.float32(pts).reshape(-1, 2) if pts else None


def pick_target(a_list):
    ex = [b for n, b in a_list if n == "EXTENSION_TABLETOP"]
    if len(ex) == 1:
        return ex[0], "EXTENSION_TABLETOP"
    tp = [b for n, b in a_list if n == "TABLETOP"]
    if len(ex) == 0 and len(tp) == 1:
        return tp[0], "TABLETOP"
    return None, None


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cv2.setRNGSeed(0)
    pair_rows = []
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
            sx, sy = w / float(A_w), h / float(A_h)
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
            pr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                  "island_present": bool(len(ib0) == 1 and len(ib1) == 1), "methods": {}}
            tt0, _ = pick_target(a0)
            tt1, _ = pick_target(a1)
            pr["target_t0_valid"] = tt0 is not None
            pr["target_t1_valid"] = tt1 is not None
            if len(ib0) == 1 and len(ib1) == 1:
                o0 = [b for n, b in a0 if n != "ISLAND_BODY"]
                o1 = [b for n, b in a1 if n != "ISLAND_BODY"]
                pr["ib0_bbox"] = ib0[0]
                pr["fg_others0"] = o0
                mA0 = island_mask(shape, ib0[0], o0)
                mA1 = island_mask(shape, ib1[0], o1)
                for mth in METHODS:
                    mm = matches_for(mth, ga, gb, mA0, mA1)
                    if mm == "SIFT_UNAVAILABLE":
                        pr["methods"][mth] = {"state": "SIFT_UNAVAILABLE"}
                        continue
                    if mm is None:
                        pr["methods"][mth] = {"state": "INSUFFICIENT", "pair_state": "INSUFFICIENT"}
                        continue
                    p0, p1 = mm
                    recv, pooled = run_method_full(p0, p1)
                    # final transform（all matches RANSAC）
                    Mf, _ = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                                        ransacReprojThreshold=3.0)
                    recv["final_M_2x3"] = [list(x) for x in Mf.tolist()] if Mf is not None else None
                    recv["pooled_holdout_median"] = round(float(np.median(pooled)), 3) if pooled else None
                    recv["pooled_holdout_p90"] = round(float(np.percentile(pooled, 90)), 3) if pooled else None
                    hull = float(cv2.contourArea(cv2.convexHull(p0.astype(np.int32)))) if len(p0) >= 4 else 0.0
                    island_area = (ib0[0][2] - ib0[0][0]) * (ib0[0][3] - ib0[0][1])
                    cells = len(set(zip((p0[:, 0] / CELL).astype(int), (p0[:, 1] / CELL).astype(int))))
                    recv["spatial"] = {"matches": int(len(p0)),
                                       "hull_island_ratio": round(hull / max(1, island_area), 3),
                                       "occupied_cells": int(cells)}
                    pr["methods"][mth] = recv
            pair_rows.append(pr)
        v.close()
        print("case done", mid, c["role"], flush=True)

    # ---- union / consensus（真实重算；不用动作 GT）----
    island_pairs = [pr for pr in pair_rows if pr["island_present"]]
    union_n = multi_n = single_n = none_n = conflict_n = 0
    disag_med, disag_p90, cons_rep, cons_pooled = [], [], [], []
    for pr in island_pairs:
        val = [m for m in METHODS if state_of(pr, m) == "LOCAL_ANCHOR_VALIDATED"]
        pr["validated_method_count"] = len(val)
        if len(val) == 0:
            none_n += 1
            pr["consensus"] = "NO_VALID_ANCHOR"
            continue
        union_n += 1
        if len(val) == 1:
            single_n += 1
            pr["consensus"] = "SINGLE_METHOD_VALIDATED"
            pr["representative"] = val[0]
            cons_rep.append(val[0])
            m0 = pr["methods"][val[0]]
            if m0.get("pooled_holdout_median") is not None:
                cons_pooled.append((m0["pooled_holdout_median"], m0["pooled_holdout_p90"]))
            continue
        # ≥2 validated → 固定 6×6 island grid 分歧
        gpts = island_grid(pr["ib0_bbox"], pr.get("fg_others0", []))
        pairs_dis = []
        if gpts is not None and len(gpts) >= 4:
            g0 = gpts
            for a in val:
                M = np.asarray(pr["methods"][a]["final_M_2x3"], dtype=np.float64)
                pred = cv2.transform(g0.reshape(-1, 1, 2), M).reshape(-1, 2)
                for b in val:
                    if b <= a:
                        continue
                    Mb = np.asarray(pr["methods"][b]["final_M_2x3"], dtype=np.float64)
                    predb = cv2.transform(g0.reshape(-1, 1, 2), Mb).reshape(-1, 2)
                    d = np.linalg.norm(pred - predb, axis=1)
                    pairs_dis.append((a, b, float(np.median(d)), float(np.percentile(d, 90))))
        # 成簇：存在一对 ≤AGREE_PX 即视为两两一致簇（聚类规则跑前固定）
        clusters = []
        for a in val:
            grp = [a] + [b for (x, b, md, _) in pairs_dis if x == a and md <= AGREE_PX] + \
                        [x for (x, b, md, _) in pairs_dis if b == a and md <= AGREE_PX]
            grp = list(dict.fromkeys(grp))
            clusters.append(grp)
        best_cluster = max(clusters, key=len)
        if len(best_cluster) >= 2:
            multi_n += 1
            pr["consensus"] = "MULTI_METHOD_CONSENSUS"
            pr["consensus_cluster"] = best_cluster
            # representative：簇内 pooled median 最小 → P90 → tie-break 固定顺序
            def keyf(m):
                d = pr["methods"][m]
                return (d.get("pooled_holdout_median") if d.get("pooled_holdout_median") is not None else 99,
                        d.get("pooled_holdout_p90") if d.get("pooled_holdout_p90") is not None else 999,
                        TIE_ORDER.index(m) if m in TIE_ORDER else 99)
            rep = min(best_cluster, key=keyf)
            pr["representative"] = rep
            cons_rep.append(rep)
            md = [pd[2] for pd in pairs_dis if pd[0] in best_cluster and pd[1] in best_cluster]
            if md:
                disag_med.append(max(md))
                disag_p90.append(max(pd[3] for pd in pairs_dis
                                     if pd[0] in best_cluster and pd[1] in best_cluster))
            m0 = pr["methods"][rep]
            if m0.get("pooled_holdout_median") is not None:
                cons_pooled.append((m0["pooled_holdout_median"], m0["pooled_holdout_p90"]))
        else:
            conflict_n += 1
            pr["consensus"] = "METHOD_CONFLICT"
            pr["representative"] = None
    union_cases = len({pr["case"] for pr in island_pairs if pr.get("validated_method_count", 0) >= 1})
    cons_cases = len({pr["case"] for pr in island_pairs if pr["consensus"] == "MULTI_METHOD_CONSENSUS"})
    # pooled residual（代表方法）
    pmed = [x for x, _ in cons_pooled]
    pp90 = [y for _, y in cons_pooled]
    metrics = {"island_present_pairs": len(island_pairs),
               "oracle_union_validated": union_n,
               "multi_method_consensus": multi_n,
               "single_method_validated": single_n,
               "method_conflict": conflict_n,
               "no_valid_anchor": none_n,
               "union_case_coverage": union_cases,
               "consensus_case_coverage": cons_cases,
               "consensus_pooled_holdout_median": round(float(np.median(pmed)), 3) if pmed else None,
               "consensus_pooled_holdout_p90": round(float(np.median(pp90)), 3) if pp90 else None,
               "transform_disagreement_median_px": round(float(np.median(disag_med)), 3) if disag_med else None,
               "transform_disagreement_p90_px": round(float(np.median(disag_p90)), 3) if disag_p90 else None,
               "representative_distribution": dict(sorted(
                   {m: cons_rep.count(m) for m in set(cons_rep)}.items(), key=lambda kv: -kv[1]))}
    # NEG target control（严格 t0/t1 contract）
    neg_ctrl = {"consensus": [], "single_source": []}
    for pr in island_pairs:
        if pr["role"] != "NEG":
            continue
        if not (pr.get("target_t0_valid") and pr.get("target_t1_valid")):
            continue
        if pr["consensus"] == "MULTI_METHOD_CONSENSUS":
            neg_ctrl["consensus"].append({"case": pr["case"], "pair": pr["pair"]})
        elif pr["consensus"] == "SINGLE_METHOD_VALIDATED":
            neg_ctrl["single_source"].append({"case": pr["case"], "pair": pr["pair"]})
    cons_n = len({x["case"] for x in neg_ctrl["consensus"]})
    single_n_c = len({x["case"] for x in neg_ctrl["single_source"]})
    neg_ctrl["consensus_cases"] = cons_n
    neg_ctrl["single_source_cases"] = single_n_c
    # decision
    akaze_base = sum(1 for pr in island_pairs if state_of(pr, "AKAZE_BASELINE") == "LOCAL_ANCHOR_VALIDATED")
    if multi_n >= 18 and conflict_n <= 4 and cons_cases >= 7 and multi_n > akaze_base + 4:
        status = "CONSENSUS_PROMISING"
    elif union_n > 20 and multi_n < 18:
        status = "CONSENSUS_PARTIAL"
    elif union_n <= 20 or conflict_n >= multi_n:
        status = "CONSENSUS_NOT_SUPPORTED"
    else:
        status = "CONSENSUS_PARTIAL"
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    candidate = {"method_configs": CONFIG, "methods": METHODS,
                 "consensus_rule": {"min_validated_methods": 2, "agreement_px": AGREE_PX,
                                    "cluster": "largest pairwise<=3px group (pre-fixed)"},
                 "representative_rule": {"1": "lowest pooled holdout median", "2": "lowest pooled P90",
                                         "3": "fixed tie-break order", "4": "no action GT"},
                 "metrics": metrics, "code_sha256_prefix": code_hash,
                 "status": "CALIBRATION_SHADOW_ONLY"}
    (OUT / "TREECUT_CAM01_V24_METHOD_UNION.json").write_text(
        json.dumps({"experiment": "CAM01_V24_METHOD_UNION", "metrics": metrics,
                    "per_pair": [{k: pr[k] for k in ("case", "role", "pair", "validated_method_count")}
                                 for pr in island_pairs]}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24_TRANSFORM_CONSENSUS.json").write_text(
        json.dumps({"experiment": "CAM01_V24_TRANSFORM_CONSENSUS", "metrics": metrics,
                    "pairs": [{k: pr[k] for k in ("case", "role", "pair", "consensus", "consensus_cluster",
                                                  "representative") if k in pr}
                              for pr in island_pairs]}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24_CASE_MATRIX.json").write_text(
        json.dumps({"pairs": island_pairs}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_ctrl, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V24_CANDIDATE.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=1), encoding="utf-8")
    print("metrics:", json.dumps(metrics, ensure_ascii=False))
    print("NEG ctrl:", json.dumps(neg_ctrl, ensure_ascii=False))
    print("status:", status, "| akaze_base:", akaze_base)
    # 困难案例真实状态
    for mid in (1641, 10000, 2543, 21674):
        for pr in island_pairs:
            if pr["case"] == mid:
                print(mid, pr["pair"], {m: state_of(pr, m) for m in METHODS}, "cons:", pr["consensus"])
    con.close()


def ib0_of(pr, rows):
    return None


if __name__ == "__main__":
    main()
