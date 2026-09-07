#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.2 R1 — holdout 计数 bug 修正 + Anchor 失败地图（诊断，不调参）。

修正: two_fold_validate 中 len(vi)>=8 → int(vi.sum())>=8（登记 CAM01_V22_DEFECT_HOLDOUT_COUNT_01）。
仅修此 bug；其余(网格2-fold/AKAZE/partial affine/inlier≥0.45/median≤3)不变。
新增诊断: P90/outlier 分布、空间覆盖(凸包/象限)、目标邻域 NEAR/MID/FAR、失败分类。
不做 P90 gate；不改状态口径；不造叶板；不读 A3。
"""
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
CRIT_FIT_INLIER = 0.45
CRIT_HOLDOUT_N = 8
CRIT_HOLDOUT_MED = 3.0


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


def two_fold_validate(p0, p1):
    """deterministic grid 2-fold；holdout 点数 = int(vi.sum())（修正 bug）。"""
    gx = np.floor(p0[:, 0] / CELL).astype(int)
    gy = np.floor(p0[:, 1] / CELL).astype(int)
    fold = (gx + gy) % 2
    res = {"matches": int(len(p0)), "folds": {}}
    for fitf, valf in ((0, 1), (1, 0)):
        fi = fold == fitf
        vi = fold == valf
        if int(fi.sum()) < 6 or int(vi.sum()) < CRIT_HOLDOUT_N:
            res["folds"][f"fit{fitf}val{valf}"] = {"state": "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT",
                                                   "holdout_n": int(vi.sum())}
            continue
        M, inl = cv2.estimateAffinePartial2D(p0[fi], p1[fi], method=cv2.RANSAC,
                                             ransacReprojThreshold=3.0)
        if M is None or inl is None:
            res["folds"][f"fit{fitf}val{valf}"] = {"state": "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT",
                                                   "fit_inlier_ratio": None, "holdout_n": int(vi.sum())}
            continue
        ii = inl.ravel() == 1
        fit_inl = float(ii.mean())
        p1p = cv2.transform(p0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        err = np.linalg.norm(p1p - p1[vi], axis=1)
        hmed = float(np.median(err)) if len(err) else None
        ok = (int(vi.sum()) >= CRIT_HOLDOUT_N and fit_inl >= CRIT_FIT_INLIER
              and hmed is not None and hmed <= CRIT_HOLDOUT_MED)
        res["folds"][f"fit{fitf}val{valf}"] = {
            "state": "VALIDATED" if ok else "NOT_VALIDATED",
            "fit_inlier_ratio": round(fit_inl, 3), "holdout_n": int(vi.sum()),
            "holdout_median_px": (round(hmed, 3) if hmed is not None else None),
            "holdout_p90_px": round(float(np.percentile(err, 90)), 3) if len(err) else None,
            "outlier_ratio_gt3": round(float((err > 3.0).mean()), 3) if len(err) else None}
    states = [v["state"] for v in res["folds"].values()]
    if all(s == "VALIDATED" for s in states) and len(states) == 2:
        res["pair_state"] = "LOCAL_ANCHOR_VALIDATED"
    elif any(s == "VALIDATED" for s in states):
        res["pair_state"] = "LOCAL_ANCHOR_PARTIAL"
    elif all(s == "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT" for s in states) and len(states) == 2:
        res["pair_state"] = "LOCAL_ANCHOR_INSUFFICIENT"
    else:
        res["pair_state"] = "LOCAL_ANCHOR_NOT_VALIDATED"
    return res


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    rows = []
    tgt_geom = []
    tgt_px = []
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
            fa = v.frame(t0)
            fb = v.frame(t1)
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
                   "island_both": bool(len(ib0) == 1 and len(ib1) == 1)}
            if len(ib0) == 1 and len(ib1) == 1:
                other0 = [b for n, b in a0 if n != "ISLAND_BODY"]
                other1 = [b for n, b in a1 if n != "ISLAND_BODY"]
                mA0 = island_mask(shape, ib0[0], other0)
                mA1 = island_mask(shape, ib1[0], other1)
                det = cv2.AKAZE_create()
                k0, d0 = det.detectAndCompute(ga, mask=(mA0.astype(np.uint8)) * 255)
                k1, d1 = det.detectAndCompute(gb, mask=(mA1.astype(np.uint8)) * 255)
                reasons = []
                if d0 is None or d1 is None or len(k0) < 12 or len(k1) < 12:
                    reasons.append("FEATURES_TOO_FEW")
                    rec.update({"anchor": {"pair_state": "LOCAL_ANCHOR_INSUFFICIENT"},
                                "reasons": reasons})
                else:
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
                    knn = bf.knnMatch(d0, d1, k=2)
                    good = [m for m, n in knn if m.distance < 0.8 * n.distance]
                    if len(good) < 12:
                        reasons.append("MATCHES_TOO_FEW")
                        rec.update({"anchor": {"pair_state": "LOCAL_ANCHOR_INSUFFICIENT", "matches": len(good)},
                                    "reasons": reasons})
                    else:
                        p0 = np.float32([k0[m.queryIdx].pt for m in good]).reshape(-1, 2)
                        p1 = np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 2)
                        resv = two_fold_validate(p0, p1)
                        for k, f in resv["folds"].items():
                            if f.get("state") == "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT" and f.get("holdout_n", 99) < CRIT_HOLDOUT_N:
                                reasons.append("FOLD_HOLDOUT_TOO_FEW")
                            if f.get("fit_inlier_ratio") is not None and f.get("fit_inlier_ratio", 1) < CRIT_FIT_INLIER:
                                reasons.append("LOW_FIT_INLIER")
                            if f.get("state") == "NOT_VALIDATED" and f.get("holdout_median_px", 0) and f["holdout_median_px"] > CRIT_HOLDOUT_MED:
                                reasons.append("HIGH_HOLDOUT_MEDIAN")
                        # 空间诊断
                        hull_area = 0.0
                        island_area = max(1, (ib0[0][2] - ib0[0][0]) * (ib0[0][3] - ib0[0][1]))
                        quads = {"TL": 0, "TR": 0, "BL": 0, "BR": 0}
                        icx = (ib0[0][0] + ib0[0][2]) / 2
                        icy = (ib0[0][1] + ib0[0][3]) / 2
                        for pt in p0:
                            q = ("L" if pt[0] < icx else "R") + ("T" if pt[1] < icy else "B")
                            if q in quads:
                                quads[q] += 1
                        if len(p0) >= 4:
                            hull_area = float(cv2.contourArea(cv2.convexHull(p0.astype(np.int32))))
                        cov = round(hull_area / island_area, 3)
                        occ_cells = len(set(zip((p0[:, 0] / CELL).astype(int), (p0[:, 1] / CELL).astype(int))))
                        if cov < 0.2:
                            reasons.append("SPATIALLY_CLUSTERED")
                        rec["spatial"] = {"match_count": int(len(p0)),
                                          "island_area_px": int(island_area),
                                          "convex_hull_area_px": round(hull_area, 1),
                                          "hull_island_ratio": cov,
                                          "occupied_grid_cells": int(occ_cells),
                                          "quadrants": quads}
                        # 最终 fit（全部匹配）供补偿/邻域诊断
                        Mf, _ = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                                            ransacReprojThreshold=3.0)
                        perr = None
                        if Mf is not None:
                            pp = cv2.transform(p0.reshape(-1, 1, 2), Mf).reshape(-1, 2)
                            perr = np.linalg.norm(pp - p1, axis=1)
                        # 邻域诊断（相对 t0 target）
                        tt0 = [b for n, b in a0 if n in ("EXTENSION_TABLETOP", "TABLETOP")]
                        if perr is not None and len(tt0) == 1:
                            tb = tt0[0]
                            iw = max(1, ib0[0][2] - ib0[0][0])
                            ih = max(1, ib0[0][3] - ib0[0][1])
                            scale_diag = 0.5 * (iw + ih)
                            cx_t = (tb[0] + tb[2]) / 2
                            cy_t = (tb[1] + tb[3]) / 2
                            dists = np.linalg.norm(p0 - np.array([cx_t, cy_t]), axis=1) / max(1.0, scale_diag)
                            buckets = {"NEAR": dists < 0.15, "MID": (dists >= 0.15) & (dists < 0.45),
                                       "FAR": dists >= 0.45}
                            rec["target_neighborhood"] = {}
                            for bk, maskb in buckets.items():
                                if maskb.sum() == 0:
                                    continue
                                e = perr[maskb]
                                rec["target_neighborhood"][bk] = {
                                    "count": int(maskb.sum()),
                                    "median_px": round(float(np.median(e)), 3),
                                    "p90_px": round(float(np.percentile(e, 90)), 3)}
                            near = rec["target_neighborhood"].get("NEAR", {})
                            if resv["pair_state"] == "LOCAL_ANCHOR_VALIDATED" and near.get("count", 0) < 3:
                                reasons.append("TARGET_NEIGHBORHOOD_UNSUPPORTED")
                        # tail
                        if perr is not None:
                            rec["residual_tail"] = {"p90": round(float(np.percentile(perr, 90)), 2),
                                                    "max": round(float(np.max(perr)), 2),
                                                    "outlier_gt3": round(float((perr > 3).mean()), 3),
                                                    "outlier_gt5": round(float((perr > 5).mean()), 3),
                                                    "outlier_gt10": round(float((perr > 10).mean()), 3)}
                            if resv["pair_state"] == "LOCAL_ANCHOR_VALIDATED" and \
                                    (rec["residual_tail"]["outlier_gt10"] > 0.02 or rec["residual_tail"]["p90"] > 10):
                                rec["validated_tail"] = "VALIDATED_WITH_HEAVY_TAIL"
                        rec["anchor"] = resv
                        if not reasons and resv["pair_state"] == "LOCAL_ANCHOR_VALIDATED":
                            reasons.append("VALIDATED_CLEAN")
                        rec["reasons"] = reasons
                        # 补偿目标运动（仅 VALIDATED）
                        if resv["pair_state"] == "LOCAL_ANCHOR_VALIDATED" and Mf is not None:
                            Minv = cv2.invertAffineTransform(np.asarray(Mf, dtype=np.float64))
                            def pick(a_list):
                                ex = [b for n, b in a_list if n == "EXTENSION_TABLETOP"]
                                if len(ex) == 1:
                                    return ex[0]
                                tp = [b for n, b in a_list if n == "TABLETOP"]
                                if len(ex) == 0 and len(tp) == 1:
                                    return tp[0]
                                return None
                            tt0b, tt1b = pick(a0), pick(a1)
                            if tt0b is not None and tt1b is not None:
                                def relf(bb, ib):
                                    iw_ = max(1, ib[2] - ib[0]); ih_ = max(1, ib[3] - ib[1])
                                    return {"span_w": (bb[2] - bb[0]) / iw_,
                                            "cx_rel": ((bb[0] + bb[2]) / 2 - (ib[0] + ib[2]) / 2) / iw_,
                                            "right_off": (bb[2] - ib[2]) / iw_}
                                f0 = relf(tt0b, ib0[0])
                                corners = np.float32([[tt1b[0], tt1b[1]], [tt1b[2], tt1b[1]],
                                                      [tt1b[2], tt1b[3]], [tt1b[0], tt1b[3]]]).reshape(-1, 1, 2)
                                cc = cv2.transform(corners, Minv).reshape(-1, 2)
                                bb1c = [float(cc[:, 0].min()), float(cc[:, 1].min()),
                                        float(cc[:, 0].max()), float(cc[:, 1].max())]
                                fc1 = relf(bb1c, ib0[0])
                                deltas = {k: round(fc1[k] - f0[k], 4) for k in ("span_w", "cx_rel", "right_off")}
                                tgt_geom.append({"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                                                 "deltas_norm": deltas})
                                x1, y1, x2, y2 = [int(v) for v in tt0b]
                                if x2 - x1 >= 8 and y2 - y1 >= 8:
                                    cA = ga[y1:y2, x1:x2].astype(np.float32)
                                    x1b, y1b, x2b, y2b = [int(v) for v in tt1b]
                                    regB = gb[max(0, y1b):y2b, max(0, x1b):x2b]
                                    regB = cv2.resize(regB, (x2 - x1, y2 - y1)) if regB.shape != (y2 - y1, x2 - x1) else regB
                                    before = float(np.abs(cA - regB.astype(np.float32)).mean() / 40.0)
                                    wgb = cv2.warpAffine(gb, Minv, (w, h))
                                    after = float(np.abs(cA - wgb[y1:y2, x1:x2].astype(np.float32)).mean() / 40.0)
                                    tgt_px.append({"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                                                   "raw_before_anchor_comp": round(before, 4),
                                                   "after_anchor_comp": round(after, 4)})
            rows.append(rec)
        v.close()
        print("case done", mid, c["role"], flush=True)
    from collections import Counter
    states = Counter(r.get("anchor", {}).get("pair_state", "NO_ISLAND") for r in rows)
    # 与 v2.2 对比
    try:
        old = json.loads((OUT / "TREECUT_CAM01_V22_LOCAL_ANCHOR_VALIDATION.json").read_text(encoding="utf-8"))
        old_states = old.get("anchor_states", {})
    except Exception:
        old_states = {}
    corr = {"experiment": "CAM01_V22R1_METHOD_CORRECTION",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "defect": "CAM01_V22_DEFECT_HOLDOUT_COUNT_01",
            "bug": "two_fold_validate 用 len(vi)>=8；vi 为布尔数组 → len=全部 match 数",
            "fix": "int(vi.sum())>=CRIT_HOLDOUT_N",
            "contaminated_example": {"case": 2543, "pair": "1.202->1.717", "fold": "fit1val0",
                                     "holdout_n": 6, "v22_marked": "VALIDATED"}}
    (OUT / "TREECUT_CAM01_V22R1_METHOD_CORRECTION.json").write_text(
        json.dumps(corr, ensure_ascii=False, indent=1), encoding="utf-8")
    vdoc = {"experiment": "CAM01_V22R1_LOCAL_ANCHOR_VALIDATION",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "anchor_states": dict(states),
            "v22_anchor_states": old_states,
            "pairs": rows}
    (OUT / "TREECUT_CAM01_V22R1_LOCAL_ANCHOR_VALIDATION.json").write_text(
        json.dumps(vdoc, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V22R1_TARGET_RELATIVE_GEOMETRY.json").write_text(
        json.dumps({"rows": tgt_geom}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V22R1_TARGET_PIXEL_EDGE_MOTION.json").write_text(
        json.dumps({"rows": tgt_px}, ensure_ascii=False, indent=1), encoding="utf-8")
    # failure map
    fm = {"total": len(rows), "states": dict(states)}
    reason_cnt = Counter()
    for r in rows:
        for re_ in r.get("reasons", []):
            reason_cnt[re_] += 1
    fm["failure_reasons"] = dict(reason_cnt)
    fm["validated_tail"] = Counter(r.get("validated_tail") for r in rows
                                   if r.get("validated_tail")).most_common()
    sp = [r for r in rows if "spatial" in r]
    fm["spatial"] = {"with_spatial_info": len(sp),
                     "mean_hull_ratio": round(sum(r["spatial"]["hull_island_ratio"] for r in sp) / len(sp), 3) if sp else None,
                     "clustered_count": sum(1 for r in rows if "SPATIALLY_CLUSTERED" in r.get("reasons", []))}
    tn = [r for r in rows if "target_neighborhood" in r]
    fm["target_neighborhood_pairs"] = len(tn)
    fm["near_bucket_insufficient_on_validated"] = sum(
        1 for r in rows if r.get("anchor", {}).get("pair_state") == "LOCAL_ANCHOR_VALIDATED"
        and "TARGET_NEIGHBORHOOD_UNSUPPORTED" in r.get("reasons", []))
    (OUT / "TREECUT_CAM01_V22R1_ANCHOR_FAILURE_MAP.json").write_text(
        json.dumps(fm, ensure_ascii=False, indent=1), encoding="utf-8")
    print("V22R1 states:", dict(states))
    print("V22   states:", old_states)
    print("reasons:", dict(reason_cnt))
    print("target geom rows:", len(tgt_geom), "px rows:", len(tgt_px))
    con.close()


if __name__ == "__main__":
    main()
