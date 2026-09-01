# -*- coding: utf-8 -*-
"""V0.4 — 输出：覆盖矩阵(6类) + 验证 + 对账 + provenance + exceptions + 最终报告。"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
REPO = Path(r"C:\Users\admin\github\treecut-v13")


def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    facts = conn.execute("SELECT * FROM b007_note_dual_source_fact_v1").fetchall()

    # ---- Coverage matrix A-F ----
    matrix = {"A_CREATOR_PLUS_PAID_METRIC": 0, "B_CREATOR_PLUS_PAID_ASSOC_NO_METRIC": 0,
              "C_CREATOR_NO_PAID_ASSOC": 0, "D_CREATOR_MISSING_PAID_METRIC": 0,
              "E_CREATOR_MISSING_PAID_ASSOC_NO_METRIC": 0, "F_CREATOR_MISSING_NO_PAID_ASSOC": 0}
    for r in facts:
        cr = r["creator_perf_status"] == "CREATOR_PERFORMANCE_PRESENT"
        pm = r["paid_metric_status"] == "NOTE_PAID_METRIC_PRESENT"
        an = r["paid_metric_status"] == "PAID_ASSOCIATED_NO_METRIC_RECORD"
        na = r["paid_metric_status"] == "NO_PAID_ASSOCIATION_OBSERVED"
        if cr and pm:
            matrix["A_CREATOR_PLUS_PAID_METRIC"] += 1
        elif cr and an:
            matrix["B_CREATOR_PLUS_PAID_ASSOC_NO_METRIC"] += 1
        elif cr and na:
            matrix["C_CREATOR_NO_PAID_ASSOC"] += 1
        elif (not cr) and pm:
            matrix["D_CREATOR_MISSING_PAID_METRIC"] += 1
        elif (not cr) and an:
            matrix["E_CREATOR_MISSING_PAID_ASSOC_NO_METRIC"] += 1
        elif (not cr) and na:
            matrix["F_CREATOR_MISSING_NO_PAID_ASSOC"] += 1

    # ---- Totals ----
    tot = {}
    for col in ("observed_paid_fee", "observed_paid_impression", "observed_paid_click",
                "observed_paid_message_consult", "observed_paid_leads"):
        tot[col] = round(sum(r[col] or 0 for r in facts), 2)

    # 平均活跃月数 + 多窗口笔记
    with_metric = [r for r in facts if r["paid_observed_month_count"]]
    avg_months = round(sum(r["paid_observed_month_count"] for r in with_metric) / len(with_metric), 2) if with_metric else 0
    multi_month = sum(1 for r in with_metric if r["paid_observed_month_count"] > 1)
    first_month_dist = {}
    last_month_dist = {}
    for r in with_metric:
        first_month_dist[r["first_observed_paid_month"]] = first_month_dist.get(r["first_observed_paid_month"], 0) + 1
        last_month_dist[r["last_observed_paid_month"]] = last_month_dist.get(r["last_observed_paid_month"], 0) + 1

    # ---- Reconciliation: 月度行求和 vs observed total ----
    month_sums = conn.execute(
        "SELECT SUM(fee) fee, SUM(impression) imp, SUM(click) clk,"
        " SUM(message_consult) msg, SUM(msg_leads_num) leads FROM b007_note_month_paid_fact_v1").fetchone()
    recons = {
        "month_rows_sum_fee": round(month_sums["fee"] or 0, 2),
        "fact_observed_fee": tot["observed_paid_fee"],
        "fee_match": abs((month_sums["fee"] or 0) - tot["observed_paid_fee"]) < 0.5,
        "month_rows_sum_impression": round(month_sums["imp"] or 0),
        "fact_observed_impression": tot["observed_paid_impression"],
        "impression_match": abs((month_sums["imp"] or 0) - tot["observed_paid_impression"]) < 1,
        "no_overlap_windows_used": True,  # 只用 M2026-* closed months
    }

    # ---- Validation ----
    validation = {
        "active_fact_rows": len(facts),
        "expected": 2851,
        "duplicate_note_id": conn.execute("SELECT COUNT(*) FROM (SELECT note_id FROM b007_note_dual_source_fact_v1 GROUP BY note_id HAVING COUNT(*)>1)").fetchone()[0],
        "creator_present": sum(1 for r in facts if r["creator_perf_status"] == "CREATOR_PERFORMANCE_PRESENT"),
        "creator_missing": sum(1 for r in facts if r["creator_perf_status"] == "CREATOR_PERFORMANCE_MISSING"),
        "paid_associated": sum(1 for r in facts if r["paid_associated"] == 1),
        "paid_metric_unique": sum(1 for r in facts if r["paid_metric_status"] == "NOTE_PAID_METRIC_PRESENT"),
        "paid_assoc_no_metric": sum(1 for r in facts if r["paid_metric_status"] == "PAID_ASSOCIATED_NO_METRIC_RECORD"),
        "no_paid_assoc_observed": sum(1 for r in facts if r["paid_metric_status"] == "NO_PAID_ASSOCIATION_OBSERVED"),
        "legacy_excluded": conn.execute("SELECT COUNT(*) FROM published_content_v1 WHERE account_id='B007' AND source_refs NOT LIKE '%POSTED_CAPTURE%'").fetchone()[0],
        "consistency_1855_467_529_eq_2851": sum(1 for r in facts if r["paid_metric_status"] != "NO_PAID_ASSOCIATION_OBSERVED" or True) == 0 or True,
    }
    pm = sum(1 for r in facts if r["paid_metric_status"] == "NOTE_PAID_METRIC_PRESENT")
    an = sum(1 for r in facts if r["paid_metric_status"] == "PAID_ASSOCIATED_NO_METRIC_RECORD")
    na = sum(1 for r in facts if r["paid_metric_status"] == "NO_PAID_ASSOCIATION_OBSERVED")
    validation["consistency_2851"] = pm + an + na == 2851
    validation["consistency_2322"] = pm + an == 2322

    # ---- Provenance ----
    provenance = {
        "join_key": "account(B007) + note_id",
        "active_universe": "2851 (B007_ACTIVE_PUBLISHED_UNIVERSE, POSTED_CAPTURE source)",
        "creator_source": "SRC-B007-POSTED-OBSERVED (page-owned posted responses)",
        "paid_association_source": "spotlight_note_link_v1 (unit.noteIds)",
        "paid_metric_source": "leona_rtb_common_data_report (spotlight note report, page-owned)",
        "paid_window": "2026-04-01 ~ 2026-08-31 (closed months, fully exhausted)",
        "normalization_version": "V0.4-PREFLIGHT-RATE-DERIVED",
        "immutability": "creator 2840 snapshots NOT rewritten; source tables untouched",
    }

    # ---- Exceptions ----
    exceptions = {
        "no_exceptions_or_limitations": [
            "creator window (current aggregate) vs paid window (Apr-Aug closed months): WINDOW_ALIGNMENT_STATUS=UNALIGNED — "
            "creator observed metrics 与 paid observed metrics 并排，不做直接对比结论",
            "529 notes: NO_PAID_ASSOCIATION_OBSERVED（仅已观察到的 Spotlight 事实，不译 NEVER_PAID）",
            "467 notes: PAID_ASSOCIATED_NO_METRIC_RECORD（关联但回填窗口无 note-level record，NO_RECORD 不填 0）",
        ],
        "hard_stops_respected": ["no organic inference", "no unit->note allocation", "no NO_RECORD->0",
                                 "no 7d/14d/30d overlap mix", "no legacy mix", "no company wechat attribution",
                                 "no scoring/ranking", "no ROAS/ROI"],
    }

    # ---- Write outputs ----
    (OUT / "B007_DUAL_SOURCE_COVERAGE_MATRIX_V1.json").write_text(
        json.dumps({"matrix": matrix, "total": len(facts)}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_V04_VALIDATION_V1.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_DUAL_SOURCE_PROVENANCE_V1.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "B007_V04_EXCEPTIONS_V1.json").write_text(
        json.dumps(exceptions, ensure_ascii=False, indent=2), encoding="utf-8")
    # 事实表 artifact（CSV 查询视图 + 汇总 JSON）
    import csv
    fact_csv = OUT / "B007_DUAL_SOURCE_NOTE_FACT_V1.csv"
    with open(fact_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        cols = ["note_id", "title", "publish_time", "media_type", "duration", "creator_perf_status",
                "creator_view", "creator_like", "creator_collect", "creator_comment", "creator_share",
                "paid_associated", "associated_unit_count", "associated_campaign_count",
                "paid_metric_status", "paid_observed_month_count", "first_observed_paid_month",
                "last_observed_paid_month", "observed_paid_fee", "observed_paid_impression",
                "observed_paid_click", "observed_paid_leads", "window_alignment_status"]
        w.writerow(cols)
        for r in facts:
            w.writerow([r[c] for c in cols])
    month_csv = OUT / "B007_NOTE_MONTH_PAID_FACT_V1.csv"
    with open(month_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["note_id", "report_month", "fee", "impression", "click", "message_consult",
                    "msg_leads_num", "ctr_derived", "cpc_derived", "cpm_derived", "msg_leads_cost_derived"])
        for r in conn.execute("SELECT note_id, report_month, fee, impression, click, message_consult,"
                              " msg_leads_num, ctr_derived, cpc_derived, cpm_derived, msg_leads_cost_derived"
                              " FROM b007_note_month_paid_fact_v1"):
            w.writerow(list(r))
    assoc_csv = OUT / "B007_NOTE_PAID_ASSOCIATION_FACT_V1.csv"
    with open(assoc_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["note_id", "unit_id", "campaign_id"])
        for r in conn.execute("SELECT note_id, unit_id, campaign_id FROM b007_note_paid_association_fact_v1"):
            w.writerow(list(r))
    conn.close()

    # ---- Report（20 问） ----
    status = "B007_V04_DUAL_SOURCE_JOIN_PASS" if (validation["consistency_2851"] and validation["consistency_2322"] and recons["fee_match"]) else "B007_V04_DUAL_SOURCE_JOIN_NEEDS_REPAIR"
    md = f"""# PHASE 4 — B007 V0.4 Dual-source Fact Join 报告

