# -*- coding: utf-8 -*-
"""临时占位项目(供 UI smoke; 真实候选待 G2 探测完成后由 builder 回填)。"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.claim_visual import parse_script_to_claims, classify_story_mode

SCRIPT = ("岛台想好用，这三个细节最值得看。第一，上层薄抽，收纳小物不弯腰，打开就能拿到。"
          "第二，轨道插座，吃火锅煮茶都方便，插拔也顺手。"
          "第三，伸缩桌面，来客时一拉就变宽，平时收起来不占位。厨房好不好用，全在这些小细节里。")
claims = parse_script_to_claims(SCRIPT)
beats = []
bid = "B1"
for c in claims:
    beats.append({"id": c.beat_id, "text": c.text,
                  "claim": {"id": c.claim_id, "type": c.claim_type, "text": c.text,
                            "required_action": c.required_action, "required_object": c.required_object},
                  "candidates": [], "selected": None, "qa_note": "PENDING_G2_PROBE"})
proj = {"project_id": "tech_rehearsal_v1", "account_id": "B007",
        "story_mode": classify_story_mode(SCRIPT), "script": SCRIPT,
        "config_note": "G2 探测完成后由 builder 回填候选/subclip/QA", "beats": beats}
(OUT / "TREECUT_WORKBENCH_PROJECT_V1.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
print("placeholder project:", len(beats), "beats")
