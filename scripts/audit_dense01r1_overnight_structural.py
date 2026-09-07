# -*- coding: utf-8 -*-
"""DENSE01R1 OVERNIGHT — AUDIT-ONLY STRUCTURAL DIAGNOSTIC (§20)。

正式 DENSE01R1 未实现 support-hull 结构通道（NOT_IMPLEMENTED，占位）。本脚本按 §20
新增 audit-only structural validator：对每 pair 用 accepted DINO_LK correspondences
（replay raw 的 corr 明细）建立 transform，用 OBJ01 corrected raw 结构边 chamfer
衡量几何残差是否对应真实结构错位。不改正式代码；不作 PASS/FAIL gate。

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
MANIFEST = OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json"
ROI_JSON = OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json"
REPLAY = OUT / "TREECUT_DENSE01R1_OVERNIGHT_REPLAY_replay1.json"
ROOTS = {1: r"\\X1\素材盘01\已处理素材\卖点展示类素材",
         2: r"\\X1\素材盘01\已处理素材\效果展示类素材",
         3: r"\\X1\素材盘01\已处理素材\JianyingPro Presets",
         4: r"\\X1\素材盘01\未处理素材\【工厂】"}
DYNAMIC = {"EXTENSION_TABLETOP", "PERSON", "HAND", "DRAWER", "CABINET_DOOR",
           "TRACK_SOCKET", "SOCKET_MODULE", "ROCK_TABLE_LEG", "ACRYLIC_TABLE_LEG",
           "EMBEDDED_APPLIANCE", "OTHER_MOVING_PART"}
sys.stdout.reconfigure(encoding="utf-8")


def _obj01():
    spec = importlib.util.spec_from_file_location(
        "obj01", REPO / "scripts" / "posta3_cam01_obj01.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def pct(a, q):
    a = np.asarray(a, dtype=np.float64)
    return round(float(np.percentile(a, q)), 3) if len(a) else None


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


def main():
    m = _obj01()
    raw = json.loads(REPLAY.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    roi = json.loads(ROI_JSON.read_text(encoding="utf-8"))["annotations"]
    # video cache per case
    vids = {}
    try:
        rows = []
        all_d = {"ANISO": [], "ISO": []}
        for c in man["cases"]:
            mid = c["media_id"]
            vpath = ROOTS.get(c["source_id"], "") + "\\" + c["relative_path"]
            v = Video(vpath)
            if not v.ok:
                continue
            A_w = c["frames"][0]["width"]
            A_h = c["frames"][0]["height"]
            for f in c["frames"]:
                v.frame(f["t_s"])
            rbt = {}
            for a in roi:
                if a["media_id"] == mid:
                    rbt.setdefault(a["frame_timestamp"], []).append(a)
            for pr in raw["pairs"]:
                if pr["case"] != mid:
                    continue
                t0, t1 = [float(x) for x in pr["pair"].split("->")]

                def ann(t):
                    fr = v.frame(t)
                    h, w = fr.shape[:2]
                    sx, sy = w / float(A_w), h / float(A_h)
                    return [(a["object_name"],
                             [a["bbox_pixel"][0] * sx, a["bbox_pixel"][1] * sy,
                              a["bbox_pixel"][2] * sx, a["bbox_pixel"][3] * sy])
                            for a in rbt.get(t, [])]

                a0, a1 = ann(t0), ann(t1)
                ib0 = [b for n, b in a0 if n == "ISLAND_BODY"]
                ib1 = [b for n, b in a1 if n == "ISLAND_BODY"]
                if len(ib0) != 1 or len(ib1) != 1:
                    continue
                fr0, fr1 = v.frame(t0), v.frame(t1)
                g0 = cv2.cvtColor(fr0, cv2.COLOR_BGR2GRAY)
                g1 = cv2.cvtColor(fr1, cv2.COLOR_BGR2GRAY)
                dyn0 = [b for n, b in a0 if n in DYNAMIC]
                dyn1 = [b for n, b in a1 if n in DYNAMIC]
                # t1 结构边（raw）
                e1_mask, e1_pts = m.canon_clean_edges(ib1[0], dyn1, g1, g1.shape)
                if e1_pts is None or len(e1_pts) < 8:
                    continue
                # accepted corr（production 语义）
                acc = [(x["p0"], x.get("p1_lk") or x["p1_sub"])
                       for x in pr.get("corr", [])
                       if x.get("fwd_ok") and x.get("in_island") and not x.get("in_dynamic")]
                if len(acc) < 4:
                    continue
                P0 = np.float32([p[0] for p in acc])
                P1 = np.float32([p[1] for p in acc])
                thr = pr.get("ransac_thr", 4.0)
                row = {"case": mid, "pair": pr["pair"], "state": pr["state"],
                       "n_corr": len(acc)}
                for mdl in ("PARTIAL_AFFINE", "HOMOGRAPHY"):
                    if mdl == "PARTIAL_AFFINE":
                        T, _ = cv2.estimateAffinePartial2D(P0, P1, method=cv2.RANSAC,
                                                           ransacReprojThreshold=thr)
                        if T is None:
                            row[mdl] = {"struct": None, "note": "NO_FIT"}
                            continue
                        T3 = np.vstack([T, [0, 0, 1]])
                    else:
                        T3, _ = cv2.findHomography(P0, P1, cv2.RANSAC, thr)
                        if T3 is None:
                            row[mdl] = {"struct": None, "note": "NO_FIT"}
                            continue
                    # t0 结构边 → 用 T3 变换 → t1 结构 DT chamfer
                    e0_mask, e0_pts = m.canon_clean_edges(ib0[0], dyn0, g0, g0.shape)
                    if e0_pts is None or len(e0_pts) < 4:
                        row[mdl] = {"struct": None, "note": "NO_EDGE_T0"}
                        continue
                    warped = m.apply_transform(e0_pts, T3)
                    dt1 = m.raw_dt_to_edges(g1.shape, e1_pts)
                    d = m.chamfer_dist(dt1, warped)
                    row[mdl] = {"n_edge_t0": int(len(e0_pts)),
                                "n_edge_t1": int(len(e1_pts)),
                                "struct": ({"median": round(float(np.median(d)), 3),
                                            "p90": round(float(np.percentile(d, 90)), 3),
                                            "p95": round(float(np.percentile(d, 95)), 3),
                                            "max": round(float(np.max(d)), 3)}
                                           if d is not None and len(d) else None)}
                    if row[mdl].get("struct"):
                        all_d["ANISO" if mdl == "PARTIAL_AFFINE" else "ISO"].append(
                            list(d))
                rows.append(row)
            v.close()
        pooled = {"ANISO": {"n": sum(len(x) for x in all_d["ANISO"]),
                            "median": pct(np.concatenate(all_d["ANISO"]) if all_d["ANISO"] else [], 50),
                            "p90": pct(np.concatenate(all_d["ANISO"]) if all_d["ANISO"] else [], 90),
                            "p95": pct(np.concatenate(all_d["ANISO"]) if all_d["ANISO"] else [], 95)},
                  "ISO": {"n": sum(len(x) for x in all_d["ISO"]),
                          "median": pct(np.concatenate(all_d["ISO"]) if all_d["ISO"] else [], 50),
                          "p90": pct(np.concatenate(all_d["ISO"]) if all_d["ISO"] else [], 90),
                          "p95": pct(np.concatenate(all_d["ISO"]) if all_d["ISO"] else [], 95)}}
        out = {"experiment": "DENSE01R1_OVERNIGHT_STRUCTURAL_DIAGNOSTIC",
               "note": "audit-only support-hull structural validator（正式代码未实现结构通道，NOT_IMPLEMENTED）; "
                       "raw chamfer px: t0 结构边经 corr-fit transform 投影到 t1 结构 DT",
               "rows": rows, "pooled": pooled}
        (OUT / "TREECUT_DENSE01R1_OVERNIGHT_STRUCTURAL_DIAGNOSTIC.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"rows": len(rows), "pooled": pooled}, ensure_ascii=False, indent=1))
    finally:
        pass


if __name__ == "__main__":
    main()
