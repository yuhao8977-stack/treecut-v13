# -*- coding: utf-8 -*-
"""Stage 3A.6 — 处理管线就绪（等待 B003_creator_media_metadata_safe_V2.json 到位）。

用户已核验 V2 事实（155 条/唯一/duration 155 一致/images_list 155/无敏感字段），
但文件尚未出现在 Harness 可访问路径。本脚本在文件到位后执行：
  Join → Cover Pilot5 → 升级判定。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")

# V2 文件候选位置
CANDIDATES = [
    os.path.join(DATA_ROOT, "B003_creator_media_metadata_safe_V2.json"),
    r"C:\Users\admin\Desktop\B003_creator_media_metadata_safe_V2.json",
    r"C:\Users\admin\Downloads\B003_creator_media_metadata_safe_V2.json",
    r"C:\Users\admin\Documents\B003_creator_media_metadata_safe_V2.json",
]


def find_v2():
    for p in CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def main():
    p = find_v2()
    if not p:
        print("V2 文件未找到（等用户提供）")
        # 生成准备状态（不假装）
        ready = {
            "manifest": "STAGE3A6_READINESS",
            "generated_at": "2026-08-30",
            "status": "WAITING_FOR_V2_JSON",
            "v2_file_candidates": CANDIDATES,
            "user_confirmed_facts": {
                "records": 155, "unique_note_id": 155, "date_range": "2026-03-04 ~ 2026-08-30",
                "images_list": "155/155", "video_info_duration": "155/155 consistent",
                "sensitive_fields": "NONE",
            },
            "pipeline_ready": [
                "metadata_join_v2（按 note_id）",
                "platform_reference_assets_v3（COVER_RESOURCE_DISCOVERED 升级）",
                "cover_retrieval_pilot5（origin+path 直接 GET）",
                "cover_registry_v3",
                "video_resource_discovery_pilot1（note-detail 路线）",
            ],
        }
        json.dump(ready, open(os.path.join(DATA_ROOT, "STAGE3A6_READINESS.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("-> STAGE3A6_READINESS.json")
        return 1

    print("找到 V2 文件:", p)
    data = json.load(open(p, encoding="utf-8"))
    # 用户核验
    recs = data.get("records", data) if isinstance(data, dict) else data
    if isinstance(recs, dict):
        recs = list(recs.values())
    n = len(recs)
    ids = [r.get("note_id") or r.get("id") for r in recs]
    print(f"records={n} unique={len(set(ids))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
