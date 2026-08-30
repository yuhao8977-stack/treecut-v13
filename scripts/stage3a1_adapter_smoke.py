# -*- coding: utf-8 -*-
"""B003ManualImportAdapter smoke：note_id 去重 / snapshot append-only / published_content_id≠asset。"""
import io, os, sqlite3, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.b003_import_adapter import B003ManualImportAdapterV1

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
svc = B003ManualImportAdapterV1(DB)

# 1) 同 note 两个来源 → 合并为 1 个 published_content
pc1 = svc.upsert_published_content({"account_id": "B003", "note_id": "TEST-NOTE-0001",
                                    "title": "测试", "source_refs": ["SRC-A"]})
pc2 = svc.upsert_published_content({"account_id": "B003", "note_id": "TEST-NOTE-0001",
                                    "title": "测试", "source_refs": ["SRC-B"]})
assert pc1 == pc2, "同 note 应合并为同一 published_content_id"
conn = sqlite3.connect(DB)
row = conn.execute("SELECT source_refs FROM published_content_v1 WHERE published_content_id=?", (pc1,)).fetchone()
refs = __import__("json").loads(row[0])
assert set(refs) == {"SRC-A", "SRC-B"}, refs
print(f"[去重] 同 note 多来源合并: {pc1} refs={refs} ✅")

# 2) append-only snapshot：两次快照不同 id
s1 = svc.add_performance_snapshot(pc1, {"views": 100, "metric_type": "ORGANIC", "window": "D7"})
s2 = svc.add_performance_snapshot(pc1, {"views": 200, "metric_type": "ORGANIC", "window": "D14"})
assert s1 != s2, "快照必须 append-only"
n = conn.execute("SELECT COUNT(*) FROM performance_snapshot_v1 WHERE published_content_id=?", (pc1,)).fetchone()[0]
assert n == 2, n
print(f"[append-only] 两条快照保留: {n} ✅")

# 3) published_content_id ≠ asset_id（概念验证）
pc_id = svc.published_content_id("B003", "N1")
assert not pc_id.startswith("ASSET"), "published_content_id 不应是 asset_id"
print(f"[identity] published_content_id={pc_id[:16]}… ≠ asset_id ✅")

# 4) added-WeChat 纪律：不产生 added_wechat 字段（模型无此列）
cols = [c[1] for c in conn.execute("PRAGMA table_info(performance_snapshot_v1)")]
assert not any("wechat" in c.lower() for c in cols), cols
print(f"[wechat纪律] snapshot 表无 added_wechat 列（UNATTRIBUTABLE 不落库）✅")

# 清理
conn.execute("DELETE FROM performance_snapshot_v1 WHERE published_content_id=?", (pc1,))
conn.execute("DELETE FROM published_content_v1 WHERE published_content_id=?", (pc1,))
conn.commit()
conn.close()
print("\n===== ADAPTER SMOKE: PASS ✅ =====")
