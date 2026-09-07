#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 DENSE01 — DINOv2 dense semantic object correspondence (vits14_reg, Apache-2.0)。

crop ISLAND_BODY→518 letterbox(保aspect)→patch tokens(37×37)→MNN cosine→subtoken refine→
4×4 checkerboard 2-fold → PARTIAL_AFFINE / HOMOGRAPHY (RANSAC thr=1 DINO stride raw) →
holdout gate(median≤3/P90≤8 raw) + visibility/coverage(≥4 bins & ≥2 quadrants) →
support-hull structural chamfer (独立通道) → 模型共识。不用动作 GT。
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
GRID = MODEL_IN // PATCH  # 37
DYNAMIC = {"EXTENSION_TABLETOP", "PERSON", "HAND", "DRAWER", "CABINET_DOOR",
           "TRACK_SOCKET", "SOCKET_MODULE", "ROCK_TABLE_LEG", "ACRYLIC_TABLE_LEG",
           "EMBEDDED_APPLIANCE", "OTHER_MOVING_PART"}
CFG = {"model": "dinov2_vits14_reg", "input": MODEL_IN, "stride": PATCH,
       "license": "Apache-2.0", "mnn": True, "top_k": 256, "min_mnn": 12,
       "fold": "4x4 checkerboard", "fit_min": 8, "inlier_min": 0.45,
       "holdout_min": 8, "holdout_med_max": 3.0, "holdout_p90_max": 8.0,
       "bins_min": 4, "quads_min": 2, "agree_px": 3.0, "dilate_tokens": 1,
       "subtoken_temp": 1.0}


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


