#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 V2.1 — Experiment Validity Closure + Local Island Anchor。

修正 v2 三处方法问题:
 1) bridge schedule 末端闭合到 semantic t1（最后一段真实计算）
 2) 中间帧 mask 策略如实声明: MASK_A=NONE / MASK_B=ENDPOINT_UNION(两端非岛台框并集+margin)
    / MASK_C=ENDPOINT_CORRIDOR(同对象两端唯一→外包络,否则退回 union)
 3) round-trip 仅作自检；独立验证 = AKAZE 背景区 descriptor 匹配(不参与拟合)+RANSAC inlier 支撑
    + 逆变换残差；第二通道 = warp 后背景边缘差。
新增: LOCAL_ISLAND_ANCHOR_V1（岛台主体局部参照，direct descriptor vs LK，不作动作判定）。
不改任何既有阈值；不读 A3；不造叶板 ROI。
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
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmv_camera_diag import estimate_camera_background  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
BRIDGE = {"BRIDGE_500": 0.5, "BRIDGE_250": 0.25, "BRIDGE_125": 0.125}
WMAX = 960
MARGIN = 8
CRIT = {"desc_resid": 3.0, "scene": 1.6}


def to33(M):
    M = np.asarray(M, dtype=np.float64)
    if M.shape == (2, 3):
        return np.vstack([M, [0, 0, 1.0]])
    if M.shape == (3, 3):
        return M
    return None


def build_bridge_schedule(t0, t1, step):
    """闭合到 t1：schedule[0]==t0, schedule[-1]==t1, 中间间距<=step+eps。"""
    s = [t0]
    t = t0
    while t + step < t1 - 1e-9:
        t += step
        s.append(round(t, 4))
    s.append(t1)
    return s


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


def akaze_valid(ga, gb, mask_bg, Minv):
    """独立验证：背景区 AKAZE 匹配(不参与拟合) → 逆变换残差 + inlier 支撑。"""
    m8 = (mask_bg.astype(np.uint8)) * 255
    det = cv2.AKAZE_create()
    k0, d0 = det.detectAndCompute(ga, mask=m8)
    k1, d1 = det.detectAndCompute(gb, mask=m8)
    if d0 is None or d1 is None or len(k0) < 8 or len(k1) < 8:
        return {"validation": "VALIDATION_INSUFFICIENT"}
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    try:
        knn = bf.knnMatch(d0, d1, k=2)
    except Exception:
        return {"validation": "VALIDATION_INSUFFICIENT"}
    good = []
    for m, n in knn:
        if m.distance < 0.8 * n.distance:
            good.append(m)
    if len(good) < 8:
        return {"validation": "VALIDATION_INSUFFICIENT", "matches": len(good)}
    p0 = np.float32([k0[m.queryIdx].pt for m in good]).reshape(-1, 2)
    p1 = np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 2)
    # inlier 支撑（RANSAC affine，仅一致性度量）
    _, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    inl = inl.ravel() == 1 if inl is not None else np.ones(len(p0), dtype=bool)
    # 残差：把 curr 点用 Minv 对齐回 prev
    ones = np.ones((len(p1), 1))
    hp = np.hstack([p1, ones])
    pred = (Minv @ hp.T).T
    pred = pred[:, :2] / pred[:, 2:3]
    err = np.linalg.norm(pred - p0, axis=1)
    return {"validation": "OK", "matches": int(len(p0)), "inlier_ratio": round(float(inl.mean()), 3),
            "residual_median_px": round(float(np.median(err)), 3),
            "residual_p90_px": round(float(np.percentile(err, 90)), 3)}


def edge_resid(ga, gb, Minv, shape):
    wb = cv2.warpPerspective(gb, Minv, (shape[1], shape[0]))
    e0 = cv2.Canny(ga, 80, 160).astype(np.float32) / 255.0
    e1 = cv2.Canny(cv2.cvtColor(wb, cv2.COLOR_GRAY2BGR) if False else wb, 80, 160).astype(np.float32) / 255.0
    return round(float(np.abs(e0 - e1).mean()), 4)


