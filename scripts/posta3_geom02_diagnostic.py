#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 GEOM02 — 框内运动证据诊断（raw channel，无判定/无阈值调优）。

动机: 3 个 POS 案例人工确认 MOTION_VISIBLE，但 bbox 面积/锚点几何判 STATIC/RETRACT
→ 怀疑目标框内含静态主体、动件位移被稀释。本诊断只输出 raw 指标：
  in_box_appearance_diff（相邻帧目标框内灰度均差/40）
  edge_centroid_drift_x（目标框内 Canny 边缘质心 x 位移）
  span/edge 变化率（现有锚点特征）
不加任何判定；供决定 GEOM02 特征路线（叶板级框 or 框内边缘/模板运动通道）。
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.stdout.reconfigure(encoding="utf-8")
TF = {"EXTENSION_TABLETOP", "TABLETOP"}


def imread(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def edge_cx(g):
    e = cv2.Canny(g, 80, 160)
    ys, xs = np.nonzero(e)
    return (float(xs.mean()) if len(xs) else None)


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    rows = []
    for c in man["cases"]:
        mid = c["media_id"]
        by_t = {}
        for f in c["frames"]:
            by_t[f["t_s"]] = f
        tgt = {}
        for a in roi:
            if a["media_id"] == mid and a["object_name"] in TF:
                tgt.setdefault(a["frame_timestamp"], []).append(a)
        ts = sorted(tgt)
        raw = []
        for i in range(len(ts) - 1):
            t0, t1 = ts[i], ts[i + 1]
            b0 = tgt[t0][0]["bbox_pixel"]
            b1 = tgt[t1][0]["bbox_pixel"]
            if len(tgt[t0]) != 1 or len(tgt[t1]) != 1:
                raw.append({"pair": f"{t0}->{t1}", "note": "target ambiguous"})
                continue
            g0 = cv2.cvtColor(imread(by_t[t0]["local_path"]), cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(imread(by_t[t1]["local_path"]), cv2.COLOR_BGR2GRAY)
            x1, y1, x2, y2 = [int(v) for v in b0]
            c0 = g0[y1:y2, x1:x2]
            x1b, y1b, x2b, y2b = [int(v) for v in b1]
            c1 = g1[y1b:y2b, x1b:x2b]
            c1r = cv2.resize(c1, (c0.shape[1], c0.shape[0])) if c1.shape != c0.shape else c1
            diff = float(np.abs(c0.astype(np.float32) - c1r.astype(np.float32)).mean() / 40.0)
            ec0 = edge_cx(c0)
            ec1 = edge_cx(c1)
            drift = (ec1 - ec0) if (ec0 is not None and ec1 is not None) else None
            raw.append({"pair": f"{t0}->{t1}", "in_box_diff": round(diff, 4),
                        "edge_centroid_drift_x": (round(drift, 2) if drift is not None else None)})
        rows.append({"media_id": mid, "role": c["role"], "pairs": raw})
        print(mid, c["role"], [(p.get("in_box_diff"), p.get("edge_centroid_drift_x")) for p in raw])
    (OUT / "TREECUT_POSTA3_GEOM02_DIAGNOSTIC_V1.json").write_text(
        json.dumps({"experiment": "TREECUT_POSTA3_GEOM02_DIAGNOSTIC_V1",
                    "note": "raw 指标，无判定；POS 3 MOTION_VISIBLE 用于检验框内运动可见性",
                    "cases": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("WROTE geom02 diagnostic")


if __name__ == "__main__":
    main()
