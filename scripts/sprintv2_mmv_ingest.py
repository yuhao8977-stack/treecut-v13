# -*- coding: utf-8 -*-
"""MMV Round1 人工裁决回填(追加, 不覆盖 L2) + R2 状态记录。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
now = time.strftime("%Y-%m-%d %H:%M:%S")
H = [
 {"media_id": 89, "requested": "EXTEND", "human": "FAIL", "semantics": ["PERSON_MOTION", "STATIC_PRODUCT_PRESENTATION", "TABLETOP_VISIBLE"],
  "reason": ["NO_PROVEN_TABLETOP_GEOMETRY_CHANGE", "PERSON_MOTION_NOT_PRODUCT_MOTION"], "role": "GOLDEN_HARD_NEGATIVE"},
 {"media_id": 52, "requested": "DRAWER_OPEN", "human": "GOOD", "semantics": ["DRAWER_OPEN"],
  "reason": ["DRAWER_OUTWARD", "CLOSED→OPEN"], "role": "POSITIVE_CALIBRATION", "note": "machine UNSURE 保守可接受"},
 {"media_id": 109, "requested": "DRAWER_OPEN", "human": "FAIL", "semantics": ["DRAWER_OPEN_STATE", "STATIC"],
  "reason": ["DRAWER_ALREADY_OPEN", "NO_CLOSED_TO_OPEN_TRANSITION"], "role": "STATE_NOT_ACTION_GOLDEN_NEGATIVE"},
 {"media_id": 51, "requested": "EXTEND", "human": "FAIL", "semantics": ["STATIC_PRODUCT_PRESENTATION"],
  "reason": ["NO_TARGET_TABLETOP_MOTION", "NO_TABLETOP_GEOMETRY_CHANGE"]},
 {"media_id": 1985, "requested": "EXTEND", "human": "FAIL", "semantics": ["TRACK_SOCKET", "SOCKET_MODULE", "SOCKET_ADJUST"],
  "reason": ["ROI_SEMANTIC_LEAKAGE", "SOCKET_MOTION_NOT_TABLETOP_MOTION"], "supports": ["TRACK_SOCKET", "SOCKET_ADJUST"]},
 {"media_id": 1986, "requested": "EXTEND", "human": "FAIL", "semantics": ["TRACK_SOCKET", "SOCKET_MODULE", "SOCKET_ADJUST"],
  "reason": ["ROI_SEMANTIC_LEAKAGE", "SOCKET_MOTION_NOT_TABLETOP_MOTION"], "supports": ["TRACK_SOCKET", "SOCKET_ADJUST"]}]
(OUT / "TREECUT_MMV_HUMAN_ADJUDICATION_ROUND1_V1.json").write_text(
    json.dumps({"round": 1, "append_only": True, "items": H, "generated_at": now}, ensure_ascii=False, indent=1), encoding="utf-8")
# 并入窗口级负例记忆(追加, 不覆盖)
mem = json.loads((OUT / "TREECUT_REVIEW_EXAMPLE_MEMORY_V1.json").read_text(encoding="utf-8"))
for hh in H:
    mem.setdefault("mmv_round1", []).append(hh)
mem["note"] = "追加 MMV Round1 人工裁决(窗口/素材语义级)"
(OUT / "TREECUT_REVIEW_EXAMPLE_MEMORY_V1.json").write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
print("round1 adjudication ingested", len(H))
