# PHASE4 STAGE 2 — HUMAN TRUTH RELIABILITY SCORING（V1 vs V2）

> 状态：**V2 12/12 已冻结 · 比较已运行 · 判定=UNRELIABLE_FOR_CALIBRATION（受 V2 数据质量影响，需谨慎解读）· STOP**
> 日期：2026-08-29
> 纪律：未修改 AI_LOCK / Business Rules / Knowledge / Engine · 未调参 · 未重新生成 AI answers · 未进 Stage2.1 / Stage3

---

## ⚠️ 首要发现：V2 数据本身存在系统性质量问题

在给出比较结论前必须先声明：**Adjudication V2 的 12 条数据被 UI 交互缺陷污染**，不能作为干净裁决：

1. **evidence_sufficiency 12/12 全为 SUFFICIENT** —— 包括 V1 判 `overall_unknown=YES` 的 2 条（b2f971、31b98294），它们在 V2 也是 SUFFICIENT 但 **clearly=0 / possible=0**（自相矛盾：标"证据充分"却一个业务标签都不选）
2. **possible 区 5 段全选**：a1223854(20)/d780c9ed(21)/66cc4382(21)/75c6e986(21)/d96ec717(21) —— "可能相关"区被当成清单浏览区
3. **128 处 clearly∩possible 标签重叠** —— 同一标签两区都勾（语义矛盾：不可能既"明确支持"又"可能但证据不足"）

**结论**：V2 复核 UI（两个 21 项多选区上下排列、无排他/去重提示）导致审核者产生"全选 + 重复选择"行为。**V2 的 CLEARLY 集合与 evidence 字段不可全信**。

---

## 1. 完成与冻结

**12/12 完成且冻结** ✅（`stage2_business_cognition_adjudication_v2b` 表 12 行，唯一段 12，无缺失；数据保留未删）

## 2-3. V1 vs V2 比较（needs / values）

| 字段 | exact-set 段 | Jaccard | additions | removals |
|---|---|---|---|---|
| user_needs | 4/12 | 0.24 | 22 | 54 |
| business_values | 5/12 | 0.26 | 21 | 50 |

- 高影响一致率（needs+values 逐 label）= **0.393**（95/242）
- V1→POSSIBLE 迁移 = **97 条**（证实 V1 大量多选属于"关联性"而非"证据性"）

## 4-6. V2 稀疏度（去重叠后）

| 指标 | V2（去重叠） | V1 参考 |
|---|---|---|
| 每段平均 CLEARLY needs | **5.67**（2,15,7,9,2,9,0,0,6,12,4,2）| 8.2 |
| 每段平均 CLEARLY values | **5.83**（3,7,9,10,2,5,0,0,6,14,3,11）| 7.8 |
| 每段平均 POSSIBLE（needs+values）| **23.33** | — |

- **下降但不彻底**：needs 8.2→5.67（-31%）、values 7.8→5.83（-25%）
- **但 V2 仍偏高**（部分段 clearly=15/12），且 POSSIBLE 均值 23.33 说明"可能相关"区被滥用 → **无法确认"2~4 个 CLEARLY"的稀疏期望**

## 7. 相比 V1 是否显著下降

**部分下降，但受 V2 数据污染，不能确认显著**。V2 clearly 均值 5.67/5.83 未达 2~4 期望，主要因：
- 5 段 POSSIBLE 全选拉高噪声
- 128 处重叠使 CLEARLY 集合偏大（部分标签用户其实只想要"可能"却也被计入 clearly）

## 8. 原 6 个 needs+values FP 重判（本报告最有价值的信号）

| 原 FP | V2 状态 | 含义 |
|---|---|---|
| 40d5fdbe STORAGE | **NOT_SUPPORTED** | **真 FP**（AI 错）|
| 40d5fdbe STORAGE_EFFICIENCY | **NOT_SUPPORTED** | **真 FP**（AI 错）|
| bf686b31 STORAGE_EFFICIENCY | **NOT_SUPPORTED** | **真 FP**（AI 错）|
| a1223854 CHARGING_POWER | **CLEARLY_SUPPORTED** | **假 FP**（V1 漏标，AI 对）|
| 80f182c8 POWER_CONVENIENCE | **CLEARLY_SUPPORTED** | **假 FP**（V1 漏标，AI 对）|
| d780c9ed STORAGE | **POSSIBLE_BUT_INSUFFICIENT** | AI 方向合理但 SUPPORTED 过强 |

