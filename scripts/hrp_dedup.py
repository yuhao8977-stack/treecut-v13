# -*- coding: utf-8 -*-
"""生成 Dedup 审核包(先验证流水线) + G3 审核包。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from hrp_builder import (PKG, WORK, title_card, candidate_pieces, concat, path_for, dur_of)
import subprocess
from pathlib import Path as P
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FFP = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"

sel = {s["media_id"]: s for s in json.loads((OUT / "B007_V2_SUBCLIP_SELECTION_V1.json").read_text(encoding="utf-8"))["subclips"]}
ded = json.loads((OUT / "TREECUT_PILOT_V2_DEDUP_RUN_V1.json").read_text(encoding="utf-8"))["hits"]

def win_of(media_id):
    s = sel.get(media_id)
    if not s:
        return None
    return (s.get("source_start", 0), s.get("source_start", 0) + s.get("window", 0))

def mid_of(label):
    # "B2-FEATURE_STORAGE(media 2)" → 2
    import re
    m = re.search(r"media (\d+)", label)
    return int(m.group(1)) if m else None

pieces = []
json_items = []
for i, h in enumerate(ded):
    ma, mb = mid_of(h["shot_a"]), mid_of(h["shot_b"])
    wa, wb = win_of(ma), win_of(mb)
    if not wa or not wb:
        continue
    card = title_card([f"PAIR {i+1:02d}", h["level"], f"A: {h['shot_a']}", f"B: {h['shot_b']}"],
                      WORK / f"ded_card_{i}.mp4")
    pieces.append(card)
    # A 三段
    a_p = candidate_pieces(ma, wa[0], wa[1], f"PAIR{i+1} A | {h['level']}", f"ded{i}_a")
    pieces += a_p
    b_p = candidate_pieces(mb, wb[0], wb[1], f"PAIR{i+1} B | {h['level']}", f"ded{i}_b")
    pieces += b_p
    json_items.append({"pair_id": f"PAIR{i+1:02d}", "level": h["level"], "reason": h["reason"],
                       "strength": h["strength"], "shot_a": {"label": h["shot_a"], "media_id": ma,
                        "subclip": list(wa)}, "shot_b": {"label": h["shot_b"], "media_id": mb,
                        "subclip": list(wb)}, "human_result": None})

final = PKG / "TREECUT_DEDUP_CHATGPT_REVIEW_V1.mp4"
ok = concat([str(p) for p in pieces if p is not None], final)
print("dedup concat ok:", ok, final.exists() if final.exists() else "missing")
(PKG / "TREECUT_DEDUP_CHATGPT_REVIEW_V1.json").write_text(json.dumps(
    {"pairs": json_items, "level": "HUMAN_REVIEW_EVIDENCE", "human_result": None}, ensure_ascii=False, indent=1), encoding="utf-8")
