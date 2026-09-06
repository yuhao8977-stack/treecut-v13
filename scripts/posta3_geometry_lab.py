#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 GEOM01 — Geometry 实验 infra：OLD_ABS_AREA_V1 vs RELATIVE_ANCHOR_V1（合成场景）。

旧法基线 = 冻结 build_geometry_direction_evidence（面积↑→EXTEND 等）。
新法 = 岛台相对锚点边缘模型（近侧锚边稳定 + 远侧外缘进展 + 跨度变化 + axis 推导）。
合成场景用于证明特征缺陷（透视缩放面积误判），非真实媒体结论。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmvl_master_v1 import build_geometry_direction_evidence  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")

EPS = 0.015          # 归一化边缘净位移阈值
ANCHOR_EPS = 0.02    # 锚边稳定阈值
SPAN_MIN = 0.03


def island():  # 合成岛台
    return [100, 100, 700, 500]


def new_classify(tl):
    """tl: [{t_s, bbox:[x1,y1,x2,y2], island:[..]}] → dict"""
    feats = []
    for it in tl:
        bb, ib = it["bbox"], it["island"]
        ibw = max(1, ib[2] - ib[0])
        ibh = max(1, ib[3] - ib[1])
        feats.append({
            "t": it["t_s"],
            "left_off": (bb[0] - ib[0]) / ibw, "right_off": (bb[2] - ib[2]) / ibw,
            "top_off": (bb[1] - ib[1]) / ibh, "bottom_off": (bb[3] - ib[3]) / ibh,
            "span_w": (bb[2] - bb[0]) / ibw, "span_h": (bb[3] - bb[1]) / ibh})
    if len(feats) < 2:
        return {"action": "UNKNOWN", "axis": "UNKNOWN", "codes": ["RELATIVE_GEOMETRY_INSUFFICIENT"]}
    axes = {}
    for axis, (far_key, far_sign) in {"RIGHT": ("right_off", 1), "LEFT": ("left_off", -1),
                                      "DOWN": ("bottom_off", 1), "UP": ("top_off", -1)}.items():
        far = [f[far_key] for f in feats]
        anchor_key = {"RIGHT": "left_off", "LEFT": "right_off", "DOWN": "top_off",
                      "UP": "bottom_off"}[axis]
        anch = [f[anchor_key] for f in feats]
        net_far = (far[-1] - far[0]) * far_sign
        anch_range = max(anch) - min(anch)
        axes[axis] = {"net_far": net_far, "anchor_range": anch_range}
    # 选 dominant axis：远侧净位移最大且锚边稳定
    cand = [ax for ax, d in axes.items() if abs(d["net_far"]) > EPS and d["anchor_range"] <= ANCHOR_EPS]
    if not cand:
        return {"action": "STATIC", "axis": "UNKNOWN",
                "codes": ["ANCHOR_EDGE_OSCILLATION_NO_PROGRESSION"], "stats": axes}
    axis = max(cand, key=lambda ax: abs(axes[ax]["net_far"]))
    far = [f[{"RIGHT": "right_off", "LEFT": "left_off", "DOWN": "bottom_off", "UP": "top_off"}[axis]]
           for f in feats]
    sign = {"RIGHT": 1, "LEFT": -1, "DOWN": 1, "UP": -1}[axis]
    net_far = (far[-1] - far[0]) * sign
    span = [f["span_w"] if axis in ("LEFT", "RIGHT") else f["span_h"] for f in feats]
    net_span = span[-1] - span[0]
    codes = ["ANCHOR_EDGE_STABLE"]
    if net_far > 0 and net_span >= -SPAN_MIN:
        action = "EXTEND"
        codes += ["FAR_EDGE_OUTWARD_PROGRESS", "SPAN_INCREASE" if net_span > 0 else "SPAN_STABLE"]
    elif net_far < 0 and net_span <= SPAN_MIN:
        action = "RETRACT"
        codes += ["FAR_EDGE_INWARD_PROGRESS", "SPAN_DECREASE" if net_span < 0 else "SPAN_STABLE"]
    else:
        action = "UNKNOWN"
        codes.append("AXIS_MOTION_AMBIGUOUS")
    return {"action": action, "axis": axis, "codes": codes,
            "stats": {"net_far_norm": round(net_far, 4), "net_span_norm": round(net_span, 4),
                      "anchor_range_norm": round(axes[axis]["anchor_range"], 4)}}


