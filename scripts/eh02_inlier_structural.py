# -*- coding: utf-8 -*-
"""EH02 §3-§5: GFTT materialization rebuild w/ RANSAC inlier mask + inlier support-hull
structural correction.

§3 重新执行相同 estimateAffinePartial2D on full GFTT accepted tracks，保存 ransac_inlier_mask
/inlier indices/inlier p0/p1；确认新重建 matrix 与 M1 materialized matrix fixed-grid
disagreement < 容差（否则 EH02_M1_TRANSFORM_REBUILD_MISMATCH STOP）。
§4-§5 用 RANSAC inliers 重建 convex hull（margin 14px 保持），重算 symmetric chamfer，
label 沿用 symP90<=12 CONSISTENT/>12 DISAGREEMENT/无=UNKNOWN。
role-blind：不读 role。
"""
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
STRUCT_SYM_P90_MAX = 12.0
sys.stdout.reconfigure(encoding="utf-8")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


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
            if w > 960:
                fr = cv2.resize(fr, (960, int(h * 960 / w)), interpolation=cv2.INTER_AREA)
        self.cache[key] = fr
        return fr

    def close(self):
        if self.cap:
            self.cap.release()


def hull_mask_from_pts(pts, ib, margin, shape):
    mask = np.zeros(shape, dtype=bool)
    if len(pts) < 3:
        return mask
    hull = cv2.convexHull(np.float32(pts)).reshape(-1, 2)
    img = np.zeros(shape, dtype=np.uint8)
    cv2.fillConvexPoly(img, hull.astype(np.int32), 1)
    k = max(1, int(round(margin)))
    img = cv2.dilate(img, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    mask = img > 0
    x1, y1, x2, y2 = [int(v) for v in ib]
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(shape[1], x2); y2 = min(shape[0], y2)
    body = np.zeros(shape, dtype=bool)
    body[y1:y2, x1:x2] = True
    return mask & body


def canon_clean_edges_masked(ib, dyn_boxes, gray_raw, shape_raw, keep_mask, canon=256):
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


def predict_grid(M2x3, ib, grid=(9, 6)):
    x0, y0, x1, y1 = [float(v) for v in ib]
    xs = np.linspace(x0 + (x1 - x0) * 0.08, x0 + (x1 - x0) * 0.92, grid[0])
    ys = np.linspace(y0 + (y1 - y0) * 0.08, y0 + (y1 - y0) * 0.92, grid[1])
    gx, gy = np.meshgrid(xs, ys)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    p1p = cv2.transform(pts.reshape(-1, 1, 2).astype(np.float32),
                        np.float32(M2x3)).reshape(-1, 2)
    return p1p


def grid_disagreement(Ma, Mb, ib):
    pa = predict_grid(Ma, ib)
    pb = predict_grid(Mb, ib)
    d = np.linalg.norm(pa - pb, axis=1)
    return float(np.median(d))


def inv_affine(M2x3):
    M3 = np.vstack([np.asarray(M2x3, dtype=np.float64), [0, 0, 1.0]])
    return np.linalg.inv(M3)[:2]


def main():
    corr_all = load("TREECUT_CAM01_EH01M1_GFTT_CORRESPONDENCES.json")["rows"]
    gftt_mats = load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    m1_by = {}
    for r in gftt_mats:
        if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE":
            m1_by[(r["case"], r["pair"])] = r
    corr_by = {(r["case"], r["pair"]): r for r in corr_all}

    # ===== §3 rebuild with inlier mask =====
    rebuilt = []
    mismatch = []
    cv2.setRNGSeed(0)
    for (mid, pair) in sorted(m1_by.keys()):
        m1 = m1_by[(mid, pair)]
        cr = corr_by.get((mid, pair))
        corr = cr.get("corr", []) if cr else []
        P0 = np.float32([[c["p0"][0], c["p0"][1]] for c in corr])
        P1 = np.float32([[c["p1"][0], c["p1"][1]] for c in corr])
        M, inl = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                             ransacReprojThreshold=3.0)
        if M is None or inl is None:
            rebuilt.append({"case": mid, "pair": pair, "status": "REBUILD_FAIL"})
            continue
        inl_mask = (inl.ravel() == 1)
        row = {"case": mid, "pair": pair,
               "n_tracks": int(len(P0)),
               "n_inliers": int(inl_mask.sum()),
               "inlier_ratio": round(float(inl_mask.mean()), 3),
               "ransac_inlier_mask": [bool(x) for x in inl_mask],
               "inlier_indices": [int(i) for i in np.nonzero(inl_mask)[0]],
               "inlier_p0": [[round(float(x), 3), round(float(y), 3)]
                             for (x, y) in P0[inl_mask]],
               "inlier_p1": [[round(float(x), 3), round(float(y), 3)]
                             for (x, y) in P1[inl_mask]],
               "matrix_M2x3": M.tolist(),
               "m1_matrix_M2x3": m1.get("M2x3")}
        # matrix consistency vs M1
        ib = None  # filled below from roi
        row["status"] = "REBUILT"
        rebuilt.append(row)
    # matrix consistency check needs island bbox
    roi = load("TREECUT_POSTA3_HUMAN_ROI_V1.json")["annotations"]
    for row in rebuilt:
        if row.get("status") != "REBUILT":
            continue
        mid, pair = row["case"], row["pair"]
        t0 = float(pair.split("->")[0])
        ib = None
        for a in roi:
            if a["media_id"] == mid and a["frame_timestamp"] == t0 and a["object_name"] == "ISLAND_BODY":
                ib = a["bbox_pixel"]
                break
        if ib is None:
            row["matrix_consistency"] = "NO_ISLAND"
            continue
        d = grid_disagreement(row["matrix_M2x3"], row["m1_matrix_M2x3"], ib)
        row["matrix_consistency"] = "MATCH" if d < 1e-6 else "MISMATCH"
        row["matrix_disagreement_med_px"] = round(d, 9)
        if d >= 1e-6:
            mismatch.append({"case": mid, "pair": pair, "d": d})
    (OUT / "TREECUT_CAM01_EH02_GFTT_INLIERS.json").write_text(
        json.dumps({"rows": rebuilt,
                    "all_matrix_match": len(mismatch) == 0,
                    "mismatches": mismatch}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("rebuild matrix match:", len(mismatch) == 0, "| inlier rows:", len(rebuilt))
    if mismatch:
        print("EH02_M1_TRANSFORM_REBUILD_MISMATCH — STOP")
        return

    # ===== §4-5 inlier support hull structural =====
    man = load("TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json")
    inl_by = {(r["case"], r["pair"]): r for r in rebuilt}
    rows_out = []
    vid = {}
    try:
        for (mid, pair) in sorted(m1_by.keys()):
            row = {"case": mid, "pair": pair}
            inl = inl_by.get((mid, pair))
            if not inl or inl.get("status") != "REBUILT":
                row["structural"] = {"state": "STRUCTURAL_UNKNOWN", "note": "NO_INLIERS"}
                rows_out.append(row)
                continue
            if mid not in vid:
                c0 = next(c for c in man["cases"] if c["media_id"] == mid)
                vpath = ROOTS.get(c0["source_id"], "") + "\\" + c0["relative_path"]
                v = Video(vpath)
                if v.ok:
                    for f in c0["frames"]:
                        v.frame(f["t_s"])
                vid[mid] = v
            v = vid.get(mid)
            if not v or not v.ok:
                row["structural"] = {"state": "STRUCTURAL_UNKNOWN", "note": "VIDEO_UNAVAILABLE"}
                rows_out.append(row)
                continue
            t0 = float(pair.split("->")[0])
            t1 = float(pair.split("->")[1])
            fr0, fr1 = v.frame(t0), v.frame(t1)
            if fr0 is None or fr1 is None:
                row["structural"] = {"state": "STRUCTURAL_UNKNOWN", "note": "NO_FRAME"}
                rows_out.append(row)
                continue
            g0 = cv2.cvtColor(fr0, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(fr1, cv2.COLOR_BGR2GRAY)
            c0 = next(c for c in man["cases"] if c["media_id"] == mid)
            A_w = c0["frames"][0]["width"]
            A_h = c0["frames"][0]["height"]

            def ann(t):
                fr = v.frame(t)
                h, w = fr.shape[:2]
                sx, sy = w / float(A_w), h / float(A_h)
                return [(a["object_name"],
                         [a["bbox_pixel"][0] * sx, a["bbox_pixel"][1] * sy,
                          a["bbox_pixel"][2] * sx, a["bbox_pixel"][3] * sy])
                        for a in roi if a["media_id"] == mid and a["frame_timestamp"] == t]
            a0, a1 = ann(t0), ann(t1)
            ib0 = [b for n, b in a0 if n == "ISLAND_BODY"]
            ib1 = [b for n, b in a1 if n == "ISLAND_BODY"]
            if len(ib0) != 1 or len(ib1) != 1:
                row["structural"] = {"state": "STRUCTURAL_UNKNOWN", "note": "NO_ISLAND"}
                rows_out.append(row)
                continue
            others0 = [b for n, b in a0 if n != "ISLAND_BODY"]
            others1 = [b for n, b in a1 if n != "ISLAND_BODY"]
            iP0 = np.float32(inl["inlier_p0"])
            iP1 = np.float32(inl["inlier_p1"])
            if len(iP0) < 4:
                row["structural"] = {"state": "STRUCTURAL_UNKNOWN", "note": "INLIER_SUPPORT<4"}
                rows_out.append(row)
                continue
            # inlier-only hull + 14px margin（M1 continuity）+ clip island + excl others
            km0 = hull_mask_from_pts(iP0, ib0[0], 14.0, g0.shape)
            km1 = hull_mask_from_pts(iP1, ib1[0], 14.0, g1.shape)
            for ob in others0:
                ox1, oy1, ox2, oy2 = [int(z) for z in ob]
                oy1 = max(0, oy1); oy2 = min(g0.shape[0], oy2)
                ox1 = max(0, ox1); ox2 = min(g0.shape[1], ox2)
                if ox2 > ox1 and oy2 > oy1:
                    km0[oy1:oy2, ox1:ox2] = False
            for ob in others1:
                ox1, oy1, ox2, oy2 = [int(z) for z in ob]
                oy1 = max(0, oy1); oy2 = min(g1.shape[0], oy2)
                ox1 = max(0, ox1); ox2 = min(g1.shape[1], ox2)
                if ox2 > ox1 and oy2 > oy1:
                    km1[oy1:oy2, ox1:ox2] = False
            _, e0p = canon_clean_edges_masked(ib0[0], others0, g0, g0.shape, km0)
            _, e1p = canon_clean_edges_masked(ib1[0], others1, g1, g1.shape, km1)
            M2x3 = inl["matrix_M2x3"]
            row["structural"] = {"n_inliers": int(len(iP0)),
                                 "n_edge_t0": len(e0p), "n_edge_t1": len(e1p)}
            if len(e0p) >= 4 and len(e1p) >= 4:
                dt1 = raw_dt_to_edges(g1.shape, e1p)
                dt0 = raw_dt_to_edges(g0.shape, e0p)
                wf = cv2.transform(e0p.reshape(-1, 1, 2).astype(np.float32),
                                   np.float32(M2x3)).reshape(-1, 2)
                wy = np.clip(np.round(wf[:, 1]).astype(int), 0, g1.shape[0] - 1)
                wx = np.clip(np.round(wf[:, 0]).astype(int), 0, g1.shape[1] - 1)
                fwd = chamfer_stats(dt1[wy, wx])
                try:
                    Minv = inv_affine(M2x3)
                    wr = cv2.transform(e1p.reshape(-1, 1, 2).astype(np.float32),
                                       np.float32(Minv)).reshape(-1, 2)
                    ry = np.clip(np.round(wr[:, 1]).astype(int), 0, g0.shape[0] - 1)
                    rx = np.clip(np.round(wr[:, 0]).astype(int), 0, g0.shape[1] - 1)
                    rev = chamfer_stats(dt0[ry, rx])
                except Exception:
                    rev = None
                row["structural"]["forward"] = fwd
                row["structural"]["reverse"] = rev
                if fwd and rev:
                    sym = np.concatenate([dt1[wy, wx], dt0[ry, rx]])
                    row["structural"]["symmetric"] = chamfer_stats(sym)
                sym = row["structural"].get("symmetric")
                if sym and sym.get("p90") is not None:
                    row["structural"]["state"] = (
                        "STRUCTURAL_CONSISTENT" if sym["p90"] <= STRUCT_SYM_P90_MAX
                        else "STRUCTURAL_DISAGREEMENT")
                else:
                    row["structural"]["state"] = "STRUCTURAL_UNKNOWN"
            else:
                row["structural"]["state"] = "STRUCTURAL_UNKNOWN"
                row["structural"]["note"] = "EDGE_SUPPORT_INSUFFICIENT"
            rows_out.append(row)
    finally:
        for v in vid.values():
            try:
                v.close()
            except Exception:
                pass
    (OUT / "TREECUT_CAM01_EH02_STRUCTURAL_CORRECTED.json").write_text(
        json.dumps({"rows": rows_out}, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    old = load("TREECUT_CAM01_EH01M1_STRUCTURAL_DIAGNOSTIC.json")["rows"]
    old_by = {(r["case"], r["pair"]): (r.get("structural") or {}).get("state") for r in old}
    new_cnt = Counter((r.get("structural") or {}).get("state") for r in rows_out)
    changed = []
    for r in rows_out:
        k = (r["case"], r["pair"])
        o = old_by.get(k)
        n = (r.get("structural") or {}).get("state")
        if o != n:
            changed.append({"case": r["case"], "pair": r["pair"],
                            "old": o, "new": n,
                            "new_sym_p90": (r.get("structural") or {}).get("symmetric", {}).get("p90")})
    print("old:", dict(Counter(v for v in old_by.values() if v)))
    print("corrected:", dict(new_cnt))
    print("changed:", len(changed))
    for c in changed:
        print(" ", c)


if __name__ == "__main__":
    main()
