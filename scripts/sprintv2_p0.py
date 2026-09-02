# -*- coding: utf-8 -*-
"""P0: 分步基线(避免网络盘探测阻塞)。"""
import json, sqlite3, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["stage8_gates"]["G1_PRODUCTION_SOURCE"]["status"] = "PASS_FROZEN"
d["g1"]["final_frozen"] = {
    "status": "STAGE8_G1_PASS",
    "A4a": "PRODUCTION_ELIGIBILITY_SAFETY_AGREEMENT (45/45, 非通用准确率)",
    "A4b": "SOURCE_ROLE_TYPE_ACCURACY = NOT_FULLY_MEASURABLE_FROM_CURRENT_L3_SCHEMA",
    "idx63": "REVIEW_REQUIRED / NOT_ELIGIBLE — 非阻塞(不进入生产池即可)",
    "L3_override_scope": "APPROVED 仅覆盖人工具体审核对象(30条); 不传播到 source/folder/category",
    "strict_pool": {"machine_verified": 13617, "post_l3": 13642},
    "full_regression_at_freeze": {"passed": 326, "skipped": 2, "failed": 0}}
d["pilot_status"]["B007_FIRST_REAL_PILOT_V2"] = "HUMAN_NEEDS_REPAIR"
d["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("G1 freeze recorded")

con = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
ic = con.execute("PRAGMA quick_check").fetchone()[0]
fk = con.execute("PRAGMA foreign_key_check").fetchall()
role_n = con.execute("SELECT count(*) FROM b007_source_role_v1").fetchone()[0]
role_unk = con.execute("SELECT count(*) FROM b007_source_role_v1 WHERE source_role='UNKNOWN'").fetchone()[0]
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.production_source import ProductionSourceService
s = ProductionSourceService(DB)
ok, info = s.is_production_eligible("media_file", 18)
print("integrity:", ic, "fk:", len(fk), "roles:", role_n, "unknown:", role_unk)
print("service smoke media18:", ok, info.get("reasons") if not ok else "eligible")
git = subprocess.run(["git", "-C", r"C:\Users\admin\github\treecut-v13", "status", "--short"],
                     capture_output=True, text=True).stdout.strip()
print("git dirty:", git)
(OUT / "TREECUT_SPRINTV2_P0_BASELINE_V1.json").write_text(json.dumps(
    {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "g1_frozen": True,
     "db_integrity": ic, "fk_issues": len(fk), "role_rows": role_n, "role_unknown": role_unk,
     "service_smoke_media18": {"eligible": ok, "reasons": info.get("reasons")},
     "git_dirty": git}, ensure_ascii=False, indent=2), encoding="utf-8")
print("P0 saved")