**洗牌结果：3 真 FP + 2 假 FP + 1 POSSIBLE**
- 若按此修正：原 6 FP 中 2 个应转 TP → **原 UCR=15% 确实高估**，真实 UCR 可能约 7-8%
- ⚠️ 但注意：a1223854/80f182c8 两段 POSSIBLE 区全选（20/21），其 CLEARLY 判定**受污染**——假 FP 结论需谨慎，方向性成立（AI 可能没那么错），数值不能直接引用

## 9. search_intent FP（3 个 ISLAND_STORAGE）

**NOT_REVIEWED_IN_ADJUDICATION_V2** —— V2b 不审 search_intent，不用于核心可靠性判定。✅ 符合指令

## 10-11. Confidence

- HIGH: 2 条（b2f971、31b98294——恰是 V1 unknown 的两条，V2 全空 + HIGH）
- MEDIUM: 10 条 · LOW: 0 条
- **HIGH-confidence 子集一致率 = 无法计算**（2 条 HIGH 段 V1 也几乎空，无标签可比）
- LOW-confidence 数量 = 0（用户未使用"不确定"选项——复核者仍倾向于给出判断而非承认不确定）

## 12-13. V1 疲劳/过标信号 & V2 稀疏性

- **V1 过标信号确认**：97 条 V1 标签在 V2 迁往 POSSIBLE —— V1 的 8.2/7.8 均值主要来自"关联性"多选
- **V2 未明显更稀疏**：因 POSSIBLE 区被全选滥用，V2 的"证据导向"被稀释；仅 overlap=0 的 2 条（b2f971/31b98294）是干净的"零主张"段

## 14. 最终 Reliability Verdict

**UNRELIABLE_FOR_CALIBRATION**（原始比较 0.393 < 0.70）

**但必须声明**：该判定部分由 V2 数据质量（UI 缺陷）驱动，而非纯 V1 不可靠。正确解读：
- **确认的**：V1 过标真实存在（97 迁移）、原 6 FP 至少 3 个真 FP、UCR 15% 高估
- **无法确认的**：V2 的 CLEARLY 精确值（受重叠/全选污染）、evidence 字段（全 SUFFICIENT 不可信）

## 15. Human24 旧指标

**Precision 0.85 / UCR 0.15 仍只能 DIAGNOSTIC_ONLY** ✅ —— 且本次确认 UCR 高估，更不能作成绩

## 16. 是否允许进入 Stage2.1

**否** —— 当前不进入 Stage2.1 Claim Gating。原因：
1. V1 不可靠（已确认过标）
2. V2 被 UI 缺陷污染，无法作为干净裁决真值
3. "人工尺子"尚未校准成功

---

## 下一步建议（不自动执行）

**修复 V2b 复核 UI 后重做 12 条**（不需要重新设计全部流程）：
1. **排他单选设计**：每个标签改为 3 态单选（CLEARLY / POSSIBLE / 不选）而非两个独立多选区——从根上消除重叠与全选
2. **evidence 字段修复**：移除默认值/改为显式必选，且提供"证据不足→不应标 CLEARLY"的联动提示
3. **POSSIBLE 区上限提示**：限制"可能相关"数量（如 ≤5），防止清单浏览式全选
4. 重做 12 条后重新运行 `stage4_human24_v1_vs_v2.py`

**原 FP 洗牌的方向性结论已可用**：AI 的 CHARGING_POWER/POWER_CONVENIENCE 主张可能并非错误（V1 漏标），STORAGE 类 3 个 FP 大概率是真 FP——这为未来规则收紧提供了方向（STORAGE 外推需证据门控），但**数值不能引用**。

---

## 产物
- `HUMAN24_V1_VS_V2_COMPARISON.json`（原始比较，UNRELIABLE 0.393）
- 本报告 `docs/PHASE4_STAGE2_HUMAN_TRUTH_RELIABILITY_SCORING.md`
- V2 12 条冻结保留（未删未改）· 未修改任何 AI/Rules/Knowledge/Engine

## 停点

**STOP** —— 未自动执行 Stage2.1。等修复 V2b UI 后排期重做 12 条复核。
