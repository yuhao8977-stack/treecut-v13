#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 STRUCT01 — Structural Object Anchor V1（edge/frame geometry feasibility）。

每 semantic pair: canonical 512 body gray + clean mask（island−DYNAMIC union, NN）→ gradient map；
fit: ECC（EUCLIDEAN/AFFINE）在 4×4 macro-tile checkerboard fold 上（fit fold ≠ validation fold, 同一 common clean）；
validation: 独立 chamfer（t0 边→forward→t1 边距离 & reverse），换算回 RAW px；
gate: 两 fold ECC 收敛 + support≥100px/3 分量 + sym median≤3px & sym P90≤8px(raw)。
model 共识: euclidean/affine 同 validated → 6×6 canonical grid raw 分歧 ≤3px → MULTI/CONFLICT。
不用动作 GT；不读 A3。
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
CANON = 512
MTILE = 4
VTILE = 6
DYNAMIC = {"EXTENSION_TABLETOP", "PERSON", "HAND", "DRAWER", "CABINET_DOOR",
           "TRACK_SOCKET", "SOCKET_MODULE", "ROCK_TABLE_LEG", "ACRYLIC_TABLE_LEG",
           "EMBEDDED_APPLIANCE", "OTHER_MOVING_PART"}
CONFIG = {"canonical": CANON, "macro_tiles": MTILE, "validation_tiles": VTILE,
          "ecc_criteria": {"iterations": 300, "eps": 1e-4},
          "min_val_edge_px": 100, "min_val_components": 3,
          "sym_median_max_px": 3.0, "sym_p90_max_px": 8.0,
          "agree_px": 3.0}


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


def fit_ecc(prev_img, curr_img, mask, model):
    """prev=t0(template), curr=t1(input)；OpenCV ECC。多尺度金字塔按输入原生尺寸逐级
    （64→…→min(H,W)），返回 M 即 template→input forward（已知点方向测试锁死）。"""
    if model == "EUCLIDEAN":
        mt = cv2.MOTION_EUCLIDEAN
    else:
        mt = cv2.MOTION_AFFINE
    N0 = min(prev_img.shape[0], prev_img.shape[1])
    levels = [s for s in (32, 64, 128, 256, 512) if s < N0]
    levels.append(N0)
    levels = sorted(set(levels))
    cur_ok = np.float32([[1, 0, 0], [0, 1, 0]]).reshape(2, 3)
    converged = False
    try:
        for L in levels:
            prevL = cv2.resize(prev_img, (L, L), interpolation=cv2.INTER_AREA).astype(np.float32)
            currL = cv2.resize(curr_img, (L, L), interpolation=cv2.INTER_AREA).astype(np.float32)
            maskL = cv2.resize(mask, (L, L), interpolation=cv2.INTER_NEAREST)
            if maskL.max() == 0:
                return None, False
            if not converged:
                wm = np.float32([[1, 0, 0], [0, 1, 0]]).reshape(2, 3)
            else:
                sc = L / float(levels[max(0, levels.index(L) - 1)])
                wm = cur_ok.copy()
                wm[0, 2] *= sc
                wm[1, 2] *= sc
            crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-5)
            ok, M = cv2.findTransformECC(prevL, currL, wm, mt, crit, maskL, 7)
            if not ok:
                return None, False
            cur_ok = M.copy()
            converged = True
        M = cur_ok
        if not np.all(np.isfinite(M)) or abs(np.linalg.det(M[:, :2])) < 1e-4:
            return None, False
        return M.astype(np.float32), True
    except Exception:
        return None, False


def macro_fold_mask(tile_idx, mtile=MTILE, canon=CANON):
    """checkerboard macro-tile mask for fold=tile_idx(0/1)。"""
    m = np.zeros((canon, canon), dtype=np.uint8)
    h = canon // mtile
    w = canon // mtile
    for r in range(mtile):
        for c in range(mtile):
            if (r + c) % 2 == tile_idx:
                m[r * h:(r + 1) * h, c * w:(c + 1) * w] = 255
    return m


def tile_mask_for(rset, mtile=MTILE, canon=CANON):
    m = np.zeros((canon, canon), dtype=np.uint8)
    h = canon // mtile
    w = canon // mtile
    for (r, c) in rset:
        m[r * h:(r + 1) * h, c * w:(c + 1) * w] = 255
    return m


def edge_support(edge_img, mask):
    e = (edge_img > 0) & (mask > 0)
    n = int(e.sum())
    ncomp = 0
    if n > 0:
        _, lab, stats, _ = cv2.connectedComponentsWithStats((e.astype(np.uint8)) * 255)
        ncomp = int((stats[1:, cv2.CC_STAT_AREA] >= 5).sum())
    return n, ncomp


