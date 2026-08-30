# -*- coding: utf-8 -*-
"""Stage 3A.2 — 数据就绪检查（B003 后台数据 + 成片资产）。

输出 B003_STAGE3A2_READINESS.json：
  后台数据：未提供
  成片资产：已发现 Z:\B组更新视频（约 360 个成片，文件名=日期+产品编号，无 note 映射）
  判定：STAGE3A_WAITING_FOR_MORE_DATA
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT = os.path.join(DATA_ROOT, "B003_STAGE3A2_READINESS.json")


def main():
    # 统计 Z 盘 B 组成片
    groups = {
        "Z:\\B组更新视频\\已发视频一": 209,
        "Z:\\B组更新视频\\已发视频二": 118,
        "Z:\\B组更新视频\\已发视频.1": 8,
        "Z:\\B组更新视频\\已发视频.2": 12,
        "Z:\\B组更新视频\\已发视频三（洗稿）": 13,
    }
    total = sum(groups.values())

    ready = {
        "manifest": "B003_STAGE3A2_READINESS",
        "generated_at": "2026-08-30",
        "account": {"internal_id": "B003", "display_name": "BARBERRY坤宝岛台定制"},
        "backend_data_provided": False,
        "backend_data_detail": "用户尚未放置 B003 小红书后台导出（note 清单/表现/投流）",
        "finished_assets_discovered": {
            "found": True,
            "root": r"Z:\B组更新视频",
            "groups": groups,
            "total_videos": total,
            "filename_format": "日期+产品编号（如 3.9 产品1.mp4）或 mmexport 微信导出名",
            "note_mapping_available": False,
            "note": "文件名不含 note 标题/note_id → 无法自动匹配 note；"
                    "需 duration+发布时间的匹配 或 人工确认",
        },
        "pipeline_ready": {
            "B003ManualImportAdapterV1": "就绪（note_id 去重/append-only snapshot/wechat UNATTRIBUTABLE）",
            "asset_mapping_methods": ["EXACT", "HIGH_CONFIDENCE", "AMBIGUOUS", "UNKNOWN"],
            "segment_join": "PublishedContent → Finished Asset → Segments（Stage3 Pilot 合法路径）",
            "business_cognition": "V2.1（Consumer Policy 生效，UNKNOWN≠FALSE）",
        },
        "verdict": "STAGE3A_WAITING_FOR_MORE_DATA",
        "next_required": [
            "B003 小红书后台导出：note_id/url/title/publish_time + views/likes/favorites/comments/shares"
            "（+私信/留资/投流如有）",
            "确认 Z:\\B组更新视频 是否全部属于 B003（或哪些属于）",
            "（可选）note→成片的人工映射（标题/发布时间/时长）",
        ],
        "guard": "后台数据未到不虚构；成片未确认归属不强映射；不进入 Content DNA",
    }
    json.dump(ready, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)
    print("判定: STAGE3A_WAITING_FOR_MORE_DATA")


if __name__ == "__main__":
    main()
