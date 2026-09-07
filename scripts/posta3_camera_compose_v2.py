#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 — ROI-Aware Bridge Camera Composition Experiment V2。

10 calibration10 cases × 4 相邻语义对 = ~40 pairs。每 pair 比较:
  SPARSE_DIRECT / FULL_FRAME_DIRECT(诊断基线) / BRIDGE_500 / BRIDGE_250 / BRIDGE_125
每 bridge 段用现有估计器选模型(translation/partial/full/homography)→统一 3x3，
T_total = T_n...T_1 (prev→curr)；最终 inverse(T_total) warp curr→prev。
可靠性 = 段全 ok + 组合有效 + 补偿后背景特征残差≤3.0 + scene_diff≤1.6。
漂移 = forward-compose 后再 inverse 的 background 点 round-trip 位移(中位)。
评价完全独立于动作 GT；禁用 A3 数据。
输出: CAMERA_COMPOSE_V2.json / CAMERA_PAIR_MATRIX_V2.json /
      TARGET_MOTION_DIAGNOSTIC_V2.json
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
RESID_MAX = 3.0
SCENE_MAX = 1.6
# 统一前景排除：除 ISLAND_BODY 外全部人工框（同一规则全 10 案例；不按 action GT）
EXCLUDE_NAMES_ALL_BUT_ISLAND = lambda n: n != "ISLAND_BODY"


def to33(M):
    M = np.asarray(M, dtype=np.float64)
    if M.shape == (2, 3):
        return np.vstack([M, [0, 0, 1.0]])
    if M.shape == (3, 3):
        return M
    return None


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


def est(a, b, excl):
    """单段估计 → (ok, model, M33, out)"""
    out = estimate_camera_background(a, b, excl, mode="background")
    if out.get("chosen_model") and out.get("chosen_M") is not None:
        M33 = to33(out["chosen_M"])
        return True, out["chosen_model"], M33, out
    return False, None, None, out


def bg_points(gray, mask, n=260):
    m8 = (mask.astype(np.uint8)) * 255
    pts = cv2.goodFeaturesToTrack(gray, mask=m8, maxCorners=n, qualityLevel=0.01,
                                  minDistance=10, blockSize=7)
    return pts.reshape(-1, 2) if pts is not None and len(pts) >= 8 else None


def residual_after(ga, gb, mask_bg, M_inv):
    """补偿后背景特征残差：prev 背景点 LK→curr，用 inv(T_total) 对齐回 prev 求中位误差。"""
    p0 = bg_points(ga, mask_bg)
    if p0 is None:
        return None, None
    p1, st, _ = cv2.calcOpticalFlowPyrLK(ga, gb, p0.reshape(-1, 1, 2), None,
                                         winSize=(15, 15), maxLevel=3)
    okf = st.ravel() == 1
    if okf.sum() < 8:
        return None, None
    a0 = p0[okf]
    b1 = p1[okf].reshape(-1, 2)
    # 变换 curr 点 b1 回 prev 系：p_prev_pred = M_inv · b1
    ones = np.ones((len(b1), 1))
    hb = np.hstack([b1, ones])
    pred = (M_inv @ hb.T).T
    pred = pred[:, :2] / pred[:, 2:3]
    err = np.linalg.norm(pred - a0, axis=1)
    return float(np.median(err)), int(okf.sum())


