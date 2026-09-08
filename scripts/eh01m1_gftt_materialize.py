# -*- coding: utf-8 -*-
"""CAM01 EH01 M1 — V23 GFTT EXACT REPLAY + TRANSFORM MATERIALIZATION.

权威真值：reports/storage/TREECUT_CAM01_V23_METHOD_MATRIX.json（commit 09e3b5b,
blob 98e74be9973097e7e02cc708482c1be5ea1d4da7）—— 不用 V23 REPORT.md 文字。
只 replay GFTT_LK_LOCAL，冻结 V23 参数（见 EH01M1_CONFIG.json）。
§8 fingerprint gate：36/36 pair state + fold state 全一致才 materialize。
materialize 仅 historical+replay 双 VALIDATED，命名 DERIVED_V23_GFTT_REFERENCE_TRANSFORM。
role-blind：直到 §21 target diagnostic 前不读 role。
"""
import cv2
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
HIST = OUT / "TREECUT_CAM01_V23_METHOD_MATRIX.json"
sys.stdout.reconfigure(encoding="utf-8")

ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
WMAX = 960
CELL = 40
CONFIG = {"analysis_width_max": 960, "grid_cell": 40,
          "ransac_thr": 3.0, "fit_inlier_min": 0.45,
          "holdout_min": 8, "holdout_median_max_px": 3.0,
          "gftt": {"maxCorners": 300, "qualityLevel": 0.02,
                   "minDistance": 6, "lk_win": 21, "lk_maxLevel": 3,
                   "fb_max_px": 3.0}}
CRIT = (0.45, 8, 3.0)  # inlier, holdout_min, median
PROV = {"source_artifact_commit": "09e3b5b",
        "source_artifact_blob": "98e74be9973097e7e02cc708482c1be5ea1d4da7",
        "script_commit": "09e3b5b (scripts/posta3_cam01_v23.py)"}


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


def fold_split(p0):
    gx = np.floor(p0[:, 0] / CELL).astype(int)
    gy = np.floor(p0[:, 1] / CELL).astype(int)
    return (gx + gy) % 2


def holdout_stats(errs):
    e = np.asarray(errs)
    if len(e) == 0:
        return None
    return {"n": int(len(e)), "median_px": round(float(np.median(e)), 3),
            "p90_px": round(float(np.percentile(e, 90)), 3)}


def validate_pairs(p0, p1):
    fold = fold_split(p0)
    res = {"folds": {}}
    for fitf, valf in ((0, 1), (1, 0)):
        fi = fold == fitf
        vi = fold == valf
        rec = {"fit_n": int(fi.sum()), "holdout_n": int(vi.sum())}
        if int(fi.sum()) < 6 or int(vi.sum()) < CRIT[1]:
            rec["state"] = "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"
            res["folds"][f"fit{fitf}val{valf}"] = rec
            continue
        M, inl = cv2.estimateAffinePartial2D(p0[fi], p1[fi], method=cv2.RANSAC,
                                             ransacReprojThreshold=CONFIG["ransac_thr"])
        if M is None or inl is None:
            rec["state"] = "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT"
            res["folds"][f"fit{fitf}val{valf}"] = rec
            continue
        ii = inl.ravel() == 1
        fit_inl = float(ii.mean())
        p1p = cv2.transform(p0[vi].reshape(-1, 1, 2), M).reshape(-1, 2)
        err = np.linalg.norm(p1p - p1[vi], axis=1)
        hs = holdout_stats(err)
        for k, v in hs.items():
            rec[k] = v
        rec["fit_inlier_ratio"] = round(fit_inl, 3)
        rec["state"] = "VALIDATED" if (rec["holdout_n"] >= CRIT[1] and fit_inl >= CRIT[0]
                                       and hs["median_px"] <= CRIT[2]) else "NOT_VALIDATED"
        res["folds"][f"fit{fitf}val{valf}"] = rec
    sts = [v["state"] for v in res["folds"].values()]
    if len(sts) == 2 and all(s == "VALIDATED" for s in sts):
        res["pair_state"] = "LOCAL_ANCHOR_VALIDATED"
    elif len(sts) == 2 and any(s == "VALIDATED" for s in sts):
        res["pair_state"] = "LOCAL_ANCHOR_PARTIAL"
    elif len(sts) == 2 and all(s == "LOCAL_ANCHOR_VALIDATION_INSUFFICIENT" for s in sts):
        res["pair_state"] = "LOCAL_ANCHOR_INSUFFICIENT"
    else:
        res["pair_state"] = "LOCAL_ANCHOR_NOT_VALIDATED"
    return res


