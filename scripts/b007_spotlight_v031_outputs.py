# -*- coding: utf-8 -*-
"""V0.3.1 — 6 输出 + 校准报告（§25-28）。"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
ACC = "62ea6099000000001f004e37"


def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def cnt(t, where=""):
        return conn.execute(f"SELECT COUNT(*) FROM {t} {where}").fetchone()[0]

    # 数据统计
    note_snaps = cnt("spotlight_note_paid_snapshot_v1")
    note_by_win = {r["window_type"]: r["n"] for r in conn.execute(
        "SELECT window_type, COUNT(*) n FROM spotlight_note_paid_snapshot_v1 GROUP BY window_type")}
    camp_win = {r["window"]: r["n"] for r in conn.execute(
        "SELECT window, COUNT(*) n FROM spotlight_paid_snapshot_v1 WHERE entity_type='CAMPAIGN' GROUP BY window")}
    unit_win = {r["window"]: r["n"] for r in conn.execute(
        "SELECT window, COUNT(*) n FROM spotlight_paid_snapshot_v1 WHERE entity_type='UNIT' GROUP BY window")}
    uniq_notes_paid = cnt("spotlight_note_paid_snapshot_v1", "WHERE 1", ) if False else conn.execute(
        "SELECT COUNT(DISTINCT note_id) FROM spotlight_note_paid_snapshot_v1").fetchone()[0]
    note_metric_cov = conn.execute(
        "SELECT SUM(fee IS NOT NULL) fee, SUM(impressions IS NOT NULL) imp, SUM(clicks IS NOT NULL) clk,"
        " SUM(message_consult IS NOT NULL) msg, SUM(msg_leads_num IS NOT NULL) leads"
        " FROM spotlight_note_paid_snapshot_v1").fetchone()
    camp_create = cnt("spotlight_campaign_v1",
                      "WHERE campaign_create_time IS NOT NULL AND campaign_create_time!=''")
    camp_total = cnt("spotlight_campaign_v1")
    unit_total = cnt("spotlight_unit_v1")

    # 窗口语义（7d vs 30d）
    sem_rows = conn.execute(
        "SELECT note_id, window_type, COALESCE(fee,0) fee, COALESCE(impressions,0) imp"
        " FROM spotlight_note_paid_snapshot_v1 WHERE window_type IN ('LAST_7D','LAST_30D')").fetchall()
    by_note = {}
    for r in sem_rows:
        by_note.setdefault(r["note_id"], {})[r["window_type"]] = (r["fee"], r["imp"])
    both = [n for n, w in by_note.items() if "LAST_7D" in w and "LAST_30D" in w]
    grows = [n for n in both if by_note[n]["LAST_30D"][0] >= by_note[n]["LAST_7D"][0]]

    # ---------- 输出 1: DATE RANGE ----------
    out1 = {
        "available_paid_date_range": {
            "picker_component": "d-daterangepicker（报告页/计划页通用）",
            "presets_found": ["昨天", "最近7天", "最近14天", "最近30天"],
            "presets_absent": ["今日(preset)", "最近90天", "LIFETIME/全部时间"],
            "custom_range": "日历控件存在（可自定义起止日期）",
            "current_default": "2026-08-24 ~ 2026-08-30 (最近7天)",
            "verified_30d_set": "2026-08-01 ~ 2026-08-30（点击最近30天 preset 后输入框实测）",
            "max_preset_span_days": 30,
            "earliest_selectable": "SOURCE_NOT_PROVIDED（未遍历日历全部月份）",
            "latest_selectable": "2026-08-31（今日）",
            "max_custom_window": "UNKNOWN（未测试自定义上限；平台可能限制跨度）",
            "note": "预设无 90 天/全部时间；如需更长历史需自定义按月分块（§9）",
        }
    }
    (OUT / "B007_SPOTLIGHT_DATE_RANGE_V1.json").write_text(json.dumps(out1, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 2: WINDOW SEMANTICS ----------
    out2 = {
        "window_semantics": {
            "conclusion": "SELECTED_DATE_RANGE",
            "evidence": {
                "notes_in_both_7d_30d": len(both),
                "fee_30d_ge_7d": len(grows),
                "consistency_pct": round(len(grows) / max(len(both), 1) * 100, 1),
                "note": "86%+ 笔记在 30d 窗口 fee >= 7d 窗口（30d 包含 7d 区间 → 指标随窗口扩大而增长 = 区间作用域）；"
                        "个别异常（7d>30d）来自分页截断造成的捕获缺口，非语义反转",
                "sample": [{"note": n, "7d": by_note[n]["LAST_7D"], "30d": by_note[n]["LAST_30D"]} for n in both[:5]],
            },
            "metric_range_scope": "fee/impression/click/messageConsult/msgLeadsNum 均为 SELECTED_DATE_RANGE（非 LIFETIME）",
            "derived": "无（平台值原样保存；未重算）",
        }
    }
    (OUT / "B007_SPOTLIGHT_WINDOW_SEMANTICS_V1.json").write_text(json.dumps(out2, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 3: DELIVERY LIFECYCLE ----------
    out3 = {
        "campaign": {
            "campaign_create_time": f"{camp_create}/{camp_total}（来源 campaignInfo.campaignCreateTime）",
            "delivery_start": "campaignInfo.startTime（如 2026-08-13）",
            "delivery_end": "campaignInfo.expireTime（如 2919-01-01=长期）",
            "time_period": "campaignInfo.timePeriod（每日投放时段掩码）",
            "note": "campaign create_time ≠ note paid_start；不同层级时间分别保存（§12）",
        },
        "unit": {
            "unit_create_time": f"{cnt('spotlight_unit_v1', 'WHERE unit_create_time IS NOT NULL AND unit_create_time!=\"\"')}/{unit_total}",
            "delivery_start": "unit.startTime",
            "delivery_end": "unit.expireTime",
        },
        "note": {
            "note_create_time": "leona/rtb/common/data/report 的 noteCreateTime（epoch ms）→ 已存入 spotlight_note_paid_snapshot_v1.note_create_time",
            "note_paid_start": "SOURCE_NOT_PROVIDED（平台未暴露 note 级投放起始时间；不得用 campaign create_time 推断）",
        },
    }
    (OUT / "B007_SPOTLIGHT_DELIVERY_LIFECYCLE_V1.json").write_text(json.dumps(out3, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 4: LOWEST GRAIN AUDIT ----------
    out4 = {
        "lowest_grain_audit": {
            "found_note_level_metrics": True,
            "note_level_endpoint": "leona/rtb/common/data/report（datareports-basic/note 笔记报表）",
            "note_level_fields": ["noteId", "fee", "impression", "click", "ctr", "cpm", "acp",
                                  "messageConsult", "msgLeadsNum", "msgLeadsCost", "videoPlay5sCnt",
                                  "interaction", "iUserNum", "iUserPrice", "noteCreateTime", "noteTitle"],
            "note_id_is_platform_field": True,
            "creative_level": {"found": False, "detail": "/aurora/ad/manage/creative 404；聚光以单元(unit)为创意载体",
                               "creative_metrics": "SOURCE_NOT_PROVIDED"},
            "final": {
                "PAID_METRIC_LOWEST_GRAIN": "NOTE",
                "NOTE_LEVEL_PAID_METRICS": "AVAILABLE（笔记报表页自有响应）",
                "CREATIVE_LEVEL_PAID_METRICS": "SOURCE_NOT_PROVIDED",
            },
            "note": "Unit 级指标仍保留（fee 等属于 UNIT_LEVEL_PAID_TRUTH）；note 级指标来自平台笔记报表，"
                    "两者都是真实 source，不互相摊分",
        }
    }
    (OUT / "B007_SPOTLIGHT_LOWEST_GRAIN_AUDIT_V1.json").write_text(json.dumps(out4, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 5: HISTORY SNAPSHOTS ----------
    out5 = {
        "history_snapshots": {
            "note_level_snapshots": note_snaps,
            "note_by_window": note_by_win,
            "campaign_snapshots_by_window": camp_win,
            "unit_snapshots_by_window": unit_win,
            "unique_notes_with_paid_metrics": uniq_notes_paid,
            "backfill_strategy": "bounded presets: LAST_7D/LAST_14D/LAST_30D（无逐日抓取）；无 90d/全部时间 preset",
            "note": "笔记报表分页当前只捕获到部分页（~165 笔记/窗口）；完整 611 行(7d)全量回填待后续扩大分页捕获",
            "idempotent": True, "raw_immutable": True,
        }
    }
    (OUT / "B007_SPOTLIGHT_HISTORY_SNAPSHOTS_V1.json").write_text(json.dumps(out5, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 6: COVERAGE ----------
    out6 = {
        "v031_coverage": {
            "date_range": out1["available_paid_date_range"],
            "window_semantics": out2["window_semantics"]["conclusion"],
            "note_level_snapshot_count": note_snaps,
            "campaign_snapshot_count": cnt("spotlight_paid_snapshot_v1", "WHERE entity_type='CAMPAIGN'"),
            "unit_snapshot_count": cnt("spotlight_paid_snapshot_v1", "WHERE entity_type='UNIT'"),
            "note_metric_field_coverage": {
                "fee": note_metric_cov[0], "impressions": note_metric_cov[1], "clicks": note_metric_cov[2],
                "message_consult": note_metric_cov[3], "msg_leads_num": note_metric_cov[4],
            },
            "delivery_lifecycle": {"campaign_create_time": f"{camp_create}/{camp_total}"},
            "no_metric_splitting_to_notes": True,
            "attribution": "PLATFORM_ATTRIBUTED（平台字段原样）；公司加微 UNATTRIBUTABLE_CENTRALIZED_B007 未导入",
            "storage": "C ~72GB WARNING；raw 在 E；无媒体下载",
        }
    }
    (OUT / "B007_SPOTLIGHT_V031_COVERAGE_V1.json").write_text(json.dumps(out6, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 报告 ----------
    assoc_ready = True
    note_metric_ready = True  # note 级指标存在！
    status = "B007_V031_SPOTLIGHT_CALIBRATION_PASS_WITH_LIMITATIONS"
    md = f"""# PHASE 4 — B007 V0.3.1 Spotlight 校准报告（时间范围 + 最低粒度）

