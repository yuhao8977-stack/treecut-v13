#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""POST-A3 — GEOM gate（真实 calibration10 ROI）: OLD_ABS_AREA_V1 vs RELATIVE_ANCHOR_V1。

门: POS(4) NEW direction EXTEND correct >=3/4；NEG(6) NEW False EXTEND=0；NEW 优于 OLD。
NEG 无动件/无岛台案例如实记录（无目标→非 EXTEND）。
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
sys.path.insert(0, str(REPO / "src"))
from treecut.services.mmvl_master_v1 import build_geometry_direction_evidence  # noqa: E402
sys.stdout.reconfigure(encoding="utf-8")

spec = importlib.util.spec_from_file_location("glab", REPO / "scripts" / "posta3_geometry_lab.py")
glab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glab)

TF = {"EXTENSION_TABLETOP", "TABLETOP"}


def resolve(bxs):
    t = [b for b in bxs if b["object_name"] in TF]
    if len(t) == 1:
        return list(t[0]["bbox_pixel"])
    return None


def main():
    man = json.loads((OUT / "TREECUT_POSTA3_CALIBRATION10_MANIFEST_V1.json").read_text(encoding="utf-8"))
    roi = json.loads((OUT / "TREECUT_POSTA3_HUMAN_ROI_V1.json").read_text(encoding="utf-8"))["annotations"]
    rows = []
    for c in man["cases"]:
        mid = c["media_id"]
        tls = []
        for f in c["frames"]:
            bxs = [a for a in roi if a["media_id"] == mid and a["frame_timestamp"] == f["t_s"]]
            bb = resolve(bxs)
            ibs = [a for a in bxs if a["object_name"] == "ISLAND_BODY"]
            island = list(ibs[0]["bbox_pixel"]) if len(ibs) == 1 else None
            if bb is not None:
                tls.append({"t_s": f["t_s"], "bbox": bb, "island": island})
        # OLD
        if len(tls) >= 2:
            tls_old = [{"t_s": x["t_s"], "bbox_pixel": x["bbox"],
                        "island_pixel": x["island"]} for x in tls]
            g = build_geometry_direction_evidence("TABLETOP", "A", tls_old, camera_unreliable=False)
            old = g.direction_action
        else:
            old = "UNKNOWN(insufficient)"
        # NEW
        new = glab.new_classify(tls) if len(tls) >= 2 else \
            {"action": "UNKNOWN", "axis": "UNKNOWN", "codes": ["RELATIVE_GEOMETRY_INSUFFICIENT"]}
        rows.append({"media_id": mid, "role": c["role"], "target_frames": len(tls),
                     "island_present": any(x["island"] is not None for x in tls),
                     "OLD_direction": old, "NEW_direction": new["action"],
                     "NEW_axis": new.get("axis"), "NEW_codes": new.get("codes", [])})
        print(f"{mid} [{c['role']}] tls={len(tls)} island={any(x['island'] is not None for x in tls)} "
              f"OLD={old} NEW={new['action']} axis={new.get('axis')}")
    pos = [r for r in rows if r["role"] == "POS"]
    neg = [r for r in rows if r["role"] == "NEG"]
    for tag, key in (("OLD", "OLD_direction"), ("NEW", "NEW_direction")):
        pos_ok = sum(1 for r in pos if r[key] == "EXTEND")
        neg_fp = sum(1 for r in neg if r[key] == "EXTEND")
        print(f"{tag}: POS EXTEND correct {pos_ok}/{len(pos)} | NEG False EXTEND {neg_fp}/{len(neg)}")
    doc = {"experiment": "TREECUT_POSTA3_GEOMETRY_GATE_V1",
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "gate": {"pos_correct_ge": "3/4", "neg_false_extend": 0},
           "summary": {"OLD_pos_correct": sum(1 for r in pos if r["OLD_direction"] == "EXTEND"),
                       "NEW_pos_correct": sum(1 for r in pos if r["NEW_direction"] == "EXTEND"),
                       "OLD_neg_false_extend": sum(1 for r in neg if r["OLD_direction"] == "EXTEND"),
                       "NEW_neg_false_extend": sum(1 for r in neg if r["NEW_direction"] == "EXTEND")},
           "rows": rows}
    (OUT / "TREECUT_POSTA3_GEOMETRY_GATE_V1.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("WROTE geometry gate")


if __name__ == "__main__":
    main()