def gftt_tracks(g0, g1, mask0):
    """V23 GFTT_LK_LOCAL exact：backward LK init=None（无 initial flow），FB<=3。"""
    pts = cv2.goodFeaturesToTrack(g0, mask=(mask0.astype(np.uint8)) * 255,
                                  maxCorners=CONFIG["gftt"]["maxCorners"],
                                  qualityLevel=CONFIG["gftt"]["qualityLevel"],
                                  minDistance=CONFIG["gftt"]["minDistance"], blockSize=7)
    if pts is None or len(pts) < 12:
        return None
    p1t, st, _ = cv2.calcOpticalFlowPyrLK(
        g0, g1, pts, None,
        winSize=(CONFIG["gftt"]["lk_win"], CONFIG["gftt"]["lk_win"]),
        maxLevel=CONFIG["gftt"]["lk_maxLevel"])
    p0b, stb, _ = cv2.calcOpticalFlowPyrLK(
        g1, g0, p1t, None,
        winSize=(CONFIG["gftt"]["lk_win"], CONFIG["gftt"]["lk_win"]),
        maxLevel=CONFIG["gftt"]["lk_maxLevel"])
    ok = (st.ravel() == 1) & (stb.ravel() == 1)
    if ok.any():
        d = np.linalg.norm(p0b[ok].reshape(-1, 2) - pts[ok].reshape(-1, 2), axis=1)
        ok = ok.copy()
        ok[ok] = d <= CONFIG["gftt"]["fb_max_px"]
    if ok.sum() < 12:
        return None
    return (pts[ok].reshape(-1, 2).astype(np.float32),
            p1t[ok].reshape(-1, 2).astype(np.float32))


def materialize_affine(p0, p1, thr=3.0):
    """DERIVED transform：完整 FB<=3 accepted，estimateAffinePartial2D RANSAC thr=3.0。"""
    M, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                         ransacReprojThreshold=thr)
    if M is None or inl is None:
        return None, None
    return M, float((inl.ravel() == 1).mean())


def predict_grid(T, ib, grid=(9, 6)):
    x0, y0, x1, y1 = [float(v) for v in ib]
    xs = np.linspace(x0 + (x1 - x0) * 0.08, x0 + (x1 - x0) * 0.92, grid[0])
    ys = np.linspace(y0 + (y1 - y0) * 0.08, y0 + (y1 - y0) * 0.92, grid[1])
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    p1p = cv2.transform(pts.reshape(-1, 1, 2).astype(np.float32),
                        np.float32(T)).reshape(-1, 2)
    return p1p


def transform_disagreement(Ta, Tb, ib):
    pa = predict_grid(Ta, ib)
    pb = predict_grid(Tb, ib)
    d = np.linalg.norm(pa - pb, axis=1)
    return float(np.median(d)), float(np.percentile(d, 90))


