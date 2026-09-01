# PHASE 4 — B007 V0.3.2 报告：Note Paid Metrics 全覆盖 + 历史回填

- 日期: 2026-09-01 11:03:51
- 状态: **B007_V032_PAID_HISTORY_PASS**

## 1. 分页问题解决（§31）

**根因**：分页省略号。页码按钮只渲染 `1 2 3 4 5 ... N`，省略号后的目标页码无 DOM 元素 → 原按页码点击在省略号后失效（卡 ~10 页）。

**方案**：页大小 **100 条/页**（真实 d-select 选择器）+ **下一页 icon 按钮**持续点击（真实 Playwright click）。
实测：2641 行从 133 页(20/页) → 27 页(100/页)；April 从 255 页 → 51 页。

**NOTE_REPORT_EXHAUSTED**：{"M2026-04": "UNKNOWN", "M2026-05": "UNKNOWN", "M2026-06": "UNKNOWN", "M2026-07": "UNKNOWN", "M2026-08": "UNKNOWN"}（next disabled 判定）

## 2. 历史回填（互不重叠自然月 2026-04..08）

| 窗口 | 页数 | 行数 | 唯一笔记 | fee 非空 | 穷尽 |
|---|---|---|---|---|---|
| M2026-04 | 51 | 1230 | 1230 | 1230 | True |
| M2026-05 | 77 | 1308 | 1308 | 1308 | True |
| M2026-06 | 38 | 963 | 963 | 963 | True |
| M2026-07 | 31 | 881 | 881 | 881 | True |
| M2026-08 | 28 | 811 | 811 | 811 | True |

## 3. 覆盖（§30）

- A 尝试窗口: ['M2026-04', 'M2026-05', 'M2026-06', 'M2026-07', 'M2026-08']
- B 穷尽 TRUE: ['M2026-04', 'M2026-05', 'M2026-06', 'M2026-07', 'M2026-08']
- C 部分: 无
- D 总行数: 5193
- E 有指标唯一笔记: **1855**
- F 付费关联笔记: 2322
- G 覆盖比: **79.9%**
- H ACTIVE 匹配: 1855
- I LEGACY 匹配: 0
- J UNMATCHED: 0
- M ZERO 笔记: 1698（平台明确 fee=0）
- N 缺失/无记录: 467（2322 - 有记录笔记；= NO_RECORD_IN_WINDOW，不填 0）
- O 失败窗口: 无

## 4. 就绪标志（§32）

{
  "IDENTITY_JOIN_READY": true,
  "ASSOCIATION_JOIN_READY": true,
  "NOTE_PAID_METRIC_JOIN_READY": true,
  "HISTORICAL_PAID_JOIN_READY": true,
  "historical_note": "1855 unique notes with paid metrics across 5 non-overlapping months (5193 month-note rows); coverage 79.9% of 2322 paid-associated"
}

## 5. OBSERVED_PAID_TOTAL（§22/§23/§24）

- 基于互不重叠月度窗口加总 → OBSERVED_PAID_TOTAL_FEE/IMPRESSIONS/CLICKS/LEADS
- **绝不命名为 LIFETIME**；7d/14d/30d 重叠窗口不参与加总

## 6. 下一步（STOP — 不自动进入 V0.4）

V0.4 可直接执行（HISTORICAL_PAID_JOIN_READY=True）；等架构师确认。
