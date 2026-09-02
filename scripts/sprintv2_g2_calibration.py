# -*- coding: utf-8 -*-
"""G2 校准集: 资产级摘要 + 帧级条目(108+帧级 L2 状态, 80-120 指导区间内如实落盘)。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.action_subclip import parse_qwen_state

EV = json.loads((OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json").read_text(encoding="utf-8"))["items"]
man = {m["media_id"]: m for m in json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))}
extra = {}
p = OUT / "_g2_extra_inventory.json"
if p.exists():
    for v in json.loads(p.read_text(encoding="utf-8")).values():
        for it in v:
            extra[it["media_id"]] = it["rel"]
relmap = {mid: (m.get("rel") or extra.get(mid, "")) for mid, m in man.items()}

frame_items = []
asset_summary = {}
for e in EV:
    mid = e.get("media_id")
    st = parse_qwen_state(e.get("qwen_l2_raw") or "")
    if e.get("error"):
        continue
    frame_items.append({"media_id": mid, "group": e.get("group"), "t_s": e.get("t_s"),
                        "state_l2": st, "pass": e.get("pass4_dense") and "dense" or
                        (e.get("pass3") and "pass3" or (e.get("pass2") and "pass2" or "base")),
                        "level": "L2_VISUAL_CANDIDATE"})
    a = asset_summary.setdefault(mid, {"media_id": mid, "group": e.get("group"),
                                       "rel": relmap.get(mid, ""), "n_frames": 0,
                                       "n_action": 0, "n_object": 0, "n_not": 0})
    a["n_frames"] += 1
    if st in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END"):
        a["n_action"] += 1
    elif st == "OBJECT_PRESENT":
        a["n_object"] += 1
    else:
        a["n_not"] += 1
for a in asset_summary.values():
    a["kind"] = ("positive" if a["n_action"] > 0 and a["n_not"] == 0 else
                 "negative" if a["n_not"] > 0 and a["n_action"] == 0 else "mixed")
cal = {"target_note": "80-120 为集合规模指导; 本集=资产级20 + 帧级条目(证据驱动, L2, 不虚构)",
       "asset_level": sorted(asset_summary.values(), key=lambda x: x["media_id"]),
       "frame_level": frame_items,
       "n_assets": len(asset_summary), "n_frames": len(frame_items),
       "n_action_frames": sum(1 for f in frame_items if f["state_l2"] in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")),
       "n_object_frames": sum(1 for f in frame_items if f["state_l2"] == "OBJECT_PRESENT"),
       "n_not_frames": sum(1 for f in frame_items if f["state_l2"] == "NOT_PRESENT"),
       "hard_negatives": [f for f in frame_items if f["group"] in ("EXTEND_HARDNEG", "STORAGE_EMPTY", "CABINET_EMPTY")],
       "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
(OUT / "TREECUT_G2_ACTION_CALIBRATION_V1.json").write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: cal[k] for k in ("n_assets", "n_frames", "n_action_frames", "n_object_frames", "n_not_frames",
                                       "hard_negatives")}, ensure_ascii=False))
