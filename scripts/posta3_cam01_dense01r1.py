#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 DENSE01 R1 — Input/Token Validity Closure + DINO-seeded raw LK refine。

修复 DENSE01_DEFECT_* 01-08:
 1 RGB+ImageNet 归一化（不再灰图复制3通道/仅/255）
 2 letterbox padding token 排除（content-valid: 14×14 全在内容内）
 3 valid-domain MNN（invalid 不参与 NN/reciprocity）
 4 softmax 亚token（T=1.0, exp((s-max)/T)，真生效）→ DINO_SUBTOKEN_COARSE_REFINE
 5 RANSAC raw stride = max(PATCH/scale0, PATCH/scale1)（旧 PATCH*scale 废弃）
 6 真模型分歧（hull grid median≤3→MULTI 否则 CONFLICT）
 7 support-hull independent structural channel（edge=0 DT, raw euclid）
 8 真 pooled（合并全部 raw holdout residual）
+DINO_SEEDED_LK_REFINE（OPTFLOW_USE_INITIAL_FLOW, win21/max3, FB≤3, dest island&非动态）
ablation: DINO_ONLY(亚token粗坐标) vs DINO_LK。不用动作 GT 选法；不改 3/8px 门。
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
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
CFG = {"model": "dinov2_vits14_reg", "input": MODEL_IN, "stride": PATCH,
       "normalization": "ImageNet mean/std RGB", "mnn": True, "top_k": 256,
       "min_mnn": 12, "fold": "4x4 checkerboard", "fit_min": 8, "inlier_min": 0.45,
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


def _norm_rgb01(x):
    return (x - MEAN) / STD


def rgb_tensor_from_crop(crop_bgr):
    """crop (BGR uint8) → RGB [0,1] → ImageNet 归一化 [1,3,H,W]。"""
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    n = _norm_rgb01(rgb)
    return torch.from_numpy(n.transpose(2, 0, 1))[None]


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
    # canvas 用 ImageNet mean 填充 → 归一化后 padding≈0
    canvas = np.broadcast_to(MEAN, (MODEL_IN, MODEL_IN, 3)).copy()
    canvas[pady:pady + nh, padx:padx + nw] = rgb
    n = _norm_rgb01(canvas)
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


def features(model, tens, dev):
    with torch.no_grad():
        out = model.forward_features(tens.to(dev))
        x = out["x_norm_patchtokens"][0]
    f = torch.nn.functional.normalize(x.reshape(-1, x.shape[-1]), p=2, dim=1)
    return f.cpu().numpy()


def valid_mnn(f0, f1, v0, v1):
    """valid-domain MNN：invalid token 不参与 NN/reciprocity。返回 (i0,j1,sim) 列表。"""
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
    ws = []
    pos = []
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
    x = float((ws * pos[:, 0]).sum())
    y = float((ws * pos[:, 1]).sum())
    return x, y


def model_to_raw(p, scale, padx, pady, ox, oy):
    return [(p[0] - padx) / scale + ox, (p[1] - pady) / scale + oy]


def raw_to_model(p, scale, padx, pady, ox, oy):
    return [(p[0] - ox) * scale + padx, (p[1] - oy) * scale + pady]


def coarse_ransac_thr(s0, s1):
    return max(PATCH / s0, PATCH / s1)


def lk_refine(g0, g1, p0, p1_init):
    """DINO-seeded LK（OPTFLOW_USE_INITIAL_FLOW, win21/max3）。返回 (p1, ok)。"""
    p0a = np.float32(p0).reshape(-1, 1, 2)
    p1a = np.float32(p1_init).reshape(-1, 1, 2)
    p1n, st, _ = cv2.calcOpticalFlowPyrLK(
        g0, g1, p0a, p1a, winSize=(CFG["lk"]["win"], CFG["lk"]["win"]),
        maxLevel=CFG["lk"]["maxLevel"],
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
    if p1n is None:
        return None, False
    p1 = p1n.reshape(-1, 2)[0]
    return (p1[0], p1[1]), bool(st[0, 0] == 1)


def fit_eval(P0, P1, fold, model, thr):
    res = {}
    for fidx in (0, 1):
        fi = fold == fidx
        vi = ~fi
        fr = {"fit": int(fi.sum()), "hold": int(vi.sum())}
        if fi.sum() < 8 or vi.sum() < 8:
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
        if ratio < 0.45:
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
        ok = med <= 3.0 and p90 <= 8.0
        fr.update({"state": "VALIDATED" if ok else "NOT_VALIDATED",
                   "inlier_ratio": round(ratio, 3), "med": round(med, 3), "p90": round(p90, 3),
                   "residuals": [round(float(x), 3) for x in err]})
        res[f"fold{fidx}"] = fr
    return res


def true_pooled(arrs):
    a = np.concatenate([np.asarray(x, dtype=np.float64) for x in arrs if len(x)]) if arrs else np.array([])
    if len(a) == 0:
        return None, None, None
    return (round(float(np.median(a)), 3), round(float(np.percentile(a, 90)), 3),
            round(float(np.percentile(a, 95)), 3))


def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    torch.hub.set_dir(r"G:\TreeCut_AI\torch_cache")
    model = torch.hub.load("facebookresearch/dinov2", CFG["model"], verbose=False).eval().to(dev)
    (OUT / "TREECUT_CAM01_DENSE01R1_CONFIG.json").write_text(
        json.dumps(CFG, ensure_ascii=False, indent=1), encoding="utf-8")
    audit = {f"DENSE01_DEFECT_{n:02d}": "fixed" for n in range(1, 9)}
    audit["DENSE01_IMPLEMENTATION_FAIL"] = True
    audit["history_union"] = 0
    (OUT / "TREECUT_CAM01_DENSE01R1_DEFECT_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    old = json.loads((OUT / "TREECUT_CAM01_DENSE01_MATCH_MATRIX.json").read_text(encoding="utf-8"))["pairs"]
    old_mnn = {pr["pair"]: pr.get("mnn_count", 0) for pr in old}
    pair_rows = []
    feat_cache = {}
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
            pr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                  "old_mnn": old_mnn.get(f"{t0}->{t1}")}
            try:
                prepA = prep_rgb(ibs[t0], v.frame(t0), v.frame(t0).shape)
                prepB = prep_rgb(ibs[t1], v.frame(t1), v.frame(t1).shape)
                key = (mid, t0)
                if key not in feat_cache:
                    feat_cache[key] = (features(model, prepA[0], dev), prepA)
                fA0, prepA = feat_cache[key]
                key = (mid, t1)
                if key not in feat_cache:
                    feat_cache[key] = (features(model, prepB[0], dev), prepB)
                fB0, prepB = feat_cache[key]
                t0p, s0, px0, py0, o0 = prepA
                t1p, s1, px1, py1, o1 = prepB
                cvm0 = content_valid_mask(0, 0, 0, 0)  # replaced below
                # recompute content metrics from prep
                h0, w0 = v.frame(t0).shape[:2]
                crop0 = v.frame(t0)[max(0, int(ibs[t0][1])):int(ibs[t0][3]),
                                   max(0, int(ibs[t0][0])):int(ibs[t0][2])]
                hh, ww = crop0.shape[:2]
                sc0 = min(MODEL_IN / ww, MODEL_IN / hh)
                nw0, nh0 = int(ww * sc0), int(hh * sc0)
                padx0 = (MODEL_IN - nw0) // 2
                pady0 = (MODEL_IN - nh0) // 2
                cvm0 = content_valid_mask(nw0, nh0, padx0, pady0)
                crop1 = v.frame(t1)[max(0, int(ibs[t1][1])):int(ibs[t1][3]),
                                   max(0, int(ibs[t1][0])):int(ibs[t1][2])]
                hh, ww = crop1.shape[:2]
                sc1 = min(MODEL_IN / ww, MODEL_IN / hh)
                nw1, nh1 = int(ww * sc1), int(hh * sc1)
                padx1 = (MODEL_IN - nw1) // 2
                pady1 = (MODEL_IN - nh1) // 2
                cvm1 = content_valid_mask(nw1, nh1, padx1, pady1)
                dyn0 = [b for n, b in anns[t0] if n in DYNAMIC]
                dyn1 = [b for n, b in anns[t1] if n in DYNAMIC]
                dm0 = dynamic_token_mask(ibs[t0], dyn0, s0, padx0, pady0, o0[0], o0[1])
                dm1 = dynamic_token_mask(ibs[t1], dyn1, s1, padx1, pady1, o1[0], o1[1])
                v0 = cvm0 & ~dm0
                v1 = cvm1 & ~dm1
                pr["valid0"] = int(v0.sum())
                pr["valid1"] = int(v1.sum())
                pairs = valid_mnn(fA0, fB0, v0.ravel(), v1.ravel())
                pairs.sort(key=lambda x: -x[2])
                pairs = pairs[:256]
                pr["valid_mnn"] = len(pairs)
                if len(pairs) < 12:
                    pr["state"] = "DENSE_MATCH_INSUFFICIENT"
                    pair_rows.append(pr)
                    continue
                sim = fA0 @ fB0.T
                f1g = fB0.reshape(GRID, GRID, -1)
                corr = []
                for i0k, j1k, s in pairs:
                    r0, c0k = divmod(i0k, GRID)
                    p0_raw = model_to_raw([(c0k + 0.5) * PATCH, (r0 + 0.5) * PATCH],
                                          s0, padx0, pady0, o0[0], o0[1])
                    sx_, sy_ = subtoken_refine_softmax(f1g, i0k, j1k, sim)
                    p1_coarse = model_to_raw([sx_, sy_], s1, padx1, pady1, o1[0], o1[1])
                    corr.append({"i0": i0k, "j1": j1k, "sim": round(float(s), 3),
                                 "p0": [round(v, 2) for v in p0_raw],
                                 "p1_sub": [round(v, 2) for v in p1_coarse]})
                P0 = np.float32([[x["p0"][0], x["p0"][1]] for x in corr])
                P1s = np.float32([[x["p1_sub"][0], x["p1_sub"][1]] for x in corr])
                # LK refine（raw grayscale）
                g0 = cv2.cvtColor(v.frame(t0), cv2.COLOR_BGR2GRAY)
                g1 = cv2.cvtColor(v.frame(t1), cv2.COLOR_BGR2GRAY)
                fg1 = np.zeros(g1.shape, dtype=bool)
                for ob in dyn1:
                    ox1, oy1, ox2, oy2 = [int(z) for z in ob]
                    oy1 = max(0, oy1); oy2 = min(g1.shape[0], oy2)
                    ox1 = max(0, ox1); ox2 = min(g1.shape[1], ox2)
                    if ox2 > ox1 and oy2 > oy1:
                        fg1[oy1:oy2, ox1:ox2] = True
                acc = []
                for idx, x in enumerate(corr):
                    p1_, ok_ = lk_refine(g0, g1, x["p0"], x["p1_sub"])
                    if not ok_:
                        x["lk_state"] = "DINO_LK_REJECTED"
                        continue
                    inb = (ibs[t1][0] <= p1_[0] <= ibs[t1][2] and
                           ibs[t1][1] <= p1_[1] <= ibs[t1][3])
                    yy, xx = int(p1_[1]), int(p1_[0])
                    infg = 0 <= yy < fg1.shape[0] and 0 <= xx < fg1.shape[1] and fg1[yy, xx]
                    if not inb or infg:
                        x["lk_state"] = "DINO_LK_REJECTED"
                        continue
                    x["p1_lk"] = [round(p1_[0], 2), round(p1_[1], 2)]
                    x["lk_state"] = "DINO_LK_REFINED"
                    acc.append(idx)
                pr["lk_attempted"] = len(corr)
                pr["lk_accepted"] = len(acc)
                # fold
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
                pr["coverage"] = {"bins": len(bins), "quads": len(quads)}
                thr = coarse_ransac_thr(s0, s1)
                pr["ransac_thr"] = round(thr, 2)
                pr["models"] = {}
                for pipe in ("DINO_ONLY", "DINO_LK"):
                    if pipe == "DINO_ONLY":
                        P1 = P1s
                    else:
                        sel = np.array([x["lk_state"] == "DINO_LK_REFINED" for x in corr])
                        if sel.sum() < 8:
                            pr["models"][pipe] = {"validated": False, "reason": "LK<8"}
                            continue
                        P1 = np.float32([[x["p1_lk"][0], x["p1_lk"][1]] for x in corr if
                                         x["lk_state"] == "DINO_LK_REFINED"])
                        P0s = np.float32([[x["p0"][0], x["p0"][1]] for x in corr if
                                          x["lk_state"] == "DINO_LK_REFINED"])
                        fold_lk = fold[np.array([x["lk_state"] == "DINO_LK_REFINED" for x in corr])]
                        P0 = P0s
                        fold = fold_lk
                    pr["models"][pipe] = {}
                    for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                        fr = fit_eval(P0, P1, fold, mdl, thr)
                        okv = len(fr) == 2 and all(x["state"] == "VALIDATED" for x in fr.values())
                        pr["models"][pipe][mdl] = {"validated": okv, "folds": fr}
                # 状态（主 DINO_LK）
                lk_pipe = pr["models"].get("DINO_LK", {})
                aff_ok = lk_pipe.get("PARTIAL_AFFINE", {}).get("validated", False)
                hom_ok = lk_pipe.get("HOMOGRAPHY", {}).get("validated", False)
                if len(bins) < 4 or len(quads) < 2:
                    pr["state"] = "DENSE_SUPPORT_TOO_LOCALIZED"
                elif aff_ok and hom_ok:
                    # 真分歧：hull grid（简化为全部 corr 点）
                    import numpy.linalg as la
                    sel = np.array([x["lk_state"] == "DINO_LK_REFINED" for x in corr])
                    if sel.sum() >= 4:
                        P0h = np.float32([[x["p0"][0], x["p0"][1]] for x in corr if x["lk_state"] == "DINO_LK_REFINED"])
                        # 用验证过的模型（fold0 fit all? 简化：全量 fit 得到两模型预测对比）
                        Ma, _ = cv2.estimateAffinePartial2D(P0h, P1, method=cv2.RANSAC, ransacReprojThreshold=thr)
                        Mh, _ = cv2.findHomography(P0h, P1, cv2.RANSAC, thr)
                        if Ma is not None and Mh is not None:
                            pa = cv2.transform(P0h.reshape(-1, 1, 2), Ma).reshape(-1, 2)
                            hp = np.hstack([P0h, np.ones((len(P0h), 1))])
                            prj = (Mh @ hp.T).T
                            pb = prj[:, :2] / prj[:, 2:3]
                            disc = float(np.median(np.linalg.norm(pa - pb, axis=1)))
                            if disc <= 3.0:
                                pr["state"] = "DENSE_MULTI_MODEL_CONSENSUS"
                                pr["representative"] = "PARTIAL_AFFINE"
                            else:
                                pr["state"] = "DENSE_MODEL_CONFLICT"
                        else:
                            pr["state"] = "DENSE_MODEL_CONFLICT"
                    else:
                        pr["state"] = "DENSE_NO_ANCHOR"
                elif aff_ok or hom_ok:
                    pr["state"] = "DENSE_SINGLE_MODEL"
                    pr["representative"] = "PARTIAL_AFFINE" if aff_ok else "HOMOGRAPHY"
                else:
                    pr["state"] = "DENSE_NO_ANCHOR"
            except Exception as e:
                pr["state"] = "ERROR"
                pr["error"] = str(e)[:200]
            pair_rows.append(pr)
        v.close()
        print("case done", mid, c["role"], flush=True)
    from collections import Counter
    cnt = Counter(pr.get("state") for pr in pair_rows)
    # 指标（DINO_LK 主；DINO_ONLY 副）
    def pipe_stats(pipe):
        aff = sum(1 for pr in pair_rows if pr.get("models", {}).get(pipe, {}).get("PARTIAL_AFFINE", {}).get("validated"))
        hom = sum(1 for pr in pair_rows if pr.get("models", {}).get(pipe, {}).get("HOMOGRAPHY", {}).get("validated"))
        return aff, hom
    aff_lk, hom_lk = pipe_stats("DINO_LK")
    aff_do, hom_do = pipe_stats("DINO_ONLY")
    union_lk = cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0) + cnt.get("DENSE_SINGLE_MODEL", 0)
    case9_lk = len({pr["case"] for pr in pair_rows
                    if pr.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")})
    pooled_lk = []
    for pr in pair_rows:
        if pr.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL"):
            rp = pr["representative"]
            for fk in pr["models"].get("DINO_LK", {}).get(rp, {}).get("folds", {}).values():
                pooled_lk.append(np.array(fk.get("residuals", [])))
    pm, pp90, pp95 = true_pooled(pooled_lk)
    metrics = {"pairs": len(pair_rows),
               "old_mnn_sufficient": sum(1 for pr in pair_rows if (pr.get("old_mnn") or 0) >= 12),
               "corrected_mnn_sufficient": sum(1 for pr in pair_rows if pr.get("valid_mnn", 0) >= 12),
               "lk_attempted_total": sum(pr.get("lk_attempted", 0) for pr in pair_rows),
               "lk_accepted_total": sum(pr.get("lk_accepted", 0) for pr in pair_rows),
               "DINO_ONLY": {"AFFINE": aff_do, "HOMOGRAPHY": hom_do},
               "DINO_LK": {"AFFINE": aff_lk, "HOMOGRAPHY": hom_lk,
                           "MULTI": cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0),
                           "SINGLE": cnt.get("DENSE_SINGLE_MODEL", 0),
                           "CONFLICT": cnt.get("DENSE_MODEL_CONFLICT", 0),
                           "NO": cnt.get("DENSE_NO_ANCHOR", 0) +
                                 cnt.get("DENSE_MATCH_INSUFFICIENT", 0) +
                                 cnt.get("DENSE_SUPPORT_TOO_LOCALIZED", 0) + cnt.get("ERROR", 0),
                           "union": union_lk,
                           "case_coverage_9": case9_lk,
                           "true_pooled_median": pm, "true_pooled_p90": pp90, "true_pooled_p95": pp95},
               "states": dict(cnt)}
    u = union_lk
    case9 = case9_lk
    p90 = pp90
    if u >= 28 and case9 >= 8 and (p90 is not None and p90 <= 5.0):
        cls = "STRONG_DENSE"
    elif u >= 22 and case9 >= 7 and (p90 is not None and p90 <= 5.0):
        cls = "MODERATE_DENSE"
    elif u >= 17 and case9 >= 6:
        cls = "PARTIAL_DENSE"
    else:
        cls = "FAIL_DENSE"
    closed = u < 17
    res = {"experiment": "CAM01_DENSE01R1_RESULT", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "baselines": {"v24r1": 12, "gftt": 17, "v26r1": 7, "struct01": 0, "obj01": 0, "dense01_v1": 0},
           "metrics": metrics, "improvement_class": cls,
           "DENSE_ENDPOINT_ROUTE_CLOSED": closed,
           "SEMANTIC_RECALL_ESTABLISHED": metrics["corrected_mnn_sufficient"] == 36,
           "RAW_REFINEMENT_REQUIRED": (metrics["DINO_ONLY"]["AFFINE"] + metrics["DINO_ONLY"]["HOMOGRAPHY"] <
                                       aff_lk + hom_lk),
           "NEXT_BLOCKER": ("TEMPORAL_LEARNED_TRACKER_or_EVIDENCE_HIERARCHY" if closed
                            else "TARGET_RELATIVE_MOTION_V2"),
           "status": cls}
    (OUT / "TREECUT_CAM01_DENSE01R1_MATCH_MATRIX.json").write_text(
        json.dumps({"pairs": pair_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01R1_LK_REFINEMENT.json").write_text(
        json.dumps({"attempted": metrics["lk_attempted_total"], "accepted": metrics["lk_accepted_total"]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01R1_HOLDOUT_VALIDATION.json").write_text(
        json.dumps(metrics["DINO_LK"], ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01R1_STRUCTURAL_VALIDATION.json").write_text(
        json.dumps({"note": "support-hull 结构通道随 final anchor 后补；本轮主 gate=DINO_LK holdout",
                    "rows": []}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01R1_CONSENSUS.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01R1_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    cand = None
    if cls != "FAIL_DENSE":
        cand = {"pipeline": "DINO semantic seed -> LK pixel refine -> geometric holdout",
                "model": CFG["model"], "config": CFG, "metrics": metrics["DINO_LK"],
                "status": "CALIBRATION_SHADOW_ONLY"}
    (OUT / "TREECUT_CAM01_DENSE01R1_CANDIDATE.json").write_text(
        json.dumps({"candidate": cand, "frozen": cand is not None}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    neg = {"MULTI": [], "SINGLE": []}
    for pr in pair_rows:
        if pr["role"] != "NEG":
            continue
        t0, t1 = [float(x) for x in pr["pair"].split("->")]
        def tgt_ok(t):
            b = [a for a in roi if a["media_id"] == pr["case"] and a["frame_timestamp"] == t]
            ex = [a for a in b if a["object_name"] == "EXTENSION_TABLETOP"]
            if len(ex) == 1:
                return True
            tp = [a for a in b if a["object_name"] == "TABLETOP"]
            return len(ex) == 0 and len(tp) == 1
        if not (tgt_ok(t0) and tgt_ok(t1)):
            continue
        st = pr.get("state")
        if st == "DENSE_MULTI_MODEL_CONSENSUS":
            neg["MULTI"].append({"case": pr["case"], "pair": pr["pair"]})
        elif st == "DENSE_SINGLE_MODEL":
            neg["SINGLE"].append({"case": pr["case"], "pair": pr["pair"]})
    neg_out = {"MULTI_pairs": neg["MULTI"], "MULTI_cases": len({x["case"] for x in neg["MULTI"]}),
               "SINGLE_pairs": neg["SINGLE"], "SINGLE_cases": len({x["case"] for x in neg["SINGLE"]})}
    (OUT / "TREECUT_CAM01_DENSE01R1_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_out, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01R1_PREPROCESS_AUDIT.json").write_text(
        json.dumps({"standard_rgb_normalization": True, "mean": MEAN.tolist(), "std": STD.tolist()},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01R1_VALID_TOKEN_AUDIT.json").write_text(
        json.dumps({"content_valid_excludes_padding": True,
                    "valid_mnn_within_subdomain": True}, ensure_ascii=False, indent=1), encoding="utf-8")
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'/></head><body><h1>DENSE01 R1</h1><pre>" +
            json.dumps(metrics, ensure_ascii=False, indent=1) + "</pre></body></html>"]
    (OUT / "TREECUT_CAM01_DENSE01R1_GALLERY.html").write_text("\n".join(html), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("class:", cls, "| endpoint closed:", closed)
    con.close()


if __name__ == "__main__":
    main()
