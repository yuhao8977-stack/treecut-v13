# -*- coding: utf-8 -*-
"""MMVV A1 — 由 L3_HUMAN_ROI 计算几何轨迹证据（非自动真值；evidence-only）。
每次人工保存后重跑: python tools/mmv_a1_annotate/build_geometry.py
输出 TREECUT_MMVV_A1_GEOMETRY_TRAJECTORY.json（独立字段，不覆盖任何 ROI 层）。
"""
import json, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "reports" / "storage"
MANIFEST = OUT / "TREECUT_MMVV_A1_FRAME_MANIFEST.json"
ROI_FILE = OUT / "TREECUT_MMVV_HUMAN_GT_ROI_A1.json"
GEO_FILE = OUT / "TREECUT_MMVV_A1_GEOMETRY_TRAJECTORY.json"


def main():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rois = json.loads(ROI_FILE.read_text(encoding="utf-8"))["annotations"]
    cases = []
    for c in man["cases"]:
        mid = c["media_id"]
        objs = {}
        for f in c["frames"]:
            if "error" in f:
                continue
            for a in rois:
                if a["media_id"] == mid and a["frame_timestamp"] == f["t_s"]:
                    x1, y1, x2, y2 = a["bbox_pixel"]
                    rec = {
                        "frame": f["frame"], "t_s": f["t_s"],
                        "bbox_center_x": (x1 + x2) / 2.0, "bbox_center_y": (y1 + y2) / 2.0,
                        "bbox_width": x2 - x1, "bbox_height": y2 - y1, "bbox_area": (x2 - x1) * (y2 - y1),
                        "left_edge": x1, "right_edge": x2, "top_edge": y1, "bottom_edge": y2,
                    }
                    objs.setdefault(a["object_name"], []).append(rec)
        # 相对 ISLAND_BODY 几何（有则加）
        ib = objs.get("ISLAND_BODY")
        for name, traj in objs.items():
            if name == "ISLAND_BODY" or not ib:
                continue
            ib0 = ib[0] if ib else None
            for k, rec in enumerate(traj):
                ref = ib[k] if k < len(ib) else ib0
                if ref:
                    rec["rel_island_dx"] = round(rec["bbox_center_x"] - ref["bbox_center_x"], 2)
                    rec["rel_island_dy"] = round(rec["bbox_center_y"] - ref["bbox_center_y"], 2)
        cases.append({"media_id": mid, "requested": c["requested"],
                      "frozen_window_s": c["frozen_window_s"], "objects": objs})
    doc = {"annotation_version": "A1", "source": "L3_HUMAN_ROI",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "note": "evidence-only；不覆盖 L2_QWEN/HEURISTIC；几何变化是证据非自动真值",
           "cases": cases}
    GEO_FILE.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(c["objects"].get(o, [])) for c in cases for o in c["objects"])
    print("geometry OK, boxes total =", total, "->", GEO_FILE)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
