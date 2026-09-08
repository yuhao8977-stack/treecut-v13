# -*- coding: utf-8 -*-
"""EH01 M1 §17-§19：GFTT support-hull structural diagnostic + §21 target diagnostic.

对每 GFTT materialized pair：t0/t1 convex hull（GFTT accepted p0/p1）+ 1-patch margin，
结构边只取 hull 内 AND ISLAND_BODY AND 非其它 L3 ROI。symmetric forward/reverse chamfer
（OBJ01 corrected edge=0 DT raw Euclidean）。label: symP90<=12 CONSISTENT / >12 DISAGREEMENT /
无有效 UNKNOWN。role-blind：target diagnostic 最后才读 role。
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


def _obj01():
    spec = importlib.util.spec_from_file_location(
        "obj01", REPO / "scripts" / "posta3_cam01_obj01.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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


def apply_affine(pts, M2x3):
    p = cv2.transform(pts.reshape(-1, 1, 2).astype(np.float32),
                      np.float32(M2x3)).reshape(-1, 2)
    return p


def inv_affine(M2x3):
    M3 = np.vstack([np.asarray(M2x3, dtype=np.float64), [0, 0, 1.0]])
    return np.linalg.inv(M3)[:2]


def main():
    m = _obj01()
    roi = load("TREECUT_POSTA3_HUMAN_ROI_V1.json")["annotations"]
    man = load("TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json")
    gftt_mats = load("TREECUT_CAM01_EH01M1_GFTT_TRANSFORMS.json")["rows"]
    corr_all = load("TREECUT_CAM01_EH01M1_GFTT_CORRESPONDENCES.json")["rows"]
    cam = load("TREECUT_POSTA3_CAMERA_PAIR_MATRIX_V2.json")["cases"]
    cam_by = {}
    for c in cam:
        cam_by[(c["case"], c["pair"])] = (c.get("SPARSE_DIRECT") or {}).get("state")

    gmat = {}
    for r in gftt_mats:
        if r.get("status") == "GFTT_MATERIALIZED_REFERENCE_CANDIDATE":
            gmat[(r["case"], r["pair"])] = r
    corr_by = {(r["case"], r["pair"]): r for r in corr_all}
    role_by = {c["media_id"]: c["role"] for c in man["cases"]}

    struct_rows = []
    vid = {}
    try:
        for (mid, pair) in sorted(gmat.keys()):
            row = {"case": mid, "pair": pair}
            # global state
            row["global_state"] = cam_by.get((mid, pair))
            # structural
            if mid not in vid:
                rowdb = None
                # find source path from manifest
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
                struct_rows.append(row)
                continue
            t0 = float(pair.split("->")[0])
            t1 = float(pair.split("->")[1])
            fr0, fr1 = v.frame(t0), v.frame(t1)
            if fr0 is None or fr1 is None:
                row["structural"] = {"state": "STRUCTURAL_UNKNOWN", "note": "NO_FRAME"}
                struct_rows.append(row)
                continue
            g0 = cv2.cvtColor(fr0, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(fr1, cv2.COLOR_BGR2GRAY)
            # ROI per t
            A_w = next(c for c in man["cases"] if c["media_id"] == mid)["frames"][0]["width"]
            A_h = next(c for c in man["cases"] if c["media_id"] == mid)["frames"][0]["height"]

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
                struct_rows.append(row)
                continue
            others0 = [b for n, b in a0 if n != "ISLAND_BODY"]
            others1 = [b for n, b in a1 if n != "ISLAND_BODY"]
            cr = corr_by.get((mid, pair))
            corr = cr.get("corr", []) if cr else []
            if len(corr) < 4:
                row["structural"] = {"state": "STRUCTURAL_UNKNOWN", "note": "SUPPORT<4"}
                struct_rows.append(row)
                continue
            P0 = np.float32([[c["p0"][0], c["p0"][1]] for c in corr])
            P1 = np.float32([[c["p1"][0], c["p1"][1]] for c in corr])
            # hull margin 1 patch raw stride ≈ 14 (GFTT 无 scale 概念 → 用 14px 保守，仅 mask 粗化)
            km0 = hull_mask_from_pts(P0, ib0[0], 14.0, g0.shape)
            km1 = hull_mask_from_pts(P1, ib1[0], 14.0, g1.shape)
            # 排除其它 L3 ROI（在 island_mask 语义 = others 排除）
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
            M2x3 = gmat[(mid, pair)].get("M2x3")
            row["structural"] = {"n_edge_t0": len(e0p), "n_edge_t1": len(e1p)}
            if M2x3 and len(e0p) >= 4 and len(e1p) >= 4:
                dt1 = raw_dt_to_edges(g1.shape, e1p)
                dt0 = raw_dt_to_edges(g0.shape, e0p)
                wf = apply_affine(e0p, M2x3)
                wy = np.clip(np.round(wf[:, 1]).astype(int), 0, g1.shape[0] - 1)
                wx = np.clip(np.round(wf[:, 0]).astype(int), 0, g1.shape[1] - 1)
                fwd = chamfer_stats(dt1[wy, wx])
                try:
                    Minv = inv_affine(M2x3)
                    wr = apply_affine(e1p, Minv)
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
            struct_rows.append(row)
    finally:
        for v in vid.values():
            try:
                v.close()
            except Exception:
                pass
    (OUT / "TREECUT_CAM01_EH01M1_STRUCTURAL_DIAGNOSTIC.json").write_text(
        json.dumps({"rows": struct_rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== §21 target diagnostic（role-blind 后才读 role） =====
    def tgt_ok(mid, t):
        b = [a for a in roi if a["media_id"] == mid and a["frame_timestamp"] == t]
        ex = [a for a in b if a["object_name"] == "EXTENSION_TABLETOP"]
        if len(ex) == 1:
            return True
        tp = [a for a in b if a["object_name"] == "TABLETOP"]
        return len(ex) == 0 and len(tp) == 1

    td = {"POS": [], "NEG": []}
    for row in struct_rows:
        mid, pair = row["case"], row["pair"]
        rl = role_by.get(mid)
        if rl not in ("POS", "NEG"):
            continue
        t0, t1 = [float(x) for x in pair.split("->")]
        ok = tgt_ok(mid, t0) and tgt_ok(mid, t1)
        td[rl].append({"case": mid, "pair": pair, "target_valid": bool(ok),
                       "materialized": True,
                       "deterministic": gmat[(mid, pair)]["deterministic_rebuild"],
                       "structural": (row.get("structural") or {}).get("state"),
                       "global_state": row.get("global_state")})
    out = {"POS": {"count": len(td["POS"]),
                   "target_valid": sum(1 for x in td["POS"] if x["target_valid"]),
                   "rows": td["POS"]},
           "NEG": {"count": len(td["NEG"]),
                   "target_valid": sum(1 for x in td["NEG"] if x["target_valid"]),
                   "rows": td["NEG"]},
           "NEG_MATERIALIZED_REFERENCE_TARGET_VALID": sum(
               1 for x in td["NEG"] if x["target_valid"]),
           "NEG_STRONG_REFERENCE_TARGET_VALID": 0,  # 强度等级等 EH02，禁止升级
           "note": "NEG materialized target-valid ≠ NEG strong；强度等 EH02 决定"}
    (OUT / "TREECUT_CAM01_EH01M1_TARGET_DIAGNOSTIC.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    sc = Counter((r.get("structural") or {}).get("state") for r in struct_rows)
    print("structural labels:", dict(sc))
    print("NEG target-valid materialized:", out["NEG"]["target_valid"])
    print("POS target-valid materialized:", out["POS"]["target_valid"])
    # NEG focus pairs
    for x in td["NEG"]:
        if x["case"] in (1641, 2543):
            print("NEG focus:", x["case"], x["pair"], "target_valid:", x["target_valid"],
                  "structural:", x["structural"], "deterministic:", x["deterministic"])


if __name__ == "__main__":
    main()
