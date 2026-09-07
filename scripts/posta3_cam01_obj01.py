#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 CAM01 OBJ01 — Semantic Object Box Anchor Feasibility。

ISLAND_BODY_t0→t1 直接对象级 bbox 变换（ANISO 主 / ISO 对照；无拟合无特征匹配、无旋转发明）。
独立验证：动态排除后的 clean 结构边（全部为 holdout），forward/reverse chamfer 全部在 raw 像素空间
（修正 STRUCT01 三处工具缺陷：DT 方向 edge=0；raw 各向异性真坐标；0 残差非缺失）。
target 相对运动仅诊断（raw vs 补偿后），不做动作判定；不用动作 GT 选模型。
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
CANON = 512
DYNAMIC = {"EXTENSION_TABLETOP", "PERSON", "HAND", "DRAWER", "CABINET_DOOR",
           "TRACK_SOCKET", "SOCKET_MODULE", "ROCK_TABLE_LEG", "ACRYLIC_TABLE_LEG",
           "EMBEDDED_APPLIANCE", "OTHER_MOVING_PART"}
CONFIG = {"canonical": CANON,
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


def box_transform(ib0, ib1, model):
    """对象级 bbox 变换（无拟合）。ANISO: sx,sy+tx,ty；ISO: 中心+几何均 scale。返回 3x3。"""
    x0, y0, x1, y1 = [float(v) for v in ib0]
    X0, Y0, X1, Y1 = [float(v) for v in ib1]
    W0 = max(1e-9, x1 - x0)
    H0 = max(1e-9, y1 - y0)
    W1 = max(1e-9, X1 - X0)
    H1 = max(1e-9, Y1 - Y0)
    if model == "ANISO":
        sx = W1 / W0
        sy = H1 / H0
        tx = X0 - x0 * sx
        ty = Y0 - y0 * sy
    else:  # ISOTROPIC
        s = np.sqrt((W1 * H1) / (W0 * H0))
        cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2
        CX1, CY1 = (X0 + X1) / 2, (Y0 + Y1) / 2
        sx = sy = s
        tx = CX1 - cx0 * s
        ty = CY1 - cy0 * s
    return np.float32([[sx, 0, tx], [0, sy, ty], [0, 0, 1.0]])


def canon_clean_edges(ib, dyn_boxes, gray_raw, shape_raw, canon=CANON):
    """canonical clean 结构边（Canny，动态排除）→ (canon_edge_mask, raw_pt_list)。"""
    x1, y1, x2, y2 = [int(v) for v in ib]
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(shape_raw[1], x2); y2 = min(shape_raw[0], y2)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None, []
    crop = gray_raw[y1:y2, x1:x2]
    body = cv2.resize(crop, (canon, canon), interpolation=cv2.INTER_AREA)
    # 动态排除 canonical mask
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
    ys, xs = np.nonzero(edge)
    pts = []
    if len(xs):
        # canonical → raw（岛台线性映射）
        X0, Y0 = float(ib[0]), float(ib[1])
        pts = np.float32([[X0 + (u / canon) * W, Y0 + (v / canon) * H]
                          for u, v in zip(xs, ys)])
    return edge.astype(np.uint8), pts


def raw_dt_to_edges(shape_raw, edge_pts):
    """raw 帧 DT：edge 像素=0、背景=nonzero → distanceTransform 给"到最近 edge"距离。
    edge_pts: Nx2 raw float。"""
    im = np.ones(shape_raw, dtype=np.uint8) * 1
    xs = np.clip(edge_pts[:, 0].astype(int), 0, shape_raw[1] - 1)
    ys = np.clip(edge_pts[:, 1].astype(int), 0, shape_raw[0] - 1)
    im[ys, xs] = 0
    dt = cv2.distanceTransform(im, cv2.DIST_L2, 3).astype(np.float64)
    return dt


def chamfer_dist(dt, pts_raw):
    if len(pts_raw) == 0:
        return None
    xs = np.clip(np.round(pts_raw[:, 0]).astype(int), 0, dt.shape[1] - 1)
    ys = np.clip(np.round(pts_raw[:, 1]).astype(int), 0, dt.shape[0] - 1)
    d = dt[ys, xs]
    d = d[np.isfinite(d)]
    return d if len(d) else None


def apply_transform(pts, T):
    ones = np.ones((len(pts), 1))
    h = np.hstack([pts, ones])
    out = (T @ h.T).T
    return out[:, :2] / out[:, 2:3]


def stats_raw(d):
    if d is None or len(d) == 0:
        return None, None, None
    return (round(float(np.median(d)), 3), round(float(np.percentile(d, 90)), 3),
            round(float(np.percentile(d, 95)), 3))


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = con.cursor()
    cv2.setRNGSeed(0)
    corr = {"experiment": "CAM01_OBJ01_STRUCT01_CORRECTIONS",
            "CAM01_STRUCT01_DEFECT_CHAMFER_DT_01": "DT 方向修正：edge=0/背景≠0 → distanceTransform 输出到最近 edge",
            "raw_coord": "不再 canonical*min(sx,sy)；预测/目标点真实映回 raw 后 Euclidean",
            "zero_not_missing": "0 残差以 is not None 判定（不吞 0）",
            "struct01_history_untouched": True}
    (OUT / "TREECUT_CAM01_OBJ01_STRUCT01_CORRECTIONS.json").write_text(
        json.dumps(corr, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_OBJ01_CONFIG.json").write_text(
        json.dumps(CONFIG, ensure_ascii=False, indent=1), encoding="utf-8")
    pair_rows = []
    jitter_rows = []
    tgt_diag = []
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
            e0c, p0raw = canon_clean_edges(ib0, dyn0, g0, sh)
            e1c, p1raw = canon_clean_edges(ib1, dyn1, g1, sh)
            pr = {"case": mid, "role": c["role"], "pair": f"{t0}->{t1}"}
            if e0c is None or e1c is None:
                pr["state"] = "OBJECT_BOX_NO_ANCHOR"
                pr["reason"] = "island_crop_small"
                pair_rows.append(pr)
                continue
            n0 = int(e0c.sum())
            n1 = int(e1c.sum())
            comp0 = 0
            if n0:
                _, lab, st0, _ = cv2.connectedComponentsWithStats(e0c * 255)
                comp0 = int((st0[1:, cv2.CC_STAT_AREA] >= 5).sum())
            comp1 = 0
            if n1:
                _, lab, st1, _ = cv2.connectedComponentsWithStats(e1c * 255)
                comp1 = int((st1[1:, cv2.CC_STAT_AREA] >= 5).sum())
            pr["edge_px"] = [n0, n1]
            pr["components"] = [comp0, comp1]
            if n0 < CONFIG["min_val_edge_px"] or n1 < CONFIG["min_val_edge_px"] \
                    or comp0 < CONFIG["min_val_components"] or comp1 < CONFIG["min_val_components"]:
                pr["state"] = "OBJECT_ANCHOR_VALIDATION_INSUFFICIENT"
                pair_rows.append(pr)
                continue
            dt1 = raw_dt_to_edges(sh, p1raw)
            dt0 = raw_dt_to_edges(sh, p0raw)
            # jitter 诊断
            jitter_rows.append({"case": mid, "pair": f"{t0}->{t1}",
                                "center_disp_px": round(float(np.hypot(
                                    (ib1[0] + ib1[2]) / 2 - (ib0[0] + ib0[2]) / 2,
                                    (ib1[1] + ib1[3]) / 2 - (ib0[1] + ib0[3]) / 2)), 2),
                                "w_ratio": round((ib1[2] - ib1[0]) / (ib0[2] - ib0[0]), 4),
                                "h_ratio": round((ib1[3] - ib1[1]) / (ib0[3] - ib0[1]), 4)})
            T_an = box_transform(ib0, ib1, "ANISO")
            T_iso = box_transform(ib0, ib1, "ISOTROPIC")
            res = {}
            for mdl, T in (("ANISO", T_an), ("ISO", T_iso)):
                fwd = apply_transform(p0raw, T)
                d_f = chamfer_dist(dt1, fwd)
                rev = apply_transform(p1raw, np.linalg.inv(T))
                d_r = chamfer_dist(dt0, rev)
                fm, fp90, fp95 = stats_raw(d_f)
                rm, rp90, rp95 = stats_raw(d_r)
                sym_m = max(fm, rm) if (fm is not None and rm is not None) else None
                sym_p90 = max(fp90, rp90) if (fp90 is not None and rp90 is not None) else None
                ok = (sym_m is not None and sym_m <= CONFIG["sym_median_max_px"]
                      and sym_p90 is not None and sym_p90 <= CONFIG["sym_p90_max_px"])
                res[mdl] = {"validated": bool(ok), "forward_med": fm, "forward_p90": fp90,
                            "reverse_med": rm, "reverse_p90": rp90,
                            "sym_median": sym_m, "sym_p90": sym_p90}
            an_ok = res["ANISO"]["validated"]
            iso_ok = res["ISO"]["validated"]
            pr["models"] = res
            if an_ok and iso_ok:
                # 6×6 canonical grid raw 分歧
                gpts = []
                for rr in range(6):
                    for cc in range(6):
                        gpts.append([(cc + 0.5) / 6, (rr + 0.5) / 6])
                gpts = np.float32(gpts)
                X0, Y0 = float(ib0[0]), float(ib0[1])
                W0 = max(1e-9, ib0[2] - ib0[0])
                H0 = max(1e-9, ib0[3] - ib0[1])
                pts = np.float32([[X0 + u * W0, Y0 + v * H0] for u, v in gpts])
                pa = apply_transform(pts, T_an)
                pb = apply_transform(pts, T_iso)
                disc = float(np.median(np.linalg.norm(pa - pb, axis=1)))
                if disc <= CONFIG["agree_px"]:
                    pr["state"] = "OBJECT_BOX_MULTI_CONSENSUS"
                    pr["representative"] = "ANISO" if (res["ANISO"]["sym_median"] or 99) <= \
                        (res["ISO"]["sym_median"] or 99) else "ISO"
                else:
                    pr["state"] = "OBJECT_BOX_MODEL_CONFLICT"
                pr["model_disagreement_raw_median"] = round(disc, 3)
            elif an_ok or iso_ok:
                pr["state"] = "OBJECT_BOX_SINGLE_VALIDATED"
                pr["representative"] = "ANISO" if an_ok else "ISO"
            else:
                pr["state"] = "OBJECT_BOX_NO_ANCHOR"
            pair_rows.append(pr)
        v.close()
        print("case done", mid, c["role"], flush=True)
    from collections import Counter
    cnt = Counter(pr.get("state") for pr in pair_rows)
    an_v = sum(1 for pr in pair_rows if pr.get("models", {}).get("ANISO", {}).get("validated"))
    iso_v = sum(1 for pr in pair_rows if pr.get("models", {}).get("ISO", {}).get("validated"))
    elig = sum(1 for pr in pair_rows
               if pr.get("state") not in ("OBJECT_ANCHOR_VALIDATION_INSUFFICIENT",))
    metrics = {"pairs": len(pair_rows), "validation_eligible": elig,
               "ANISOTROPIC_validated": an_v, "ISOTROPIC_validated": iso_v,
               "OBJECT_BOX_MULTI": cnt.get("OBJECT_BOX_MULTI_CONSENSUS", 0),
               "OBJECT_BOX_SINGLE": cnt.get("OBJECT_BOX_SINGLE_VALIDATED", 0),
               "OBJECT_BOX_CONFLICT": cnt.get("OBJECT_BOX_MODEL_CONFLICT", 0),
               "OBJECT_BOX_NO_ANCHOR": cnt.get("OBJECT_BOX_NO_ANCHOR", 0) +
                                      cnt.get("OBJECT_ANCHOR_VALIDATION_INSUFFICIENT", 0),
               "object_box_union": cnt.get("OBJECT_BOX_MULTI_CONSENSUS", 0) +
                                   cnt.get("OBJECT_BOX_SINGLE_VALIDATED", 0),
               "case_coverage_9": len({pr["case"] for pr in pair_rows
                                       if pr.get("state") in ("OBJECT_BOX_MULTI_CONSENSUS",
                                                              "OBJECT_BOX_SINGLE_VALIDATED")}),
               "states": dict(cnt)}
    pooled = []
    for pr in pair_rows:
        if pr.get("state") in ("OBJECT_BOX_MULTI_CONSENSUS", "OBJECT_BOX_SINGLE_VALIDATED"):
            rp = pr["representative"]
            sm = pr["models"][rp].get("sym_median")
            if sm is not None:
                pooled.append(sm)
    pa = np.array(pooled) if pooled else np.array([])
    metrics["pooled_sym_median"] = round(float(np.median(pa)), 3) if len(pa) else None
    metrics["pooled_sym_p90"] = round(float(np.percentile(pa, 90)), 3) if len(pa) else None
    metrics["pooled_sym_p95"] = round(float(np.percentile(pa, 95)), 3) if len(pa) else None
    union = metrics["object_box_union"]
    case9 = metrics["case_coverage_9"]
    p90 = metrics["pooled_sym_p90"]
    if union >= 28 and case9 >= 8 and (p90 is not None and p90 <= 5.0):
        cls = "STRONG_OBJECT_BOX"
    elif union >= 22 and case9 >= 7 and (p90 is not None and p90 <= 5.0):
        cls = "MODERATE_OBJECT_BOX"
    elif union >= 17 and case9 >= 6:
        cls = "PARTIAL_OBJECT_BOX"
    else:
        cls = "FAIL_OBJECT_BOX"
    suff = union < 17
    res = {"experiment": "CAM01_OBJ01_RESULT", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "baselines": {"v24r1": 12, "gftt": 17, "v26r1": 7, "struct01": 0},
           "metrics": metrics, "improvement_class": cls,
           "SEMANTIC_BOX_ANCHOR_NOT_SUFFICIENT": suff,
           "NEXT_BLOCKER": ("HIGHER_LEVEL_DENSE_OBJECT_CORRESPONDENCE" if suff else "TARGET_RELATIVE_MOTION_V2"),
           "status": cls}
    (OUT / "TREECUT_CAM01_OBJ01_METHOD_MATRIX.json").write_text(
        json.dumps({"pairs": pair_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_OBJ01_STRUCTURAL_VALIDATION.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_OBJ01_BBOX_JITTER.json").write_text(
        json.dumps({"rows": jitter_rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "TREECUT_CAM01_OBJ01_TARGET_DIAGNOSTIC.json").write_text(
        json.dumps({"rows": tgt_diag, "note": "anchor 冻结后由后续轮计算补偿前后 target 运动"}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (OUT / "TREECUT_CAM01_OBJ01_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    cand = None
    if cls != "FAIL_OBJECT_BOX":
        cand = {"model": "ISLAND_BODY object-box (ANISO/ISO)", "config": CONFIG,
                "metrics": metrics, "status": "CALIBRATION_SHADOW_ONLY"}
    (OUT / "TREECUT_CAM01_OBJ01_CANDIDATE.json").write_text(
        json.dumps({"candidate": cand, "frozen": cand is not None}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    # NEG target control
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
        if st == "OBJECT_BOX_MULTI_CONSENSUS":
            neg["MULTI"].append({"case": pr["case"], "pair": pr["pair"]})
        elif st == "OBJECT_BOX_SINGLE_VALIDATED":
            neg["SINGLE"].append({"case": pr["case"], "pair": pr["pair"]})
    neg_out = {"MULTI_pairs": neg["MULTI"], "MULTI_cases": len({x["case"] for x in neg["MULTI"]}),
               "SINGLE_pairs": neg["SINGLE"], "SINGLE_cases": len({x["case"] for x in neg["SINGLE"]})}
    (OUT / "TREECUT_CAM01_OBJ01_NEG_TARGET_CONTROL.json").write_text(
        json.dumps(neg_out, ensure_ascii=False, indent=1), encoding="utf-8")
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'/><title>OBJ01</title></head><body>",
            "<h1>CAM01 OBJ01 · Semantic Object Box Anchor</h1><pre>" +
            json.dumps(metrics, ensure_ascii=False, indent=1) + "</pre></body></html>"]
    (OUT / "TREECUT_CAM01_OBJ01_GALLERY.html").write_text("\n".join(html), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("class:", cls, "| not_sufficient:", suff)
    for mid in (1641, 10000, 2543, 21674):
        sub = [pr for pr in pair_rows if pr["case"] == mid]
        print(mid, [(pr["pair"], pr.get("state"),
                     pr.get("models", {}).get("ANISO", {}).get("validated"),
                     pr.get("models", {}).get("ISO", {}).get("validated")) for pr in sub])
    print("NEG:", json.dumps(neg_out, ensure_ascii=False))
    con.close()


if __name__ == "__main__":
    main()
