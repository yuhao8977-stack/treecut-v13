# -*- coding: utf-8 -*-
"""G2 ChatGPT 审核包: 20 Queries × Top1-3(前文/窗/后文+标签)。超大体自动拆 PART2。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from hrp_builder import PKG, WORK, title_card, candidate_pieces, concat
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
q20 = json.loads((OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").read_text(encoding="utf-8"))["queries"]
win = json.loads((OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").read_text(encoding="utf-8"))["windows"]
meta = {w["media_id"]: w for w in win}

pieces = []
json_items = []
PART_CAP = 1 << 28  # 256MB 上限自动拆
for qi, q in enumerate(q20):
    act = q.get("action")
    t3 = q.get("top3") or []
    card = title_card([f"QUERY {qi+1:02d}", f"requested_action={act}", ""],
                      WORK / f"g2_card_{qi}.mp4")
    if card:
        pieces.append(card)
    if not t3:
        json_items.append({"query_id": q["qid"], "requested_action": act,
                           "source_available": False, "no_valid_source": True, "top": [], "human_result": None})
        continue
    for ri, c in enumerate(t3):
        mid = c["media_id"]
        s, e = c["subclip"]
        m = meta.get(mid, {})
        ms = m.get("motion_support", "?")
        mac = m.get("action", act)
        aw = m.get("action_window")
        lab = (f"QUERY {qi+1:02d} TOP{ri+1} | seg={mid} | req={act}\n"
               f"machine action={mac} motion={ms}" + (f" | act_win {aw[0]}-{aw[1]}s" if aw else ""))
        pp = candidate_pieces(mid, float(s), float(e), lab, f"g2_{qi}_{ri}")
        pieces += pp
        json_items.append({"query_id": q["qid"], "requested_action": act, "rank": ri + 1,
                           "segment_short": str(mid), "subclip_start": s, "subclip_end": e,
                           "action_window": aw, "motion_support": ms, "machine_action": mac,
                           "evidence_refs": [x.get("t_s") for x in m.get("evidence_refs", [])],
                           "human_result": None})

# 按 query 边界切两段(若需)
final1 = PKG / "TREECUT_G2_CHATGPT_REVIEW_V1.mp4"
ok = concat([str(p) for p in pieces if p is not None], final1)
print("G2 concat ok:", ok, "pieces:", len(pieces), "sizeMB:", round(final1.stat().st_size / 1e6, 1) if final1.exists() else None)
(PKG / "TREECUT_G2_CHATGPT_REVIEW_V1.json").write_text(json.dumps(
    {"queries": json_items, "level": "HUMAN_REVIEW_EVIDENCE"}, ensure_ascii=False, indent=1), encoding="utf-8")