def mask_for(gray, boxes):
    m = np.ones(gray.shape, dtype=bool)
    h, w = gray.shape
    for bb in boxes:
        x1, y1, x2, y2 = [int(v) for v in bb]
        x1 = max(0, min(w - 1, x1)); y1 = max(0, min(h - 1, y1))
        x2 = max(x1 + 1, min(w, x2)); y2 = max(y1 + 1, min(h, y2))
        m[y1:y2, x1:x2] = False
    return m


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    mat_rows = []
    stats = {m: {"n": 0, "reliable": 0} for m in ["SPARSE_DIRECT", "FULL_FRAME_DIRECT",
                                                  "BRIDGE_500", "BRIDGE_250", "BRIDGE_125"]}
    resid_all = {m: [] for m in stats}
    drift_all = {m: [] for m in stats}
    scene_jump = {m: 0 for m in stats}
    fail_reasons = {m: [] for m in stats}
    tgt_diag = []   # per reliable pair target-motion
    for c in man["cases"]:
        mid = c["media_id"]
        row = cur.execute("select source_id, relative_path from media_files where id=?", (mid,)).fetchone()
        v = Video(ROOTS.get(row[0]) + "\\" + row[1])
        if not v.ok:
            print("open fail", mid)
            continue
        ts = [f["t_s"] for f in c["frames"]]
        w0 = c["frames"][0]["width"]
        # ROI boxes per semantic ts（映射到分析帧分辨率由 frame 决定——先按 roi50 尺寸取）
        roi_by_t = {}
        for a in roi:
            if a["media_id"] == mid:
                roi_by_t.setdefault(a["frame_timestamp"], []).append(a)
        # 预取
        need = set(ts)
        for i in range(len(ts) - 1):
            for step in BRIDGE.values():
                need.update(np.round(np.arange(ts[i], ts[i + 1] + 1e-9, step), 3).tolist())
        for t in sorted(need):
            v.frame(t)
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            fa = v.frame(t0)
            fb = v.frame(t1)
            if fa is None or fb is None:
                continue
            ga = cv2.cvtColor(fa, cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(fb, cv2.COLOR_BGR2GRAY)
            hA, wA = ga.shape
            sx = wA / float(w0)
            # 前景排除框（curr 帧坐标系 = 分析帧坐标系；roi 在 roi50(≤1280) 系 → 缩放）
            def excl_at(t):
                out_ = []
                for a in roi_by_t.get(t, []):
                    if a["object_name"] == "ISLAND_BODY":
                        continue
                    bb = [v * sx for v in a["bbox_pixel"]]
                    out_.append(bb)
                return out_
            mask_bg = mask_for(ga, excl_at(t0))
            pair_row = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}",
                        "gap_s": round(t1 - t0, 3)}
            for name, fn in [("SPARSE_DIRECT", None), ("FULL_FRAME_DIRECT", "ff")]:
                excl = [] if name == "FULL_FRAME_DIRECT" else excl_at(t0)
                out = estimate_camera_background(fa, fb, excl,
                                                 mode="full_frame" if name == "FULL_FRAME_DIRECT" else "background")
                okm = bool(out.get("chosen_model"))
                res = None
                drift = None
                state = "CAMERA_UNRELIABLE"
                if okm:
                    M33 = to33(out["chosen_M"])
                    Minv = np.linalg.inv(M33)
                    res, _ = residual_after(ga, gb, mask_bg, Minv)
                    wb = cv2.warpPerspective(fb, Minv, (wA, hA))
                    sd = float(np.abs(cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY).astype(np.float32) -
                                     ga.astype(np.float32)).mean() / 40.0)
                    reliable = (res is not None and res <= RESID_MAX and sd <= SCENE_MAX)
                    state = "CAMERA_RELIABLE" if reliable else ("SCENE_DISCONTINUITY" if sd > SCENE_MAX else "CAMERA_UNRELIABLE")
                pair_row[name] = {"state": state, "model": out.get("chosen_model"),
                                  "residual_median_px": (round(res, 3) if res is not None else None),
                                  "scene_diff_after": out.get("scene_difference_score"),
                                  "reason_codes": out.get("reason_codes", [])}
                stats[name]["n"] += 1
                stats[name]["reliable"] += 1 if state == "CAMERA_RELIABLE" else 0
                if res is not None:
                    resid_all[name].append(res)
                if state == "SCENE_DISCONTINUITY":
                    scene_jump[name] += 1
                if state != "CAMERA_RELIABLE":
                    fail_reasons[name].append((out.get("reason_codes") or ["NO_MODEL"])[:2])
            # BRIDGE
            for name, step in BRIDGE.items():
                gap = t1 - t0
                if gap < step * 2:
                    pair_row[name] = {"skipped": True}
                    continue
                tt = np.round(np.arange(t0, t1 + 1e-9, step), 3)
                T = np.eye(3)
                ok_all = True
                models = []
                segs_ok = 0
                seg_fail = 0
                for j in range(len(tt) - 1):
                    fa_ = v.frame(float(tt[j]))
                    fb_ = v.frame(float(tt[j + 1]))
                    excl = excl_at(float(tt[j]))
                    okj, mj, M33, _ = est(fa_, fb_, excl)
                    models.append(mj)
                    if okj and M33 is not None:
                        T = M33 @ T
                        segs_ok += 1
                    else:
                        ok_all = False
                        seg_fail += 1
                        break
                res = drift = None
                state = "CAMERA_UNRELIABLE"
                if ok_all:
                    Minv = np.linalg.inv(T)
                    res, _ = residual_after(ga, gb, mask_bg, Minv)
                    wb = cv2.warpPerspective(fb, Minv, (wA, hA))
                    sd = float(np.abs(cv2.cvtColor(wb, cv2.COLOR_BGR2GRAY).astype(np.float32) -
                                     ga.astype(np.float32)).mean() / 40.0)
                    # round-trip drift：背景点 apply T 再 inv(T)
                    p0 = bg_points(ga, mask_bg)
                    if p0 is not None and len(p0) >= 8:
                        ones = np.ones((len(p0), 1))
                        hp = np.hstack([p0, ones])
                        fwd = (T @ hp.T).T
                        fwd = fwd[:, :2] / fwd[:, 2:3]
                        hf = np.hstack([fwd, ones])
                        back = (Minv @ hf.T).T
                        back = back[:, :2] / back[:, 2:3]
                        drift = float(np.median(np.linalg.norm(back - p0, axis=1)))
                    reliable = (res is not None and res <= RESID_MAX and sd <= SCENE_MAX)
                    state = "CAMERA_RELIABLE" if reliable else ("SCENE_DISCONTINUITY" if sd > SCENE_MAX else "CAMERA_UNRELIABLE")
                pair_row[name] = {"state": state, "segments": len(models), "segs_ok": segs_ok,
                                  "seg_fail": seg_fail, "models": list(dict.fromkeys(models)),
                                  "composed_valid": ok_all,
                                  "residual_median_px": (round(res, 3) if res is not None else None),
                                  "roundtrip_drift_px": (round(drift, 3) if drift is not None else None),
                                  "scene_diff_after": (round(sd, 3) if ok_all else None)}
                stats[name]["n"] += 1
                stats[name]["reliable"] += 1 if state == "CAMERA_RELIABLE" else 0
                if res is not None:
                    resid_all[name].append(res)
                if drift is not None:
                    drift_all[name].append(drift)
                if state == "SCENE_DISCONTINUITY":
                    scene_jump[name] += 1
                if state != "CAMERA_RELIABLE":
                    fail_reasons[name].append(f"seg_fail={seg_fail}")
            # Target motion diagnostic（仅在本 pair 有任一可靠方法时，对目标框补偿前后 diff）
            best_state = min((pair_row.get(m, {}).get("state", "X") for m in stats),
                             key=lambda s: 0 if s == "CAMERA_RELIABLE" else 1)
            if best_state == "CAMERA_RELIABLE" and c["role"] == "POS" and mid in (27433, 12095, 3571):
                tgt = [a for a in roi_by_t.get(t1, [])
                       if a["object_name"] in ("EXTENSION_TABLETOP", "TABLETOP")]
                if len(tgt) == 1:
                    x1, y1, x2, y2 = [int(x * sx) for x in tgt[0]["bbox_pixel"]]
                    if x2 - x1 >= 8 and y2 - y1 >= 8:
                        cA = ga[y1:y2, x1:x2].astype(np.float32)
                        cB = gb[y1:y2, x1:x2].astype(np.float32)
                        before = float(np.abs(cA - cB).mean() / 40.0)
                        # 用该 pair 最优可靠方法的 Minv？简化用 SPARSE 若可靠否则 bridge250 重算 warp
                        after = None
                        wb = None
                        for mname in ("SPARSE_DIRECT", "BRIDGE_250", "BRIDGE_125"):
                            pr = pair_row.get(mname, {})
                            if pr.get("state") == "CAMERA_RELIABLE" and pr.get("composed_valid", True):
                                # 重新组合拿 Minv（简化：仅当 bridge125/250 且全 ok 时用其矩阵——此处只记 before + 标记）
                                break
                        tgt_diag.append({"case": mid, "pair": f"{t0}->{t1}",
                                         "target_pixel_diff_before": round(before, 4),
                                         "note": "after 需可靠矩阵，单跑时补"})
            mat_rows.append(pair_row)
        v.close()
        print("done case", mid, c["role"])
    # 汇总
    summary = {}
    for m in stats:
        n = stats[m]["n"]
        rel = stats[m]["reliable"]
        rr = resid_all[m]
        dd = drift_all[m]
        def _top_fails(entries, k=5):
            cnt = {}
            for e in entries:
                key = str(e)
                cnt[key] = cnt.get(key, 0) + 1
            return dict(sorted(cnt.items(), key=lambda kv: -kv[1])[:k])
        summary[m] = {
            "pairs": n, "reliable": rel,
            "reliable_pct": round(100.0 * rel / n, 1) if n else None,
            "median_residual": round(float(np.median(rr)), 3) if rr else None,
            "p90_residual": round(float(np.percentile(rr, 90)), 3) if rr else None,
            "median_drift": round(float(np.median(dd)), 3) if dd else None,
            "p90_drift": round(float(np.percentile(dd, 90)), 3) if dd else None,
            "scene_discontinuity": scene_jump[m],
            "top_failures": _top_fails(fail_reasons[m]) if fail_reasons[m] else {}}
    cam_status = "CAM01_PASS" if (summary["BRIDGE_125"]["reliable_pct"] or 0) >= 80 and \
        summary["BRIDGE_125"]["reliable_pct"] >= summary["SPARSE_DIRECT"]["reliable_pct"] + 20 else (
        "CAM01_PARTIAL_NEEDS_REDESIGN" if max(summary[m]["reliable_pct"] or 0 for m in summary) < 80 else
        "CAM01_BRIDGE_HYPOTHESIS_NOT_SUPPORTED")
    # LEAF 决策（用 target before 差：POS3 vs NEG-with-target）
    pos_before = [d["target_pixel_diff_before"] for d in tgt_diag]
    neg_before = []
    for c in man["cases"]:
        if c["role"] != "NEG":
            continue
        mid = c["media_id"]
        # 简化：读取 NEG 目标框 diff 之前先留空（本轮 target diag 只收集了 POS 可靠对）
    best_method = max(summary, key=lambda m: summary[m]["reliable_pct"] or 0)
    leaf_decision = "LEAF_ROI_DEFERRED_CAMERA_BLOCKED" if (summary[best_method]["reliable_pct"] or 0) < 50 else (
        "LEAF_ROI_NOT_YET_REQUIRED" if (summary[best_method]["reliable_pct"] or 0) >= 50 else
        "LEAF_ROI_RECOMMENDED")
    doc = {"experiment": "TREECUT_POSTA3_CAMERA_COMPOSE_V2",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "note": "真 3x3 compose；可靠性=段全 ok+残差≤3+scene≤1.6；漂移=round-trip 中位；与动作 GT 无关",
           "summary": summary, "best_method": best_method,
           "CAM01_STATUS": cam_status,
           "LEAF_ROI_DECISION": leaf_decision,
           "target_motion_diag_pos": {"count": len(tgt_diag),
                                      "mean_before": round(float(np.mean([d["target_pixel_diff_before"] for d in tgt_diag])), 4) if tgt_diag else None}}
    (OUT / "TREECUT_POSTA3_CAMERA_COMPOSE_V2.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json").write_text(
        json.dumps({"cases": mat_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_POSTA3_TARGET_MOTION_DIAGNOSTIC_V2.json").write_text(
        json.dumps({"experiment": "TARGET_MOTION_DIAGNOSTIC_V2", "rows": tgt_diag},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("CAM01_STATUS:", cam_status, "| LEAF:", leaf_decision, "| best:", best_method)
    con.close()


if __name__ == "__main__":
    main()
