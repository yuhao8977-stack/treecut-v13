#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.6 R1 — 真 canonical pair support + 真实 NEG target control。

修复 CAM01_V26_DEFECT_CANONICAL_CELL_01: t1 clean 曾误用 t0 像素矩形。
实现真 canonical: 每帧 ISLAND_BODY - DYNAMIC union → crop→NN 512×512 binary → clean_canon_t,
common = AND; 6×6 cell 在 canonical 平面定义; common_clean_px 取自 canonical。
source GFTT 仍在真实 t0 帧、按 canonical cell→t0 rect + t0 动态像素 mask 提取（不做 resize 后 LK）。
修复 CAM01_V26_DEFECT_NEG_CONTROL_PLACEHOLDER_02: 真实 pick_target 严格 contract 统计。
参数全沿用 V2.6 冻结值；不调参；不用动作 GT（role 仅诊断）。
"""
import base64
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
GRID = 6
CANON = 512
DYNAMIC = {"EXTENSION_TABLETOP", "PERSON", "HAND", "DRAWER", "CABINET_DOOR",
           "TRACK_SOCKET", "SOCKET_MODULE", "ROCK_TABLE_LEG", "ACRYLIC_TABLE_LEG",
           "EMBEDDED_APPLIANCE", "OTHER_MOVING_PART"}
CONFIG = {"grid": GRID, "canonical": CANON, "dynamic_labels": sorted(DYNAMIC),
          "min_common_clean_px": 800, "min_corners": 12, "max_candidates": 6,
          "fb_max_px": 3.0, "fit_inlier_min": 0.45, "holdout_min": 8,
          "holdout_median_max_px": 3.0, "agreement_px": 3.0,
          "gftt": {"maxCorners": 200, "qualityLevel": 0.02, "minDistance": 6},
          "lk": {"win": 21, "maxLevel": 3}}


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


def mask_canon(ib, dyn_boxes, canon=CANON):
    """ISLAND_BODY bbox → canonical 平面干净 mask（动态前景 union 挖除；NN 几何，非图像 resize）。"""
    m = np.ones((canon, canon), dtype=bool)
    x1, y1, x2, y2 = [float(v) for v in ib]
    W = max(1e-6, x2 - x1)
    H = max(1e-6, y2 - y1)
    for ob in dyn_boxes:
        u0 = (ob[0] - x1) / W
        v0 = (ob[1] - y1) / H
        u1 = (ob[2] - x1) / W
        v1 = (ob[3] - y1) / H
        a = int(max(0, u0 * canon))
        b = int(max(0, v0 * canon))
        c = int(min(canon, u1 * canon))
        d = int(min(canon, v1 * canon))
        if c > a and d > b:
            m[b:d, a:c] = False
    return m


def canon_cell_px(mask, r, c, grid=GRID, canon=CANON):
    h = canon // grid
    w = canon // grid
    return int(mask[r * h:(r + 1) * h, c * w:(c + 1) * w].sum())


def canon_cell_rect(r, c, grid=GRID, canon=CANON):
    h = canon // grid
    w = canon // grid
    return [c * w, r * h, (c + 1) * w, (r + 1) * h]


def canon_to_frame_rect(ib, r, c, grid=GRID):
    x1, y1, x2, y2 = [float(v) for v in ib]
    u0, u1 = c / grid, (c + 1) / grid
    v0, v1 = r / grid, (r + 1) / grid
    return [x1 + u0 * (x2 - x1), y1 + v0 * (y2 - y1),
            x1 + u1 * (x2 - x1), y1 + v1 * (y2 - y1)]


def fold_validate(p0, p1):
    fold = (np.floor(p0[:, 0] / 40).astype(int) + np.floor(p0[:, 1] / 40).astype(int)) % 2
    pooled = []
    folds = {}
    for fitf, valf in ((0, 1), (1, 0)):
        fi, vi = fold == fitf, fold == valf
        fr = {"fit_n": int(fi.sum()), "holdout_n": int(vi.sum())}
        if int(fi.sum()) < 6 or int(vi.sum()) < 8:
            fr["state"] = "NOT_VALIDATED"
            folds[f"fit{fitf}val{valf}"] = fr
            continue
        M, inl = cv2.estimateAffinePartial2D(p0[fi], p1[fi], method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if M is None or inl is None:
            fr["state"] = "NOT_VALIDATED"
            folds[f"fit{fitf}val{valf}"] = fr
            continue
        fit_inl = float((inl.ravel() == 1).mean())
        p1p = cv2.transform(p0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        err = np.linalg.norm(p1p - p1[vi], axis=1)
        pooled.extend(err.tolist())
        fr.update({"state": "VALIDATED" if (fr["holdout_n"] >= 8 and fit_inl >= 0.45
                                            and float(np.median(err)) <= 3.0) else "NOT_VALIDATED",
                   "fit_inlier_ratio": round(fit_inl, 3),
                   "holdout_median_px": round(float(np.median(err)), 3),
                   "holdout_residuals": [round(float(x), 3) for x in err]})
        folds[f"fit{fitf}val{valf}"] = fr
    sts = [v["state"] for v in folds.values()]
    if len(sts) == 2 and all(s == "VALIDATED" for s in sts):
        ps = "REGION_VALIDATED"
    elif any(s == "VALIDATED" for s in sts):
        ps = "REGION_PARTIAL"
    else:
        ps = "REGION_NOT_VALIDATED"
    return ps, pooled, folds


def island_grid(ib, others, n=GRID):
    x1, y1, x2, y2 = [float(v) for v in ib]
    pts = []
    for i in range(n):
        for j in range(n):
            px = x1 + (i + 0.5) * (x2 - x1) / n
            py = y1 + (j + 0.5) * (y2 - y1) / n
            if not any(ob[0] <= px <= ob[2] and ob[1] <= py <= ob[3] for ob in others):
                pts.append([px, py])
    return np.float32(pts).reshape(-1, 2) if pts else None


def pick_target_boxes(boxes):
    """box list [(name,bbox)] → (bbox|None, state)。EXTENSION_TABLETOP 优先。"""
    ex = [b for n, b in boxes if n == "EXTENSION_TABLETOP"]
    if len(ex) == 1:
        return ex[0], "VALID"
    tp = [b for n, b in boxes if n == "TABLETOP"]
    if len(ex) == 0 and len(tp) == 1:
        return tp[0], "TABLETOP_FALLBACK"
    return None, "TARGET_INVALID"


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cv2.setRNGSeed(0)
    corr = {"experiment": "CAM01_V26R1_METHOD_CORRECTION",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "CAM01_V26_DEFECT_CANONICAL_CELL_01": "t1 clean 曾用 t0 像素矩形 → 现真 canonical 512 平面 + AND",
            "CAM01_V26_DEFECT_NEG_CONTROL_PLACEHOLDER_02": "NEG control 占位 → 真实 pick_target 严格 contract",
            "v26_superseded": "V26_RESULT_SUPERSEDED_PENDING_R1"}
    (OUT / "TREECUT_CAM01_V26R1_METHOD_CORRECTION.json").write_text(
        json.dumps(corr, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V26_CONFIG.json").write_text(
        json.dumps(CONFIG, ensure_ascii=False, indent=1), encoding="utf-8")
    pair_rows = []
    gallery = []
    for c in man["cases"]:
        mid = c["media_id"]
        row = cur.execute("select source_id, relative_path from media_files where id=?", (mid,)).fetchone()
        v = Video(ROOTS.get(row[0]) + "\\" + row[1])
        if not v.ok:
            continue
        A_w = c["frames"][0]["width"]
        A_h = c["frames"][0]["height"]
        ts = [f["t_s"] for f in c["frames"]]
        rbt = {}
        for a in roi:
            if a["media_id"] == mid:
                rbt.setdefault(a["frame_timestamp"], []).append(a)
        for t in ts:
            v.frame(t)

        def ann(t):
            fr = v.frame(t)
            h, w = fr.shape[:2]
            sx, sy = w / float(A_w), h / float(A_h)
            return [(a["object_name"], [a["bbox_pixel"][0] * sx, a["bbox_pixel"][1] * sy,
                                        a["bbox_pixel"][2] * sx, a["bbox_pixel"][3] * sy])
                    for a in rbt.get(t, [])]
        anns = {t: ann(t) for t in ts}
        ibs = {}
        island_ok = True
        for t in ts:
            ib = [b for n, b in anns[t] if n == "ISLAND_BODY"]
            if len(ib) != 1:
                island_ok = False
                break
            ibs[t] = ib[0]
        if not island_ok:
            v.close()
            continue
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            ib0, ib1 = ibs[t0], ibs[t1]
            f0, f1 = v.frame(t0), v.frame(t1)
            g0 = cv2.cvtColor(f0, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
            sh = g0.shape
            o0all = anns[t0]
            o1all = anns[t1]
            dyn0 = [b for n, b in o0all if n in DYNAMIC]
            dyn1 = [b for n, b in o1all if n in DYNAMIC]
            # canonical clean（真实现）
            mc0 = mask_canon(ib0, dyn0)
            mc1 = mask_canon(ib1, dyn1)
            common = mc0 & mc1
            # target contract（真实，双端独立）
            tt0, st0 = pick_target_boxes(o0all)
            tt1, st1 = pick_target_boxes(o1all)
            t0v = st0 in ("VALID", "TABLETOP_FALLBACK")
            t1v = st1 in ("VALID", "TABLETOP_FALLBACK")
            # 候选 cell（canonical common px + 真实帧 GFTT）
            cands = []
            cells_info = {}
            for r in range(GRID):
                for cc in range(GRID):
                    cid = f"r{r}c{cc}"
                    cpx = canon_cell_px(common, r, cc)
                    cells_info[cid] = {"common_clean_px": cpx}
                    if cpx < CONFIG["min_common_clean_px"]:
                        continue
                    # 映回 t0 真实帧 + t0 动态 mask 挖除
                    rr0 = canon_to_frame_rect(ib0, r, cc)
                    x1, y1, x2, y2 = [int(x) for x in rr0]
                    x1 = max(0, x1); y1 = max(0, y1)
                    x2 = min(sh[1], x2); y2 = min(sh[0], y2)
                    if x2 - x1 < 16 or y2 - y1 < 16:
                        continue
                    # t0 动态像素 mask（真帧）→ 挖除
                    mfull = np.ones(sh, dtype=np.uint8)
                    for ob in dyn0:
                        ox1, oy1, ox2, oy2 = [int(v) for v in ob]
                        oy1 = max(0, oy1); oy2 = min(sh[0], oy2)
                        ox1 = max(0, ox1); ox2 = min(sh[1], ox2)
                        if ox2 > ox1 and oy2 > oy1:
                            mfull[oy1:oy2, ox1:ox2] = 0
                    cellmask = mfull[y1:y2, x1:x2]
                    pts = cv2.goodFeaturesToTrack(g0[y1:y2, x1:x2], mask=cellmask,
                                                  maxCorners=CONFIG["gftt"]["maxCorners"],
                                                  qualityLevel=CONFIG["gftt"]["qualityLevel"],
                                                  minDistance=CONFIG["gftt"]["minDistance"], blockSize=7)
                    ncor = int(len(pts)) if pts is not None else 0
                    cells_info[cid]["corners_t0"] = ncor
                    if ncor >= CONFIG["min_corners"]:
                        cands.append((cid, ncor, cpx))
            cands.sort(key=lambda x: (-x[1], -x[2]))
            cands = cands[:CONFIG["max_candidates"]]
            pr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                  "target_t0": st0, "target_t1": st1,
                  "target_t0_valid": t0v, "target_t1_valid": t1v,
                  "common_clean_availability": len(cands) > 0,
                  "candidate_count": len(cands),
                  "canonical_common_clean_total": int(common.sum()),
                  "cells": cells_info, "regions": {}}
            valid = []
            vrecs = {}
            for cid, _, _ in cands:
                r_, cc_ = int(cid[1]), int(cid[3])
                rr0 = canon_to_frame_rect(ib0, r_, cc_)
                x1, y1, x2, y2 = [int(x) for x in rr0]
                x1 = max(0, x1); y1 = max(0, y1)
                x2 = min(sh[1], x2); y2 = min(sh[0], y2)
                mfull = np.ones(sh, dtype=np.uint8)
                for ob in dyn0:
                    ox1, oy1, ox2, oy2 = [int(v) for v in ob]
                    oy1 = max(0, oy1); oy2 = min(sh[0], oy2)
                    ox1 = max(0, ox1); ox2 = min(sh[1], ox2)
                    if ox2 > ox1 and oy2 > oy1:
                        mfull[oy1:oy2, ox1:ox2] = 0
                pts = cv2.goodFeaturesToTrack(g0[y1:y2, x1:x2], mask=mfull[y1:y2, x1:x2],
                                              maxCorners=CONFIG["gftt"]["maxCorners"],
                                              qualityLevel=CONFIG["gftt"]["qualityLevel"],
                                              minDistance=CONFIG["gftt"]["minDistance"], blockSize=7)
                if pts is None or len(pts) < 12:
                    pr["regions"][cid] = {"state": "REGION_INSUFFICIENT", "reason": "few_source"}
                    continue
                pl = pts.reshape(-1, 2).copy()
                pl[:, 0] += x1
                pl[:, 1] += y1
                ptsg = pl.reshape(-1, 1, 2).astype(np.float32)
                p1t, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, ptsg, None,
                                                      winSize=(CONFIG["lk"]["win"], CONFIG["lk"]["win"]),
                                                      maxLevel=CONFIG["lk"]["maxLevel"])
                if p1t is None:
                    pr["regions"][cid] = {"state": "REGION_INSUFFICIENT", "reason": "lk_fail"}
                    continue
                p1g = p1t.reshape(-1, 2)
                p0b, stb, _ = cv2.calcOpticalFlowPyrLK(g1, g0, p1t, None,
                                                       winSize=(CONFIG["lk"]["win"], CONFIG["lk"]["win"]),
                                                       maxLevel=CONFIG["lk"]["maxLevel"])
                okf = (st.ravel() == 1) & (stb.ravel() == 1)
                if okf.any():
                    d = np.linalg.norm(p0b[okf].reshape(-1, 2) - pl[okf], axis=1)
                    okf = okf.copy()
                    okf[okf] = d <= CONFIG["fb_max_px"]
                if okf.sum() < 12:
                    pr["regions"][cid] = {"state": "REGION_INSUFFICIENT", "reason": "fb_fail"}
                    continue
                pf0 = pl[okf].astype(np.float32)
                pf1 = p1g[okf].astype(np.float32)
                ibx1, iby1, ibx2, iby2 = ib1
                dest_ok = (pf1[:, 0] >= ibx1) & (pf1[:, 0] <= ibx2) & \
                          (pf1[:, 1] >= iby1) & (pf1[:, 1] <= iby2)
                if dest_ok.sum() < 8:
                    pr["regions"][cid] = {"state": "REGION_INSUFFICIENT", "reason": "dest_out"}
                    continue
                pf0, pf1 = pf0[dest_ok], pf1[dest_ok]
                mfg1 = np.zeros(sh, dtype=bool)
                for ob in dyn1:
                    ox1, oy1, ox2, oy2 = [int(v) for v in ob]
                    oy1 = max(0, oy1); oy2 = min(sh[0], oy2)
                    ox1 = max(0, ox1); ox2 = min(sh[1], ox2)
                    if ox2 > ox1 and oy2 > oy1:
                        mfg1[oy1:oy2, ox1:ox2] = True
                fi_ = pf1[:, 0].astype(int)
                fj_ = pf1[:, 1].astype(int)
                if mfg1[fj_, fi_].sum() >= 4:
                    pr["regions"][cid] = {"state": "REGION_INSUFFICIENT", "reason": "dest_in_fg"}
                    continue
                state, pooled, folds = fold_validate(pf0, pf1)
                Mf, _ = cv2.estimateAffinePartial2D(pf0, pf1, method=cv2.RANSAC, ransacReprojThreshold=3.0)
                rec = {"state": state, "tracked_n": int(len(pf0)), "folds": folds,
                       "final_M_2x3": [list(x) for x in Mf.tolist()] if Mf is not None else None,
                       "source_cell": cid}
                if pooled:
                    rec["pooled_median"] = round(float(np.median(pooled)), 3)
                    rec["pooled_p90"] = round(float(np.percentile(pooled, 90)), 3)
                pr["regions"][cid] = rec
                if state == "REGION_VALIDATED":
                    valid.append(cid)
                    vrecs[cid] = rec
            # clique
            if len(valid) >= 2:
                others0b = [b for n, b in o0all if n != "ISLAND_BODY"]
                gpts = island_grid(ib0, others0b)
                dis = {}
                if gpts is not None and len(gpts) >= 4:
                    for a in valid:
                        Ma = np.asarray(vrecs[a]["final_M_2x3"], dtype=np.float64)
                        pa = cv2.transform(gpts.reshape(-1, 1, 2), Ma).reshape(-1, 2)
                        for b in valid:
                            if b <= a:
                                continue
                            Mb = np.asarray(vrecs[b]["final_M_2x3"], dtype=np.float64)
                            pb = cv2.transform(gpts.reshape(-1, 1, 2), Mb).reshape(-1, 2)
                            d = np.linalg.norm(pa - pb, axis=1)
                            dis[(a, b)] = (float(np.median(d)), float(np.percentile(d, 90)))
                edges = {k for k, val in dis.items() if val[0] <= 3.0}
                n = len(valid)
                best_cl = None
                best_key = None
                for mask in range(1 << n):
                    if bin(mask).count("1") < 2:
                        continue
                    mem = [valid[i] for i in range(n) if mask >> i & 1]
                    if all((a, b) in edges or (b, a) in edges for a in mem for b in mem if b > a):
                        meds = [vrecs[m].get("pooled_median") or 99 for m in mem]
                        p90s = [vrecs[m].get("pooled_p90") or 999 for m in mem]
                        if best_cl is None or len(mem) > len(best_cl) or \
                           (len(mem) == len(best_cl) and (max(meds), max(p90s)) < best_key):
                            best_cl = mem
                            best_key = (max(meds), max(p90s))
                if best_cl and len(best_cl) >= 2:
                    rep = min(best_cl, key=lambda p: (vrecs[p].get("pooled_median") or 99,
                                                      vrecs[p].get("pooled_p90") or 999, p))
                    pr["region_state"] = "PAIR_REGION_MULTI_CONSENSUS"
                    pr["clique"] = best_cl
                    pr["representative"] = rep
                else:
                    pr["region_state"] = "PAIR_REGION_CONFLICT"
            elif len(valid) == 1:
                pr["region_state"] = "PAIR_REGION_SINGLE"
                pr["representative"] = valid[0]
            else:
                pr["region_state"] = "PAIR_REGION_NO_ANCHOR"
            pair_rows.append(pr)
        # gallery pair t0 帧 + t1 帧（岛台/动态框/候选标色）
        for idx, t in enumerate(ts):
            fr = v.frame(t)
            h, w = fr.shape[:2]
            tw = 300
            frs = cv2.resize(fr, (tw, int(h * tw / w)), interpolation=cv2.INTER_AREA)
            sc = tw / w
            ib = ibs[t]
            cv2.rectangle(frs, (int(ib[0] * sc), int(ib[1] * sc)),
                          (int(ib[2] * sc), int(ib[3] * sc)), (0, 0, 255), 2)
            gallery.append({"case": mid, "t": t, "img": "data:image/jpeg;base64," +
                            base64.b64encode(cv2.imencode(".jpg", frs,
                                                          [cv2.IMWRITE_JPEG_QUALITY, 65])[1]).decode()})
        v.close()
        print("case done", mid, c["role"], flush=True)
    from collections import Counter
    cnt = Counter(pr.get("region_state") for pr in pair_rows)
    cand_total = sum(pr.get("candidate_count", 0) for pr in pair_rows)
    avail = sum(1 for pr in pair_rows if pr.get("common_clean_availability"))
    val_inst = sum(1 for pr in pair_rows for rr in pr.get("regions", {}).values()
                   if rr.get("state") == "REGION_VALIDATED")
    pooled_all = []
    for pr in pair_rows:
        rep = pr.get("representative")
        if rep and rep in pr.get("regions", {}):
            for fk in pr["regions"][rep].get("folds", {}).values():
                pooled_all.extend(fk.get("holdout_residuals", []))
    pa = np.array(pooled_all) if pooled_all else np.array([])
    metrics = {"island_present_pairs": len(pair_rows),
               "v26_old_common_clean_availability": 34,
               "r1_canonical_common_clean_availability": avail,
               "avg_candidate_regions_per_pair": round(cand_total / max(1, len(pair_rows)), 2),
               "validated_region_instances": val_inst,
               "PAIR_REGION_MULTI": cnt.get("PAIR_REGION_MULTI_CONSENSUS", 0),
               "PAIR_REGION_SINGLE": cnt.get("PAIR_REGION_SINGLE", 0),
               "PAIR_REGION_CONFLICT": cnt.get("PAIR_REGION_CONFLICT", 0),
               "PAIR_REGION_NO_ANCHOR": cnt.get("PAIR_REGION_NO_ANCHOR", 0),
               "region_union": cnt.get("PAIR_REGION_MULTI_CONSENSUS", 0) + cnt.get("PAIR_REGION_SINGLE", 0),
               "case_coverage_9": len({pr["case"] for pr in pair_rows
                                       if pr.get("region_state") in ("PAIR_REGION_MULTI_CONSENSUS",
                                                                     "PAIR_REGION_SINGLE")}),
               "multi_case_coverage_9": len({pr["case"] for pr in pair_rows
                                             if pr.get("region_state") == "PAIR_REGION_MULTI_CONSENSUS"}),
               "pooled_median": round(float(np.median(pa)), 3) if len(pa) else None,
               "pooled_p90": round(float(np.percentile(pa, 90)), 3) if len(pa) else None,
               "pooled_p95": round(float(np.percentile(pa, 95)), 3) if len(pa) else None,
               "states": dict(cnt)}
    multi = metrics["PAIR_REGION_MULTI"]
    union = metrics["region_union"]
    case9 = metrics["case_coverage_9"]
    p90 = metrics["pooled_p90"]
    if multi >= 24 and case9 >= 8 and (p90 is not None and p90 <= 5.0):
        cls = "STRONG_REGION_IMPROVEMENT"
    elif multi >= 18 and case9 >= 7 and (p90 is not None and p90 <= 5.0):
        cls = "MODERATE_REGION_IMPROVEMENT"
    elif multi < 18 and union >= 20 and case9 >= 7:
        cls = "PARTIAL_REGION_SIGNAL"
    else:
        cls = "FAIL"
    closed = cls == "FAIL" and union < 20
    res = {"experiment": "CAM01_V26R1_RESULT", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "baselines": {"v24r1_multi": 12, "gftt_whole": 17, "v25_case_patch": 0, "v26_pair": 7},
           "metrics": metrics, "improvement_class": cls,
           "PATCH_GRID_ROUTE_CLOSED": closed,
           "NEXT_BLOCKER": ("STRUCTURAL_OBJECT_ANCHOR_V1" if closed else None),
           "status": cls}
    (OUT / "TREECUT_CAM01_V26R1_CANONICAL_SUPPORT.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V26R1_REGION_METHOD_MATRIX.json").write_text(
        json.dumps({"pairs": pair_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V26R1_REGION_CONSENSUS.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V26R1_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    # NEG control（真实）
    neg = {"MULTI": [], "SINGLE": []}
    for pr in pair_rows:
        if pr["role"] != "NEG":
            continue
        if not (pr.get("target_t0_valid") and pr.get("target_t1_valid")):
            continue
        st = pr.get("region_state")
        if st == "PAIR_REGION_MULTI_CONSENSUS":
            neg["MULTI"].append({"case": pr["case"], "pair": pr["pair"]})
        elif st == "PAIR_REGION_SINGLE":
            neg["SINGLE"].append({"case": pr["case"], "pair": pr["pair"]})
    neg_out = {"MULTI_pairs": neg["MULTI"], "MULTI_cases": len({x["case"] for x in neg["MULTI"]}),
               "SINGLE_pairs": neg["SINGLE"], "SINGLE_cases": len({x["case"] for x in neg["SINGLE"]}),
               "computed": True}
    (OUT / "TREECUT_CAM01_V26R1_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_out, ensure_ascii=False, indent=1), encoding="utf-8")
    html = ["<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'/><title>V2.6R1 Pair Gallery</title>",
            "<style>img{width:190px;border:1px solid #aaa;margin:2px}body{font-family:'Microsoft YaHei'}</style></head><body>",
            "<h1>CAM01 V2.6R1 · 真 canonical pair support（红框=ISLAND_BODY；帧按 t 序两两成对）</h1>"]
    for g in gallery:
        html.append(f"<img src='{g['img']}' title='case {g['case']} @ {g['t']}s'/>")
    html.append("</body></html>")
    (OUT / "TREECUT_CAM01_V26R1_PAIR_REGION_GALLERY.html").write_text("\n".join(html), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("class:", cls, "| route closed:", closed)
    for mid in (1641, 10000, 2543, 21674):
        sub = [pr for pr in pair_rows if pr["case"] == mid]
        print(mid, [(pr["pair"], pr.get("region_state"), pr.get("candidate_count")) for pr in sub])
    print("NEG ctrl:", json.dumps(neg_out, ensure_ascii=False))
    con.close()


if __name__ == "__main__":
    main()
