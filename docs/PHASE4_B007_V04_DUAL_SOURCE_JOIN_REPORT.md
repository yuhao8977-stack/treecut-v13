# PHASE 4 — B007 V0.4 Dual-source Fact Join 报告

- 日期: 2026-09-01 11:46:27
- 状态: **B007_V04_DUAL_SOURCE_JOIN_PASS**

## 0. Preflight（必做修复）
- 5193 条月度快照 Derived Rate 已从聚合基础量重算：CTR=click/impression, CPC=fee/click, CPM=fee/impression*1000, LEAD_COST=fee/leads
- 分母 0 → NULL；基础量合计与修正前一致（{"month_rows_sum_fee": 3448.77, "fact_observed_fee": 3448.77, "fee_match": true, "month_rows_sum_impression": 83405, "fact_observed_impression": 83405.0, "impression_match": true, "no_overlap_windows_used": true}）；未重抓 Raw

## 1. 20 问回答

1. Active facts 恰好 2851？ → **True**（2851）
2. Creator present/missing？ → 2840 / 11
3. Paid associated / no association？ → 2322 / 529
4. Paid metric present？ → 1855
5. Associated but no metric？ → 467
6. Apr-Aug observed fee 总额？ → **3448.77 元**
7. Apr-Aug impression 总额？ → **83405.0**
8. Apr-Aug click 总额？ → **9877.0**
9. Apr-Aug platform leads 总额？ → **36.0**
10. 有 Paid 数据笔记平均活跃月数？ → **2.8**
11. first/last observed month 分布？ → first: {"M2026-04": 1230, "M2026-05": 323, "M2026-06": 105, "M2026-08": 95, "M2026-07": 102}; last: {"M2026-07": 375, "M2026-04": 121, "M2026-05": 273, "M2026-06": 275, "M2026-08": 811}
12. 跨多个 Paid month 的笔记数？ → **1384**
13. Creator/Paid window 对齐？ → **UNALIGNED**（creator=当前聚合，paid=Apr-Aug 闭月；并排不对比）
14. Organic 推断？ → **NO**
15. Unit→Note 分摊？ → **NO**
16. NO_RECORD 填 0？ → **NO**
17. 混入 7/14/30d 重叠窗口？ → **NO**（只用 M2026-* 闭月）
18. 混入 459 Legacy？ → **NO**（legacy 459 条独立 LEGACY_REFERENCE）
19. 公司集中加微进入 attribution？ → **NO**（UNATTRIBUTABLE_CENTRALIZED_B007）
20. 评分/排名？ → **NO**

## 2. Coverage Matrix（2851 全集）

{
  "A_CREATOR_PLUS_PAID_METRIC": 1849,
  "B_CREATOR_PLUS_PAID_ASSOC_NO_METRIC": 464,
  "C_CREATOR_NO_PAID_ASSOC": 527,
  "D_CREATOR_MISSING_PAID_METRIC": 6,
  "E_CREATOR_MISSING_PAID_ASSOC_NO_METRIC": 3,
  "F_CREATOR_MISSING_NO_PAID_ASSOC": 2
}

## 3. Validation

{
  "active_fact_rows": 2851,
  "expected": 2851,
  "duplicate_note_id": 0,
  "creator_present": 2840,
  "creator_missing": 11,
  "paid_associated": 2322,
  "paid_metric_unique": 1855,
  "paid_assoc_no_metric": 467,
  "no_paid_assoc_observed": 529,
  "legacy_excluded": 459,
  "consistency_2851": true,
  "consistency_2322": true
}

## 4. Reconciliation

{
  "month_rows_sum_fee": 3448.77,
  "fact_observed_fee": 3448.77,
  "fee_match": true,
  "month_rows_sum_impression": 83405,
  "fact_observed_impression": 83405.0,
  "impression_match": true,
  "no_overlap_windows_used": true
}

## 5. Provenance

{
  "join_key": "account(B007) + note_id",
  "active_universe": "2851 (B007_ACTIVE_PUBLISHED_UNIVERSE, POSTED_CAPTURE source)",
  "creator_source": "SRC-B007-POSTED-OBSERVED (page-owned posted responses)",
  "paid_association_source": "spotlight_note_link_v1 (unit.noteIds)",
  "paid_metric_source": "leona_rtb_common_data_report (spotlight note report, page-owned)",
  "paid_window": "2026-04-01 ~ 2026-08-31 (closed months, fully exhausted)",
  "normalization_version": "V0.4-PREFLIGHT-RATE-DERIVED",
  "immutability": "creator 2840 snapshots NOT rewritten; source tables untouched"
}

## 6. 命名纪律
- CREATOR_OBSERVED_PERFORMANCE（不叫 organic）；OBSERVED_PAID_TOTAL_2026_04_TO_2026_08（不叫 LIFETIME）
- FIRST_OBSERVED_PAID_WINDOW（不叫 paid_start_date）；NO_PAID_ASSOCIATION_OBSERVED（不叫 NEVER_PAID）
- 2026-09 = CURRENT_PARTIAL_WINDOW（独立，不混闭月）

## 7. V0.5 Readiness
事实数据足够进入 V0.5 Sample Selection（2851 双源事实 + 5193 月事实 + 4625 关联事实）；不自动设计 Sample 算法。

## 8. 下一步（STOP）
等待架构师确认；V0.5 才进入样本选择。
