# -*- coding: utf-8 -*-
"""CAM01 DENSE01 R2 — FROZEN INTENDED-SPEC CLOSURE (正式实现).

补全 DENSE01R1 规格中声明但未实现的 FB≤3 gate，并用 FB-filtered evidence set
重跑完整几何 pipeline（fold/RANSAC/holdout/consensus）。冻结参数与 R1 完全一致
（不得修改），仅把"正式 accepted"从 forward-only 改为：
  fwd_ok AND bwd_ok AND FB<=3 AND p1 in ISLAND_BODY_t1 AND p1 not dynamic_t1.
覆盖/fold/RANSAC/holdout/consensus 全部只用 FINAL_ACCEPTED_FB3（同一 evidence set）。
另实现 support-hull 结构通道（convexHull(FB3 P0/P1) + 1-patch margin + clip 到
ISLAND_BODY，forward+reverse symmetric chamfer，OBJ01 corrected DT）。
role-blind：不读 case role；NEG target control 仅最后汇总。
禁止修改冻结参数；输出全部新文件名 TREECUT_CAM01_DENSE01R2_*。
"""
import json
import os
import sqlite3
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
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
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
       "normalization": "ImageNet mean/std RGB", "mnn": True, "top_k": 256,
       "min_mnn": 12, "fold": "4x4 checkerboard", "fit_min": 8, "inlier_min": 0.45,
       "holdout_min": 8, "holdout_med_max": 3.0, "holdout_p90_max": 8.0,
       "bins_min": 4, "quads_min": 2, "agree_px": 3.0, "T": 1.0,
       "lk": {"win": 21, "maxLevel": 3, "fb_max": 3.0},
       "fb": {"backward_init_is_p0": True, "gate_before_fit": True}}
(OUT / "TREECUT_CAM01_DENSE01R2_CONFIG.json").write_text(
    json.dumps(CFG, ensure_ascii=False, indent=1), encoding="utf-8")


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


def valid_mnn(f0, f1, v0, v1):
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


def lk_forward_backward(g0, g1, p0, p1_init, win=21, max_level=3):
    """FORWARD: p0 -> t1 (init=p1_sub DINO). BACKWARD: forward p1 -> t0 (init=p0).
    返回 (p1, fwd_ok, p0_back, bwd_ok, fb_px)。"""
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


def fit_eval(P0, P1, fold, model, thr):
    res = {}
    for fidx in (0, 1):
        fi = fold == fidx
        vi = ~fi
        fr = {"fit": int(fi.sum()), "hold": int(vi.sum())}
        if fi.sum() < CFG["fit_min"] or vi.sum() < CFG["holdout_min"]:
            fr["state"] = "FIT_INSUFFICIENT"
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
        if ratio < CFG["inlier_min"]:
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
        p95 = float(np.percentile(err, 95))
        ok = med <= CFG["holdout_med_max"] and p90 <= CFG["holdout_p90_max"]
        fr.update({"state": "VALIDATED" if ok else
                   ("HOLDOUT_MEDIAN_FAIL_ONLY" if med > CFG["holdout_med_max"]
                    and p90 <= CFG["holdout_p90_max"]
                    else "HOLDOUT_P90_FAIL_ONLY" if p90 > CFG["holdout_p90_max"]
                    and med <= CFG["holdout_med_max"]
                    else "HOLDOUT_MED_AND_P90_FAIL"),
                   "inlier_ratio": round(ratio, 3), "med": round(med, 3),
                   "p90": round(p90, 3), "p95": round(p95, 3),
                   "residuals": [round(float(x), 3) for x in err]})
        res[f"fold{fidx}"] = fr
    return res


def true_pooled(arrs):
    a = np.concatenate([np.asarray(x, dtype=np.float64) for x in arrs if len(x)]) if arrs else np.array([])
    if len(a) == 0:
        return None, None, None
    return (round(float(np.median(a)), 3), round(float(np.percentile(a, 90)), 3),
            round(float(np.percentile(a, 95)), 3))


def lk_accept_verdict(fwd_ok, bwd_ok, fb_px, in_island, in_dynamic, fb_max=3.0):
    """正式 accepted 判定（纯函数，可单测）：全部条件满足才 ACCEPT。"""
    if not fwd_ok:
        return "FWD_FAIL"
    if not bwd_ok:
        return "BWD_FAIL"
    if fb_px is None or fb_px > fb_max:
        return "FB>3"
    if not in_island:
        return "OUTSIDE_ISLAND"
    if in_dynamic:
        return "DYNAMIC"
    return "ACCEPT"