def old_direction(tl):
    tls = [{"t_s": it["t_s"], "bbox_pixel": it["bbox"], "island_pixel": it["island"]} for it in tl]
    g = build_geometry_direction_evidence("TABLETOP", "A", tls, camera_unreliable=False)
    return g.direction_action, g.state_progress, g.reason_codes


def tl_from(bboxes, island_px=None):
    ib = island_px or island()
    return [{"t_s": float(i), "bbox": list(b), "island": list(ib)} for i, b in enumerate(bboxes)]


SCEN = {}


def main():
    S = {}
    # 1) EXTEND right（真拉出：右缘外移+跨度增；左锚稳定）
    b = []
    for i in range(5):
        x2 = 400 + i * 60
        b.append([300, 180, x2, 380])
    S["extend_right"] = tl_from(b)
    # 2) RETRACT right（收回）
    b = []
    for i in range(5):
        x2 = 640 - i * 60
        b.append([300, 180, x2, 380])
    S["retract_right"] = tl_from(b)
    # 3) perspective grow static（推近：岛台与目标同比例放大，offsets 不变 → 真 STATIC）
    b = []
    for i, k in enumerate([1.0, 1.1, 1.2, 1.3, 1.4]):
        b.append([int(300 * k), int(180 * k), int(560 * k), int(380 * k)])
    ib_g = [[int(100 * k), int(100 * k), int(700 * k), int(500 * k)] for k in [1.0, 1.1, 1.2, 1.3, 1.4]]
    S["perspective_grow_static"] = [{"t_s": float(i), "bbox": list(b[i]), "island": list(ib_g[i])}
                                    for i in range(5)]
    # 4) perspective shrink static
    b = []
    ib_s = []
    for i, k in enumerate([1.0, 0.92, 0.84, 0.76, 0.68]):
        b.append([int(300 * k), int(180 * k), int(560 * k), int(380 * k)])
        ib_s.append([int(100 * k), int(100 * k), int(700 * k), int(500 * k)])
    S["perspective_shrink_static"] = [{"t_s": float(i), "bbox": list(b[i]), "island": list(ib_s[i])}
                                      for i in range(5)]
    # 5) truly static
    S["static"] = tl_from([[300, 180, 560, 380]] * 5)
    rows = []
    for name, tl in S.items():
        old_a, old_s, old_c = old_direction(tl)
        new = new_classify(tl)
        rows.append({"scenario": name, "OLD_ABS_AREA": old_a, "OLD_state": old_s,
                     "NEW_RELATIVE_ANCHOR": new["action"], "NEW_axis": new["axis"],
                     "NEW_codes": new["codes"], "NEW_stats": new.get("stats")})
        print(f"{name:28s} OLD={old_a:8s} NEW={new['action']:8s} axis={new['axis']:5s}")
    doc = {"experiment": "TREECUT_POSTA3_GEOMETRY_CALIBRATION_V1",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "phase": "SYNTHETIC_INFRA_ONLY（非真实媒体；人工 ROI 后跑真实）",
           "method": "OLD_ABS_AREA_V1(frozen) vs RELATIVE_ANCHOR_V1(新,岛台归一锚边+外缘+跨度+axis)",
           "scenarios": rows,
           "expected": {"extend_right": "EXTEND", "retract_right": "RETRACT",
                        "perspective_grow_static": "STATIC(旧会误判 EXTEND)",
                        "perspective_shrink_static": "STATIC(旧会误判 RETRACT)", "static": "STATIC"}}
    (OUT / "TREECUT_POSTA3_GEOMETRY_CALIBRATION_V1.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("WROTE geometry calibration json")


if __name__ == "__main__":
    main()
