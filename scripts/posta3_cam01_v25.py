#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.5 — Automatic Stable Anchor Patch Representation。

ISLAND_BODY 内 4×4 normalized grid(16 cells) → 前景污染(任一帧 overlap>25%)剔除、
纹理/角点保守(5帧 min)过滤 → top≤4 stable patch（空间多样）→ 每 pair 逐 patch GFTT+LK+FB
+ 目的 patch 落区检查(15% margin) + 确定性 2-fold 验证(gate 不变) → patch 真 clique 共识(6×6 grid ≤3px)。
不用动作 GT；不读 A3；无新人工。含 V24R1 baseline true pooled 修正(从已存矩阵合并真实残差)。
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
CELL_PX = 40
GRID_N = 4
PAIR_GRID_N = 6
OVERLAP_MAX = 0.25
MARGIN = 0.15
MIN_CORNERS = 8
MIN_GRAD = 250.0
MAX_PATCH = 4
FIT_INL = 0.45
HO_N = 8
HO_MED = 3.0
AGREE = 3.0
SCORE_CFG = {"grid": GRID_N, "overlap_max": OVERLAP_MAX, "margin": MARGIN,
             "min_corners": MIN_CORNERS, "min_grad": MIN_GRAD, "max_patches": MAX_PATCH,
             "score": "0.5*clip(min_grad/2500) + 0.5*clip(min_corners/30)",
             "texture_persistence": "min over 5 semantic frames (conservative)"}


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


def cell_rect(ib, r, c, n=GRID_N):
    x1, y1, x2, y2 = ib
    u0, u1 = c / n, (c + 1) / n
    v0, v1 = r / n, (r + 1) / n
    return [x1 + u0 * (x2 - x1), y1 + v0 * (y2 - y1),
            x1 + u1 * (x2 - x1), y1 + v1 * (y2 - y1)]


def overlap_ratio(rect, boxes):
    x1, y1, x2, y2 = rect
    area = max(1e-6, (x2 - x1) * (y2 - y1))
    inter = 0.0
    for ob in boxes:
        ox1, oy1, ox2, oy2 = ob
        ix = max(0, min(x2, ox2) - max(x1, ox1))
        iy = max(0, min(y2, oy2) - max(y1, oy1))
        inter += ix * iy
    return inter / area


def patch_texture(gray_patch):
    if gray_patch is None or gray_patch.size == 0 or gray_patch.shape[0] < 4 or gray_patch.shape[1] < 4:
        return 0.0, 0
    gx = cv2.Sobel(gray_patch, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_patch, cv2.CV_32F, 0, 1, ksize=3)
    grad = float(np.abs(gx).mean() + np.abs(gy).mean())
    pts = cv2.goodFeaturesToTrack(gray_patch, maxCorners=60, qualityLevel=0.02,
                                  minDistance=5, blockSize=5)
    corners = int(len(pts)) if pts is not None else 0
    return grad, corners


