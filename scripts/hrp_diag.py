# -*- coding: utf-8 -*-
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
WORK = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\hrp_work")
import importlib.util
spec = importlib.util.spec_from_file_location("b", str(Path(__file__).parent / "hrp_builder.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
print("PKG", b.PKG, b.PKG.exists())
card = b.title_card(["PAIR 01", "NARRATIVE_NEAR_DUPLICATE"], WORK / "ded_card_0.mp4")
print("card:", card)
sel = {s["media_id"]: s for s in json.loads((OUT / "B007_V2_SUBCLIP_SELECTION_V1.json").read_text(encoding="utf-8"))["subclips"]}
m1 = sel[2]
path = b.path_for(m1["media_id"])
print("path:", path, "exists:", path and Path(path).exists())
s = m1.get("source_start", 0); e = s + m1.get("window", 0)
print("dur:", b.dur_of(path) if path else None, "win", s, e)
pp = b.candidate_pieces(m1["media_id"], s, e, "PAIR1 A", "ded0_a")
print("pieces:", len(pp))
for p in pp:
    print("  ", p, p.exists() if p else None)