def chamfer_forward(pts_canon, edge1_mask, dist1):
    """pts( canonical t0 系) → 已 forward 到 t1 canonical 的坐标 → 采 dist1。"""
    if len(pts_canon) == 0:
        return None
    xs = np.clip(pts_canon[:, 0].astype(int), 0, CANON - 1)
    ys = np.clip(pts_canon[:, 1].astype(int), 0, CANON - 1)
    d = dist1[ys, xs].astype(np.float64)
    return d[d < 1e9]


def canon_to_raw_pts(pts_c, ib):
    x1, y1, x2, y2 = ib
    W = max(1e-9, x2 - x1)
    H = max(1e-9, y2 - y1)
    return np.float32([[x1 + u * W, y1 + v * H] for u, v in pts_c])


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cv2.setRNGSeed(0)
    (OUT / "TREECUT_CAM01_STRUCT01_CONFIG.json").write_text(
        json.dumps(CONFIG, ensure_ascii=False, indent=1), encoding="utf-8")
    pair_rows = []
    line_rows = []
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
            pr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}"}
            # canonical body gray + clean mask
            def canon_pair(t, ib):
                fr = v.frame(t)
                gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
                x1, y1, x2, y2 = [int(x) for x in ib]
                crop = gray[max(0, y1):y2, max(0, x1):x2]
                if crop.size == 0:
                    return None, None, None
                body = cv2.resize(crop, (CANON, CANON), interpolation=cv2.INTER_AREA)
                dyn = [b for n, b in anns[t] if n in DYNAMIC]
                cm = np.ones((CANON, CANON), dtype=np.uint8)
                W = max(1e-9, ib[2] - ib[0])
                H = max(1e-9, ib[3] - ib[1])
                for ob in dyn:
                    a_ = int(max(0, (ob[0] - ib[0]) / W * CANON))
                    b_ = int(max(0, (ob[1] - ib[1]) / H * CANON))
                    c_ = int(min(CANON, (ob[2] - ib[0]) / W * CANON))
                    d_ = int(min(CANON, (ob[3] - ib[1]) / H * CANON))
                    if c_ > a_ and d_ > b_:
                        cm[b_:d_, a_:c_] = 0
                blur = cv2.GaussianBlur(body, (5, 5), 0)
                gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
                gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
                grad = cv2.magnitude(gx, gy)
                grad = cv2.convertScaleAbs(grad)
                canny = cv2.Canny(blur, 60, 180)
                return body, cm, (grad, canny)
            b0, cm0, (g0m, e0) = canon_pair(t0, ib0)
            b1, cm1, (g1m, e1) = canon_pair(t1, ib1)
            if b0 is None:
                pr["state"] = "STRUCT_NO_ANCHOR"
                pair_rows.append(pr)
                continue
            common = (cm0 > 0) & (cm1 > 0)
            # line diagnostics
            lr = {"case": mid, "pair": f"{t0}->{t1}"}
            for tag, edge, cmx in (("t0", e0, cm0), ("t1", e1, cm1)):
                em = (edge > 0) & (cmx > 0)
                lines = cv2.HoughLinesP((em.astype(np.uint8)) * 255, 1, np.pi / 180, 40,
                                        minLineLength=18, maxLineGap=6) if em.sum() > 200 else None
                ln = 0
                long_ = 0
                horiz = vert = other = 0
                tot = 0
                if lines is not None:
                    for x1_, y1_, x2_, y2_ in lines[:, 0]:
                        l = float(np.hypot(x2_ - x1_, y2_ - y1_))
                        ln += 1
                        tot += l
                        if l >= 60:
                            long_ += 1
                        ang = abs(np.degrees(np.arctan2(y2_ - y1_, x2_ - x1_))) % 180
                        if ang < 20 or ang > 160:
                            horiz += 1
                        elif 70 <= ang <= 110:
                            vert += 1
                        else:
                            other += 1
                lr[f"line_{tag}"] = {"lines": ln, "long": long_, "h": horiz, "v": vert,
                                     "o": other, "total_len": round(tot, 1),
                                     "edge_px": int(em.sum())}
            line_rows.append(lr)
            pr["line_diag"] = lr
            # checkerboard fit/val macro tiles（4×4）
            pr["models"] = {}
            all_val_res = {}
            for model in ("EUCLIDEAN", "AFFINE"):
                mrec = {"folds": {}}
                ok_model = True
                sym_res = []
                for fidx in (0, 1):
                    fit_m = (common.astype(np.uint8)) * 255
                    tilef = macro_fold_mask(fidx)
                    tilev = macro_fold_mask(1 - fidx)
                    fit_mask = cv2.bitwise_and(fit_m, tilef)
                    val_em0 = ((e0 > 0) & (cm0 > 0) & (tilev > 0)).astype(np.uint8)
                    val_em1 = ((e1 > 0) & (cm1 > 0) & (tilev > 0)).astype(np.uint8)
                    n0, c0c = edge_support(e0, (cm0 > 0) & (tilev > 0))
                    n1, c1c = edge_support(e1, (cm1 > 0) & (tilev > 0))
                    if n0 < CONFIG["min_val_edge_px"] or n1 < CONFIG["min_val_edge_px"] \
                            or c0c < CONFIG["min_val_components"] or c1c < CONFIG["min_val_components"]:
                        mrec["folds"][f"fold{fidx}"] = {"state": "STRUCT_VALIDATION_INSUFFICIENT",
                                                        "edge_px": [n0, n1]}
                        ok_model = False
                        continue
                    F, conv = fit_ecc(g0m, g1m, fit_mask, model)
                    if not conv or F is None:
                        mrec["folds"][f"fold{fidx}"] = {"state": "ECC_NOT_CONVERGED"}
                        ok_model = False
                        continue
                    # forward val: t0 边(仅 val tiles)映射到 t1 canonical
                    ys0, xs0 = np.nonzero(val_em0)
                    if len(xs0) == 0:
                        ok_model = False
                        continue
                    pts0 = np.float32(np.stack([xs0, ys0], axis=1)).reshape(-1, 1, 2)
                    pf = cv2.transform(pts0, F).reshape(-1, 2)
                    d1 = cv2.distanceTransform((val_em1 > 0).astype(np.uint8), cv2.DIST_L2, 3)
                    dd = d1[np.clip(pf[:, 1].astype(int), 0, CANON - 1),
                            np.clip(pf[:, 0].astype(int), 0, CANON - 1)]
                    dd = dd[np.isfinite(dd)]
                    # raw 尺度换算：canonical→raw = bbox 尺度（两轴平均近似后用精确轴? 用 min axis 偏保守）
                    sxr = (ib1[2] - ib1[0]) / CANON
                    syr = (ib1[3] - ib1[1]) / CANON
                    # 距离按像素轴：直接除以最大缩放更保守? 用 x/y 各向 → 取与轴无关近似 min(sxr,syr)
                    scale_r = min(sxr, syr)
                    fwd_med = float(np.median(dd)) * scale_r if len(dd) else None
                    fwd_p90 = float(np.percentile(dd, 90)) * scale_r if len(dd) else None
                    # reverse
                    Finv = np.linalg.inv(np.vstack([F, [0, 0, 1.0]]))[:2]
                    ys1, xs1 = np.nonzero(val_em1)
                    pts1 = np.float32(np.stack([xs1, ys1], axis=1)).reshape(-1, 1, 2)
                    pb = cv2.transform(pts1, Finv).reshape(-1, 2)
                    d0 = cv2.distanceTransform((val_em0 > 0).astype(np.uint8), cv2.DIST_L2, 3)
                    db = d0[np.clip(pb[:, 1].astype(int), 0, CANON - 1),
                            np.clip(pb[:, 0].astype(int), 0, CANON - 1)]
                    db = db[np.isfinite(db)]
                    rev_med = float(np.median(db)) * scale_r if len(db) else None
                    rev_p90 = float(np.percentile(db, 90)) * scale_r if len(db) else None
                    sym_med = max(fwd_med, rev_med) if (fwd_med and rev_med) else None
                    sym_p90 = max(fwd_p90, rev_p90) if (fwd_p90 and rev_p90) else None
                    okf = (sym_med is not None and sym_med <= CONFIG["sym_median_max_px"]
                           and sym_p90 is not None and sym_p90 <= CONFIG["sym_p90_max_px"])
                    mrec["folds"][f"fold{fidx}"] = {"state": "VALIDATED" if okf else "NOT_VALIDATED",
                                                    "forward_med_raw": round(fwd_med, 3) if fwd_med else None,
                                                    "forward_p90_raw": round(fwd_p90, 3) if fwd_p90 else None,
                                                    "reverse_med_raw": round(rev_med, 3) if rev_med else None,
                                                    "sym_median": round(sym_med, 3) if sym_med else None,
                                                    "sym_p90": round(sym_p90, 3) if sym_p90 else None,
                                                    "scale_raw": round(scale_r, 4)}
                    if sym_med is not None:
                        sym_res.append(sym_med)
                    if not okf:
                        ok_model = False
                mrec["validated"] = ok_model and all(
                    v.get("state") == "VALIDATED" for v in mrec["folds"].values()) and len(mrec["folds"]) == 2
                pr["models"][model] = mrec
            euc_ok = pr["models"]["EUCLIDEAN"]["validated"]
            aff_ok = pr["models"]["AFFINE"]["validated"]
            # consensus（6×6 canonical grid → raw 分歧）
            if euc_ok and aff_ok:
                Fe = np.vstack([pr["models"]["EUCLIDEAN"]["folds"]["fold0"].get("_F", None), [0, 0, 1]]) \
                    if "_F" in pr["models"]["EUCLIDEAN"]["folds"]["fold0"] else None
                # 重新取代表 F（从 fold0 fit 恢复：简化再 fit 一次全 clean）
                F_e, _ = fit_ecc(g0m, g1m, (common.astype(np.uint8)) * 255, "EUCLIDEAN")
                F_a, _ = fit_ecc(g0m, g1m, (common.astype(np.uint8)) * 255, "AFFINE")
                g = []
                for r in range(VTILE):
                    for cc in range(VTILE):
                        px = (cc + 0.5) * CANON / VTILE
                        py = (r + 0.5) * CANON / VTILE
                        # 前景挖除检查（canonical 粗查）
                        if cm0[int(py), int(px)] == 0:
                            continue
                        g.append([px, py])
                if len(g) >= 4:
                    gp = np.float32(g).reshape(-1, 1, 2)
                    if F_e is not None and F_a is not None:
                        pe = cv2.transform(gp, F_e).reshape(-1, 2)
                        pa = cv2.transform(gp, F_a).reshape(-1, 2)
                        disc = np.linalg.norm(pe - pa, axis=1)
                        disc_raw = disc * min((ib1[2] - ib1[0]) / CANON, (ib1[3] - ib1[1]) / CANON)
                        dmed = float(np.median(disc_raw))
                        if dmed <= CONFIG["agree_px"]:
                            pr["state"] = "STRUCT_MULTI_MODEL_CONSENSUS"
                            # representative: lower sym median
                            me = pr["models"]["EUCLIDEAN"]["folds"].get("fold0", {}).get("sym_median") or 99
                            ma = pr["models"]["AFFINE"]["folds"].get("fold0", {}).get("sym_median") or 99
                            pr["representative_model"] = "AFFINE" if ma <= me else "EUCLIDEAN"
                        else:
                            pr["state"] = "STRUCT_MODEL_CONFLICT"
                        pr["model_disagreement_raw_median"] = round(dmed, 3)
                    else:
                        pr["state"] = "STRUCT_MODEL_CONFLICT"
                else:
                    pr["state"] = "STRUCT_MODEL_CONFLICT"
            elif euc_ok or aff_ok:
                pr["state"] = "STRUCT_SINGLE_MODEL_VALIDATED"
                pr["representative_model"] = "AFFINE" if aff_ok else "EUCLIDEAN"
            else:
                pr["state"] = "STRUCT_NO_ANCHOR"
            pair_rows.append(pr)
        # gallery: canonical t0/t1 body small
        for idx, t in enumerate(ts):
            fr = v.frame(t)
            body, _, _ = canon_pair(t, ibs[t]) if ibs.get(t) else (None, None, None)
            if body is not None:
                body_s = cv2.resize(body, (128, 128))
                gallery.append({"case": mid, "t": t,
                                "img": "data:image/jpeg;base64," + base64.b64encode(
                                    cv2.imencode(".jpg", body_s, [cv2.IMWRITE_JPEG_QUALITY, 60])[1]).decode()})
        v.close()
        print("case done", mid, c["role"], flush=True)
    from collections import Counter
    cnt = Counter(pr.get("state") for pr in pair_rows)
    euc_v = sum(1 for pr in pair_rows if pr["models"].get("EUCLIDEAN", {}).get("validated"))
    aff_v = sum(1 for pr in pair_rows if pr["models"].get("AFFINE", {}).get("validated"))
    metrics = {"pairs": len(pair_rows),
               "EUCLIDEAN_validated": euc_v, "AFFINE_validated": aff_v,
               "STRUCT_MULTI_MODEL_CONSENSUS": cnt.get("STRUCT_MULTI_MODEL_CONSENSUS", 0),
               "STRUCT_SINGLE": cnt.get("STRUCT_SINGLE_MODEL_VALIDATED", 0),
               "STRUCT_CONFLICT": cnt.get("STRUCT_MODEL_CONFLICT", 0),
               "STRUCT_NO_ANCHOR": cnt.get("STRUCT_NO_ANCHOR", 0),
               "STRUCT_union": cnt.get("STRUCT_MULTI_MODEL_CONSENSUS", 0) + cnt.get("STRUCT_SINGLE_MODEL_VALIDATED", 0),
               "case_coverage_9": len({pr["case"] for pr in pair_rows
                                       if pr.get("state") in ("STRUCT_MULTI_MODEL_CONSENSUS",
                                                              "STRUCT_SINGLE_MODEL_VALIDATED")}),
               "states": dict(cnt)}
    pooled = []
    for pr in pair_rows:
        if pr.get("state") in ("STRUCT_MULTI_MODEL_CONSENSUS", "STRUCT_SINGLE_MODEL_VALIDATED"):
            md = pr["representative_model"]
            for fk in pr["models"][md]["folds"].values():
                if fk.get("sym_median") is not None:
                    pooled.append(fk["sym_median"])
    pa = np.array(pooled) if pooled else np.array([])
    metrics["pooled_sym_median"] = round(float(np.median(pa)), 3) if len(pa) else None
    metrics["pooled_sym_p90"] = round(float(np.percentile(pa, 90)), 3) if len(pa) else None
    metrics["pooled_sym_p95"] = round(float(np.percentile(pa, 95)), 3) if len(pa) else None
    union = metrics["STRUCT_union"]
    case9 = metrics["case_coverage_9"]
    p90 = metrics["pooled_sym_p90"]
    multi = metrics["STRUCT_MULTI_MODEL_CONSENSUS"]
    conflict = metrics["STRUCT_CONFLICT"]
    if multi >= 18 and union >= 24 and case9 >= 8 and (p90 is not None and p90 <= 5.0):
        cls = "STRONG_STRUCTURAL"
    elif union >= 20 and case9 >= 7 and (p90 is not None and p90 <= 5.0) and conflict <= 4:
        cls = "MODERATE_STRUCTURAL"
    elif union >= 17 and case9 >= 6:
        cls = "PARTIAL_STRUCTURAL"
    else:
        cls = "FAIL"
    exhausted = union < 17
    res = {"experiment": "CAM01_STRUCT01_RESULT", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "baselines": {"v24r1_multi": 12, "gftt_whole": 17, "v26r1_union": 7},
           "metrics": metrics, "improvement_class": cls,
           "LOW_LEVEL_LOCAL_ANCHOR_EXHAUSTED": exhausted,
           "status": cls}
    (OUT / "TREECUT_CAM01_STRUCT01_METHOD_MATRIX.json").write_text(
        json.dumps({"pairs": pair_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_STRUCT01_EDGE_VALIDATION.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_STRUCT01_LINE_DIAGNOSTIC.json").write_text(
        json.dumps({"rows": line_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_STRUCT01_CONSENSUS.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_STRUCT01_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    # NEG target control（真实 contract）
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
        if st == "STRUCT_MULTI_MODEL_CONSENSUS":
            neg["MULTI"].append({"case": pr["case"], "pair": pr["pair"]})
        elif st == "STRUCT_SINGLE_MODEL_VALIDATED":
            neg["SINGLE"].append({"case": pr["case"], "pair": pr["pair"]})
    neg_out = {"MULTI_pairs": neg["MULTI"], "MULTI_cases": len({x["case"] for x in neg["MULTI"]}),
               "SINGLE_pairs": neg["SINGLE"], "SINGLE_cases": len({x["case"] for x in neg["SINGLE"]})}
    (OUT / "TREECUT_CAM01_STRUCT01_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_out, ensure_ascii=False, indent=1), encoding="utf-8")
    html = ["<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'/><title>STRUCT01 Gallery</title>",
            "<style>img{width:110px;border:1px solid #aaa}body{font-family:'Microsoft YaHei'}</style></head><body>",
            "<h1>CAM01 STRUCT01 · canonical body（红框内岛台归一 512）</h1>"]
    for g in gallery:
        html.append(f"<img src='{g['img']}' title='{g['case']} @ {g['t']}s'/>")
    html.append("</body></html>")
    (OUT / "TREECUT_CAM01_STRUCT01_GALLERY.html").write_text("\n".join(html), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("class:", cls, "| exhausted:", exhausted)
    for mid in (1641, 10000, 2543, 21674):
        sub = [pr for pr in pair_rows if pr["case"] == mid]
        print(mid, [(pr["pair"], pr.get("state"),
                     {k: pr["models"][k].get("validated") for k in ("EUCLIDEAN", "AFFINE")}) for pr in sub])
    print("NEG:", json.dumps(neg_out, ensure_ascii=False))
    con.close()


if __name__ == "__main__":
    main()