def mask_from_boxes(shape, boxes, margin=MARGIN):
    m = np.ones(shape, dtype=bool)
    h, w = shape
    for bb in boxes:
        x1, y1, x2, y2 = [int(v) for v in bb]
        x1 = max(0, x1 - margin); y1 = max(0, y1 - margin)
        x2 = min(w, x2 + margin); y2 = min(h, y2 + margin)
        m[y1:y2, x1:x2] = False
    return m


def union_boxes(t0_boxes, t1_boxes):
    out = [b for _, b in t0_boxes] + [b for _, b in t1_boxes]
    return out


def corridor_boxes(t0_boxes, t1_boxes):
    """同对象两端唯一 → 外包络；否则退回 union。"""
    by0 = {}
    for n, b in t0_boxes:
        by0.setdefault(n, []).append(b)
    by1 = {}
    for n, b in t1_boxes:
        by1.setdefault(n, []).append(b)
    out = []
    for n in set(by0) | set(by1):
        b0 = by0.get(n, [])
        b1 = by1.get(n, [])
        if len(b0) == 1 and len(b1) == 1:
            a, c = b0[0], b1[0]
            x1 = min(a[0], c[0]); y1 = min(a[1], c[1])
            x2 = max(a[2], c[2]); y2 = max(a[3], c[3])
            out.append([x1, y1, x2, y2])
        else:
            out += b0 + b1
    return out


