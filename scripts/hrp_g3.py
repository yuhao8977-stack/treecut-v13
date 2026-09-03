# -*- coding: utf-8 -*-
"""G3 ChatGPT 审核包: 16 Beats, 每 Beat 卡(SCRIPT/CLAIMS/STORY/REQUIRED) + Top1-3 前文/窗/后文。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from hrp_builder import PKG, WORK, title_card, candidate_pieces, concat
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
proj = json.loads((OUT / "TREECUT_WORKBENCH_PROJECT_V1.json").read_text(encoding="utf-8"))
story = proj.get("story_mode", "?")

pieces = []
json_items = []
for bi, b in enumerate(proj.get("beats", [])):
    cl = b.get("claim") or {}
    text = (cl.get("text") or b.get("text") or "")[:70]
    req = f"req_act={cl.get('required_action') or '-'} req_obj={cl.get('required_object') or '-'}"
    card = title_card([f"BEAT {b['id']}", f"SCRIPT: {text}", f"STORY_MODE: {story}", req],
                      WORK / f"g3_card_{bi}.mp4")
    if card:
        pieces.append(card)
    top = (b.get("candidates") or [])[:3]
    if not top:
        json_items.append({"beat_id": b["id"], "script_text": text, "required_visual": req,
                           "story_mode": story, "top": [], "no_valid_source": True, "human_result": None})
    for ri, c in enumerate(top):
        sc = c.get("subclip") or {}
        mid = c.get("media_id")
        lab = f"BEAT {b['id']} TOP{ri+1} | seg={mid} | {req}"
        pp = candidate_pieces(mid, float(sc.get("start_s", 0)), float(sc.get("end_s", 0)),
                              lab, f"g3_{bi}_{ri}")
        pieces += pp
        json_items.append({"beat_id": b["id"], "script_text": text, "story_mode": story,
                           "required_visual": req, "rank": ri + 1,
                           "segment_short": str(mid),
                           "subclip": [sc.get("start_s"), sc.get("end_s")],
                           "human_result": None})

final = PKG / "TREECUT_G3_CHATGPT_REVIEW_V1.mp4"
ok = concat([str(p) for p in pieces if p is not None], final)
print("G3 concat ok:", ok, "| pieces:", len(pieces))
(PKG / "TREECUT_G3_CHATGPT_REVIEW_V1.json").write_text(json.dumps(
    {"beats": json_items, "story_mode": story, "level": "HUMAN_REVIEW_EVIDENCE"}, ensure_ascii=False, indent=1), encoding="utf-8")
