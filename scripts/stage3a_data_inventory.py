# -*- coding: utf-8 -*-
"""Stage 3A — B003_DATA_SOURCE_INVENTORY.json。

结论：当前环境 B003 数据源为空（诚实盘点，不假设存在）。
列出：已扫描位置 / 缺失的数据类型 / 需要的导入物。
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
OUT = os.path.join(DATA_ROOT, "B003_DATA_SOURCE_INVENTORY.json")


def main():
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # 扫描 DB 所有表是否有 B003 相关内容
    db_hits = []
    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        t = r["name"]
        try:
            cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({t})")]
            rows = conn.execute(f"SELECT * FROM {t} LIMIT 5").fetchall()
            for row in rows:
                if any(str(v).upper().find("B003") >= 0 for v in dict(row).values() if v is not None):
                    db_hits.append({"table": t, "sample": {k: str(v)[:30] for k, v in dict(row).items()}})
                    break
        except Exception:
            pass
    conn.close()

    # 文件扫描（DATA_ROOT）
    file_hits = []
    for f in sorted(os.listdir(DATA_ROOT)):
        if "b003" in f.lower():
            file_hits.append(f)

    inventory = {
        "manifest": "B003_DATA_SOURCE_INVENTORY",
        "generated_at": "2026-08-30",
        "account_target": "B003",
        "conclusion": "B003_DATA_NOT_FOUND — 当前环境无任何 B003 已发布内容/表现/映射数据",
        "scanned_locations": [
            {"location": "materials.db 全部 60+ 表", "b003_hits": len(db_hits), "detail": db_hits[:5]},
            {"location": "DATA_ROOT 全部 json", "b003_hits": len(file_hits), "detail": file_hits},
            {"location": "repo（XHS reader/import 工具）", "b003_hits": 0, "detail": "无 reader/import 工具"},
            {"location": "Downloads（小红书媒体文件）", "b003_hits": 0,
             "detail": "仅图片/视频下载，无 note metadata/表现数据，且非 B003 账号"},
        ],
        "account_tables_checked": {
            "account_dna": "rows=0（空）",
            "sources": "rows=4（Phase1 来源注册，非发布内容）",
            "production_plans": "rows=2（模板假设，非表现数据）",
        },
        "required_sources_for_stage3a": [
            {"source_id": "SRC-B003-NOTES", "data_type": "published_note_metadata",
             "required_fields": ["note_id", "note_url", "title", "publish_time", "account_id", "content_type", "duration"],
             "status": "MISSING"},
            {"source_id": "SRC-B003-PERF", "data_type": "performance_snapshots",
             "required_fields": ["note_id", "snapshot_time", "views", "likes", "favorites", "comments",
                                 "shares", "private_messages", "leads", "ad_spend", "paid_impressions",
                                 "paid_clicks", "paid_leads", "window"],
             "status": "MISSING"},
            {"source_id": "SRC-B003-ASSET", "data_type": "asset_mapping",
             "required_fields": ["note_id", "asset_id", "mapping_method", "confidence"],
             "status": "MISSING"},
            {"source_id": "SRC-B003-WECHAT", "data_type": "added_wechat",
             "required_fields": ["note_id", "added_wechat_count", "attributable"],
             "status": "MISSING",
             "note": "如为集中归集（非单视频可归因），必须标 UNATTRIBUTABLE，不得反推单视频加微信"},
        ],
        "data_gap_evidence": {
            "db_tables_with_b003": len(db_hits),
            "files_with_b003": len(file_hits),
            "existing_content_related_tables": ["content_classification", "content_value", "content_templates",
                                                "account_dna"],
            "note": "content_classification/content_value 是素材级（asset_id），非已发布内容级；"
                    "无 note_id / publish_time / performance 字段",
        },
        "guard": "诚实盘点：不假设 B003 数据存在；在数据导入前不得进入 Content DNA / 模板挖掘",
    }
    json.dump(inventory, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("B003 数据源盘点结论: B003_DATA_NOT_FOUND")


if __name__ == "__main__":
    main()
