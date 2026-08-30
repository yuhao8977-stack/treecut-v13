# -*- coding: utf-8 -*-
"""Stage 3A.1 — B003_REQUIRED_DATA_IMPORT_SPEC_V1.json（最小导入规格）。

本地数据恢复结果：
  - 找到 1 条明确 @BARBERRY note（拆解爆款视频0.1.xlsx：654215c9，4235赞/2838藏/62评）
  - 1 条锚点风格标题（"沙发后放个岛台简直不要太香"）
  - D:\坤宝岛台 运营系统存在但无生产发布数据
  → B003 完整数据需从小红书后台导出导入
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
OUT = os.path.join(DATA_ROOT, "B003_REQUIRED_DATA_IMPORT_SPEC_V1.json")


def main():
    spec = {
        "manifest": "B003_REQUIRED_DATA_IMPORT_SPEC_V1",
        "generated_at": "2026-08-30",
        "account": {"internal_id": "B003", "display_name": "BARBERRY坤宝岛台定制",
                    "platform": "XIAOHONGSHU"},
        "recovery_result": {
            "found_in_local": 2,
            "detail": [
                {"source": "SRC-CHAOJIE-0.1", "note_id": "654215c90000000023039459",
                 "title": "岛台vs传统餐桌🏠该如何选择呢🧐", "likes": 4235, "favorites": 2838,
                 "comments": 62, "evidence": "文案含 @BARBERRY坤宝"},
                {"source": "SRC-CHAOJIE-0.1", "note_id": None,
                 "title": "再见了传统横厅👋👋（沙发后放个岛台简直不要太香🔥）",
                 "evidence": "标题/话题匹配锚点 '大横厅设计布局 沙发后岛台'，无 note_id（不视为可靠身份）"},
            ],
            "local_system_d_kunbao": {"exists": True, "production_data": "NONE",
                                      "note": "D:\\坤宝岛台 有框架（素材/热词/封面库210条）但无发布记录/复盘/数据统计"},
        },
        "minimum_viable_dataset": {
            "published_notes": {
                "required": ["note_id", "url", "title", "publish_time"],
                "optional": ["duration", "content_type", "cover_ref"],
            },
            "performance": {
                "required": ["views", "likes", "favorites", "comments", "shares"],
                "optional": ["interaction_rate", "follower_delta", "homepage_visits"],
                "window_note": "若只有累计值 → performance_window=UNKNOWN 或 LIFETIME（须可证明）；禁止推测 D7/D30",
            },
            "acquisition": {
                "required_if_available": ["private_messages", "leads", "forms"],
                "note": "优先可追踪信号；added-WeChat 一律 UNATTRIBUTABLE_CENTRALIZED_B007，不导入单视频加微",
            },
            "paid": {
                "required_if_available": ["note_id", "spend", "paid_impressions", "paid_clicks",
                                          "paid_leads", "paid_private_messages", "date/window"],
                "note": "Organic/Paid 严格分离；禁止 MIXED 解释为 Organic quality",
            },
            "asset": {
                "required_if_available": ["local_video", "export_video", "file_hash", "duration",
                                          "known_finished_video_mapping"],
                "note": "允许 PublishedContent → Finished Asset → Segments（Stage3 Pilot 合法路径）",
            },
        },
        "import_formats": ["xlsx", "csv", "json", "MANUAL_SOURCE（截图需保留 provenance）"],
        "import_pipeline": ["raw_import", "normalize", "identity_validation", "PublishedContentRecord"],
        "dedup_rule": "note_id 为发布身份证据；同 note 多来源合并 source_refs，保留多个 PerformanceSnapshot，不生成重复 PublishedContentRecord",
        "guard": "不得覆盖原始文件；不得伪造 performance_window；added-WeChat 不参与 B003 内容级评价",
    }
    json.dump(spec, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