def hull_mask_from_pts(pts, ib, margin, shape):
    """convexHull(pts) + margin 扩张，clip 到 ISLAND_BODY(ib)。返回 bool mask(shape)。"""
    mask = np.zeros(shape, dtype=bool)
    if len(pts) < 3:
        return mask
    hull = cv2.convexHull(np.float32(pts)).reshape(-1, 2)
    # 扩张：沿 hull 多边形顶点向外 margin（粗近似：多边形膨胀 via 逐边平移不可靠，
    # 改用：hull 点集 + margin 外扩的圆覆盖 → 用 dilate 后重新 hull 更稳妥）
    img = np.zeros(shape, dtype=np.uint8)
    cv2.fillConvexPoly(img, hull.astype(np.int32), 1)
    k = max(1, int(round(margin)))
    img = cv2.dilate(img, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    mask = img > 0
    # clip 到 ISLAND_BODY
    x1, y1, x2, y2 = [int(v) for v in ib]
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(shape[1], x2); y2 = min(shape[0], y2)
    body = np.zeros(shape, dtype=bool)
    body[y1:y2, x1:x2] = True
    return mask & body


def raw_dt_to_edges(shape_raw, edge_pts):
    im = np.ones(shape_raw, dtype=np.uint8)
    xs = np.clip(edge_pts[:, 0].astype(int), 0, shape_raw[1] - 1)
    ys = np.clip(edge_pts[:, 1].astype(int), 0, shape_raw[0] - 1)
    im[ys, xs] = 0
    return cv2.distanceTransform(im, cv2.DIST_L2, 3).astype(np.float64)


def chamfer_stats(d):
    if d is None or len(d) == 0:
        return None
    return {"median": round(float(np.median(d)), 3),
            "p90": round(float(np.percentile(d, 90)), 3),
            "p95": round(float(np.percentile(d, 95)), 3)}


def apply_transform_pts(pts, T3):
    ones = np.ones((len(pts), 1))
    h = np.hstack([pts, ones])
    out = (T3 @ h.T).T
    return out[:, :2] / out[:, 2:3]


def canon_clean_edges_masked(ib, dyn_boxes, gray_raw, shape_raw, keep_mask, canon=256):
    """clean 结构边（Canny，动态排除）且仅保留 keep_mask 内（support hull+margin）。"""
    x1, y1, x2, y2 = [int(v) for v in ib]
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(shape_raw[1], x2); y2 = min(shape_raw[0], y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None, []
    crop = gray_raw[y1:y2, x1:x2]
    body = cv2.resize(crop, (canon, canon), interpolation=cv2.INTER_AREA)
    cm = np.ones((canon, canon), dtype=np.uint8)
    W = max(1e-9, ib[2] - ib[0])
    H = max(1e-9, ib[3] - ib[1])
    for ob in dyn_boxes:
        a_ = int(max(0, (ob[0] - ib[0]) / W * canon))
        b_ = int(max(0, (ob[1] - ib[1]) / H * canon))
        c_ = int(min(canon, (ob[2] - ib[0]) / W * canon))
        d_ = int(min(canon, (ob[3] - ib[1]) / H * canon))
        if c_ > a_ and d_ > b_:
            cm[b_:d_, a_:c_] = 0
    blur = cv2.GaussianBlur(body, (5, 5), 0)
    canny = cv2.Canny(blur, 60, 180)
    edge = ((canny > 0) & (cm > 0))
    # keep_mask（raw 平面）→ canonical
    km = keep_mask[y1:y2, x1:x2]
    km = cv2.resize(km.astype(np.uint8), (canon, canon), interpolation=cv2.INTER_NEAREST) > 0
    edge = edge & km
    ys, xs = np.nonzero(edge)
    pts = []
    if len(xs):
        X0, Y0 = float(ib[0]), float(ib[1])
        pts = np.float32([[X0 + (u / canon) * W, Y0 + (v / canon) * H]
                          for u, v in zip(xs, ys)])
    return edge.astype(np.uint8), pts


def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.hub.set_dir(r"G:\TreeCut_AI\torch_cache")
    t0_all = time.time()
    model = torch.hub.load("facebookresearch/dinov2", CFG["model"], verbose=False).eval().to(dev)
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    roi = json.loads(ROI_JSON.read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    feat_cache = {}
    pair_rows = []
    old_validated_folds = set()
    ov = json.loads((OUT / "TREECUT_DENSE01R1_OVERNIGHT_FAILURE_MAP.json").read_text(encoding="utf-8"))
    for r in ov["rows"]:
        for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
            e = r.get("DINO_LK." + mdl)
            if e and e.get("folds"):
                for fk, fv in e["folds"].items():
                    if fv.get("state") == "VALIDATED":
                        old_validated_folds.add((r["case"], r["pair"], mdl, fk))
    t_fit_total = 0.0
    for c in man["cases"]:
        mid = c["media_id"]
        row = cur.execute("select source_id, relative_path from media_files where id=?", (mid,)).fetchone()
        if not row:
            continue
        v = Video(ROOTS.get(row[0], "") + "\\" + row[1])
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
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            pr = {"case": mid, "pair": f"{t0}->{t1}", "role": c["role"]}
            try:
                fr0, fr1 = v.frame(t0), v.frame(t1)
                prepA = prep_rgb(ibs[t0], fr0, fr0.shape)
                prepB = prep_rgb(ibs[t1], fr1, fr1.shape)
                key = (mid, t0)
                if key not in feat_cache:
                    with torch.no_grad():
                        out = model.forward_features(prepA[0].to(dev))
                        x = out["x_norm_patchtokens"][0]
                    f = torch.nn.functional.normalize(x.reshape(-1, x.shape[-1]), p=2, dim=1)
                    feat_cache[key] = f.cpu().numpy()
                fA0 = feat_cache[key]
                key = (mid, t1)
                if key not in feat_cache:
                    with torch.no_grad():
                        out = model.forward_features(prepB[0].to(dev))
                        x = out["x_norm_patchtokens"][0]
                    f = torch.nn.functional.normalize(x.reshape(-1, x.shape[-1]), p=2, dim=1)
                    feat_cache[key] = f.cpu().numpy()
                fB0 = feat_cache[key]
                t0p, s0, px0, py0, o0 = prepA
                t1p, s1, px1, py1, o1 = prepB
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
                pr["token"] = {"total": GRID * GRID, "valid0": int(v0.sum()), "valid1": int(v1.sum())}
                pairs = valid_mnn(fA0, fB0, v0.ravel(), v1.ravel())
                pairs.sort(key=lambda x: -x[2])
                pairs = pairs[:CFG["top_k"]]
                pr["valid_mnn"] = len(pairs)
                pr["mnn_sufficient"] = len(pairs) >= CFG["min_mnn"]
                if len(pairs) < CFG["min_mnn"]:
                    pr["state"] = "MATCH_INSUFFICIENT"
                    pair_rows.append(pr)
                    continue
                sim = fA0 @ fB0.T
                f1g = fB0.reshape(GRID, GRID, -1)
                corr = []
                for i0k, j1k, s in pairs:
                    r0, c0k = divmod(i0k, GRID)
                    p0_raw = model_to_raw([(c0k + 0.5) * PATCH, (r0 + 0.5) * PATCH],
                                          s0, px0, py0, o0[0], o0[1])
                    sx_, sy_ = subtoken_refine_softmax(f1g, i0k, j1k, sim)
                    p1_coarse = model_to_raw([sx_, sy_], s1, px1, py1, o1[0], o1[1])
                    corr.append({"i0": i0k, "j1": j1k, "sim": round(float(s), 4),
                                 "p0": [round(v, 2) for v in p0_raw],
                                 "p1_sub": [round(v, 2) for v in p1_coarse]})
                g0 = cv2.cvtColor(fr0, cv2.COLOR_BGR2GRAY)
                g1 = cv2.cvtColor(fr1, cv2.COLOR_BGR2GRAY)
                fg1 = np.zeros(g1.shape, dtype=bool)
                for ob in dyn1:
                    ox1, oy1, ox2, oy2 = [int(z) for z in ob]
                    oy1 = max(0, oy1); oy2 = min(g1.shape[0], oy2)
                    ox1 = max(0, ox1); ox2 = min(g1.shape[1], ox2)
                    if ox2 > ox1 and oy2 > oy1:
                        fg1[oy1:oy2, ox1:ox2] = True
                # 真 forward+backward LK
                for x in corr:
                    p1_, fwd_ok, p0b_, bwd_ok, fb = lk_forward_backward(
                        g0, g1, x["p0"], x["p1_sub"], CFG["lk"]["win"], CFG["lk"]["maxLevel"])
                    x["fwd_ok"] = fwd_ok
                    x["bwd_ok"] = bwd_ok
                    x["fb_px"] = (round(fb, 3) if fb is not None else None)
                    x["reject"] = None
                    if fwd_ok:
                        inb = (ibs[t1][0] <= p1_[0] <= ibs[t1][2] and
                               ibs[t1][1] <= p1_[1] <= ibs[t1][3])
                        yy, xx = int(p1_[1]), int(p1_[0])
                        infg = 0 <= yy < fg1.shape[0] and 0 <= xx < fg1.shape[1] and fg1[yy, xx]
                    else:
                        inb, infg = False, False
                    x["reject"] = lk_accept_verdict(fwd_ok, bwd_ok, fb, inb, infg,
                                                    CFG["lk"]["fb_max"])
                    if x["reject"] == "ACCEPT":
                        x["p1_fb"] = [round(p1_[0], 2), round(p1_[1], 2)]
                acc = [x for x in corr if x["reject"] == "ACCEPT"]
                pr["lk_attempted"] = len(corr)
                pr["corr"] = corr  # 保留明细供 LK_FB reject taxonomy
                pr["fwd_ok"] = sum(1 for x in corr if x["fwd_ok"])
                pr["bwd_ok"] = sum(1 for x in corr if x["bwd_ok"])
                pr["fb3_raw"] = sum(1 for x in corr if x["fb_px"] is not None and x["fb_px"] <= CFG["lk"]["fb_max"])
                pr["final_accepted_fb3"] = len(acc)
                if len(acc) < CFG["fit_min"]:
                    pr["state"] = "LK_INSUFFICIENT_AFTER_FB"
                    pair_rows.append(pr)
                    continue
                # ===== FB3 evidence set → coverage/fold/fit 全部同一 set =====
                P0 = np.float32([x["p0"] for x in acc])
                P1 = np.float32([x["p1_fb"] for x in acc])
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
                # hull ratio
                hull_a = cv2.convexHull(P0).reshape(-1, 2)
                hull_area = cv2.contourArea(hull_a)
                body_area = max(1e-9, W0 * H0)
                pr["coverage"] = {"bins": len(bins), "quads": len(quads),
                                  "hull_ratio": round(float(hull_area / body_area), 4),
                                  "n_fb3": len(acc)}
                pr["fold_ids"] = {"fold0": [i for i in range(len(acc)) if fold[i] == 0],
                                  "fold1": [i for i in range(len(acc)) if fold[i] == 1]}
                fold0 = set(pr["fold_ids"]["fold0"])
                fold1 = set(pr["fold_ids"]["fold1"])
                pr["fold_disjoint"] = len(fold0 & fold1) == 0
                thr = coarse_ransac_thr(s0, s1)
                pr["ransac_thr_raw"] = round(float(thr), 6)
                pr["ransac_thr_check"] = {
                    "all_pass": abs(float(thr) - max(14.0 / s0, 14.0 / s1)) < 1e-6}
                pr["models"] = {}
                for pipe in ("DINO_ONLY_SUBTOKEN", "DINO_LK_FB3"):
                    if pipe == "DINO_ONLY_SUBTOKEN":
                        P1f = np.float32([x["p1_sub"] for x in acc])
                    else:
                        P1f = P1
                    pr["models"][pipe] = {}
                    for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                        t_f = time.time()
                        fr = fit_eval(P0, P1f, fold, mdl, thr)
                        t_fit_total += time.time() - t_f
                        okv = len(fr) == 2 and all(x["state"] == "VALIDATED" for x in fr.values())
                        pr["models"][pipe][mdl] = {"validated": okv, "folds": fr}
                lk_pipe = pr["models"]["DINO_LK_FB3"]
                aff_ok = lk_pipe["PARTIAL_AFFINE"]["validated"]
                hom_ok = lk_pipe["HOMOGRAPHY"]["validated"]
                if pr["coverage"]["bins"] < CFG["bins_min"] or pr["coverage"]["quads"] < CFG["quads_min"]:
                    pr["state"] = "SUPPORT_TOO_LOCALIZED"
                elif aff_ok and hom_ok:
                    # true consensus：共同 FB3 support deterministic grid
                    Ma, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                                        ransacReprojThreshold=thr)
                    Mh, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
                    if Ma is not None and Mh is not None and len(P0) >= 4:
                        pa = cv2.transform(P0.reshape(-1, 1, 2), Ma).reshape(-1, 2)
                        hp = np.hstack([P0, np.ones((len(P0), 1))])
                        prj = (Mh @ hp.T).T
                        pb = prj[:, :2] / prj[:, 2:3]
                        disc = np.linalg.norm(pa - pb, axis=1)
                        pr["consensus"] = {"median": round(float(np.median(disc)), 3),
                                           "p90": round(float(np.percentile(disc, 90)), 3)}
                        pr["state"] = ("DENSE_MULTI_MODEL_CONSENSUS" if np.median(disc) <= CFG["agree_px"]
                                       else "DENSE_MODEL_CONFLICT")
                        pr["representative"] = "PARTIAL_AFFINE"
                    else:
                        pr["state"] = "DENSE_MODEL_CONFLICT"
                elif aff_ok or hom_ok:
                    pr["state"] = "DENSE_SINGLE_MODEL"
                    pr["representative"] = "PARTIAL_AFFINE" if aff_ok else "HOMOGRAPHY"
                else:
                    pr["state"] = "DENSE_NO_ANCHOR"
                # ===== structural support-hull diagnostic（symmetric） =====
                try:
                    rep = pr.get("representative", "PARTIAL_AFFINE")
                    if aff_ok or hom_ok:
                        if rep == "PARTIAL_AFFINE":
                            Ma, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                                                ransacReprojThreshold=thr)
                            T3 = np.vstack([Ma, [0, 0, 1]]) if Ma is not None else None
                        else:
                            T3, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
                    else:
                        T3 = None
                    m0 = max(1e-9, PATCH / s0)
                    m1 = max(1e-9, PATCH / s1)
                    km0 = hull_mask_from_pts(P0, ibs[t0], m0, g0.shape)
                    km1 = hull_mask_from_pts(P1, ibs[t1], m1, g1.shape)
                    e0m, e0p = canon_clean_edges_masked(ibs[t0], dyn0, g0, g0.shape, km0)
                    e1m, e1p = canon_clean_edges_masked(ibs[t1], dyn1, g1, g1.shape, km1)
                    struct = {"n_edge_t0": int(len(e0p)) if e0p is not None else 0,
                              "n_edge_t1": int(len(e1p)) if e1p is not None else 0}
                    if T3 is not None and e0p is not None and e1p is not None and len(e0p) >= 4 and len(e1p) >= 4:
                        dt1 = raw_dt_to_edges(g1.shape, e1p)
                        dt0 = raw_dt_to_edges(g0.shape, e0p)
                        wf = apply_transform_pts(e0p, T3)
                        wy = np.clip(np.round(wf[:, 1]).astype(int), 0, g1.shape[0] - 1)
                        wx = np.clip(np.round(wf[:, 0]).astype(int), 0, g1.shape[1] - 1)
                        fwd = chamfer_stats(dt1[wy, wx])
                        try:
                            T3inv = np.linalg.inv(T3)
                            wr = apply_transform_pts(e1p, T3inv)
                            ry = np.clip(np.round(wr[:, 1]).astype(int), 0, g0.shape[0] - 1)
                            rx = np.clip(np.round(wr[:, 0]).astype(int), 0, g0.shape[1] - 1)
                            rev = chamfer_stats(dt0[ry, rx])
                        except Exception:
                            rev = None
                        struct["forward"] = fwd
                        struct["reverse"] = rev
                        if fwd and rev:
                            sym = np.concatenate([dt1[wy, wx], dt0[ry, rx]])
                            struct["symmetric"] = chamfer_stats(sym)
                        if (aff_ok or hom_ok) and fwd and fwd.get("p90") and fwd["p90"] > 12.0:
                            struct["flag"] = "DENSE_STRUCTURAL_DISAGREEMENT"
                    pr["structural"] = struct
                except Exception as e:
                    pr["structural"] = {"error": f"{type(e).__name__}: {str(e)[:120]}"}
            except Exception as e:
                pr["state"] = "ERROR"
                pr["error"] = f"{type(e).__name__}: {str(e)[:150]}"
            pair_rows.append(pr)
        v.close()
        print("case done", mid, flush=True)
    con.close()
    cnt = Counter(pr.get("state") for pr in pair_rows)
    aff_lk = sum(1 for p in pair_rows
                 if p.get("models", {}).get("DINO_LK_FB3", {}).get("PARTIAL_AFFINE", {}).get("validated"))
    hom_lk = sum(1 for p in pair_rows
                 if p.get("models", {}).get("DINO_LK_FB3", {}).get("HOMOGRAPHY", {}).get("validated"))
    aff_do = sum(1 for p in pair_rows
                 if p.get("models", {}).get("DINO_ONLY_SUBTOKEN", {}).get("PARTIAL_AFFINE", {}).get("validated"))
    hom_do = sum(1 for p in pair_rows
                 if p.get("models", {}).get("DINO_ONLY_SUBTOKEN", {}).get("HOMOGRAPHY", {}).get("validated"))
    union = cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0) + cnt.get("DENSE_SINGLE_MODEL", 0)
    case9 = len({p["case"] for p in pair_rows
                 if p.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")})
    pooled = []
    for p in pair_rows:
        if p.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL"):
            rp = p.get("representative", "PARTIAL_AFFINE")
            for fk in p.get("models", {}).get("DINO_LK_FB3", {}).get(rp, {}).get("folds", {}).values():
                pooled.append(np.array(fk.get("residuals", [])))
    pm, pp90, pp95 = true_pooled(pooled)
    fb3_total = sum(p.get("final_accepted_fb3", 0) for p in pair_rows)
    pairs_fb3_ge8 = sum(1 for p in pair_rows if p.get("final_accepted_fb3", 0) >= 8)
    fwd_total = sum(p.get("fwd_ok", 0) for p in pair_rows)
    bwd_total = sum(p.get("bwd_ok", 0) for p in pair_rows)
    metrics = {"pairs": len(pair_rows),
               "mnn_sufficient": sum(1 for p in pair_rows if p.get("mnn_sufficient")),
               "lk_attempted_total": sum(p.get("lk_attempted", 0) for p in pair_rows),
               "fwd_ok_total": fwd_total, "bwd_ok_total": bwd_total,
               "fb3_raw_total": sum(p.get("fb3_raw", 0) for p in pair_rows),
               "final_accepted_fb3_total": fb3_total,
               "pairs_fb3_ge8": pairs_fb3_ge8,
               "DINO_LK_FB3": {"AFFINE": aff_lk, "HOMOGRAPHY": hom_lk,
                               "MULTI": cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0),
                               "SINGLE": cnt.get("DENSE_SINGLE_MODEL", 0),
                               "CONFLICT": cnt.get("DENSE_MODEL_CONFLICT", 0),
                               "NO": cnt.get("DENSE_NO_ANCHOR", 0) + cnt.get("ERROR", 0),
                               "LK_INSUFFICIENT_AFTER_FB": cnt.get("LK_INSUFFICIENT_AFTER_FB", 0),
                               "MATCH_INSUFFICIENT": cnt.get("MATCH_INSUFFICIENT", 0),
                               "SUPPORT_TOO_LOCALIZED": cnt.get("SUPPORT_TOO_LOCALIZED", 0),
                               "union": union, "case_coverage_9": case9,
                               "true_pooled_median": pm, "true_pooled_p90": pp90,
                               "true_pooled_p95": pp95},
               "DINO_ONLY_SUBTOKEN": {"AFFINE": aff_do, "HOMOGRAPHY": hom_do},
               "state_counts": dict(cnt)}
    (OUT / "TREECUT_CAM01_DENSE01R2_MATCH_MATRIX.json").write_text(
        json.dumps({"pairs": pair_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    # failure map (from matrix pairs)
    (OUT / "TREECUT_CAM01_DENSE01R2_FAILURE_MAP.json").write_text(
        json.dumps({"rows": pair_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    # LK FB summary
    (OUT / "TREECUT_CAM01_DENSE01R2_LK_FB.json").write_text(
        json.dumps({"attempted": sum(p.get("lk_attempted", 0) for p in pair_rows),
                    "fwd_ok": fwd_total, "bwd_ok": bwd_total,
                    "fb3_raw": sum(p.get("fb3_raw", 0) for p in pair_rows),
                    "final_accepted_fb3": fb3_total,
                    "reject_counts": dict(Counter(
                        r for p in pair_rows for x in p.get("corr", [])
                        if "corr" in p for r in [x.get("reject")] if r))},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    # holdout validation
    (OUT / "TREECUT_CAM01_DENSE01R2_HOLDOUT_VALIDATION.json").write_text(
        json.dumps({"DINO_LK_FB3": metrics["DINO_LK_FB3"],
                    "DINO_ONLY_SUBTOKEN": metrics["DINO_ONLY_SUBTOKEN"]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    # spatial coverage
    (OUT / "TREECUT_CAM01_DENSE01R2_SPATIAL_COVERAGE.json").write_text(
        json.dumps({"rows": [{"case": p["case"], "pair": p["pair"],
                              "coverage": p.get("coverage"),
                              "fold_disjoint": p.get("fold_disjoint")} for p in pair_rows]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    # model consensus
    cons = []
    for p in pair_rows:
        if "consensus" in p:
            cons.append({"case": p["case"], "pair": p["pair"], "state": p["state"],
                         "consensus": p["consensus"]})
    (OUT / "TREECUT_CAM01_DENSE01R2_MODEL_CONSENSUS.json").write_text(
        json.dumps({"rows": cons}, ensure_ascii=False, indent=1), encoding="utf-8")
    # structural validation
    (OUT / "TREECUT_CAM01_DENSE01R2_STRUCTURAL_VALIDATION.json").write_text(
        json.dumps({"rows": [{"case": p["case"], "pair": p["pair"],
                              "structural": p.get("structural")} for p in pair_rows]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    # DINO vs LK
    dvl = []
    for p in pair_rows:
        d = {"case": p["case"], "pair": p["pair"]}
        for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
            fo = p.get("models", {}).get("DINO_ONLY_SUBTOKEN", {}).get(mdl, {}).get("folds", {})
            fl = p.get("models", {}).get("DINO_LK_FB3", {}).get(mdl, {}).get("folds", {})

            def bmed(fd):
                ms = [fv["med"] for fv in fd.values() if fv.get("med") is not None]
                return min(ms) if ms else None
            mo, ml = bmed(fo), bmed(fl)
            if mo is None or ml is None:
                d[mdl] = "NO_COMPARISON"
            else:
                dmed = ml - mo
                d[mdl] = "HELPED" if dmed < -0.3 else "HURT" if dmed > 0.3 else "NEUTRAL"
        dvl.append(d)
    mcell = Counter(x[mdl] for x in dvl for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"))
    pair_lvl = Counter()
    for x in dvl:
        vals = [x[m] for m in ("PARTIAL_AFFINE", "HOMOGRAPHY") if x[m] != "NO_COMPARISON"]
        if not vals:
            pair_lvl["NO_COMPARISON"] += 1
        elif all(v == "HELPED" for v in vals):
            pair_lvl["HELPED_ONLY"] += 1
        elif all(v == "HURT" for v in vals):
            pair_lvl["HURT_ONLY"] += 1
        elif all(v == "NEUTRAL" for v in vals):
            pair_lvl["NEUTRAL_ONLY"] += 1
        else:
            pair_lvl["MIXED"] += 1
    (OUT / "TREECUT_CAM01_DENSE01R2_DINO_VS_LK.json").write_text(
        json.dumps({"MODEL_COMPARISON_COUNTS": dict(mcell),
                    "PAIR_LEVEL_COUNTS": dict(pair_lvl),
                    "per_pair": dvl}, ensure_ascii=False, indent=1), encoding="utf-8")
    # old validated folds retention
    new_val = set()
    for p in pair_rows:
        for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
            e = p.get("models", {}).get("DINO_LK_FB3", {}).get(mdl)
            if e and e.get("folds"):
                for fk, fv in e["folds"].items():
                    if fv.get("state") == "VALIDATED":
                        new_val.add((p["case"], p["pair"], mdl, fk))
    retained = old_validated_folds & new_val
    lost = old_validated_folds - new_val
    fresh = new_val - old_validated_folds
    fold_cmp = {"old_validated": len(old_validated_folds),
                "new_validated": len(new_val),
                "retained": len(retained), "lost": len(lost), "new": len(fresh),
                "retained_detail": sorted(retained),
                "lost_detail": sorted(lost), "new_detail": sorted(fresh)}
    # NEG target control
    neg = {"MULTI": [], "SINGLE": []}
    for p in pair_rows:
        if p["role"] != "NEG":
            continue
        t0, t1 = [float(x) for x in p["pair"].split("->")]
        def tgt_ok(t):
            b = [a for a in roi if a["media_id"] == p["case"] and a["frame_timestamp"] == t]
            ex = [a for a in b if a["object_name"] == "EXTENSION_TABLETOP"]
            if len(ex) == 1:
                return True
            tp = [a for a in b if a["object_name"] == "TABLETOP"]
            return len(ex) == 0 and len(tp) == 1
        if not (tgt_ok(t0) and tgt_ok(t1)):
            continue
        st = p.get("state")
        if st == "DENSE_MULTI_MODEL_CONSENSUS":
            neg["MULTI"].append({"case": p["case"], "pair": p["pair"]})
        elif st == "DENSE_SINGLE_MODEL":
            neg["SINGLE"].append({"case": p["case"], "pair": p["pair"]})
    neg_out = {"MULTI_pairs": neg["MULTI"], "MULTI_cases": len({x["case"] for x in neg["MULTI"]}),
               "SINGLE_pairs": neg["SINGLE"], "SINGLE_cases": len({x["case"] for x in neg["SINGLE"]})}
    (OUT / "TREECUT_CAM01_DENSE01R2_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_out, ensure_ascii=False, indent=1), encoding="utf-8")
    u = union
    p90 = pp90
    if u >= 28 and case9 >= 8 and (p90 is not None and p90 <= 5.0) and cnt.get("DENSE_MODEL_CONFLICT", 0) <= 3:
        cls = "STRONG_DENSE"
    elif u >= 22 and case9 >= 7 and (p90 is not None and p90 <= 5.0) and cnt.get("DENSE_MODEL_CONFLICT", 0) <= 4:
        cls = "MODERATE_DENSE"
    elif u >= 17 and case9 >= 6:
        cls = "PARTIAL_DENSE"
    else:
        cls = "FAIL_DENSE"
    closed = u < 17
    res = {"experiment": "CAM01_DENSE01R2_RESULT",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "historical": {"dense01": 0, "dense01r1_forward_only": 0,
                          "overnight_replay_forward_only": 0},
           "metrics": metrics,
           "fold_retention": fold_cmp,
           "semantic_match_sufficient": f"{metrics['mnn_sufficient']}/36",
           "semantic_recall_status": "NOT_FORMALLY_GATED",
           "raw_refinement_effective": (metrics["DINO_ONLY_SUBTOKEN"]["AFFINE"] +
                                        metrics["DINO_ONLY_SUBTOKEN"]["HOMOGRAPHY"] <
                                        aff_lk + hom_lk),
           "raw_refinement_sufficient": union >= 17,
           "improvement_class": cls,
           "DENSE_ENDPOINT_ROUTE_CLOSED": closed,
           "DENSE_ENDPOINT_CAPABILITY": "NOT_ESTABLISHED" if closed else "ESTABLISHED",
           "NEXT_BLOCKER": ("EVIDENCE_HIERARCHY_REDESIGN_or_TEMPORAL_LEARNED_TRACKER"
                            if closed else "TARGET_RELATIVE_MOTION_V2"),
           "status": cls}
    (OUT / "TREECUT_CAM01_DENSE01R2_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    cand = None
    if cls != "FAIL_DENSE":
        cand = {"pipeline": "DINO semantic seed -> FB3 LK -> geometric holdout (frozen spec)",
                "model": CFG["model"], "config": CFG, "metrics": metrics["DINO_LK_FB3"],
                "status": "CALIBRATION_SHADOW_ONLY"}
    (OUT / "TREECUT_CAM01_DENSE01R2_CANDIDATE.json").write_text(
        json.dumps({"candidate": cand, "frozen": cand is not None}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'/></head><body><h1>DENSE01 R2</h1><pre>" +
            json.dumps(metrics, ensure_ascii=False, indent=1) + "</pre></body></html>"]
    (OUT / "TREECUT_CAM01_DENSE01R2_GALLERY.html").write_text("\n".join(html), encoding="utf-8")
    print(json.dumps({"metrics": metrics, "fold_retention": fold_cmp,
                      "class": cls, "closed": closed,
                      "model_cells": dict(mcell), "pair_level": dict(pair_lvl)},
                     ensure_ascii=False, indent=1))
    print("class:", cls, "| endpoint closed:", closed)


if __name__ == "__main__":
    main()