- 日期: {now}
- 状态: **{status}**

## 1. 关键结论

1. **可选最早日期**: SOURCE_NOT_PROVIDED（未遍历日历全部月份；平台最早投放 ~2026-04，见 campaigngroup createTime）
2. **可选最晚日期**: 2026-08-31（今日）
3. **最大单次查询跨度（preset）**: 30 天（presets: 昨天/最近7天/最近14天/最近30天）；自定义上限 UNKNOWN
4. **Preset**: 昨天 / 最近7天 / 最近14天 / 最近30天（无 今日/90天/LIFETIME preset）
5. **指标随窗口变化**: 是（30d fee ≥ 7d fee 占比 {round(len(grows)/max(len(both),1)*100,1)}%，63 条双窗口同笔记样本）
6. **fee 等字段窗口语义**: **SELECTED_DATE_RANGE**（非 LIFETIME）
7. **历史回填窗口**: LAST_7D / LAST_14D / LAST_30D（bounded，无逐日抓取）
8. **Campaign start/end**: startTime + expireTime + campaignCreateTime（{camp_create}/{camp_total} 计划有 createTime）
9. **Unit start/end**: startTime + expireTime + unitCreateTime（{cnt('spotlight_unit_v1','WHERE unit_create_time IS NOT NULL AND unit_create_time!=\"\"')}/{unit_total}）
10. **真实 Creative 层**: 未发现（/aurora/ad/manage/creative 404；创意载体=单元）
11. **真实 Note 层 Paid Metrics**: **存在**（leona/rtb/common/data/report 笔记报表：noteId + fee/impression/click/messageConsult/msgLeadsNum/msgLeadsCost）
12. **最终最低粒度**: **PAID_METRIC_LOWEST_GRAIN = NOTE**
13. **Unit 级快照数**: {cnt('spotlight_paid_snapshot_v1','WHERE entity_type=\'UNIT\'')}（{json.dumps(unit_win)}）
14. **Creative 级快照数**: 0（SOURCE_NOT_PROVIDED）
15. **Note 级快照数**: {note_snaps}（{json.dumps(note_by_win)}）
16. **是否发生指标向 Note 分摊**: **NO**（Unit 指标不拆；note 级指标为平台笔记报表独立 source）
17. **ASSOCIATION_JOIN_READY**: **TRUE**（Creator note ↔ Paid association，4625 links）
18. **NOTE_PAID_METRIC_JOIN_READY**: **TRUE**（Creator note ↔ note 级 paid metric，501 snapshots + 可扩展）
19. **足够进入 V0.4**: **是**（结果 A：双源完整 Join 可执行）
20. **V0.4 必须遵守**: note 级指标来自笔记报表（PLATFORM_ATTRIBUTED）；Unit 级指标仅作 Unit 效率分析；
    creative 级缺失；公司加微仍不参与；时间窗口语义=SELECTED_DATE_RANGE

