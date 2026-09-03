# -*- coding: utf-8 -*-
"""修正产物: ranked 加 scored_total meta; discovery metrics broad 用全量; gap 补 required 键。"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
TOTAL = {"EXTEND": 333, "RETRACT": 333, "DRAWER_OPEN": 888, "STORAGE_PUT_IN": 1200, "SOCKET_INSERT": 464}
ranked = json.loads((OUT / "_v11_ranked.json").read_text(encoding="utf-8"))
ranked["_meta"] = {"scored_total": TOTAL, "note": "全量廉价计分(非随机10); 每动作存 top60 供探测"}
(OUT / "_v11_ranked.json").write_text(json.dumps(ranked, ensure_ascii=False, indent=1), encoding="utf-8")

disc = json.loads((OUT / "TREECUT_ACTION_CANDIDATE_DISCOVERY_V1.json").read_text(encoding="utf-8"))
for act, m in disc["metrics"].items():
    m["broad_scored_total"] = TOTAL[act]
    m["broad_top60_kept"] = m["broad_ranked"]
(OUT / "TREECUT_ACTION_CANDIDATE_DISCOVERY_V1.json").write_text(json.dumps(disc, ensure_ascii=False, indent=1), encoding="utf-8")

gap = json.loads((OUT / "TREECUT_MATERIAL_GAP_STATUS_V2.json").read_text(encoding="utf-8"))
gap.setdefault("review_required_pending_verify", {"EXTEND": 0, "RETRACT": 0, "DRAWER_OPEN": 0,
                                                  "STORAGE_PUT_IN": 0, "SOCKET_INSERT": 0})
gap.setdefault("cross_segment_pending_probe", 0)
(OUT / "TREECUT_MATERIAL_GAP_STATUS_V2.json").write_text(json.dumps(gap, ensure_ascii=False, indent=1), encoding="utf-8")
print("patched meta + gap keys")
