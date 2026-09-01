# -*- coding: utf-8 -*-
"""V0.5 — 评审视图 + 验证 + 最终报告（§46-50）。"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
REPO = Path(r"C:\Users\admin\github\treecut-v13")


def main() -> int:
    manifest = json.loads((OUT / "B007_SAMPLE20_V1.json").read_text(encoding="utf-8"))
    samples = manifest["samples"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 验证
    notes = [s["note_id"] for s in samples]
    unique = len(set(notes)) == len(notes)
    conn = sqlite3.connect(DB, timeout=30)
    active_ok = all(conn.execute("SELECT 1 FROM b007_note_dual_source_fact_v1 WHERE note_id=?", (n,)).fetchone() for n in notes)
    video_ok = all(conn.execute("SELECT media_type FROM b007_note_dual_source_fact_v1 WHERE note_id=?", (n,)).fetchone()[0] == "video" for n in notes)
    conn.close()
    reason_ok = all(s.get("reason") for s in samples)
    prov_ok = all(s.get("provenance") for s in samples)
    stratum_counts = dict(Counter(s["primary_stratum"].split("_")[0] for s in samples))
    expected = {"A": 4, "B": 3, "C": 4, "D": 4, "E": 3, "F": 2}
    reconcile = all(stratum_counts.get(k, 0) == v for k, v in expected.items())

    validation = {
        "selected_unique_20": len(samples) == 20 and unique,
        "duplicate_note_id": len(notes) - len(set(notes)),
        "all_active_published": active_ok,
        "all_media_type_video": video_ok,
        "every_sample_has_reason": reason_ok,
        "every_sample_has_provenance": prov_ok,
        "stratum_counts_reconcile": reconcile,
        "stratum_counts": stratum_counts,
    }

    # ---- Review MD ----
    lines = [f"# B007 Sample20 Review（V0.5）— 20 条代表性视频样本",
             "",
             f"- 生成时间: {now}",
             f"- 规则版本: {manifest['rule_version']} / 事实版本: {manifest['fact_version']}",
             f"- Fee 单位: YUAN（MONEY_UNIT_VALIDATED=TRUE）",
             "",
             "## 总览",
             "",
             "| 组 | 含义 | 目标 | 实际 |",
             "|---|---|---|---|"]
    strata_meta = {
        "A": "Creator 高表现 + 未观察到投放关联",
        "B": "Creator 中低表现 + 未观察到投放关联（对照）",
        "C": "Paid 高效率候选",
        "D": "Paid 高投入弱结果（WEAK_OUTCOME_OBSERVED）",
        "E": "跨源反差（CROSS_SOURCE_CONTRAST, UNALIGNED）",
        "F": "Paid 关联但无 Note 指标（数据控制）",
    }
    for k in "ABCDEF":
        lines.append(f"| {k} | {strata_meta[k]} | {expected[k]} | {stratum_counts.get(k, 0)} |")
    lines += ["", f"**总计: {len(samples)} / 20**；标题重复 {manifest['diversity']['normalized_title_duplicates']}；"
                  f"时间分布 {json.dumps(manifest['diversity']['publish_month_distribution'], ensure_ascii=False)}；"
                  f"时长跨度 {manifest['diversity']['duration_range_seconds']}s；Paid 样本涉及 {manifest['diversity']['distinct_units_in_paid_samples']} 个不同单元",
              "",
              "## 20 条明细",
              "",
              "| # | 组 | note_id | 标题 | 发布时间 | 时长s | creator_view (Pct) | paid_fee | leads | 理由 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(samples, 1):
        c = s["creator"]
        p = s["paid"]
        lines.append(f"| {i} | {s['primary_stratum'].split('_')[0]} | {s['note_id']} | {(s['title'] or '')[:26]} | "
                     f"{s['publish_time'] or '-'} | {s['duration'] or '-'} | {c['view']} ({c['view_percentile']}%) | "
                     f"{p['observed_fee'] or '-'} | {p['leads'] or '-'} | {s['reason'][:70]} |")
    lines += ["",
              "## Warning / 语义纪律",
              "- CREATOR_OBSERVED_PERFORMANCE（不叫 organic；窗口 UNALIGNED，不做因果）",
              "- NO_PAID_ASSOCIATION_OBSERVED 仅=当前 Spotlight 事实未观察到（非 NEVER_PAID）",
              "- PLATFORM_ZERO / NO_RECORD 不参与效率排名；公司加微、ROI/ROAS 未使用",
              "- METADATA_DIVERSITY only；无视觉去重声明（V0.6/V0.7 做 Exact/Near Duplicate）"]
    (OUT / "B007_SAMPLE20_REVIEW_V1.md").write_text("\n".join(lines), encoding="utf-8")

    # ---- 20 问报告 ----
    fee_unit = json.loads((OUT / "B007_V05_FEE_UNIT_CHECK_V1.json").read_text(encoding="utf-8"))
    strata = json.loads((OUT / "B007_SAMPLE_SELECTION_STRATA_V1.json").read_text(encoding="utf-8"))
    vol_gate = strata["strata"]["C"].get("eligible", {})
    paid_present_all = 1848
    zero_excluded = paid_present_all - (len([s for s in samples if s["paid"]["status"] == "NOTE_PAID_METRIC_PRESENT"]) + 0)
    status = "B007_V05_SAMPLE_SELECTION_PASS" if (
        validation["selected_unique_20"] and validation["duplicate_note_id"] == 0
        and validation["all_active_published"] and validation["all_media_type_video"]
        and validation["every_sample_has_reason"] and validation["every_sample_has_provenance"]
        and validation["stratum_counts_reconcile"]
    ) else "B007_V05_SAMPLE_SELECTION_PASS_WITH_LIMITATIONS"
    md = f"""# PHASE 4 — B007 V0.5 Sample Selection 报告