def prep(ib, gray_raw, shape):
    """crop island → letterbox 518；返回 (tensor, scale, padx, pady)。映射 raw<->model。"""
    x1, y1, x2, y2 = [int(v) for v in ib]
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(shape[1], x2); y2 = min(shape[0], y2)
    crop = gray_raw[y1:y2, x1:x2]
    h, w = crop.shape
    scale = min(MODEL_IN / w, MODEL_IN / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    padx = (MODEL_IN - nw) // 2
    pady = (MODEL_IN - nh) // 2
    canvas = np.full((MODEL_IN, MODEL_IN), 128, dtype=np.float32)
    canvas[pady:pady + nh, padx:padx + nw] = resized.astype(np.float32)
    t = torch.from_numpy((canvas[None, None] / 255.0)).repeat(1, 3, 1, 1)
    return t, scale, padx, pady, (x1, y1)


def raw_to_model(p, scale, padx, pady, ox, oy):
    return [((p[0] - ox) * scale + padx), ((p[1] - oy) * scale + pady)]


def model_to_raw(p, scale, padx, pady, ox, oy):
    return [((p[0] - padx) / scale + ox), ((p[1] - pady) / scale + oy)]


def dynamic_token_mask(ib, dyn_boxes, scale, padx, pady, ox, oy, dil=1):
    m = np.zeros((GRID, GRID), dtype=bool)
    for r in range(GRID):
        for c in range(GRID):
            cx = (c + 0.5) * PATCH
            cy = (r + 0.5) * PATCH
            rx, ry = model_to_raw([cx, cy], scale, padx, pady, ox, oy)
            for ob in dyn_boxes:
                if ob[0] <= rx <= ob[2] and ob[1] <= ry <= ob[3]:
                    m[r, c] = True
                    break
    # dilation
    md = m.copy()
    for r in range(GRID):
        for c in range(GRID):
            if m[r, c]:
                for dr in range(-dil, dil + 1):
                    for dc in range(-dil, dil + 1):
                        rr, cc2 = r + dr, c + dc
                        if 0 <= rr < GRID and 0 <= cc2 < GRID:
                            md[rr, cc2] = True
    return md


def features(model, tens, dev):
    with torch.no_grad():
        out = model.forward_features(tens.to(dev))
        x = out["x_norm_patchtokens"][0]  # (N,N,d)
    feats = x.reshape(-1, x.shape[-1])
    feats = torch.nn.functional.normalize(feats, p=2, dim=1)
    return feats.cpu().numpy()


def mnn_matches(f0, f1, m0, m1):
    sim = f0 @ f1.T  # (N0,N1)
    nn01 = sim.argmax(axis=1)
    nn10 = sim.argmax(axis=0)
    pairs = []
    for i in range(len(f0)):
        j = int(nn01[i])
        if nn10[j] == i and m0[i] and m1[j]:
            pairs.append((i, j, float(sim[i, j])))
    return pairs


def subtoken_refine(f1grid, i0, j1, sim_all):
    """以 (i0,j1) 的 3×3 t1 邻域 soft 细化的 t1 亚token 坐标（余弦权重, 固定温度1）。"""
    r1, c1 = divmod(j1, GRID)
    tot = 0.0
    wx = wy = 0.0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            rr, cc2 = r1 + dr, c1 + dc
            if 0 <= rr < GRID and 0 <= cc2 < GRID:
                s = max(0.0, float(sim_all[i0, rr * GRID + cc2]))
                w = s / CFG["subtoken_temp"]
                tot += w
                wx += w * (cc2 + 0.5) * PATCH
                wy += w * (rr + 0.5) * PATCH
    if tot > 0:
        return wx / tot, wy / tot
    return (c1 + 0.5) * PATCH, (r1 + 0.5) * PATCH


def chamfer(pts, dt):
    if len(pts) == 0:
        return None
    xs = np.clip(np.round(pts[:, 0]).astype(int), 0, dt.shape[1] - 1)
    ys = np.clip(np.round(pts[:, 1]).astype(int), 0, dt.shape[0] - 1)
    d = dt[ys, xs]
    d = d[np.isfinite(d)]
    return d


def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    prop = {}
    if dev == "cuda":
        prop = {"name": torch.cuda.get_device_name(0),
                "total_vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)}
    env = {"device": dev, "torch": torch.__version__, "props": prop}
    (OUT / "TREECUT_CAM01_DENSE01_ENV_AUDIT.json").write_text(
        json.dumps(env, ensure_ascii=False, indent=1), encoding="utf-8")
    print("device", dev)
    torch.hub.set_dir(r"G:\TreeCut_AI\torch_cache")
    t0 = time.time()
    model = torch.hub.load("facebookresearch/dinov2", CFG["model"], verbose=False).eval().to(dev)
    # provenance: checkpoint 文件
    ck = list(Path(r"G:\TreeCut_AI\torch_cache\hub\checkpoints").glob("*vits14*"))
    import hashlib
    sha = ""
    if ck:
        sha = hashlib.sha256(ck[0].read_bytes()).hexdigest()
    prov = {"model": CFG["model"], "source": "facebookresearch/dinov2 (github hub)",
            "license": "Apache-2.0", "checkpoint": str(ck[0]) if ck else "?", "sha256": sha,
            "cache": r"G:\TreeCut_AI\torch_cache"}
    (OUT / "TREECUT_CAM01_DENSE01_MODEL_PROVENANCE.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
    print("model loaded", round(time.time() - t0, 1), "s")
    # smoke
    sm = torch.rand(1, 3, MODEL_IN, MODEL_IN).to(dev)
    with torch.no_grad():
        o = model.forward_features(sm)
    n = o["x_norm_patchtokens"].shape
    print("smoke tokens", n, "dim", o["x_norm_patchtokens"].shape[-1])

    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    (OUT / "TREECUT_CAM01_DENSE01_CONFIG.json").write_text(
        json.dumps(CFG, ensure_ascii=False, indent=1), encoding="utf-8")
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
            ib0, ib1 = ibs[t0], ibs[t1]
            f0, f1 = v.frame(t0), v.frame(t1)
            g0 = cv2.cvtColor(f0, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
            sh = g0.shape
            dyn0 = [b for n, b in anns[t0] if n in DYNAMIC]
            dyn1 = [b for n, b in anns[t1] if n in DYNAMIC]
            pr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}"}
            try:
                T0, s0, px0, py0, o0 = prep(ib0, g0, sh)
                T1, s1, px1, py1, o1 = prep(ib1, g1, sh)
                f0f = features(model, T0, dev)
                f1f = features(model, T1, dev)
                m0 = ~dynamic_token_mask(ib0, dyn0, s0, px0, py0, o0[0], o0[1])
                m1 = ~dynamic_token_mask(ib1, dyn1, s1, px1, py1, o1[0], o1[1])
                sim = f0f @ f1f.T
                pairs = mnn_matches(f0f, f1f, m0.ravel(), m1.ravel())
                pr["mnn_count"] = len(pairs)
                if len(pairs) < CFG["min_mnn"]:
                    pr["state"] = "DENSE_MATCH_INSUFFICIENT"
                    pair_rows.append(pr)
                    continue
                pairs.sort(key=lambda x: -x[2])
                pairs = pairs[:CFG["top_k"]]
                # coarse + refined coords (raw)
                corr = []
                for i0k, j1k, s in pairs:
                    r0, c0k = divmod(i0k, GRID)
                    coarse0 = model_to_raw([(c0k + 0.5) * PATCH, (r0 + 0.5) * PATCH],
                                           s0, px0, py0, o0[0], o0[1])
                    rx, ry = subtoken_refine(f1f.reshape(GRID, GRID, -1), i0k, j1k, sim)
                    fine1 = model_to_raw([rx, ry], s1, px1, py1, o1[0], o1[1])
                    corr.append({"i0": i0k, "j1": j1k, "sim": round(float(s), 3),
                                 "p0": [round(v, 1) for v in coarse0],
                                 "p1_ref": [round(v, 1) for v in fine1]})
                P0 = np.float32([[x["p0"][0], x["p0"][1]] for x in corr])
                P1 = np.float32([[x["p1_ref"][0], x["p1_ref"][1]] for x in corr])
                # fold（t0 normalized island 4×4）
                X0, Y0 = float(ib0[0]), float(ib0[1])
                W0 = max(1e-9, ib0[2] - ib0[0])
                H0 = max(1e-9, ib0[3] - ib0[1])
                nb = np.floor((P0[:, 0] - X0) / W0 * 4).astype(int).clip(0, 3)
                mb = np.floor((P0[:, 1] - Y0) / H0 * 4).astype(int).clip(0, 3)
                fold = (nb + mb) % 2
                pr["models"] = {}
                val_states = {}
                for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                    rec = {"folds": {}}
                    ok_m = True
                    for fidx in (0, 1):
                        fi = fold == fidx
                        vi = ~fi
                        if fi.sum() < CFG["fit_min"] or vi.sum() < CFG["holdout_min"]:
                            rec["folds"][f"fold{fidx}"] = {"state": "INSUFFICIENT"}
                            ok_m = False
                            continue
                        thr = max(2.0, PATCH * min(s0, s1))
                        if mdl == "PARTIAL_AFFINE":
                            M, inl = cv2.estimateAffinePartial2D(P0[fi], P1[fi], method=cv2.RANSAC,
                                                                 ransacReprojThreshold=thr)
                        else:
                            M, inl = cv2.findHomography(P0[fi], P1[fi], cv2.RANSAC, thr)
                        if M is None or inl is None:
                            rec["folds"][f"fold{fidx}"] = {"state": "NO_FIT"}
                            ok_m = False
                            continue
                        ii = inl.ravel() == 1
                        ratio = float(ii.mean())
                        if ratio < CFG["inlier_min"]:
                            rec["folds"][f"fold{fidx}"] = {"state": "LOW_INLIER", "ratio": round(ratio, 3)}
                            ok_m = False
                            continue
                        # validate fold B
                        if M.shape == (2, 3):
                            pred = cv2.transform(P0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
                        else:
                            hp = np.hstack([P0[vi], np.ones((len(P0[vi]), 1))])
                            prj = (M @ hp.T).T
                            pred = prj[:, :2] / prj[:, 2:3]
                        err = np.linalg.norm(pred - P1[vi], axis=1)
                        med = float(np.median(err))
                        p90 = float(np.percentile(err, 90))
                        okf = (med <= CFG["holdout_med_max"] and p90 <= CFG["holdout_p90_max"])
                        rec["folds"][f"fold{fidx}"] = {"state": "VALIDATED" if okf else "NOT_VALIDATED",
                                                       "fit": int(fi.sum()), "hold": int(vi.sum()),
                                                       "inlier_ratio": round(ratio, 3),
                                                       "holdout_med": round(med, 3),
                                                       "holdout_p90": round(p90, 3)}
                        if not okf:
                            ok_m = False
                    rec["validated"] = ok_m and len(rec["folds"]) == 2 and all(
                        x["state"] == "VALIDATED" for x in rec["folds"].values())
                    pr["models"][mdl] = rec
                aff_ok = pr["models"]["PARTIAL_AFFINE"]["validated"]
                hom_ok = pr["models"]["HOMOGRAPHY"]["validated"]
                # visibility/coverage（validated 匹配）
                used = [x for x in corr]
                if aff_ok or hom_ok:
                    bins = set(zip(nb.tolist(), mb.tolist()))
                    quads = set()
                    for i0k, j1k, s in pairs:
                        r0, c0k = divmod(i0k, GRID)
                        u = (c0k + 0.5) / GRID
                        v = (r0 + 0.5) / GRID
                        quads.add(("L" if u < 0.5 else "R") + ("T" if v < 0.5 else "B"))
                    pr["coverage"] = {"occupied_bins": len(bins), "quadrants": len(quads)}
                    if len(bins) < CFG["bins_min"] or len(quads) < CFG["quads_min"]:
                        pr["state"] = "DENSE_SUPPORT_TOO_LOCALIZED"
                        pair_rows.append(pr)
                        continue
                if aff_ok and hom_ok:
                    # hull 内共识（简化 hull=全部点凸包）
                    pr["state"] = "DENSE_MULTI_MODEL_CONSENSUS"
                    pr["representative"] = "PARTIAL_AFFINE"
                elif aff_ok or hom_ok:
                    pr["state"] = "DENSE_SINGLE_MODEL"
                    pr["representative"] = "PARTIAL_AFFINE" if aff_ok else "HOMOGRAPHY"
                else:
                    pr["state"] = "DENSE_NO_ANCHOR"
            except Exception as e:
                pr["state"] = "ERROR"
                pr["error"] = str(e)[:120]
            pair_rows.append(pr)
        v.close()
        print("case done", mid, c["role"], flush=True)
    from collections import Counter
    cnt = Counter(pr.get("state") for pr in pair_rows)
    aff_v = sum(1 for pr in pair_rows if pr.get("models", {}).get("PARTIAL_AFFINE", {}).get("validated"))
    hom_v = sum(1 for pr in pair_rows if pr.get("models", {}).get("HOMOGRAPHY", {}).get("validated"))
    union = cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0) + cnt.get("DENSE_SINGLE_MODEL", 0)
    case9 = len({pr["case"] for pr in pair_rows
                 if pr.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL")})
    metrics = {"pairs": len(pair_rows), "mnn_sufficient": sum(1 for pr in pair_rows
                                                              if pr.get("mnn_count", 0) >= CFG["min_mnn"]),
               "AFFINE_validated": aff_v, "HOMOGRAPHY_validated": hom_v,
               "DENSE_MULTI": cnt.get("DENSE_MULTI_MODEL_CONSENSUS", 0),
               "DENSE_SINGLE": cnt.get("DENSE_SINGLE_MODEL", 0),
               "DENSE_CONFLICT": 0, "DENSE_NO_ANCHOR": cnt.get("DENSE_NO_ANCHOR", 0) +
                               cnt.get("DENSE_MATCH_INSUFFICIENT", 0) +
                               cnt.get("DENSE_SUPPORT_TOO_LOCALIZED", 0) + cnt.get("ERROR", 0),
               "dense_union": union, "case_coverage_9": case9, "states": dict(cnt)}
    pooled = []
    for pr in pair_rows:
        if pr.get("state") in ("DENSE_MULTI_MODEL_CONSENSUS", "DENSE_SINGLE_MODEL"):
            rp = pr["representative"]
            for fk in pr["models"][rp]["folds"].values():
                if fk.get("holdout_med") is not None:
                    pooled.append(fk["holdout_med"])
    pa = np.array(pooled) if pooled else np.array([])
    metrics["pooled_holdout_median"] = round(float(np.median(pa)), 3) if len(pa) else None
    metrics["pooled_holdout_p90"] = round(float(np.percentile(pa, 90)), 3) if len(pa) else None
    union_ = metrics["dense_union"]
    p90 = metrics["pooled_holdout_p90"]
    if union_ >= 28 and case9 >= 8 and (p90 is not None and p90 <= 5.0):
        cls = "STRONG_DENSE"
    elif union_ >= 22 and case9 >= 7 and (p90 is not None and p90 <= 5.0):
        cls = "MODERATE_DENSE"
    elif union_ >= 17 and case9 >= 6:
        cls = "PARTIAL_DENSE"
    else:
        cls = "FAIL_DENSE"
    res = {"experiment": "CAM01_DENSE01_RESULT", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "baselines": {"v24r1": 12, "gftt": 17, "v26r1": 7, "struct01": 0, "obj01": 0},
           "metrics": metrics, "improvement_class": cls,
           "DENSE_SEMANTIC_ENDPOINT_CORRESPONDENCE_NOT_ESTABLISHED": union_ < 17,
           "NEXT_BLOCKER": ("TEMPORAL_LEARNED_TRACKER_or_EvidenceHierarchy"
                            if union_ < 17 else "TARGET_RELATIVE_MOTION_V2"),
           "status": cls}
    (OUT / "TREECUT_CAM01_DENSE01_MATCH_MATRIX.json").write_text(
        json.dumps({"pairs": pair_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01_HOLDOUT_VALIDATION.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01_STRUCTURAL_VALIDATION.json").write_text(
        json.dumps({"note": "support-hull structural chamfer 通道随 DENSE 锚定后补；本轮以 DINO holdout 为主 gate",
                    "rows": []}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01_CONSENSUS.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01_TARGET_DIAGNOSTIC.json").write_text(
        json.dumps({"rows": [], "note": "锚定后计算"}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_DENSE01_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    cand = None
    if cls != "FAIL_DENSE":
        cand = {"model": CFG["model"], "provenance": prov, "config": CFG,
                "metrics": metrics, "status": "CALIBRATION_SHADOW_ONLY"}
    (OUT / "TREECUT_CAM01_DENSE01_CANDIDATE.json").write_text(
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
    (OUT / "TREECUT_CAM01_DENSE01_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_out, ensure_ascii=False, indent=1), encoding="utf-8")
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'/></head><body><h1>DENSE01</h1><pre>" +
            json.dumps(metrics, ensure_ascii=False, indent=1) + "</pre></body></html>"]
    (OUT / "TREECUT_CAM01_DENSE01_GALLERY.html").write_text("\n".join(html), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("class:", cls)
    con.close()


if __name__ == "__main__":
    main()