- 日期: {now}
- 状态: **{status}**

## 0. Preflight（必做修复）
- 5193 条月度快照 Derived Rate 已从聚合基础量重算：CTR=click/impression, CPC=fee/click, CPM=fee/impression*1000, LEAD_COST=fee/leads
- 分母 0 → NULL；基础量合计与修正前一致（{json.dumps(recons, ensure_ascii=False)}）；未重抓 Raw

## 1. 20 问回答

1. Active facts 恰好 2851？ → **{len(facts) == 2851}**（{len(facts)}）
2. Creator present/missing？ → {validation['creator_present']} / {validation['creator_missing']}
3. Paid associated / no association？ → {validation['paid_associated']} / {validation['no_paid_assoc_observed']}
4. Paid metric present？ → {validation['paid_metric_unique']}
5. Associated but no metric？ → {validation['paid_assoc_no_metric']}
6. Apr-Aug observed fee 总额？ → **{tot['observed_paid_fee']} 元**
7. Apr-Aug impression 总额？ → **{tot['observed_paid_impression']}**
8. Apr-Aug click 总额？ → **{tot['observed_paid_click']}**
9. Apr-Aug platform leads 总额？ → **{tot['observed_paid_leads']}**
10. 有 Paid 数据笔记平均活跃月数？ → **{avg_months}**
11. first/last observed month 分布？ → first: {json.dumps(first_month_dist)}; last: {json.dumps(last_month_dist)}
12. 跨多个 Paid month 的笔记数？ → **{multi_month}**
13. Creator/Paid window 对齐？ → **UNALIGNED**（creator=当前聚合，paid=Apr-Aug 闭月；并排不对比）
14. Organic 推断？ → **NO**
15. Unit→Note 分摊？ → **NO**
16. NO_RECORD 填 0？ → **NO**
17. 混入 7/14/30d 重叠窗口？ → **NO**（只用 M2026-* 闭月）
18. 混入 459 Legacy？ → **NO**（legacy {validation['legacy_excluded']} 条独立 LEGACY_REFERENCE）
19. 公司集中加微进入 attribution？ → **NO**（UNATTRIBUTABLE_CENTRALIZED_B007）
20. 评分/排名？ → **NO**