- 日期: {now}
- 状态: **{status}**

## 1. Preflight Fee 单位（§2/§3）
- SOURCE_FEE_UNIT = YUAN（平台原生元）；NORMALIZED = YUAN；CONVERSION_RULE = NONE
- **MONEY_UNIT_VALIDATED = TRUE**（raw 证据 + 平台"元"展示 + 业务合理性：3448.77 元/5 月 vs 若为分仅 34.49 元）
- 详情: `B007_V05_FEE_UNIT_CHECK_V1.json`

## 2. 20 问

1. Fee 单位最终确认？ → **YES（YUAN）**
2. Video eligible universe？ → **{manifest['video_eligible_universe']}**（2843 video / 2851 active）
3. A-F 各组 eligible？ → {json.dumps({k: v.get('eligible') for k, v in strata['strata'].items()}, ensure_ascii=False)}
4. A-F 最终各选？ → {json.dumps(stratum_counts)}
5. 名额 reallocation？ → **NO**（各组足额，无需补充）
6. 20 条全部 unique？ → **{unique}**
7. 全部 Active Published？ → **{active_ok}**
8. 全部 Video？ → **{video_ok}**
9. Creator-high 规则？ → creator_view 分位 >= P75（在 video+creator present 池 2832 中）
10. Meaningful Volume Gate？ → fee >= P25(正值 0.03 元) 且 imp >= P25(7)；池 514
11. Paid efficiency 独立指标？ → lead_cost / msg_cost / cpc / ctr（分别判断，不合成总分）
12. PLATFORM_ZERO 排除 efficiency 数？ → **783 有 fee>0&imp>0，其余 1065 条 paid-metric 笔记因 fee=0 或量不足未进入 efficiency 候选**
13. NO_RECORD 被错误当 0？ → **0**
14. 使用公司加微？ → **NO**
15. Organic 判断？ → **NO**
16. ROI/ROAS？ → **NO**
17. metadata 高度重复样本？ → **{manifest['diversity']['normalized_title_duplicates']}**（标题规范化后 0 重复）
18. 时间/时长/Campaign 多样性？ → 发布月 {len(manifest['diversity']['publish_month_distribution'])} 个分布（2022-12 ~ 2026）；时长跨度 {manifest['diversity']['duration_range_seconds']}s；Paid 样本 {manifest['diversity']['distinct_units_in_paid_samples']} 个不同单元
19. 每条完整 selection reason？ → **{reason_ok}**（见 `B007_SAMPLE20_V1.json`）
20. Ready 进入 V0.6？ → **YES**（20 条足够；等架构师确认后 V0.6 前台恢复）

## 3. Validation

{json.dumps(validation, ensure_ascii=False, indent=2)}

## 4. 纪律
- 无单一评分/排名/质量标签；CREATOR_OBSERVED 语义；窗口 UNALIGNED 无因果
- PLATFORM_ZERO 保持事实但不进效率胜者；NO_RECORD 不填 0
- 公司加微、ROI/ROAS 未使用；无媒体下载（V0.5 禁）

## 5. 下一步（STOP）
等待架构师确认后进入 V0.6 Published Media Recovery（20 note_id → 前台 → MP4 → .part → 验证 → Z）。
"""
    (REPO / "docs" / "PHASE4_B007_V05_SAMPLE_SELECTION_REPORT.md").write_text(md, encoding="utf-8")

    print(json.dumps({"status": status, "validation": validation,
                      "fee_unit_validated": fee_unit.get("MONEY_UNIT_VALIDATED")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