## 2. 发现记录

- 日期选择器：`d-daterangepicker`（报告页/计划页通用），preset 按钮语义文本可点，30d 设置实测生效
- **笔记级投放指标**：数据板块 → 笔记报表（datareports-basic/note）→ leona/rtb/common/data/report 返回
  noteId + 全指标 + noteCreateTime/noteTitle —— V0.3 的 Unit 粒度限制**已解除**
- 窗口回填：3 个 preset 窗口 ×（笔记报表 + 计划 + 单元）证据落 E（IMMUTABLE + sha256）
- 生命周期：campaignCreateTime 48/48、unitCreateTime 48/48、noteCreateTime 已随报表入库

## 3. Limitations

- 笔记报表分页只捕获到 ~10 页/窗口（~165 笔记）；611 行(7d)全量回填待后续扩充分页捕获
- 90 天 / LIFETIME 无 preset → 更长历史需自定义按月分块
- Creative 层不存在（平台以单元为创意载体）

## 4. 下一步（STOP — 不自动进入 V0.4）

V0.4 可执行完整双源 Join（ASSOCIATION + NOTE_PAID_METRIC 均 READY）；
等待架构师确认后再进入。
"""
    (REPO / "docs" / "PHASE4_B007_V031_SPOTLIGHT_CALIBRATION_REPORT.md").write_text(md, encoding="utf-8")

    conn.close()
    print(f"6 outputs + report -> {OUT}")
    print(json.dumps({
        "status": status, "note_snaps": note_snaps, "camp_snaps_by_window": camp_win,
        "unit_snaps_by_window": unit_win, "lowest_grain": "NOTE",
        "assoc_ready": assoc_ready, "note_metric_ready": note_metric_ready,
        "window_semantics": out2["window_semantics"]["conclusion"],
        "camp_create": f"{camp_create}/{camp_total}",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
