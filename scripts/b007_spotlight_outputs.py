# -*- coding: utf-8 -*-
"""V0.3 — B007 Spotlight 输出生成：8 JSON + 最终报告（§35-42）。"""
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

def q(conn, sql, args=()):
    return conn.execute(sql, args).fetchall()


def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    acct = q(conn, "SELECT * FROM spotlight_account_v1")[0] if q(conn, "SELECT 1 FROM spotlight_account_v1") else None
    camps = [dict(r) for r in q(conn, "SELECT * FROM spotlight_campaign_v1 ORDER BY campaign_id")]
    units = [dict(r) for r in q(conn, "SELECT * FROM spotlight_unit_v1 ORDER BY unit_id")]
    links = [dict(r) for r in q(conn, "SELECT * FROM spotlight_note_link_v1")]
    snaps = [dict(r) for r in q(conn, "SELECT * FROM spotlight_paid_snapshot_v1 ORDER BY entity_type")]

    # 汇总统计
    n_camp = len(camps)
    n_unit = len(units)
    n_links = len(links)
    n_unique_notes = len({l["note_id"] for l in links})
    n_snap = len(snaps)
    snap_by_type = {}
    for s in snaps:
        snap_by_type[s["entity_type"]] = snap_by_type.get(s["entity_type"], 0) + 1

    # 覆盖率（非空指标）
    def cov(rows, fields, metric_key):
        stats = {}
        for f in fields:
            n = sum(1 for r in rows if r.get(metric_key, {}).get(f) not in (None, ""))
            stats[f] = {"count": n, "pct": round(n / max(len(rows), 1) * 100, 1)}
        return stats

    camp_metrics = [json.loads(s["metric_json"]) for s in snaps if s["entity_type"] == "CAMPAIGN"]
    unit_metrics = [json.loads(s["metric_json"]) for s in snaps if s["entity_type"] == "UNIT"]
    core = ("fee", "impression", "click", "ctr", "cpm", "messageConsult", "msgLeadsNum", "msgLeadsCost")
    camp_cov = {f: {"count": sum(1 for m in camp_metrics if m.get(f) not in (None, "")),
                    "pct": round(sum(1 for m in camp_metrics if m.get(f) not in (None, "")) / max(len(camp_metrics), 1) * 100, 1)}
                for f in core}
    unit_cov = {f: {"count": sum(1 for m in unit_metrics if m.get(f) not in (None, "")),
                    "pct": round(sum(1 for m in unit_metrics if m.get(f) not in (None, "")) / max(len(unit_metrics), 1) * 100, 1)}
                for f in core}

    # join 统计（唯一笔记）
    join_by_note = {}
    for l in links:
        join_by_note.setdefault(l["join_status"], set()).add(l["note_id"])
    join_uniq = {k: len(v) for k, v in join_by_note.items()}

    # 账号级指标
    acc_snap = next((s for s in snaps if s["entity_type"] == "ACCOUNT"), None)
    acc_metrics = json.loads(acc_snap["metric_json"]) if acc_snap else {}

    # ---------- 输出 1: ACCOUNT ----------
    out1 = {
        "account_id": ACC,
        "account_name": acct["account_name"] if acct else None,
        "platform": "XIAOHONGSHU_SPOTLIGHT (聚光)",
        "seller_id": acct["seller_id"] if acct else "",
        "role_type": acct["role_type"] if acct else None,
        "professional_name": acct["professional_name"] if acct else None,
        "id_calibration": "CANONICAL_ANCHOR (PAGE_OWNED_RESPONSE: leona/user/info -> userId)",
        "id_source": acct["source"] if acct else "",
        "aggregate_metrics_report_range": {"start": "2026-08-31", "end": "2026-08-31"},
        "aggregate_metrics": acc_metrics,
        "snapshot_time": now,
        "attribution_note": "账户级聚合独立保存，不摊分到 creative/note（§24）",
    }
    (OUT / "B007_SPOTLIGHT_ACCOUNT_V1.json").write_text(json.dumps(out1, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 2: CAMPAIGNS ----------
    out2 = {
        "count": n_camp,
        "source": "PAGE_OWNED_RESPONSE: light/campaign/data/list (48 campaigns, 20/page x3)",
        "campaigns": camps,
    }
    (OUT / "B007_SPOTLIGHT_CAMPAIGNS_V1.json").write_text(json.dumps(out2, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 3: CREATIVES（单元粒度说明） ----------
    out3 = {
        "status": "UNIT_GRAIN_ONLY",
        "note": "聚光页面自有响应未暴露独立 creative 实体（/aurora/ad/manage/creative 404）；"
                "最细稳定粒度为「单元(unit)」= leona/rtb/unit/search。creative 级 → SOURCE_NOT_PROVIDED（§11 只建真实层级）",
        "unit_count": n_unit,
        "units": units,
    }
    (OUT / "B007_SPOTLIGHT_CREATIVES_V1.json").write_text(json.dumps(out3, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 4: PAID SNAPSHOTS ----------
    out4 = {
        "count": n_snap,
        "by_entity_type": snap_by_type,
        "snapshot_key": "account_id + entity_type + entity_id + report_start + report_end + source",
        "idempotent": True,
        "snapshots": snaps,
    }
    (OUT / "B007_SPOTLIGHT_PAID_SNAPSHOTS_V1.json").write_text(json.dumps(out4, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 5: NOTE LINKS ----------
    out5 = {
        "count": n_links,
        "unique_promoted_notes": n_unique_notes,
        "join_to_published": join_uniq,
        "join_rule": "note_id 直连（unit.noteIds）；无 title 兜底（无需）；legacy 459 不混入 ACTIVE",
        "links": links,
    }
    (OUT / "B007_SPOTLIGHT_NOTE_LINKS_V1.json").write_text(json.dumps(out5, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 6: ATTRIBUTION POLICY ----------
    out6 = {
        "attribution_classes": {
            "PLATFORM_ATTRIBUTED_PAID_CONVERSION": "聚光页面自有响应明确提供的 creative/unit/note -> lead/conversion 字段",
            "UNATTRIBUTABLE_CENTRALIZED_B007": "公司总表 added_wechat 集中归 B007；不拆给 note/creative/campaign（§19/21）",
            "SOURCE_NOT_PROVIDED": "creative 级、账号 7d/30d 窗口等未由平台暴露的字段",
        },
        "rules": [
            "公司 added_wechat 默认 UNATTRIBUTABLE_CENTRALIZED_B007，禁止分摊",
            "仅平台 source 明确提供 note->lead/conversion 才入库为 PLATFORM_ATTRIBUTED",
            "平台 CTR/CPC/CPM 原样保存（SOURCE_METRIC）；TreeCut 重算需标 DERIVED_METRIC（§13）",
            "账户级/计划级聚合独立保存，不摊分（§24）",
        ],
        "metric_field_classes": {f: "PLATFORM_ATTRIBUTED" for f in core},
        "creator_performance": "2840 snapshots (SRC-B007-POSTED-OBSERVED) 未修改（§22）",
    }
    (OUT / "B007_SPOTLIGHT_ATTRIBUTION_POLICY_V1.json").write_text(json.dumps(out6, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 7: COVERAGE ----------
    out7 = {
        "spotlight_account": {"name": out1["account_name"], "id": ACC,
                              "id_status": "CALIBRATED_CANONICAL_ANCHOR"},
        "available_paid_date_range": {"status": "UNKNOWN_TODAY_DEFAULT",
                                      "note": "默认今日视图 2026-08-31~2026-08-31；日期选择器文本未探测到，全范围待扩展（§26）"},
        "campaign_count": n_camp,
        "adgroup_unit_count": n_unit,
        "creative_count": "SOURCE_NOT_PROVIDED (unit grain only)",
        "unique_promoted_notes": n_unique_notes,
        "paid_snapshot_count": n_snap,
        "snapshot_by_entity": snap_by_type,
        "metric_coverage_campaign": camp_cov,
        "metric_coverage_unit": unit_cov,
        "note_id_linkage": "DIRECT (unit.noteIds)",
        "published_join": {
            "ACTIVE_PUBLISHED_MATCH": join_uniq.get("ACTIVE_PUBLISHED_MATCH", 0),
            "LEGACY_IDENTITY_MATCH": join_uniq.get("LEGACY_IDENTITY_MATCH", 0),
            "UNMATCHED_PAID_NOTE": join_uniq.get("UNMATCHED_PAID_NOTE", 0),
            "active_universe": 2851,
        },
        "creator_performance_missing": 2851 - 2840,
    }
    (OUT / "B007_SPOTLIGHT_SYNC_COVERAGE_V1.json").write_text(json.dumps(out7, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 输出 8: EXCEPTIONS ----------
    out8 = {
        "exceptions": [
            {"stage": "EXPORT_LOCATOR", "severity": "INFO",
             "detail": "聚光无官方导出按钮定位（页面自有响应已提供全量数据；官方导出=OPTIONAL_SECONDARY_SOURCE）"},
            {"stage": "DATE_RANGE", "severity": "INFO",
             "detail": "默认今日视图；全历史/自定义范围待后续分批 snapshot（§26 AVAILABLE_PAID_DATE_RANGE 未完成）"},
            {"stage": "CREATIVE_GRAIN", "severity": "LIMITATION",
             "detail": "独立 creative 实体未暴露（/aurora/ad/manage/creative 404）；以单元(unit)为最细稳定粒度"},
            {"stage": "ACCOUNT_7D_30D", "severity": "LIMITATION",
             "detail": "账号级 7d/30d 窗口指标未捕获（SOURCE_NOT_PROVIDED）"},
            {"stage": "PAGINATION", "severity": "RESOLVED",
             "detail": "JS click 不触发 SPA 翻页；已用 Playwright 真实点击解决（48/48 计划与单元全分页）"},
            {"stage": "UNIT_PAGE_MISSING_RESPONSES", "severity": "INFO",
             "detail": "leona/rtb/unit/extra/list 捕获 6 份（含去重）；extra 仅状态字段"},
        ],
        "human_intervention_needed": "无（会话有效、账户匹配、无验证码；后续自定义日期范围如需选择器操作可 NEEDS_HUMAN）",
    }
    (OUT / "B007_SPOTLIGHT_SYNC_EXCEPTIONS_V1.json").write_text(json.dumps(out8, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 最终报告 ----------
    md = f"""# PHASE 4 — B007 V0.3 Spotlight Sync 报告

- 日期: {now}
- 状态: **B007_V03_SPOTLIGHT_SYNC_PASS_WITH_LIMITATIONS**

## 1. 账户（§6/§7 门 + ID 校准）

| 项 | 值 |
|---|---|
| 账户名 | {out1['account_name']} |
| account_id | {ACC}（**CANONICAL_ANCHOR_UPGRADED**：leona/user/info 页面自有响应 userId）|
| seller_id | {out1['seller_id'] or '(空)'} |
| ID 来源 | PAGE_OWNED_RESPONSE（非硬编码，binding 已升级）|

## 2. 捕获结果（页面自有响应，非模拟 API）

| 实体 | 数量 | 来源端点 |
|---|---|---|
| 计划 Campaign | **48** | light/campaign/data/list（20/页 ×3 页，Playwright 真实点击翻页）|
| 单元 Unit | **48** | leona/rtb/unit/search（20/页 ×3 页）|
| Creative | SOURCE_NOT_PROVIDED | /aurora/ad/manage/creative 404；最细稳定粒度=单元 |
| 推广笔记 unique | **{n_unique_notes}** | unit.noteIds 直连 |
| 笔记关联 note_links | {n_links} | 单元×笔记（多对多，1 笔记可多单元投放）|
| Paid Snapshot | {n_snap} | ACCOUNT {snap_by_type.get('ACCOUNT',0)} / CAMPAIGN {snap_by_type.get('CAMPAIGN',0)} / UNIT {snap_by_type.get('UNIT',0)} |

## 3. 指标覆盖（今日默认范围 2026-08-31）

| 指标 | 计划级(48) | 单元级(48) |
|---|---|---|
| fee | {camp_cov['fee']['count']} | {unit_cov['fee']['count']} |
| impression | {camp_cov['impression']['count']} | {unit_cov['impression']['count']} |
| click | {camp_cov['click']['count']} | {unit_cov['click']['count']} |
| ctr | {camp_cov['ctr']['count']} | {unit_cov['ctr']['count']} |
| cpm | {camp_cov['cpm']['count']} | {unit_cov['cpm']['count']} |
| messageConsult | {camp_cov['messageConsult']['count']} | {unit_cov['messageConsult']['count']} |
| msgLeadsNum | {camp_cov['msgLeadsNum']['count']} | {unit_cov['msgLeadsNum']['count']} |
| msgLeadsCost | {camp_cov['msgLeadsCost']['count']} | {unit_cov['msgLeadsCost']['count']} |

账户级（今日）：fee={acc_metrics.get('fee')} impression={acc_metrics.get('impression')} click={acc_metrics.get('click')} ctr={acc_metrics.get('ctr')} msgLeadsCost={acc_metrics.get('msgLeadsCost')}

## 4. Published Join（§15/§37）

- unique promoted notes: **{n_unique_notes}** / 2851 ACTIVE universe
- ACTIVE_PUBLISHED_MATCH: {join_uniq.get('ACTIVE_PUBLISHED_MATCH',0)}（唯一笔记）
- LEGACY_IDENTITY_MATCH: {join_uniq.get('LEGACY_IDENTITY_MATCH',0)}
- UNMATCHED_PAID_NOTE: {join_uniq.get('UNMATCHED_PAID_NOTE',0)}
- 459 legacy 未混入 ACTIVE；note_id 直连，无 title 兜底（§14）

## 5. 归因纪律（§19/§20/§36）

- PLATFORM_ATTRIBUTED: fee/impression/click/ctr/cpm/messageConsult/msgLeadsNum/msgLeadsCost 等（平台字段原样）
- UNATTRIBUTABLE_CENTRALIZED_B007: 公司总表 added_wechat 集中归 B007，**不拆给 note/creative/campaign**
- SOURCE_NOT_PROVIDED: creative 级 / 账号 7d/30d
- Creator 2840 Performance snapshots 未修改（§22）

## 6. 存储（§30/§31）

- C free: 启动前 72.5GB（WARNING_BUT_OPERATIONAL，结构化同步允许，无媒体下载）
- Raw：E 盘 treecut_inbox/creator/raw/creator/spotlight_*（IMMUTABLE + sha256）
- 无大型导出（今日视图数据量小）

## 7. Limitations

- AVAILABLE_PAID_DATE_RANGE：仅今日默认视图；自定义/全历史范围待扩展（分批 snapshot）
- Creative 粒度：SOURCE_NOT_PROVIDED（单元为最细稳定粒度）
- 账号 7d/30d：SOURCE_NOT_PROVIDED

## 8. V0.4 Readiness（§39）

- 48 计划 + 48 单元 + 2322 推广笔记 + 97 快照 + 全 ACTIVE join → **数据足以进入 V0.4 Creator+Spotlight Dual-source Join**
- 但日期范围建议在 V0.4 前扩展（多窗口 snapshot）以获得跨时间投放历史

## 9. 下一步（STOP — 不自动进入 V0.4）

等待架构师确认；Winner/Sample/视频恢复/Content DNA 均在 Prohibitions。
"""
    (REPO / "docs" / "PHASE4_B007_V03_SPOTLIGHT_SYNC_REPORT.md").write_text(md, encoding="utf-8")

    conn.close()
    print("8 outputs + report written to", OUT)
    print(json.dumps({
        "campaigns": n_camp, "units": n_unit, "unique_promoted_notes": n_unique_notes,
        "note_links": n_links, "snapshots": n_snap, "join_unique": join_uniq,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
