#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.2 — Local Anchor Validity Closure + Target Relative Motion Bug Fix。

修正 v2.1 两处:
 A) TARGET_RELATIVE 曾用 t1 target bbox 同时算 f0/f1 → 本版分别取 target_t0/target_t1
    （contract: EXTENSION_TABLETOP 优先；两端各恰 1；否则 TABLETOP fallback(记录)；否则 INSUFFICIENT）。
 B) LOCAL_ISLAND_ANCHOR residual 曾为拟合内残差 → 本版 deterministic 2-fold（空间网格 hash）：
    fit fold → validate 另一 fold；两 fold 交叉；holdout median≤3.0 & fit inlier≥0.45 & holdout≥8 → VALIDATED。
仅岛台局部 anchor + 目标运动诊断；不改阈值；不读 A3；不造叶板。
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


def rel_feat(bb, ib):
    """bb/island 均在同一坐标空间（分析帧）→ 归一化相对特征。"""
    iw = max(1, ib[2] - ib[0]); ih = max(1, ib[3] - ib[1])
    cx = (bb[0] + bb[2]) / 2.0; cy = (bb[1] + bb[3]) / 2.0
    return {"left_off": (bb[0] - ib[0]) / iw, "right_off": (bb[2] - ib[2]) / iw,
            "top_off": (bb[1] - ib[1]) / ih, "bottom_off": (bb[3] - ib[3]) / ih,
            "span_w": (bb[2] - bb[0]) / iw, "span_h": (bb[3] - bb[1]) / ih,
            "cx_rel": (cx - (ib[0] + ib[2]) / 2.0) / iw,
            "cy_rel": (cy - (ib[1] + ib[3]) / 2.0) / ih}


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
    """deterministic 2-fold（按 prev kp 空间网格）→ (结果dict, 全部匹配的最终 fit 用可选项)"""
    gx = np.floor(p0[:, 0] / CELL).astype(int)
    gy = np.floor(p0[:, 1] / CELL).astype(int)
    fold = (gx + gy) % 2
    res = {"matches": int(len(p0)), "folds": {}}
    for fitf, valf in ((0, 1), (1, 0)):
        fi = fold == fitf
        vi = fold == valf
        if fi.sum() < 6 or vi.sum() < 6:
            res["folds"][f"fit{fitf}val{valf}"] = {"state": "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"}
            continue
        M, inl = cv2.estimateAffinePartial2D(p0[fi], p1[fi], method=cv2.RANSAC,
                                             ransacReprojThreshold=3.0)
        if M is None or inl is None:
            res["folds"][f"fit{fitf}val{valf}"] = {"state": "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT",
                                                   "fit_inlier_ratio": None}
            continue
        ii = inl.ravel() == 1
        fit_inl = float(ii.mean())
        p1p = cv2.transform(p0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        err = np.linalg.norm(p1p - p1[vi], axis=1)
        hmed = float(np.median(err)) if len(err) else None
        res["folds"][f"fit{fitf}val{valf}"] = {
            "state": "VALIDATED" if (len(vi) >= CRIT_HOLDOUT_N and fit_inl >= CRIT_FIT_INLIER
                                     and hmed is not None and hmed <= CRIT_HOLDOUT_MED) else "NOT_VALIDATED",
            "fit_inlier_ratio": round(fit_inl, 3), "holdout_n": int(vi.sum()),
            "holdout_median_px": (round(hmed, 3) if hmed is not None else None),
            "holdout_p90_px": round(float(np.percentile(err, 90)), 3) if len(err) else None}
    states = [v["state"] for k, v in res["folds"].items()]
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
    audit = {"TARGET_RELATIVE_T1_BBOX_REUSED_FOR_T0": True,
             "LOCAL_ANCHOR_RESIDUAL_IN_SAMPLE": True,
             "evidence": {"v21_file": "scripts/posta3_cam01_v21.py",
                          "target_bug": "v21 目标相对运动仅取 t1 target 框同时算 f0/f1",
                          "anchor_bug": "v21 岛台 descriptor residual 在拟合同一批 RANSAC inliers 上计算(in-sample)"}}
    local_rows = []
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
        # 预取语义帧
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
            a0 = ann(t0)
            a1 = ann(t1)
            ib0 = [b for n, b in a0 if n == "ISLAND_BODY"]
            ib1 = [b for n, b in a1 if n == "ISLAND_BODY"]
            other0 = [b for n, b in a0 if n != "ISLAND_BODY"]
            other1 = [b for n, b in a1 if n != "ISLAND_BODY"]
            lr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                  "island_both": bool(len(ib0) == 1 and len(ib1) == 1)}
            if len(ib0) == 1 and len(ib1) == 1:
                mA0 = island_mask(shape, ib0[0], other0)
                mA1 = island_mask(shape, ib1[0], other1)
                det = cv2.AKAZE_create()
                k0, d0 = det.detectAndCompute(ga, mask=(mA0.astype(np.uint8)) * 255)
                k1, d1 = det.detectAndCompute(gb, mask=(mA1.astype(np.uint8)) * 255)
                if d0 is not None and d1 is not None and len(k0) >= 12 and len(k1) >= 12:
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
                    knn = bf.knnMatch(d0, d1, k=2)
                    good = [m for m, n in knn if m.distance < 0.8 * n.distance]
                    if len(good) >= 12:
                        p0 = np.float32([k0[m.queryIdx].pt for m in good]).reshape(-1, 2)
                        p1 = np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 2)
                        lr["anchor"] = two_fold_validate(p0, p1)
                        # 分解（用 fit on fold0 的结果近似；无新 gate，仅 evidence）
                        M, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                                             ransacReprojThreshold=3.0)
                        if M is not None:
                            A = M[:2, :2]
                            lr["transform_evidence"] = {
                                "translation_px": [round(float(M[0, 2]), 2), round(float(M[1, 2]), 2)],
                                "scale": round(float(np.sqrt(abs(np.linalg.det(A)))), 4),
                                "rotation_deg": round(float(np.degrees(np.arctan2(A[1, 0], A[0, 0]))), 2)}
                        # 最终 fit（全部匹配）供补偿
                        Mf, _ = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                                            ransacReprojThreshold=3.0)
                        if Mf is not None:
                            lr["final_M_2x3"] = [list(x) for x in Mf.tolist()]
                            # ---- 仅 VALIDATED 才做锚点补偿目标运动 ----
                            if lr["anchor"].get("pair_state") == "LOCAL_ANCHOR_VALIDATED":
                                # 目标 contract
                                def pick_target(a_list):
                                    ext = [b for n, b in a_list if n == "EXTENSION_TABLETOP"]
                                    if len(ext) == 1:
                                        return ext[0], "EXTENSION_TABLETOP"
                                    top = [b for n, b in a_list if n == "TABLETOP"]
                                    if len(ext) == 0 and len(top) == 1:
                                        return top[0], "TABLETOP_FALLBACK"
                                    return None, "TARGET_RELATIVE_INSUFFICIENT"
                                tt0, st0 = pick_target(a0)
                                tt1, st1 = pick_target(a1)
                                if tt0 is not None and tt1 is not None and st0 != "TARGET_RELATIVE_INSUFFICIENT" \
                                        and st1 != "TARGET_RELATIVE_INSUFFICIENT":
                                    f0 = rel_feat(tt0, ib0[0])
                                    f1 = rel_feat(tt1, ib1[0])
                                    # anchor 补偿几何：curr 目标角点经 inv(T) 回 prev 系，再相对 island_t0
                                    Minv = cv2.invertAffineTransform(np.asarray(Mf, dtype=np.float64))
                                    corners = np.float32([[tt1[0], tt1[1]], [tt1[2], tt1[1]],
                                                         [tt1[2], tt1[3]], [tt1[0], tt1[3]]]).reshape(-1, 1, 2)
                                    cc = cv2.transform(corners, Minv).reshape(-1, 2)
                                    bb1c = [float(cc[:, 0].min()), float(cc[:, 1].min()),
                                            float(cc[:, 0].max()), float(cc[:, 1].max())]
                                    fc1 = rel_feat(bb1c, ib0[0])
                                    deltas = {k: round(fc1[k] - f0[k], 4) for k in
                                              ("left_off", "right_off", "top_off", "bottom_off",
                                               "span_w", "span_h", "cx_rel", "cy_rel")}
                                    tgt_geom.append({"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                                                     "target_selection": st0 if st0 != "TABLETOP_FALLBACK" else "TABLETOP",
                                                     "deltas_norm": deltas})
                                    # 像素/边缘（锚点补偿前后）
                                    x1, y1, x2, y2 = [int(v) for v in tt0]
                                    if x2 - x1 >= 8 and y2 - y1 >= 8:
                                        cA = ga[y1:y2, x1:x2].astype(np.float32)
                                        x1b, y1b, x2b, y2b = [int(v) for v in tt1]
                                        regB = gb[max(0, y1b):y2b, max(0, x1b):x2b]
                                        regB = cv2.resize(regB, (x2 - x1, y2 - y1)) if regB.shape != (y2 - y1, x2 - x1) else regB
                                        before = float(np.abs(cA - regB.astype(np.float32)).mean() / 40.0)
                                        wgb = cv2.warpAffine(gb, Minv, (w, h))
                                        regW = wgb[y1:y2, x1:x2]
                                        after = float(np.abs(cA - regW.astype(np.float32)).mean() / 40.0)
                                        eA = cv2.Canny(ga[y1:y2, x1:x2], 80, 160)
                                        eW = cv2.Canny(wgb[y1:y2, x1:x2], 80, 160)
                                        tgt_px.append({"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                                                       "raw_before_anchor_comp": round(before, 4),
                                                       "after_anchor_comp": round(after, 4),
                                                       "edge_diff_after": round(float(np.abs(
                                                           eA.astype(np.float32) - eW.astype(np.float32)).mean() / 255.0), 4)})
                    else:
                        lr["anchor"] = {"pair_state": "LOCAL_ANCHOR_INSUFFICIENT", "note": "features_too_few"}
                else:
                    lr["anchor"] = {"pair_state": "LOCAL_ANCHOR_INSUFFICIENT", "note": "detect_too_few"}
            local_rows.append(lr)
        v.close()
        print("case done", mid, c["role"], flush=True)
    # 覆盖统计
    total = len(local_rows)
    island_p = sum(1 for r in local_rows if r.get("island_both"))
    states = [r.get("anchor", {}).get("pair_state", "N/A") for r in local_rows]
    from collections import Counter
    sc = Counter(states)
    # 报告 grouped signal（仅在 valid 对的 tgt_geom deltas）
    pos3 = [g for g in tgt_geom if g["case"] in (27433, 12095, 3571)]
    neg = [g for g in tgt_geom if g["role"] == "NEG"]
    sig = lambda rows, key: [abs(g["deltas_norm"][key]) for g in rows]
    out = {"experiment": "CAM01_V22_LOCAL_ANCHOR_VALIDATION",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "total_semantic_pairs": total, "island_present_pairs": island_p,
           "anchor_states": dict(sc),
           "local_anchor_validated_pairs": sc.get("LOCAL_ANCHOR_VALIDATED", 0),
           "criteria": {"fit_inlier_min": CRIT_FIT_INLIER, "holdout_min": CRIT_HOLDOUT_N,
                        "holdout_median_max_px": CRIT_HOLDOUT_MED, "split": "grid-2fold deterministic"},
           "pairs": local_rows}
    (OUT / "TREECUT_CAM01_V22_LOCAL_ANCHOR_VALIDATION.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V22_TARGET_RELATIVE_GEOMETRY.json").write_text(
        json.dumps({"rows": tgt_geom}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V22_TARGET_PIXEL_EDGE_MOTION.json").write_text(
        json.dumps({"rows": tgt_px}, ensure_ascii=False, indent=1), encoding="utf-8")
    audit["summary"] = {"total": total, "island_present": island_p, "anchor_states": dict(sc)}
    (OUT / "TREECUT_CAM01_V22_METHOD_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    print("anchor states:", dict(sc))
    for key in ("right_off", "span_w", "cx_rel"):
        if pos3 or neg:
            print(key, "POS3 range", (round(min(sig(pos3, key)), 4), round(max(sig(pos3, key)), 4))
                  if pos3 else None,
                  "NEG range", (round(min(sig(neg, key)), 4), round(max(sig(neg, key)), 4)) if neg else None)
    print("px rows:", len(tgt_px))
    con.close()


if __name__ == "__main__":
    main()
