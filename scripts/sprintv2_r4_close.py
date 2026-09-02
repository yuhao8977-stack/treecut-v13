# -*- coding: utf-8 -*-
"""R4 收尾: 状态 JSON 最终刷新 + 临时脚本清理。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["sprint_v2"]["full_regression_final"] = {"passed": 354, "skipped": 2, "failed": 0, "elapsed_s": 217}
d["sprint_v2"]["db_integrity_final"] = {"quick_check": "ok", "fk_issues": 0}
d["sprint_v2"]["rehearsal"] = "TREECUT_STAGE8_REHEARSAL_V1.json (VOICE_INPUT_REQUIRED/BGM_LIBRARY_NOT_READY, 非V3)"
d["sprint_v2"]["evidence_frames"] = 108
d["sprint_v2"]["rounds_done"] = 4
d["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# 清理一次性临时脚本
for p in Path(r"C:\Users\admin\github\treecut-v13\scripts").glob("_g2_*.py"):
    p.unlink(missing_ok=True)
print("state finalized + cleanup")