def main():
    # config hash
    cfg_str = json.dumps(CONFIG, sort_keys=True, ensure_ascii=False)
    cfg_hash = hashlib.sha256(cfg_str.encode("utf-8")).hexdigest()
    (OUT / "TREECUT_CAM01_EH01M1_CONFIG.json").write_text(
        json.dumps({"experiment": "EH01M1_CONFIG", "config": CONFIG,
                    "config_sha256": cfg_hash,
                    "frozen_from": "V23 @ 09e3b5b (TREECUT_CAM01_V23_METHOD_CONFIG.json)",
                    "note": "只 replay GFTT_LK_LOCAL；V23 exact params 原样"}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    roi = json.loads(ROI_JSON.read_text(encoding="utf-8"))["annotations"]
    hist_rows = json.loads(HIST.read_text(encoding="utf-8"))["pairs"]
    hist_by = {(r["case"], r["pair"]): r for r in hist_rows}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cv2.setRNGSeed(0)

    # role-blind：replay 阶段不输出 role
    replay_rows = []
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
        roi_by_t = {}
        for a in roi:
            if a["media_id"] == mid:
                roi_by_t.setdefault(a["frame_timestamp"], []).append(a)
        for t in ts:
            v.frame(t)
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            fa, fb = v.frame(t0), v.frame(t1)
            if fa is None or fb is None:
                continue
            h, w = fa.shape[:2]
            sx = w / float(A_w)
            sy = h / float(A_h)
            ga = cv2.cvtColor(fa, cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(fb, cv2.COLOR_BGR2GRAY)
            shape = ga.shape

            def ann(t):
                return [(a["object_name"],
                         [a["bbox_pixel"][0] * sx, a["bbox_pixel"][1] * sy,
                          a["bbox_pixel"][2] * sx, a["bbox_pixel"][3] * sy])
                        for a in roi_by_t.get(t, [])]

            a0, a1 = ann(t0), ann(t1)
            ib0 = [b for n, b in a0 if n == "ISLAND_BODY"]
            ib1 = [b for n, b in a1 if n == "ISLAND_BODY"]
            rec = {"case": mid, "pair": f"{t0}->{t1}",
                   "island_present": bool(len(ib0) == 1 and len(ib1) == 1)}
            if len(ib0) == 1 and len(ib1) == 1:
                o0 = [b for n, b in a0 if n != "ISLAND_BODY"]
                o1 = [b for n, b in a1 if n != "ISLAND_BODY"]
                mA0 = island_mask(shape, ib0[0], o0)
                mA1 = island_mask(shape, ib1[0], o1)
                mm = gftt_tracks(ga, gb, mA0)
                if mm is None:
                    rec["pair_state"] = "LOCAL_ANCHOR_INSUFFICIENT"
                    rec["n_tracks"] = 0
                    rec["corr"] = []
                    replay_rows.append(rec)
                    continue
                p0, p1 = mm
                rec["n_tracks"] = int(len(p0))
                resv = validate_pairs(p0, p1)
                rec["pair_state"] = resv["pair_state"]
                rec["folds"] = resv["folds"]
                rec["corr"] = [{"p0": [round(float(x), 3), round(float(y), 3)],
                                "p1": [round(float(u), 3), round(float(v), 3)]}
                               for (x, y), (u, v) in zip(p0, p1)]
                rec["ib0"] = [round(float(z), 2) for z in ib0[0]]
            else:
                rec["pair_state"] = "NO_ISLAND"
                rec["n_tracks"] = 0
                rec["corr"] = []
            replay_rows.append(rec)
        v.close()
        print("case done", mid, flush=True)
    con.close()

    # ===== §8/§9 fingerprint gate =====
    hist_gftt = {}
    for r in hist_rows:
        g = r["methods"].get("GFTT_LK_LOCAL")
        if g is None:
            continue
        # 历史语义：tracks<12 → state:INSUFFICIENT（无 pair_state）；归一为 LOCAL_ANCHOR_INSUFFICIENT 等价
        hstate = g.get("pair_state")
        if hstate is None and g.get("state") == "INSUFFICIENT":
            hstate = "LOCAL_ANCHOR_INSUFFICIENT"
        hist_gftt[(r["case"], r["pair"])] = {
            "pair_state": hstate,
            "folds": g.get("folds", {}),
            "hist_validated": g.get("pair_state") == "LOCAL_ANCHOR_VALIDATED"}
    hist_val = sum(1 for v in hist_gftt.values() if v["hist_validated"])
    replay_by = {(r["case"], r["pair"]): r for r in replay_rows}
    fp = []
    for (mid, pair) in sorted(replay_by.keys()):
        hr = hist_gftt.get((mid, pair), {})
        rr = replay_by[(mid, pair)]
        hstate = hr.get("pair_state")
        rstate = rr.get("pair_state")
        if (mid, pair) not in hist_gftt:
            fp.append({"case": mid, "pair": pair, "note": "NO_HISTORICAL_GFTT_ENTRY"})
            continue
        # fold states
        hf = hr.get("folds", {})
        rf = rr.get("folds", {})
        fold_cmp = {}
        for fk in ("fit0val1", "fit1val0"):
            hfv = (hf.get(fk) or {}).get("state")
            rfv = (rf.get(fk) or {}).get("state")
            fold_cmp[fk] = {"hist": hfv, "replay": rfv, "match": hfv == rfv}
        fp.append({"case": mid, "pair": pair,
                   "hist_pair": hstate, "replay_pair": rstate,
                   "pair_match": hstate == rstate,
                   "fold": fold_cmp,
                   "fold_all_match": all(fc["match"] for fc in fold_cmp.values())})
    pair_match_all = all(x.get("pair_match", False) is True for x in fp if "pair_match" in x)
    fold_match_all = all(x.get("fold_all_match", False) is True for x in fp if "fold_all_match" in x)
    replay_val = sum(1 for r in replay_rows if r.get("pair_state") == "LOCAL_ANCHOR_VALIDATED")
    fp_out = {"historical_gftt_validated": hist_val,
              "replay_gftt_validated": replay_val,
              "pair_state_fingerprint_match_36": int(pair_match_all),
              "fold_state_fingerprint_match": int(fold_match_all),
              "rows": fp,
              "gate_passed": bool(pair_match_all and fold_match_all)}
    (OUT / "TREECUT_CAM01_EH01M1_REPLAY_FINGERPRINT.json").write_text(
        json.dumps(fp_out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("hist validated:", hist_val, "| replay validated:", replay_val,
          "| pair fp:", pair_match_all, "| fold fp:", fold_match_all)
    if not (pair_match_all and fold_match_all):
        print("M1_REPLAY_MISMATCH — STOP, no materialization")
        return

    # ===== §10-12 materialize（双 VALIDATED） =====
    cv2.setRNGSeed(0)
    mats = []
    for (mid, pair) in sorted(replay_by.keys()):
        rr = replay_by[(mid, pair)]
        hr = hist_gftt.get((mid, pair), {})
        both_val = (rr.get("pair_state") == "LOCAL_ANCHOR_VALIDATED" and
                    hr.get("hist_validated"))
        row = {"case": mid, "pair": pair,
               "pair_state_replay": rr.get("pair_state"),
               "pair_state_hist": hr.get("pair_state"),
               "can_materialize": both_val}
        if not both_val:
            row["matrix"] = None
            mats.append(row)
            continue
        corr = rr.get("corr", [])
        P0 = np.float32([[x["p0"][0], x["p0"][1]] for x in corr])
        P1 = np.float32([[x["p1"][0], x["p1"][1]] for x in corr])
        M1, inl1 = materialize_affine(P0, P1, CONFIG["ransac_thr"])
        # 第二次重建（同 seed 已设）确定性
        cv2.setRNGSeed(0)
        M2, inl2 = materialize_affine(P0, P1, CONFIG["ransac_thr"])
        ib = rr.get("ib0")
        det_ok = False
        disc = None
        if M1 is not None and M2 is not None and ib:
            med, _ = transform_disagreement(M1, M2, ib)
            disc = med
            det_ok = med < 1e-6
        row.update({
            "n_accepted": len(corr),
            "fit_all_inlier_ratio": round(inl1, 3) if inl1 is not None else None,
            "matrix": np.vstack([M1, [0, 0, 1.0]]).tolist() if M1 is not None else None,
            "M2x3": M1.tolist() if M1 is not None else None,
            "translation": [round(float(M1[0, 2]), 4), round(float(M1[1, 2]), 4)] if M1 is not None else None,
            "scale_x": round(float(np.hypot(M1[0, 0], M1[1, 0])), 5) if M1 is not None else None,
            "scale_y": round(float(np.hypot(M1[0, 1], M1[1, 1])), 5) if M1 is not None else None,
            "rotation_deg": round(float(np.degrees(np.arctan2(M1[1, 0], M1[0, 0]))), 3) if M1 is not None else None,
            "deterministic_rebuild": bool(det_ok),
            "deterministic_disagreement_med_px": disc,
            "status": ("GFTT_MATERIALIZED_REFERENCE_CANDIDATE" if (M1 is not None and det_ok)
                       else "TRANSFORM_NONDETERMINISTIC" if M1 is not None
                       else "MATERIALIZE_FAILED"),
            "source": PROV})
        mats.append(row)
    mat_ok = [r for r in mats if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE"]
    (OUT / "TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json").write_text(
        json.dumps({"rows": mats,
                    "note": "DERIVED_V23_GFTT_REFERENCE_TRANSFORM（非历史原始 matrix）；"
                            "affine RANSAC thr=3.0 on full FB<=3 accepted"},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_EH01M1_GFTT_CORRESPONDENCES.json").write_text(
        json.dumps({"rows": [{"case": r["case"], "pair": r["pair"],
                              "pair_state": r.get("pair_state"),
                              "n_tracks": r.get("n_tracks"),
                              "corr": r.get("corr", [])} for r in replay_rows]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("materialized:", len(mat_ok), "/", hist_val)


if __name__ == "__main__":
    main()
