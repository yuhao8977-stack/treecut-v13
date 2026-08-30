# -*- coding: utf-8 -*-
"""Stage 3A.2 — 将 155 条 B003 PublishedContent + Performance 写入 DB（Adapter），
并尝试 note→成片 Asset 匹配（诚实：Z盘成片日期/数量不对应 → 需人工确认）。"""
import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.b003_import_adapter import B003ManualImportAdapterV1

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
inv = json.load(open(os.path.join(DATA_ROOT, "B003_PUBLISHED_CONTENT_INVENTORY_V3.json"), encoding="utf-8"))
perf = json.load(open(os.path.join(DATA_ROOT, "B003_PERFORMANCE_SNAPSHOTS_V3.json"), encoding="utf-8"))

svc = B003ManualImportAdapterV1(DB)

# 1) 写入 PublishedContent（155 条有 note_id）
n_pc = 0
n_snap = 0
for r in inv["records"]:
    if not r["note_id"]:
        continue
    pc_id = svc.upsert_published_content({
        "account_id": "B003", "note_id": r["note_id"], "note_url": r["note_url"] or "",
        "title": r["title"], "publish_time": r["publish_time"],
        "content_type": r["content_type"], "duration": r["duration"],
        "source_refs": r["source_refs"],
    })
    n_pc += 1

# 2) 写入 PerformanceSnapshot
for s in perf["snapshots"]:
    if not s.get("note_id"):
        continue
    pc_id = svc.published_content_id("B003", s["note_id"])
    svc.add_performance_snapshot(pc_id, {
        "snapshot_time": s["snapshot_time"], "window": "UNKNOWN",
        "views": s["views"], "likes": s["likes"], "favorites": s["favorites"],
        "comments": s["comments"], "shares": s["shares"],
        "metric_type": "MIXED", "source": "SRC-B003-PERF-DETAIL",
    })
    n_snap += 1

print(f"写入 PublishedContent: {n_pc} | PerformanceSnapshot: {n_snap}")
print("DB 中 B003 published_content 总数:", svc.count())