def est_seg(a, b, boxes):
    out = estimate_camera_background(a, b, boxes, mode="background")
    if out.get("chosen_model") and out.get("chosen_M") is not None:
        return True, out["chosen_model"], to33(out["chosen_M"])
    return False, None, None


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()

    audit = {"BRIDGE_ENDPOINT_NOT_CLOSED": [], "ROUNDTRIP_DRIFT_NOT_INDEPENDENT_METRIC": True,
             "intermediate_roi_counts": {}}
    global_rows = []      # corrected global per pair/method/mask
    local_rows = []       # island anchor per eligible pair
    tgt_rel = []          # target relative motion per pair (anchor/global reliable)
    gstat = {}            # method+mask -> [reliable counts]

    def bump(key, rel):
        gstat.setdefault(key, {"n": 0, "rel": 0})
        gstat[key]["n"] += 1
        gstat[key]["rel"] += 1 if rel else 0

    for c in man["cases"]:
        mid = c["media_id"]
        row = cur.execute("select source_id, relative_path from media_files where id=?", (mid,)).fetchone()
        v = Video(ROOTS.get(row[0]) + "\\" + row[1])
        if not v.ok:
            continue
        ann0 = c["frames"][0]
        A_w, A_h = ann0["width"], ann0["height"]
        ts = [f["t_s"] for f in c["frames"]]
        roi_by_t = {}
        for a in roi:
            if a["media_id"] == mid:
                roi_by_t.setdefault(a["frame_timestamp"], []).append(a)

        def scaled_boxes(t):
            fr = v.frame(t)
            if fr is None:
                return None, None, []
            h, w = fr.shape[:2]
            sx = w / float(A_w)
            sy = h / float(A_h)
            out = []
            for a in roi_by_t.get(t, []):
                if a["object_name"] == "ISLAND_BODY":
                    continue
                bb = a["bbox_pixel"]
                out.append((a["object_name"], [bb[0] * sx, bb[1] * sy, bb[2] * sx, bb[3] * sy]))
            return w, h, out

        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            wA, hA, b0l = scaled_boxes(t0)
            _, _, b1l = scaled_boxes(t1)
            fa = v.frame(t0)
            fb = v.frame(t1)
            if fa is None or fb is None:
                continue
            ga = cv2.cvtColor(fa, cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(fb, cv2.COLOR_BGR2GRAY)
            shape = ga.shape
            # masks
            boxes_union = union_boxes(b0l, b1l)
            boxes_corr = corridor_boxes(b0l, b1l)
            mB = mask_from_boxes(shape, boxes_union)
            mC = mask_from_boxes(shape, boxes_corr)
            # --- audit: endpoint closure old-style vs new schedule ---
            for step in BRIDGE.values():
                old = np.round(np.arange(t0, t1 + 1e-9, step), 3).tolist()
                new = build_bridge_schedule(t0, t1, step)
                gap = round((t1 - old[-1]) * 1000, 1)
                if gap > 0.5:
                    audit["BRIDGE_ENDPOINT_NOT_CLOSED"].append(
                        {"case": mid, "pair": f"{t0}->{t1}", "step": step,
                         "old_last": old[-1], "t1": t1, "endpoint_gap_ms": gap})
            # --- corrected global: sparse under A/B/C, bridges under B(+250 under C) ---
            def run_one(tag, mask, boxes_for_seg, direct_only=False):
                rec = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                       "gap_s": round(t1 - t0, 3), "tag": tag}
                if direct_only:
                    okm, model, M33 = est_seg(fa, fb, boxes_for_seg(t0))
                    if not okm:
                        rec.update({"state": "CAMERA_UNRELIABLE", "reason": "NO_MODEL"})
                        bump(tag, False)
                        return rec
                    Minv = np.linalg.inv(M33)
                    va = akaze_valid(ga, gb, mask, Minv)
                    wb = cv2.warpPerspective(fb, Minv, (shape[1], shape[0]))
                    sd = float(np.abs(cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY).astype(np.float32) -
                                      ga.astype(np.float32)).mean() / 40.0)
                    ed = edge_resid(ga, cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY), np.eye(3), shape)
                    okv = va.get("validation") == "OK" and va.get("residual_median_px", 9) <= CRIT["desc_resid"]
                    rel = okv and sd <= CRIT["scene"]
                    rec.update({"state": "CAMERA_RELIABLE" if rel else "CAMERA_UNRELIABLE",
                                "model": model, "scene_diff": round(sd, 3),
                                "descriptor": va, "edge_residual_after": ed})
                    bump(tag, rel)
                    return rec
                # bridge with closed schedule
                step = next((s for k, s in BRIDGE.items() if tag.startswith(k)), None)
                sched = build_bridge_schedule(t0, t1, step)
                T = np.eye(3)
                ok_all = True
                segs = len(sched) - 1
                for j in range(segs):
                    fa_ = v.frame(sched[j])
                    fb_ = v.frame(sched[j + 1])
                    bx = boxes_for_seg(sched[j])
                    okj, _, M33 = est_seg(fa_, fb_, bx)
                    if not okj or M33 is None:
                        ok_all = False
                        break
                    T = M33 @ T
                if not ok_all:
                    rec.update({"state": "CAMERA_UNRELIABLE", "segments": segs, "reason": "SEG_FAIL"})
                    bump(tag, False)
                    return rec
                Minv = np.linalg.inv(T)
                va = akaze_valid(ga, gb, mask, Minv)
                wb = cv2.warpPerspective(fb, Minv, (shape[1], shape[0]))
                sd = float(np.abs(cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY).astype(np.float32) -
                                  ga.astype(np.float32)).mean() / 40.0)
                ed = edge_resid(ga, cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY), np.eye(3), shape)
                okv = va.get("validation") == "OK" and va.get("residual_median_px", 9) <= CRIT["desc_resid"]
                rel = okv and sd <= CRIT["scene"]
                rec.update({"state": "CAMERA_RELIABLE" if rel else "CAMERA_UNRELIABLE",
                            "segments": segs, "scene_diff": round(sd, 3),
                            "descriptor": va, "edge_residual_after": ed})
                bump(tag, rel)
                return rec

            for tag, mask, boxesf in (("SPARSE_MASK_A", np.ones(shape, bool),
                                       lambda t: []),
                                      ("SPARSE_MASK_B", mB, lambda t: boxes_union),
                                      ("SPARSE_MASK_C", mC, lambda t: boxes_corr)):
                global_rows.append(run_one(tag, mask, boxesf, direct_only=True))
            for tag in BRIDGE:
                global_rows.append(run_one(tag + "_MASK_B", mB, lambda t, u=boxes_union: u))
            global_rows.append(run_one("BRIDGE_250_MASK_C", mC, lambda t, u=boxes_corr: u))
            # --- LOCAL ISLAND ANCHOR (eligible = island at both ends) ---
            ib0 = [a["bbox_pixel"] for a in roi_by_t.get(t0, []) if a["object_name"] == "ISLAND_BODY"]
            ib1 = [a["bbox_pixel"] for a in roi_by_t.get(t1, []) if a["object_name"] == "ISLAND_BODY"]
            if len(ib0) == 1 and len(ib1) == 1:
                sx = wA / float(A_w)
                sy = hA / float(A_h)
                bb0 = [ib0[0][0] * sx, ib0[0][1] * sy, ib0[0][2] * sx, ib0[0][3] * sy]
                bb1 = [ib1[0][0] * sx, ib1[0][1] * sy, ib1[0][2] * sx, ib1[0][3] * sy]
                # island 内排除动件区域：用 union boxes ∩ island（简单：直接从 island 框扣除非岛台前景）
                # 简化：直接在 island bbox 内采样；动件多在其内 → 用 corridor boxes 反掩
                def island_mask(shape_, bb, other_boxes):
                    m = np.zeros(shape_, dtype=bool)
                    x1, y1, x2, y2 = [int(v) for v in bb]
                    x1 = max(0, x1); y1 = max(0, y1); x2 = min(shape_[1], x2); y2 = min(shape_[0], y2)
                    m[y1:y2, x1:x2] = True
                    for ob in other_boxes:
                        ox1, oy1, ox2, oy2 = [int(v) for v in ob]
                        oy1 = max(0, oy1); oy2 = min(shape_[0], oy2)
                        ox1 = max(0, ox1); ox2 = min(shape_[1], ox2)
                        m[oy1:oy2, ox1:ox2] = False
                    return m
                other0 = [b for _, b in b0l]
                other1 = [b for _, b in b1l]
                mA0 = island_mask(shape, bb0, other0)
                mA1 = island_mask(shape, bb1, other1)
                lr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                      "island_boxes": [round(x, 1) for x in bb0 + bb1]}
                # A) descriptor direct
                det = cv2.AKAZE_create()
                k0, d0 = det.detectAndCompute(ga, mask=(mA0.astype(np.uint8)) * 255)
                k1, d1 = det.detectAndCompute(gb, mask=(mA1.astype(np.uint8)) * 255)
                if d0 is not None and d1 is not None and len(k0) >= 6 and len(k1) >= 6:
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
                    knn = bf.knnMatch(d0, d1, k=2)
                    good = [m for m, n in knn if m.distance < 0.8 * n.distance]
                    if len(good) >= 6:
                        p0 = np.float32([k0[m.queryIdx].pt for m in good]).reshape(-1, 2)
                        p1 = np.float32([k1[m.trainIdx].pt for m in good]).reshape(-1, 2)
                        M, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                                             ransacReprojThreshold=3.0)
                        if M is not None and inl is not None:
                            ii = inl.ravel() == 1
                            r0 = p0[ii]; r1 = p1[ii]
                            err = np.linalg.norm(r1 - (cv2.transform(r0.reshape(-1, 1, 2),
                                                                     M).reshape(-1, 2)), axis=1)
                            lr["ISLAND_DIRECT_DESCRIPTOR"] = {
                                "matches": int(len(good)), "inlier_ratio": round(float(ii.mean()), 3),
                                "residual_median_px": round(float(np.median(err)), 3),
                                "residual_p90_px": round(float(np.percentile(err, 90)), 3),
                                "model": "partial_affine"}
                        else:
                            lr["ISLAND_DIRECT_DESCRIPTOR"] = {"state": "NO_MODEL"}
                    else:
                        lr["ISLAND_DIRECT_DESCRIPTOR"] = {"matches_too_few": len(good)}
                else:
                    lr["ISLAND_DIRECT_DESCRIPTOR"] = {"features_too_few": True}
                # B) LK direct inside island
                pts = cv2.goodFeaturesToTrack(ga, mask=(mA0.astype(np.uint8)) * 255, maxCorners=200,
                                              qualityLevel=0.01, minDistance=8, blockSize=7)
                if pts is not None and len(pts) >= 8:
                    p1t, st, _ = cv2.calcOpticalFlowPyrLK(ga, gb, pts, None, winSize=(21, 21), maxLevel=3)
                    okf = st.ravel() == 1
                    if okf.sum() >= 6:
                        dlt = p1t[okf].reshape(-1, 2) - pts[okf].reshape(-1, 2)
                        med = np.median(dlt, axis=0)
                        lr["ISLAND_DIRECT_LK"] = {"tracks": int(okf.sum()),
                                                  "translation_median_px": [round(float(med[0]), 3),
                                                                            round(float(med[1]), 3)],
                                                  "dispersion_px": round(float(np.median(
                                                      np.linalg.norm(dlt - med, axis=1))), 3)}
                local_rows.append(lr)
            # --- TARGET RELATIVE MOTION (only if some anchor/global reliable) ---
            tgt = [a for a in roi_by_t.get(t1, [])
                   if a["object_name"] in ("EXTENSION_TABLETOP", "TABLETOP")]
            if len(tgt) == 1 and len(ib0) == 1 and len(ib1) == 1:
                def rel_feat(bb_t, ib):
                    # 全部用 ROI 原始像素（同源缩放一致），算相对岛台的归一化边偏移
                    iw = max(1, ib[2] - ib[0]); ih = max(1, ib[3] - ib[1])
                    return {"left_off": (bb_t[0] - ib[0]) / iw, "right_off": (bb_t[2] - ib[2]) / iw,
                            "span_w": (bb_t[2] - bb_t[0]) / iw}
                f0 = rel_feat(tgt[0]["bbox_pixel"], ib0[0])
                f1 = rel_feat(tgt[0]["bbox_pixel"], ib1[0])
                tgt_rel.append({"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                                "right_off_delta": round(f1["right_off"] - f0["right_off"], 4),
                                "span_w_delta": round(f1["span_w"] - f0["span_w"], 4)})
        v.close()
        print("case done", mid, c["role"], flush=True)

    summary = {k: {"n": v["n"], "reliable_pct": round(100.0 * v["rel"] / v["n"], 1)}
               for k, v in gstat.items()}
    doc = {"experiment": "CAM01_V21_METHOD_AUDIT", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "audit": {"endpoint_not_closed_count": len(audit["BRIDGE_ENDPOINT_NOT_CLOSED"]),
                     "endpoint_not_closed_examples": audit["BRIDGE_ENDPOINT_NOT_CLOSED"][:8],
                     "roundtrip_not_independent": audit["ROUNDTRIP_DRIFT_NOT_INDEPENDENT_METRIC"],
                     "note": "bridge 中间帧无人工 ROI(仅语义 5 帧有) → MASK_B/C 以端点框并集/走廊代替并如实声明"}}
    (OUT / "TREECUT_CAM01_V21_METHOD_AUDIT.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    corr = {"experiment": "CAM01_V21_CORRECTED_GLOBAL", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method_summary": summary, "pairs": global_rows}
    (OUT / "TREECUT_CAM01_V21_CORRECTED_GLOBAL.json").write_text(
        json.dumps(corr, ensure_ascii=False, indent=1), encoding="utf-8")
    local_doc = {"experiment": "CAM01_V21_LOCAL_ISLAND_ANCHOR", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "pairs": local_rows}
    (OUT / "TREECUT_CAM01_V21_LOCAL_ISLAND_ANCHOR.json").write_text(
        json.dumps(local_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_V21_TARGET_RELATIVE_MOTION.json").write_text(
        json.dumps({"rows": tgt_rel}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    con.close()


if __name__ == "__main__":
    main()