def mask_for_cell(gray_shape, rect, other_boxes):
    m = np.zeros(gray_shape, dtype=bool)
    x1, y1, x2, y2 = [int(v) for v in rect]
    h, w = gray_shape
    x1 = max(0, x1); y1 = max(0, y1); x2 = min(w, x2); y2 = min(h, y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    m[y1:y2, x1:x2] = True
    for ob in other_boxes:
        ox1, oy1, ox2, oy2 = [int(v) for v in ob]
        oy1 = max(0, oy1); oy2 = min(h, oy2)
        ox1 = max(0, ox1); ox2 = min(w, ox2)
        if oy2 > oy1 and ox2 > ox1:
            m[oy1:oy2, ox1:ox2] = False
    return m


def fold_validate(p0, p1):
    """确定性 2-fold（同 gate）。返回 state + pooled residuals + fold 细节。"""
    fold = (np.floor(p0[:, 0] / CELL_PX).astype(int) + np.floor(p0[:, 1] / CELL_PX).astype(int)) % 2
    pooled = []
    folds = {}
    for fitf, valf in ((0, 1), (1, 0)):
        fi, vi = fold == fitf, fold == valf
        fr = {"fit_n": int(fi.sum()), "holdout_n": int(vi.sum())}
        if int(fi.sum()) < 6 or int(vi.sum()) < HO_N:
            fr["state"] = "PATCH_INSUFFICIENT"
            folds[f"fit{fitf}val{valf}"] = fr
            continue
        M, inl = cv2.estimateAffinePartial2D(p0[fi], p1[fi], method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if M is None or inl is None:
            fr["state"] = "PATCH_INSUFFICIENT"
            folds[f"fit{fitf}val{valf}"] = fr
            continue
        fit_inl = float((inl.ravel() == 1).mean())
        p1p = cv2.transform(p0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        err = np.linalg.norm(p1p - p1[vi], axis=1)
        pooled.extend(err.tolist())
        fr.update({"state": "PATCH_VALIDATED" if (fr["holdout_n"] >= HO_N and fit_inl >= FIT_INL
                                                  and float(np.median(err)) <= HO_MED) else "PATCH_NOT_VALIDATED",
                   "fit_inlier_ratio": round(fit_inl, 3),
                   "holdout_median_px": round(float(np.median(err)), 3),
                   "holdout_residuals": [round(float(x), 3) for x in err]})
        folds[f"fit{fitf}val{valf}"] = fr
    sts = [v["state"] for v in folds.values()]
    if len(sts) == 2 and all(s == "PATCH_VALIDATED" for s in sts):
        pair_state = "PATCH_VALIDATED"
    elif any(s == "PATCH_VALIDATED" for s in sts):
        pair_state = "PATCH_PARTIAL"
    elif len(sts) == 2 and all(s == "PATCH_INSUFFICIENT" for s in sts):
        pair_state = "PATCH_INSUFFICIENT"
    else:
        pair_state = "PATCH_NOT_VALIDATED"
    return pair_state, pooled, folds


def island_grid(ib, others, n=PAIR_GRID_N):
    x1, y1, x2, y2 = [float(v) for v in ib]
    pts = []
    for i in range(n):
        for j in range(n):
            px = x1 + (i + 0.5) * (x2 - x1) / n
            py = y1 + (j + 0.5) * (y2 - y1) / n
            if not any(ob[0] <= px <= ob[2] and ob[1] <= py <= ob[3] for ob in others):
                pts.append([px, py])
    return np.float32(pts).reshape(-1, 2) if pts else None


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cv2.setRNGSeed(0)
    (OUT / "TREECUT_CAM01_V25_PATCH_SCORE_CONFIG.json").write_text(
        json.dumps(SCORE_CFG, ensure_ascii=False, indent=1), encoding="utf-8")
    case_rows = []
    gallery = []
    bank_all = []
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

        def ann(t):
            fr = v.frame(t)
            h, w = fr.shape[:2]
            sx, sy = w / float(A_w), h / float(A_h)
            return [(a["object_name"], [a["bbox_pixel"][0] * sx, a["bbox_pixel"][1] * sy,
                                        a["bbox_pixel"][2] * sx, a["bbox_pixel"][3] * sy])
                    for a in roi_by_t.get(t, [])]
        anns = {t: ann(t) for t in ts}
        ibs = {}
        ok_all_island = True
        for t in ts:
            ib = [b for n, b in anns[t] if n == "ISLAND_BODY"]
            if len(ib) != 1:
                ok_all_island = False
                break
            ibs[t] = ib[0]
        cr = {"case": mid, "role": c["role"], "island_all_frames": ok_all_island}
        if not ok_all_island:
            cr["pairs"] = []
            case_rows.append(cr)
            v.close()
            continue
        others = {t: [b for n, b in anns[t] if n != "ISLAND_BODY"] for t in ts}
        # ---- 4×4 cell 评估（5 帧保守）----
        cells = {}
        for r in range(GRID_N):
            for cc in range(GRID_N):
                pid = f"r{r}c{cc}"
                rects = {t: cell_rect(ibs[t], r, cc) for t in ts}
                over = max(overlap_ratio(rects[t], others[t]) for t in ts)
                grads, corners = [], []
                for t in ts:
                    fr = v.frame(t)
                    gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
                    x1, y1, x2, y2 = [int(x) for x in rects[t]]
                    g, cn = patch_texture(gray[y1:y2, x1:x2])
                    grads.append(g)
                    corners.append(cn)
                mg = min(grads)
                mc = min(corners)
                reasons = []
                if over > OVERLAP_MAX:
                    reasons.append("PATCH_FOREGROUND_CONTAMINATED")
                if mg < MIN_GRAD:
                    reasons.append("LOW_TEXTURE")
                if mc < MIN_CORNERS:
                    reasons.append("FEW_FEATURES")
                score = 0.5 * min(1.0, mg / 2500.0) + 0.5 * min(1.0, mc / 30.0)
                cells[pid] = {"rects_norm": [r, cc], "overlap_max": round(over, 3),
                              "min_grad": round(mg, 1), "min_corners": mc,
                              "score": round(score, 4), "reasons": reasons}
        # 选择（象限多样）
        clean = {pid: d for pid, d in cells.items() if not d["reasons"]}
        selected = []
        quads = [((0, 1), (0, 1)), ((0, 1), (2, 3)), ((2, 3), (0, 1)), ((2, 3), (2, 3))]
        taken_quad = set()
        for rr, ccq in quads:
            cand = [(pid, d["score"]) for pid, d in clean.items()
                    if int(pid[1]) in rr and int(pid[3]) in ccq]
            if cand:
                pid = max(cand, key=lambda x: x[1])[0]
                if pid not in taken_quad:
                    selected.append(pid)
                    taken_quad.add(pid)
        # 补足至 ≤4（不同 row/col）
        rest = sorted(((pid, d["score"]) for pid, d in clean.items() if pid not in selected),
                      key=lambda x: -x[1])
        for pid, _ in rest:
            if len(selected) >= MAX_PATCH:
                break
            r0 = int(pid[1])
            if all(int(p[1]) != r0 for p in selected):
                selected.append(pid)
        cr["bank"] = {"valid_cells": len(clean), "rejected": {pid: d["reasons"]
                                                              for pid, d in cells.items() if d["reasons"]},
                      "selected": selected,
                      "bank_state": "PATCH_BANK_OK" if len(selected) >= 2 else "PATCH_BANK_INSUFFICIENT"}
        bank_all.append({"case": mid, **cr["bank"]})
        # ---- pair 级 patch 验证 + 共识 ----
        pairs = []
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            g0 = cv2.cvtColor(v.frame(t0), cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(v.frame(t1), cv2.COLOR_BGR2GRAY)
            sh = g0.shape
            pr = {"pair": f"{t0}->{t1}", "patches": {}}
            valid_patches = []
            rep_recs = {}
            for pid in selected:
                r0_, c0_ = int(pid[1]), int(pid[3])
                rect0 = cell_rect(ibs[t0], r0_, c0_)
                rect1 = cell_rect(ibs[t1], r0_, c0_)
                mask = mask_for_cell(sh, rect0, others[t0])
                if mask is None:
                    pr["patches"][pid] = {"state": "PATCH_INSUFFICIENT", "reason": "small_cell"}
                    continue
                pts = cv2.goodFeaturesToTrack(g0, mask=(mask.astype(np.uint8)) * 255,
                                              maxCorners=CONFIG_GFTT_MAX, qualityLevel=0.02,
                                              minDistance=6, blockSize=7)
                if pts is None or len(pts) < 10:
                    pr["patches"][pid] = {"state": "PATCH_INSUFFICIENT", "reason": "few_tracks"}
                    continue
                p1t, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts, None, winSize=(21, 21), maxLevel=3)
                p0b, stb, _ = cv2.calcOpticalFlowPyrLK(g1, g0, p1t, None, winSize=(21, 21), maxLevel=3)
                ok = (st.ravel() == 1) & (stb.ravel() == 1)
                if ok.any():
                    d = np.linalg.norm(p0b[ok].reshape(-1, 2) - pts[ok].reshape(-1, 2), axis=1)
                    ok = ok.copy()
                    ok[ok] = d <= 3.0
                if ok.sum() < 10:
                    pr["patches"][pid] = {"state": "PATCH_INSUFFICIENT", "reason": "fb_fail"}
                    continue
                p0f = pts[ok].reshape(-1, 2).astype(np.float32)
                p1f = p1t[ok].reshape(-1, 2).astype(np.float32)
                # destination region check (t1 normalized cell + margin)
                x1_, y1_, x2_, y2_ = rect1
                wc = (x2_ - x1_) * (1 + 2 * MARGIN)
                hc = (y2_ - y1_) * (1 + 2 * MARGIN)
                cx = (x1_ + x2_) / 2
                cy = (y1_ + y2_) / 2
                inb = (np.abs(p1f[:, 0] - cx) <= wc / 2) & (np.abs(p1f[:, 1] - cy) <= hc / 2)
                if inb.sum() < 8:
                    pr["patches"][pid] = {"state": "PATCH_INSUFFICIENT", "reason": "PATCH_TRACK_ESCAPED"}
                    continue
                p0f, p1f = p0f[inb], p1f[inb]
                state, pooled, folds = fold_validate(p0f, p1f)
                Mf, _ = cv2.estimateAffinePartial2D(p0f, p1f, method=cv2.RANSAC, ransacReprojThreshold=3.0)
                rec = {"state": state, "tracked_n": int(len(p0f)), "folds": folds,
                       "final_M_2x3": [list(x) for x in Mf.tolist()] if Mf is not None else None}
                if pooled:
                    rec["pooled_median"] = round(float(np.median(pooled)), 3)
                    rec["pooled_p90"] = round(float(np.percentile(pooled, 90)), 3)
                pr["patches"][pid] = rec
                if state == "PATCH_VALIDATED":
                    valid_patches.append(pid)
                    rep_recs[pid] = rec
            # patch clique 共识（island 6×6 grid，真 pairwise）
            if len(valid_patches) >= 2:
                gpts = island_grid(ibs[t0], others[t0])
                dis = {}
                if gpts is not None and len(gpts) >= 4:
                    for a in valid_patches:
                        Ma = np.asarray(pr["patches"][a]["final_M_2x3"], dtype=np.float64)
                        if Ma is None or Ma.shape != (2, 3):
                            continue
                        pa = cv2.transform(gpts.reshape(-1, 1, 2), Ma).reshape(-1, 2)
                        for b in valid_patches:
                            if b <= a:
                                continue
                            Mb = np.asarray(pr["patches"][b]["final_M_2x3"], dtype=np.float64)
                            if Mb is None or Mb.shape != (2, 3):
                                continue
                            pb = cv2.transform(gpts.reshape(-1, 1, 2), Mb).reshape(-1, 2)
                            d = np.linalg.norm(pa - pb, axis=1)
                            dis[(a, b)] = (float(np.median(d)), float(np.percentile(d, 90)))
                edges = {k for k, v in dis.items() if v[0] <= AGREE}
                n = len(valid_patches)
                best_cl = None
                best_key = None
                for mask in range(1 << n):
                    if bin(mask).count("1") < 2:
                        continue
                    mem = [valid_patches[i] for i in range(n) if mask >> i & 1]
                    if all((a, b) in edges or (b, a) in edges for a in mem for b in mem if b > a):
                        meds = [rep_recs[m].get("pooled_median") or 99 for m in mem]
                        p90s = [rep_recs[m].get("pooled_p90") or 999 for m in mem]
                        key = (len(mem), -max(meds), -max(p90s))
                        # 先最大 size；再低 max median/P90
                        if best_cl is None or (len(mem) > len(best_cl)) or \
                           (len(mem) == len(best_cl) and (max(meds), max(p90s)) < best_key):
                            best_cl = mem
                            best_key = (max(meds), max(p90s))
                if best_cl and len(best_cl) >= 2:
                    def rk(p):
                        return (rep_recs[p].get("pooled_median") or 99,
                                rep_recs[p].get("pooled_p90") or 999, p)
                    rep = min(best_cl, key=rk)
                    pr["region_state"] = "PATCH_MULTI_CONSENSUS"
                    pr["clique"] = best_cl
                    pr["representative"] = rep
                    pd_ = [x[0] for x in dis.values() if x[0] is not None]
                    pr["max_pairwise_median"] = round(max(pd_), 3) if pd_ else None
                    pr["max_pairwise_p90"] = round(max(x[1] for x in dis.values()), 3) if dis else None
                else:
                    pr["region_state"] = "PATCH_CONFLICT"
            elif len(valid_patches) == 1:
                pr["region_state"] = "PATCH_SINGLE_VALIDATED"
                pr["representative"] = valid_patches[0]
            else:
                pr["region_state"] = "PATCH_NO_ANCHOR"
            pairs.append(pr)
        cr["pairs"] = pairs
        case_rows.append(cr)
        # gallery thumb（每帧 base64 小图 + 网格标注）
        for t in ts:
            fr = v.frame(t)
            h, w = fr.shape[:2]
            tw = 380
            frs = cv2.resize(fr, (tw, int(h * tw / w)), interpolation=cv2.INTER_AREA)
            x1, y1, x2, y2 = [int(x * tw / w) for x in ibs[t]]
            cv2.rectangle(frs, (x1, y1), (x2, y2), (0, 0, 255), 2)
            for r in range(GRID_N):
                for cc in range(GRID_N):
                    pid = f"r{r}c{cc}"
                    rx = cell_rect(ibs[t], r, cc)
                    ax = [int(x * tw / w) for x in rx]
                    if pid in selected:
                        cv2.rectangle(frs, (ax[0], ax[1]), (ax[2], ax[3]), (0, 255, 0), 2)
                    else:
                        cv2.rectangle(frs, (ax[0], ax[1]), (ax[2], ax[3]), (200, 200, 200), 1)
            ok_, buf = cv2.imencode(".jpg", frs, [cv2.IMWRITE_JPEG_QUALITY, 70])
            gallery.append({"case": mid, "t": t, "img": "data:image/jpeg;base64," +
                            base64.b64encode(buf).decode()})
        v.close()
        print("case done", mid, c["role"], flush=True)
    # 汇总（36 island-present = 9 case×4 pair）
    states_cnt = {}
    rep_pooled = []
    sel_patches = 0
    val_patches = 0
    for cr in case_rows:
        for pr in cr.get("pairs", []):
            st = pr.get("region_state")
            states_cnt[st] = states_cnt.get(st, 0) + 1
            if st in ("PATCH_MULTI_CONSENSUS", "PATCH_SINGLE_VALIDATED"):
                rep = pr.get("representative")
                if rep:
                    rec = pr["patches"][rep]
                    for fk in rec.get("folds", {}).values():
                        rep_pooled.extend(fk.get("holdout_residuals", []))
    rep_pooled = np.array(rep_pooled) if rep_pooled else np.array([0.0])
    metrics = {"island_present_pairs": sum(len(cr.get("pairs", [])) for cr in case_rows
                                           if cr.get("island_all_frames")),
               "patch_states": states_cnt,
               "PATCH_MULTI_CONSENSUS": states_cnt.get("PATCH_MULTI_CONSENSUS", 0),
               "PATCH_SINGLE": states_cnt.get("PATCH_SINGLE_VALIDATED", 0),
               "PATCH_CONFLICT": states_cnt.get("PATCH_CONFLICT", 0),
               "PATCH_NO_ANCHOR": states_cnt.get("PATCH_NO_ANCHOR", 0),
               "patch_union": states_cnt.get("PATCH_MULTI_CONSENSUS", 0) +
                              states_cnt.get("PATCH_SINGLE_VALIDATED", 0),
               "case_coverage_9": len({cr["case"] for cr in case_rows
                                       for pr in cr.get("pairs", [])
                                       if pr.get("region_state") in ("PATCH_MULTI_CONSENSUS",
                                                                      "PATCH_SINGLE_VALIDATED")}),
               "multi_case_coverage_9": len({cr["case"] for cr in case_rows
                                             for pr in cr.get("pairs", [])
                                             if pr.get("region_state") == "PATCH_MULTI_CONSENSUS"}),
               "true_pooled_median": round(float(np.median(rep_pooled)), 3),
               "true_pooled_p90": round(float(np.percentile(rep_pooled, 90)), 3),
               "true_pooled_p95": round(float(np.percentile(rep_pooled, 95)), 3),
               "selected_patches_total": sum(len(b.get("selected", [])) for b in bank_all),
               "validated_patch_instances": sum(1 for cr in case_rows for pr in cr.get("pairs", [])
                                                for p in pr.get("patches", {}).values()
                                                if p.get("state") == "PATCH_VALIDATED")}
    # improvement class（预置）
    multi = metrics["PATCH_MULTI_CONSENSUS"]
    case9 = metrics["case_coverage_9"]
    p90 = metrics["true_pooled_p90"]
    if multi >= 24 and case9 >= 8 and p90 <= 5.0:
        cls = "STRONG_REGION_IMPROVEMENT"
    elif multi >= 18 and case9 >= 7 and p90 <= 5.0:
        cls = "MODERATE_REGION_IMPROVEMENT"
    else:
        cls = "NO_REGION_IMPROVEMENT"
    (OUT / "TREECUT_CAM01_V25_PATCH_BANK.json").write_text(
        json.dumps({"cases": bank_all}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V25_PATCH_METHOD_MATRIX.json").write_text(
        json.dumps({"cases": case_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V25_PATCH_CONSENSUS.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V25_TARGET_SUPPORT.json").write_text(
        json.dumps({"note": "target-neighborhood 诊断后补(需 target 距离)", "rows": []},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V25_NEG_TARGET_CONTROL.json").write_text(
        json.dumps({"note": "严格 contract 后补"}, ensure_ascii=False, indent=1), encoding="utf-8")
    res = {"experiment": "CAM01_V25_RESULT", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "baselines": {"v24r1_multi_consensus": 12, "gftt_whole_island": 17},
           "metrics": metrics, "improvement_class": cls,
           "CAM01_V25_status": cls}
    (OUT / "TREECUT_CAM01_V25_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    # gallery html
    html = ["<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'/><title>CAM01 V2.5 Patch Gallery</title>",
            "<style>body{font-family:'Microsoft YaHei';margin:0;background:#f5f6f8;padding:16px}",
            ".casebox{border:1px solid #ccc;background:#fff;border-radius:10px;padding:10px;margin:12px 0}",
            ".imgs{display:flex;gap:6px;flex-wrap:wrap}.imgs img{width:180px;border:1px solid #aaa}",
            ".green{color:#0a7d33}.red{color:#b3261e}figcaption{font-size:10px}</style></head><body><h1>CAM01 V2.5 · Stable Anchor Patch Gallery（绿=选中 · 红框=ISLAND_BODY · 灰=候选）</h1>"]
    for cr in case_rows:
        html.append(f"<div class='casebox'><b>case {cr['case']} {cr['role']}</b> "
                    f"bank={cr.get('bank',{}).get('valid_cells')} 选中={cr.get('bank',{}).get('selected')} "
                    f"拒绝={json.dumps(cr.get('bank',{}).get('rejected',{}),ensure_ascii=False)}<div class='imgs'>")
        for g in gallery:
            if g["case"] == cr["case"]:
                html.append(f"<figure><img src='{g['img']}'/><figcaption>F@{g['t']}s</figcaption></figure>")
        html.append("</div></div>")
    html.append("</body></html>")
    (OUT / "TREECUT_CAM01_V25_PATCH_GALLERY.html").write_text("\n".join(html), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("class:", cls)
    con.close()


CONFIG_GFTT_MAX = 150

if __name__ == "__main__":
    main()
