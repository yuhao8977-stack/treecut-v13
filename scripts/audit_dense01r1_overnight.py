# -*- coding: utf-8 -*-
"""DENSE01R1 OVERNIGHT INDEPENDENT REPLAY RUNNER (audit-only).

任务 §24/§25/§6/§10/§26 的执行器：不复用 production pipeline 的任何算法 helper，
从 manifest + HUMAN_ROI + 源视频独立复现 36-pair 全链路（特征→valid-domain MNN→
subtoken→LK forward+backward FB→fold→RANSAC holdout），落盘 raw records 供
overnight 分析脚本独立重算全部指标。

role-blind：本脚本不读取 case role，不按 POS/NEG 分支；只输出 media_id/pair。
禁止修改 production 文件。
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
PROD_MATRIX = OUT / "TREECUT_CAM01_DENSE01R1_MATCH_MATRIX.json"
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
# 冻结配置（与 TREECUT_CAM01_DENSE01R1_CONFIG.json 逐字一致，来源注释于 CONFIG json）
WMAX = 960
MODEL_IN = 518
PATCH = 14
GRID = MODEL_IN // PATCH
DYNAMIC = {"EXTENSION_TABLETOP", "PERSON", "HAND", "DRAWER", "CABINET_DOOR",
           "TRACK_SOCKET", "SOCKET_MODULE", "ROCK_TABLE_LEG", "ACRYLIC_TABLE_LEG",
           "EMBEDDED_APPLIANCE", "OTHER_MOVING_PART"}
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
CFG = {"model": "dinov2_vits14_reg", "input": 518, "stride": 14,
       "top_k": 256, "min_mnn": 12, "fit_min": 8, "inlier_min": 0.45,
       "holdout_min": 8, "holdout_med_max": 3.0, "holdout_p90_max": 8.0,
       "bins_min": 4, "quads_min": 2, "agree_px": 3.0, "T": 1.0,
       "lk": {"win": 21, "maxLevel": 3, "fb_max": 3.0}}


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


def norm_rgb01(x):
    return (x - MEAN) / STD


def prep_rgb(ib, bgr_raw, shape):
    """crop(ISLAND_BODY, raw 960 平面) → 518 letterbox RGB 归一化。独立复现。"""
    x1, y1, x2, y2 = [int(v) for v in ib]
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(shape[1], x2); y2 = min(shape[0], y2)
    crop = bgr_raw[y1:y2, x1:x2]
    h, w = crop.shape[:2]
    scale = min(MODEL_IN / w, MODEL_IN / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    padx = (MODEL_IN - nw) // 2
    pady = (MODEL_IN - nh) // 2
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    canvas = np.broadcast_to(MEAN, (MODEL_IN, MODEL_IN, 3)).copy()
    canvas[pady:pady + nh, padx:padx + nw] = rgb
    n = norm_rgb01(canvas)
    t = torch.from_numpy(n.transpose(2, 0, 1))[None]
    return t, scale, padx, pady, (x1, y1)


def content_valid_mask(nw, nh, padx, pady, grid=GRID, patch=PATCH):
    """patch 整体(四边)位于内容区才算 content-valid。独立复现。"""
    m = np.zeros((grid, grid), dtype=bool)
    for r in range(grid):
        for c in range(grid):
            x0 = c * patch
            y0 = r * patch
            if (x0 >= padx and x0 + patch <= padx + nw and
                    y0 >= pady and y0 + patch <= pady + nh):
                m[r, c] = True
    return m


def dynamic_token_mask(ib, dyn_boxes, scale, padx, pady, ox, oy, dil=1):
    """token 中心落入动态对象 bbox（raw 平面）→ 排除（膨胀 dil）。独立复现。"""
    m = np.zeros((GRID, GRID), dtype=bool)
    for r in range(GRID):
        for c in range(GRID):
            cx = (c + 0.5) * PATCH
            cy = (r + 0.5) * PATCH
            rx = (cx - padx) / scale + ox
            ry = (cy - pady) / scale + oy
            for ob in dyn_boxes:
                if ob[0] <= rx <= ob[2] and ob[1] <= ry <= ob[3]:
                    m[r, c] = True
                    break
    md = m.copy()
    for r in range(GRID):
        for c in range(GRID):
            if m[r, c]:
                for dr in range(-dil, dil + 1):
                    for dc in range(-dil, dil + 1):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < GRID and 0 <= cc < GRID:
                            md[rr, cc] = True
    return md


def valid_mnn_audit(f0, f1, v0, v1):
    """valid-domain MNN（独立实现，不复用 production）。返回 (i0,j1,sim) 列表。"""
    idx0 = np.nonzero(v0)[0]
    idx1 = np.nonzero(v1)[0]
    if len(idx0) < 1 or len(idx1) < 1:
        return []
    sim = f0[idx0] @ f1[idx1].T
    nn01 = sim.argmax(axis=1)
    nn10 = sim.argmax(axis=0)
    out = []
    for k, i in enumerate(idx0):
        jj = int(nn01[k])
        if nn10[jj] == k:
            out.append((int(i), int(idx1[jj]), float(sim[k, jj])))
    return out


def subtoken_refine_softmax(f1feat_flat, i0, j1, sim, T=1.0):
    r1, c1 = divmod(j1, GRID)
    mx = float(sim[i0, j1])
    ws, pos = [], []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            rr, cc = r1 + dr, c1 + dc
            if 0 <= rr < GRID and 0 <= cc < GRID:
                s = float(sim[i0, rr * GRID + cc])
                ws.append(float(np.exp((s - mx) / T)))
                pos.append(((cc + 0.5) * PATCH, (rr + 0.5) * PATCH))
    ws = np.array(ws)
    ws = ws / ws.sum()
    pos = np.array(pos)
    return float((ws * pos[:, 0]).sum()), float((ws * pos[:, 1]).sum())


def model_to_raw(p, scale, padx, pady, ox, oy):
    return [(p[0] - padx) / scale + ox, (p[1] - pady) / scale + oy]


def lk_refine_fb(g0, g1, p0, p1_init, win=21, max_level=3):
    """forward LK(init=p1_sub) + backward LK(init=forward result) → FB 误差。
    返回 (p1, fwd_ok, p0_back, bwd_ok, fb_px)。audit 独立实现。"""
    p0a = np.float32(p0).reshape(-1, 1, 2)
    p1a = np.float32(p1_init).reshape(-1, 1, 2)
    p1n, st, _ = cv2.calcOpticalFlowPyrLK(
        g0, g1, p0a, p1a, winSize=(win, win), maxLevel=max_level,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
    fwd_ok = bool(p1n is not None and st is not None and st[0, 0] == 1)
    p1 = (float(p1n[0, 0, 0]), float(p1n[0, 0, 1])) if fwd_ok else None
    fb_px = None
    bwd_ok = False
    p0b = None
    if fwd_ok:
        p1b = np.float32([[p1[0], p1[1]]]).reshape(-1, 1, 2)
        p0n, stb, _ = cv2.calcOpticalFlowPyrLK(
            g1, g0, p1b, p0a, winSize=(win, win), maxLevel=max_level,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
            flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
        if p0n is not None and stb is not None and stb[0, 0] == 1:
            bwd_ok = True
            p0b = (float(p0n[0, 0, 0]), float(p0n[0, 0, 1]))
            fb_px = float(np.hypot(p0b[0] - p0[0], p0b[1] - p0[1]))
    return p1, fwd_ok, p0b, bwd_ok, fb_px


def coarse_ransac_thr(s0, s1):
    return max(PATCH / s0, PATCH / s1)


def true_pooled(arrs):
    a = np.concatenate([np.asarray(x, dtype=np.float64) for x in arrs if len(x)]) if arrs else np.array([])
    if len(a) == 0:
        return None, None, None
    return (round(float(np.median(a)), 3), round(float(np.percentile(a, 90)), 3),
            round(float(np.percentile(a, 95)), 3))


def fit_eval_audit(P0, P1, fold, model, thr, fit_min=8, hold_min=8,
                   inlier_min=0.45, med_max=3.0, p90_max=8.0):
    """确定性 spatial 2-fold holdout，逐 fold 返回明细。独立复现。"""
    res = {}
    for fidx in (0, 1):
        fi = fold == fidx
        vi = ~fi
        fr = {"fit": int(fi.sum()), "hold": int(vi.sum())}
        if fi.sum() < fit_min or vi.sum() < hold_min:
            fr["state"] = "INSUFFICIENT"
            res[f"fold{fidx}"] = fr
            continue
        if model == "PARTIAL_AFFINE":
            M, inl = cv2.estimateAffinePartial2D(P0[fi], P1[fi], method=cv2.RANSAC,
                                                 ransacReprojThreshold=thr)
        else:
            M, inl = cv2.findHomography(P0[fi], P1[fi], cv2.RANSAC, thr)
        if M is None or inl is None:
            fr["state"] = "NO_FIT"
            res[f"fold{fidx}"] = fr
            continue
        ii = inl.ravel() == 1
        ratio = float(ii.mean())
        if ratio < inlier_min:
            fr["state"] = "LOW_INLIER"
            res[f"fold{fidx}"] = fr
            continue
        if M.shape == (2, 3):
            pred = cv2.transform(P0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        else:
            hp = np.hstack([P0[vi], np.ones((len(P0[vi]), 1))])
            prj = (M @ hp.T).T
            pred = prj[:, :2] / prj[:, 2:3]
        err = np.linalg.norm(pred - P1[vi], axis=1)
        med = float(np.median(err))
        p90 = float(np.percentile(err, 90))
        ok = med <= med_max and p90 <= p90_max
        fr.update({"state": "VALIDATED" if ok else "NOT_VALIDATED",
                   "inlier_ratio": round(ratio, 3), "med": round(med, 3),
                   "p90": round(p90, 3),
                   "residuals": [round(float(x), 3) for x in err]})
        res[f"fold{fidx}"] = fr
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="replay1", help="raw output tag")
    ap.add_argument("--limit-cases", type=int, default=0, help="0=all")
    ap.add_argument("--seed", type=int, default=0, help="0=no explicit seeding")
    ap.add_argument("--smoke", action="store_true", help="single case smoke")
    args = ap.parse_args()

    if args.seed:
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        cv2.setRNGSeed(args.seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.hub.set_dir(r"G:\TreeCut_AI\torch_cache")
    t_load = time.time()
    model = torch.hub.load("facebookresearch/dinov2", CFG["model"], verbose=False).eval().to(dev)
    load_s = round(time.time() - t_load, 1)

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    roi = json.loads(ROI_JSON.read_text(encoding="utf-8"))["annotations"]
    prod = json.loads(PROD_MATRIX.read_text(encoding="utf-8"))["pairs"]
    prod_mnn = {pr["pair"]: pr.get("valid_mnn") for pr in prod}
    prod_mnn_by_case = {}
    for pr in prod:
        prod_mnn_by_case.setdefault(pr["case"], {})[pr["pair"]] = pr.get("valid_mnn")
    t_start = time.time()
    cases = man["cases"][:args.limit_cases] if args.limit_cases else man["cases"]
    if args.smoke:
        cases = cases[:1]
    feat_cache = {}
    pair_rows = []
    per_case = {}
    vram_peak = 0
    feat_time_s = 0.0
    for c in cases:
        mid = c["media_id"]
        path = ROOTS.get(c["source_id"], "") + "\\" + c["relative_path"]
        v = Video(path)
        if not v.ok:
            print("OPEN_FAIL", mid, flush=True)
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
            return [(a["object_name"],
                     [a["bbox_pixel"][0] * sx, a["bbox_pixel"][1] * sy,
                      a["bbox_pixel"][2] * sx, a["bbox_pixel"][3] * sy])
                    for a in rbt.get(t, [])]

        anns = {t: ann(t) for t in ts}
        ibs = {}
        ok_all = True
        for t in ts:
            ib = [b for n, b in anns[t] if n == "ISLAND_BODY"]
            if len(ib) != 1:
                ok_all = False
                break
            ibs[t] = ib[0]
        if not ok_all:
            v.close()
            continue
        case_rows = []
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            pr = {"case": mid, "pair": f"{t0}->{t1}",
                  "prod_valid_mnn": prod_mnn_by_case.get(mid, {}).get(f"{t0}->{t1}")}
            try:
                fr0, fr1 = v.frame(t0), v.frame(t1)
                prepA = prep_rgb(ibs[t0], fr0, fr0.shape)
                prepB = prep_rgb(ibs[t1], fr1, fr1.shape)
                key = (mid, t0)
                if key not in feat_cache:
                    t_f = time.time()
                    with torch.no_grad():
                        out = model.forward_features(prepA[0].to(dev))
                        x = out["x_norm_patchtokens"][0]
                    f = torch.nn.functional.normalize(x.reshape(-1, x.shape[-1]), p=2, dim=1)
                    dt = time.time() - t_f
                    feat_cache[key] = (f.cpu().numpy(), prepA, dt)
                    feat_time_s += dt
                fA0, prepA, _ = feat_cache[key]
                key = (mid, t1)
                if key not in feat_cache:
                    t_f = time.time()
                    with torch.no_grad():
                        out = model.forward_features(prepB[0].to(dev))
                        x = out["x_norm_patchtokens"][0]
                    f = torch.nn.functional.normalize(x.reshape(-1, x.shape[-1]), p=2, dim=1)
                    dt = time.time() - t_f
                    feat_cache[key] = (f.cpu().numpy(), prepB, dt)
                    feat_time_s += dt
                fB0, prepB, _ = feat_cache[key]
                t0p, s0, px0, py0, o0 = prepA
                t1p, s1, px1, py1, o1 = prepB
                h0, w0 = fr0.shape[:2]
                crop0 = fr0[max(0, int(ibs[t0][1])):int(ibs[t0][3]),
                            max(0, int(ibs[t0][0])):int(ibs[t0][2])]
                hh, ww = crop0.shape[:2]
                sc0 = min(MODEL_IN / ww, MODEL_IN / hh)
                nw0, nh0 = int(ww * sc0), int(hh * sc0)
                cvm0 = content_valid_mask(nw0, nh0, (MODEL_IN - nw0) // 2, (MODEL_IN - nh0) // 2)
                crop1 = fr1[max(0, int(ibs[t1][1])):int(ibs[t1][3]),
                            max(0, int(ibs[t1][0])):int(ibs[t1][2])]
                hh, ww = crop1.shape[:2]
                sc1 = min(MODEL_IN / ww, MODEL_IN / hh)
                nw1, nh1 = int(ww * sc1), int(hh * sc1)
                cvm1 = content_valid_mask(nw1, nh1, (MODEL_IN - nw1) // 2, (MODEL_IN - nh1) // 2)
                dyn0 = [b for n, b in anns[t0] if n in DYNAMIC]
                dyn1 = [b for n, b in anns[t1] if n in DYNAMIC]
                dm0 = dynamic_token_mask(ibs[t0], dyn0, s0, px0, py0, o0[0], o0[1])
                dm1 = dynamic_token_mask(ibs[t1], dyn1, s1, px1, py1, o1[0], o1[1])
                v0 = cvm0 & ~dm0
                v1 = cvm1 & ~dm1
                pr["token"] = {"total": GRID * GRID,
                               "cvm0": int(cvm0.sum()), "cvm1": int(cvm1.sum()),
                               "dyn0": int(dm0.sum()), "dyn1": int(dm1.sum()),
                               "valid0": int(v0.sum()), "valid1": int(v1.sum())}
                t_m = time.time()
                pairs = valid_mnn_audit(fA0, fB0, v0.ravel(), v1.ravel())
                pairs.sort(key=lambda x: -x[2])
                pairs = pairs[:CFG["top_k"]]
                pr["valid_mnn"] = len(pairs)
                mnn_match = pr["valid_mnn"] == pr.get("prod_valid_mnn")
                pr["mnn_matches_prod"] = mnn_match
                if len(pairs) < CFG["min_mnn"]:
                    pr["state"] = "DENSE_MATCH_INSUFFICIENT"
                    pr["match_ms"] = round((time.time() - t_m) * 1000, 1)
                    case_rows.append(pr)
                    continue
                sim = fA0 @ fB0.T
                f1g = fB0.reshape(GRID, GRID, -1)
                corr = []
                sims = []
                for i0k, j1k, s in pairs:
                    r0, c0k = divmod(i0k, GRID)
                    p0_raw = model_to_raw([(c0k + 0.5) * PATCH, (r0 + 0.5) * PATCH],
                                          s0, px0, py0, o0[0], o0[1])
                    sx_, sy_ = subtoken_refine_softmax(f1g, i0k, j1k, sim)
                    r1c, c1c = divmod(j1k, GRID)
                    p1_coarse_token = model_to_raw([(c1c + 0.5) * PATCH, (r1c + 0.5) * PATCH],
                                                   s1, px1, py1, o1[0], o1[1])
                    p1_coarse = model_to_raw([sx_, sy_], s1, px1, py1, o1[0], o1[1])
                    sims.append(s)
                    corr.append({"i0": i0k, "j1": j1k, "sim": round(float(s), 4),
                                 "p0": [round(v, 2) for v in p0_raw],
                                 "p1_token": [round(v, 2) for v in p1_coarse_token],
                                 "p1_sub": [round(v, 2) for v in p1_coarse]})
                sims = np.array(sims)
                # LK forward+backward（raw grayscale, 960 平面）
                g0 = cv2.cvtColor(fr0, cv2.COLOR_BGR2GRAY)
                g1 = cv2.cvtColor(fr1, cv2.COLOR_BGR2GRAY)
                fg1 = np.zeros(g1.shape, dtype=bool)
                for ob in dyn1:
                    ox1, oy1, ox2, oy2 = [int(z) for z in ob]
                    oy1 = max(0, oy1); oy2 = min(g1.shape[0], oy2)
                    ox1 = max(0, ox1); ox2 = min(g1.shape[1], ox2)
                    if ox2 > ox1 and oy2 > oy1:
                        fg1[oy1:oy2, ox1:ox2] = True
                lk_t = time.time()
                for x in corr:
                    p1_, fwd_ok, p0b_, bwd_ok, fb = lk_refine_fb(
                        g0, g1, x["p0"], x["p1_sub"], CFG["lk"]["win"], CFG["lk"]["maxLevel"])
                    x["fwd_ok"] = fwd_ok
                    x["bwd_ok"] = bwd_ok
                    x["fb_px"] = (round(fb, 3) if fb is not None else None)
                    if fwd_ok:
                        inb = (ibs[t1][0] <= p1_[0] <= ibs[t1][2] and
                               ibs[t1][1] <= p1_[1] <= ibs[t1][3])
                        yy, xx = int(p1_[1]), int(p1_[0])
                        infg = 0 <= yy < fg1.shape[0] and 0 <= xx < fg1.shape[1] and fg1[yy, xx]
                        x["in_island"] = bool(inb)
                        x["in_dynamic"] = bool(infg)
                        x["p1_lk"] = [round(p1_[0], 2), round(p1_[1], 2)]
                        x["corr_px"] = round(float(np.hypot(p1_[0] - x["p1_sub"][0],
                                                            p1_[1] - x["p1_sub"][1])), 3)
                    else:
                        x["in_island"] = None
                        x["in_dynamic"] = None
                        x["p1_lk"] = None
                        x["corr_px"] = None
                pr["lk_ms"] = round((time.time() - lk_t) * 1000, 1)
                pr["match_ms"] = round((time.time() - t_m) * 1000, 1)
                pr["corr"] = corr  # corr 明细（§10/§11/§8 审计需要）
                # 接受定义（production 语义：fwd_ok & in_island & not in_dynamic；FB 未门控）
                acc = [x for x in corr if x["fwd_ok"] and x["in_island"] and not x["in_dynamic"]]
                pr["lk_attempted"] = len(corr)
                pr["lk_accepted_prod_semantics"] = len(acc)
                pr["lk_accepted_fb3"] = sum(1 for x in acc
                                            if x["fb_px"] is not None and x["fb_px"] <= CFG["lk"]["fb_max"])
                # 全部接受点（含 FB>3）用于后续 fold/RANSAC 主判定（与 production 同）
                P0 = np.float32([[x["p0"][0], x["p0"][1]] for x in corr])
                X0 = float(ibs[t0][0]); Y0 = float(ibs[t0][1])
                W0 = max(1e-9, ibs[t0][2] - ibs[t0][0])
                H0 = max(1e-9, ibs[t0][3] - ibs[t0][1])
                nb = np.floor((P0[:, 0] - X0) / W0 * 4).astype(int).clip(0, 3)
                mb = np.floor((P0[:, 1] - Y0) / H0 * 4).astype(int).clip(0, 3)
                fold = (nb + mb) % 2
                bins = set(zip(nb.tolist(), mb.tolist()))
                quads = set()
                for uu, vv in zip((P0[:, 0] - X0) / W0, (P0[:, 1] - Y0) / H0):
                    quads.add(("L" if uu < 0.5 else "R") + ("T" if vv < 0.5 else "B"))
                pr["coverage"] = {"bins": len(bins), "quads": len(quads)}  # production 语义（全 MNN corr）
                # accepted 子集的 coverage（§17）
                acc_idx = [i for i, x in enumerate(corr)
                           if x["fwd_ok"] and x["in_island"] and not x["in_dynamic"]]
                if len(acc_idx) >= 4:
                    P0a = P0[acc_idx]
                    nba = np.floor((P0a[:, 0] - X0) / W0 * 4).astype(int).clip(0, 3)
                    mba = np.floor((P0a[:, 1] - Y0) / H0 * 4).astype(int).clip(0, 3)
                    binsa = set(zip(nba.tolist(), mba.tolist()))
                    quadsa = set()
                    for uu, vv in zip((P0a[:, 0] - X0) / W0, (P0a[:, 1] - Y0) / H0):
                        quadsa.add(("L" if uu < 0.5 else "R") + ("T" if vv < 0.5 else "B"))
                    pr["coverage_accepted"] = {"bins": len(binsa), "quads": len(quadsa)}
                else:
                    pr["coverage_accepted"] = {"bins": 0, "quads": 0, "note": "acc<4"}
                thr = coarse_ransac_thr(s0, s1)
                pr["scale"] = {"s0": round(s0, 4), "s1": round(s1, 4)}
                pr["ransac_thr"] = round(thr, 3)
                pr["models"] = {}
                # fold assignment ids（fit/holdout 独立审计 §16，全量 corr）
                pr["fold_ids"] = {"fold0": [i for i in range(len(corr)) if fold[i] == 0],
                                  "fold1": [i for i in range(len(corr)) if fold[i] == 1]}
                for pipe in ("DINO_ONLY", "DINO_LK"):
                    if pipe == "DINO_ONLY":
                        P1 = np.float32([[x["p1_sub"][0], x["p1_sub"][1]] for x in corr])
                        P0f, foldf = P0, fold
                    else:
                        sel = np.array([x["fwd_ok"] and x["in_island"] and not x["in_dynamic"]
                                        for x in corr])
                        if sel.sum() < CFG["fit_min"]:
                            pr["models"][pipe] = {"validated": False, "reason": "LK<8"}
                            continue
                        selb = [bool(s) for s in sel]
                        P1 = np.float32([[x["p1_lk"][0], x["p1_lk"][1]]
                                         for x, s in zip(corr, selb) if s])
                        P0f = np.float32([[x["p0"][0], x["p0"][1]]
                                          for x, s in zip(corr, selb) if s])
                        foldf = fold[np.array(selb)]
                    pr["models"][pipe] = {}
                    for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                        fr = fit_eval_audit(P0f, P1, foldf, mdl, thr)
                        okv = len(fr) == 2 and all(x["state"] == "VALIDATED" for x in fr.values())
                        pr["models"][pipe][mdl] = {"validated": okv, "folds": fr}
                lk_pipe = pr["models"].get("DINO_LK", {})
                aff_ok = lk_pipe.get("PARTIAL_AFFINE", {}).get("validated", False)
                hom_ok = lk_pipe.get("HOMOGRAPHY", {}).get("validated", False)
                # production 语义：SUPPORT_TOO_LOCALIZED 用全量 corr 的 bins/quads（pr["coverage"]）
                if pr["coverage"]["bins"] < CFG["bins_min"] or pr["coverage"]["quads"] < CFG["quads_min"]:
                    pr["state"] = "DENSE_SUPPORT_TOO_LOCALIZED"
                elif aff_ok and hom_ok:
                    sel = np.array([x["fwd_ok"] and x["in_island"] and not x["in_dynamic"]
                                    for x in corr])
                    selb = [bool(s) for s in sel]
                    P0h = P0[selb]
                    P1h = np.float32([[x["p1_lk"][0], x["p1_lk"][1]]
                                      for x, s in zip(corr, selb) if s])
                    Ma, _ = cv2.estimateAffinePartial2D(P0h, P1h, method=cv2.RANSAC,
                                                        ransacReprojThreshold=thr)
                    Mh, _ = cv2.findHomography(P0h, P1h, cv2.RANSAC, thr)
                    if Ma is not None and Mh is not None and len(P0h) >= 4:
                        pa = cv2.transform(P0h.reshape(-1, 1, 2), Ma).reshape(-1, 2)
                        hp = np.hstack([P0h, np.ones((len(P0h), 1))])
                        prj = (Mh @ hp.T).T
                        pb = prj[:, :2] / prj[:, 2:3]
                        disc = float(np.median(np.linalg.norm(pa - pb, axis=1)))
                        pr["aff_hom_disagreement_px"] = round(disc, 3)
                        pr["state"] = ("DENSE_MULTI_MODEL_CONSENSUS" if disc <= CFG["agree_px"]
                                       else "DENSE_MODEL_CONFLICT")
                        pr["representative"] = "PARTIAL_AFFINE"
                    else:
                        pr["state"] = "DENSE_MODEL_CONFLICT"
                elif aff_ok or hom_ok:
                    pr["state"] = "DENSE_SINGLE_MODEL"
                    pr["representative"] = "PARTIAL_AFFINE" if aff_ok else "HOMOGRAPHY"
                else:
                    pr["state"] = "DENSE_NO_ANCHOR"
                # §17 审计：若改用 accepted 子集 coverage 判定，state 是否变化
                ca = pr.get("coverage_accepted", {})
                cb = ca.get("bins", 0) if isinstance(ca, dict) else 0
                cq = ca.get("quads", 0) if isinstance(ca, dict) else 0
                pr["state_under_accepted_coverage"] = (
                    "DENSE_SUPPORT_TOO_LOCALIZED"
                    if (cb < CFG["bins_min"] or cq < CFG["quads_min"])
                    else pr["state"])
            except Exception as e:
                import traceback
                pr["state"] = "ERROR"
                pr["error"] = f"{type(e).__name__}: {str(e)[:150]}"
                pr["error_tb"] = traceback.format_exc()[-800:]
            case_rows.append(pr)
        v.close()
        pair_rows.extend(case_rows)
        per_case[mid] = case_rows
        if torch.cuda.is_available():
            vram_peak = max(vram_peak, torch.cuda.max_memory_allocated() / 1e9)
        print("case done", mid, "pairs", len(case_rows), flush=True)
        # 增量 checkpoint：每 case 后写一次部分结果，异常中断不丢已算数据
        partial = {"experiment": "DENSE01R1_OVERNIGHT_REPLAY_RAW",
                   "tag": args.tag, "seed": args.seed, "partial": True,
                   "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "n_pairs": len(pair_rows), "pairs": pair_rows}
        (OUT / f"TREECUT_DENSE01R1_OVERNIGHT_REPLAY_{args.tag}.json").write_text(
            json.dumps(partial, ensure_ascii=False, indent=1), encoding="utf-8")
    cnt = Counter(pr.get("state") for pr in pair_rows)
    mnn_match_all = all(pr.get("mnn_matches_prod", False) is True for pr in pair_rows)
    raw = {"experiment": "DENSE01R1_OVERNIGHT_REPLAY_RAW",
           "tag": args.tag, "seed": args.seed,
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "model": CFG["model"], "checkpoint_sha256": os.environ.get("DINO_CKPT_SHA", ""),
           "model_load_s": load_s,
           "state_counts": dict(cnt),
           "mnn_matches_prod_all": mnn_match_all,
           "n_pairs": len(pair_rows),
           "pairs": pair_rows,
           "perf": {"total_s": round(time.time() - t_start, 1),
                    "feat_s": round(feat_time_s, 1),
                    "model_load_s": load_s,
                    "vram_peak_gb": round(vram_peak, 2)}}
    fn = OUT / f"TREECUT_DENSE01R1_OVERNIGHT_REPLAY_{args.tag}.json"
    fn.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"state_counts": dict(cnt), "n_pairs": len(pair_rows),
                      "mnn_matches_prod_all": mnn_match_all,
                      "total_s": raw["perf"]["total_s"]}, ensure_ascii=False, indent=1))
    print("raw written:", fn.name)


if __name__ == "__main__":
    main()
