# PHASE 4 — B007 V0.5 Sample Selection 报告

- 日期: 2026-09-01 12:08:01
- 状态: **B007_V05_SAMPLE_SELECTION_PASS**

## 1. Preflight Fee 单位（§2/§3）
- SOURCE_FEE_UNIT = YUAN（平台原生元）；NORMALIZED = YUAN；CONVERSION_RULE = NONE
- **MONEY_UNIT_VALIDATED = TRUE**（raw 证据 + 平台"元"展示 + 业务合理性：3448.77 元/5 月 vs 若为分仅 34.49 元）
- 详情: `B007_V05_FEE_UNIT_CHECK_V1.json`

## 2. 20 问

1. Fee 单位最终确认？ → **YES（YUAN）**
2. Video eligible universe？ → **2843**（2843 video / 2851 active）
3. A-F 各组 eligible？ → {"A": 74, "B": 182, "C": {"gate_pool": 514, "leads>0": 20, "msg>0": 44, "clicks>0": 514}, "D": 102, "E": 321, "F": 467}
4. A-F 最终各选？ → {"A": 4, "B": 3, "C": 4, "D": 4, "E": 3, "F": 2}
5. 名额 reallocation？ → **NO**（各组足额，无需补充）
6. 20 条全部 unique？ → **True**
7. 全部 Active Published？ → **True**
8. 全部 Video？ → **True**
9. Creator-high 规则？ → creator_view 分位 >= P75（在 video+creator present 池 2832 中）
10. Meaningful Volume Gate？ → fee >= P25(正值 0.03 元) 且 imp >= P25(7)；池 514
11. Paid efficiency 独立指标？ → lead_cost / msg_cost / cpc / ctr（分别判断，不合成总分）
12. PLATFORM_ZERO 排除 efficiency 数？ → **783 有 fee>0&imp>0，其余 1065 条 paid-metric 笔记因 fee=0 或量不足未进入 efficiency 候选**
13. NO_RECORD 被错误当 0？ → **0**
14. 使用公司加微？ → **NO**
15. Organic 判断？ → **NO**
16. ROI/ROAS？ → **NO**
17. metadata 高度重复样本？ → **0**（标题规范化后 0 重复）
18. 时间/时长/Campaign 多样性？ → 发布月 13 个分布（2022-12 ~ 2026）；时长跨度 149.0s；Paid 样本 20 个不同单元
19. 每条完整 selection reason？ → **True**（见 `B007_SAMPLE20_V1.json`）
20. Ready 进入 V0.6？ → **YES**（20 条足够；等架构师确认后 V0.6 前台恢复）

## 3. Validation

{
  "selected_unique_20": true,
  "duplicate_note_id": 0,
  "all_active_published": true,
  "all_media_type_video": true,
  "every_sample_has_reason": true,
  "every_sample_has_provenance": true,
  "stratum_counts_reconcile": true,
  "stratum_counts": {
    "A": 4,
    "B": 3,
    "C": 4,
    "D": 4,
    "E": 3,
    "F": 2
  }
}

## 4. 纪律
- 无单一评分/排名/质量标签；CREATOR_OBSERVED 语义；窗口 UNALIGNED 无因果
- PLATFORM_ZERO 保持事实但不进效率胜者；NO_RECORD 不填 0
- 公司加微、ROI/ROAS 未使用；无媒体下载（V0.5 禁）

## 5. 下一步（STOP）
等待架构师确认后进入 V0.6 Published Media Recovery（20 note_id → 前台 → MP4 → .part → 验证 → Z）。