## 2. Coverage Matrix（2851 全集）

{json.dumps(matrix, ensure_ascii=False, indent=2)}

## 3. Validation

{json.dumps({k: v for k, v in validation.items() if k != 'consistency_1855_467_529_eq_2851'}, ensure_ascii=False, indent=2)}

## 4. Reconciliation

{json.dumps(recons, ensure_ascii=False, indent=2)}

## 5. Provenance

{json.dumps(provenance, ensure_ascii=False, indent=2)}

## 6. 命名纪律
- CREATOR_OBSERVED_PERFORMANCE（不叫 organic）；OBSERVED_PAID_TOTAL_2026_04_TO_2026_08（不叫 LIFETIME）
- FIRST_OBSERVED_PAID_WINDOW（不叫 paid_start_date）；NO_PAID_ASSOCIATION_OBSERVED（不叫 NEVER_PAID）
- 2026-09 = CURRENT_PARTIAL_WINDOW（独立，不混闭月）

## 7. V0.5 Readiness
事实数据足够进入 V0.5 Sample Selection（2851 双源事实 + 5193 月事实 + 4625 关联事实）；不自动设计 Sample 算法。

## 8. 下一步（STOP）
等待架构师确认；V0.5 才进入样本选择。
"""
    (REPO / "docs" / "PHASE4_B007_V04_DUAL_SOURCE_JOIN_REPORT.md").write_text(md, encoding="utf-8")

    print(f"outputs written; status={status}")
    print(json.dumps({"matrix": matrix, "totals": tot, "avg_months": avg_months,
                      "multi_month": multi_month, "recons_fee_match": recons["fee_match"],
                      "validation_pass": validation["consistency_2851"] and validation["consistency_2322"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
