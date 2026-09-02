# -*- coding: utf-8 -*-
"""G2 诚实标注: 结合方向复核(STATIC/EXTEND/RETRACT)给窗口 motion_support; 弱证据不得冒充。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
W = json.loads((OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").read_text(encoding="utf-8"))
EV = json.loads((OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json").read_text(encoding="utf-8"))["items"]
dirrows = {}
for e in EV:
    if e.get("direction_probe"):
        t = e.get("qwen_l2_raw") or ""
        st = "EXTEND" if "direction=EXTEND" in t else ("RETRACT" if "direction=RETRACT" in t else
              ("STATIC" if "direction=STATIC" in t else "UNCERTAIN"))
        dirrows.setdefault(e["media_id"], []).append({"t_s": e.get("t_s"), "direction": st})

for w in W["windows"]:
    mid = w.get("media_id")
    ds = dirrows.get(mid, [])
    act_s = w.get("action_start_s")
    hit = next((d for d in ds if abs((d["t_s"] or 0) - (act_s or -1)) < 0.6), None)
    if hit and hit["direction"] == "STATIC":
        w["motion_support"] = "WEAK"
        w["direction_note"] = "复核时刻呈静止 → 单帧动作证据脆弱; 需更高帧率/人工确认"
    elif hit and hit["direction"] == w["action"]:
        w["motion_support"] = "MODERATE"
        w["direction_note"] = f"复核方向={hit['direction']}"
    else:
        w["motion_support"] = "WEAK"
        w["direction_note"] = "无方向确认或方向不符 → 不宣称动作已确认"
W["note"] = ("subclip 由稀疏时序帧推导; 方向复核后多数动作时刻呈 STATIC → motion_support=WEAK 不得冒充成熟动作识别; "
             "L2 候选, HUMAN_VALIDATION_PENDING")
W["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
(OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").write_text(json.dumps(W, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
print("motion_support:", dict(Counter(w.get("motion_support") for w in W["windows"])))
