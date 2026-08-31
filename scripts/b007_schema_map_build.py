# -*- coding: utf-8 -*-
"""V0.2 — B007_CREATOR_RESPONSE_SCHEMA_MAP_V1.json 生成器。

输入：schema_evidence 最新 run（逐页 redacted 响应体 + summary）+ 静态观察历史。
输出：response schema 分类 + 每端点覆盖率 + "Rich Coverage 为何低"的解释。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVIDENCE_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                     r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\schema_evidence")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_CREATOR_RESPONSE_SCHEMA_MAP_V1.json")


def latest_run() -> Path:
    runs = sorted(EVIDENCE_ROOT.glob("*")) if EVIDENCE_ROOT.exists() else []
    return runs[-1] if runs else None


def main() -> int:
    run_dir = latest_run()
    if run_dir is None:
        print("no evidence")
        return 1
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    notes = json.loads((run_dir / "notes_union.json").read_text(encoding="utf-8"))
    pages = summary["pages_in_order"]
    page_stats = summary["page_stats"]

    # 汇总覆盖率（全页）
    agg = {"records": 0, "title": 0, "publish_time": 0, "media_type": 0,
           "duration": 0, "cover": 0}
    per_page = {}
    for p in pages:
        ps = page_stats[str(p)]
        agg["records"] += ps.get("record_count", 0)
        for k in ("title", "publish_time", "media_type", "duration", "cover"):
            agg[k] += ps.get(k, 0)
        per_page[str(p)] = ps
    total_notes = agg["records"]
    coverage = {k: {"count": v, "pct": round(v / total_notes * 100, 1) if total_notes else 0}
                for k, v in agg.items()}

    # 每页记录数分布（page0=12，后续=10）
    rec_counts = {}
    for p in pages:
        rc = page_stats[str(p)]["record_count"]
        rec_counts[str(rc)] = rec_counts.get(str(rc), 0) + 1

    map_doc = {
        "map_id": "B007_CREATOR_RESPONSE_SCHEMA_MAP_V1",
        "account": {"workspace": "B007", "xhs_id": "63083262719",
                    "display_name": "KUBON坤宝高端岛台工厂"},
        "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(),
        "evidence_run": run_dir.name,
        "evidence_files": [f.name for f in run_dir.glob("posted_page_*.json")][:5]
                          + [f"... total {len(pages)} pages"],
        "response_schema_classes": [
            {
                "class": "CLASS_A_POSTED_RICH",
                "endpoint": "creator.xiaohongshu.com/api/galaxy/v2/creator/note/user/posted?tab=0&page=N",
                "trigger": "note-manager 已发布 tab；挂载 response listener 后 reload 触发 page=0；"
                           "滚动 .content 容器触发 page=1..N",
                "payload": "data.notes[10-12]",
                "fields_provided": {
                    "note_id": "id (24-hex)",
                    "title": "display_title",
                    "publish_time": "time (epoch 秒)",
                    "media_type": "type (video/image/normal)",
                    "duration": "video_info.duration (秒)",
                    "cover": "images_list[0].url -> sanitize origin+path",
                    "engagement": "view_count/likes/comments_count/shared_count/collected_count",
                    "status": "tab_status/schedule_post_time/visible_time/sticky",
                    "excluded": "xsec_token/xsec_source/签名URL 一律不落库",
                },
                "pagination": "page 参数驱动；无 has_more/hasMore/cursor 字段；"
                              "page0=12 条，page1..N=10 条",
                "coverage": coverage,
                "record_count_distribution": rec_counts,
            },
            {
                "class": "CLASS_B_DOM_SSR_ID_ONLY",
                "endpoint": "页面 DOM explore-link / window.__INITIAL_STATE__（SSR）",
                "trigger": "前台 user/profile/{xhs_id} 或 note-manager 首屏提取",
                "payload": "a[href*=explore] 链接 + 卡片文本",
                "fields_provided": {
                    "note_id": "URL 中 24-hex（稳定）",
                    "title": "卡片文本（部分，易截断）",
                    "media_type": "部分",
                    "publish_time/duration/cover": "不提供",
                },
                "coverage_evidence": "历史观察 run 140509/140714：460 条，title 仅 5/460，"
                                     "media_type 47/460，publish_time/duration 0/460",
            },
            {
                "class": "CLASS_C_DETAIL_ENDPOINTS_UNKNOWN",
                "endpoint": "galaxy/creator/data/note_detail_new, "
                            "galaxy/creator/home/latest_note_data, "
                            "galaxy/creator/datacenter/note/base",
                "note": "diag 中观察到被调用，但 V0.2 未用于 published 列表；schema 未捕获 → UNKNOWN。"
                        "Detail enrichment 按纪律 FALLBACK ONLY，本轮不逐条调用",
            },
        ],
        "why_low_rich_coverage": {
            "summary": "471 条中仅 16 title / 12 duration+cover，根因是批量捕获走的是 CLASS_B 路径，"
                       "CLASS_A（posted 富响应）只在 16 次观察中命中 1 次（page=0 仅 12 条）。",
            "evidence": [
                "观察历史 16 个 creator_raw.json：仅 run 20260831_140940 捕获到 posted 端点（12 条全富字段）；"
                "其余 run 的 observed_notes 来自 DOM/SSR（id-only）",
                "posted 分页此前未打通：旧代码只点击「下一页」按钮（UI 无此控件）+ 窗口滚动（实际是 .content 容器滚动），"
                "因此只拿到 page=0 的 12 条",
                "DB source_refs 分布佐证：409+50 行仅 OBSERVATION(a8ae/ee6d)，11+1 行含 b36e8df41e58（posted）",
            ],
            "fix_applied": "b007_schema_capture.py：挂载 listener → reload → 点击已发布 tab → "
                           "滚动全部可滚动容器 → 捕获 posted page=0..N 全响应体（redacted）",
        },
        "pagination_mechanics": {
            "endpoint_param": "page (0-based)",
            "page0_size": 12,
            "pageN_size": 10,
            "trigger_mechanism": "note-manager 已发布 tab 的 .content 容器滚动（非窗口滚动）",
            "has_more_flag": "无（用 3 轮无新响应判定穷尽）",
            "direct_fetch": "页面上下文 fetch page=1 → HTTP 406 code=-1（需 x-s/x-t 签名，不可绕过）",
            "exhaustion_rule": "连续 3 轮滚动无新 posted 响应 且 无新 note_id => EXHAUSTED；否则 UNKNOWN",
        },
        "current_status": "PAGINATION_CAPTURE_RUNNING_OR_DONE",
    }
    OUT.write_text(json.dumps(map_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"schema map -> {OUT}")
    print(f"pages={len(pages)} records={agg['records']} unique_notes={total_notes}")
    print(f"coverage={coverage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
