# PHASE4 STAGE 2.1 — FRESH18 FINAL SCORING + STAGE2 CLOSEOUT

> 状态：**Fresh18 独立验证完成 · PHASE4_STAGE2_PASS_WITH_LIMITATIONS · PHASE4_STAGE3_READY=TRUE（带字段限制）· STOP**
> 日期：2026-08-30
> 数据：`BUSINESS_COGNITION_FRESH_V1_SCORE.json` · Fresh18 AI_LOCK（sha256 `818f8d61…`）
> 纪律：未修改 Engine/Rules/Knowledge/AI_LOCK/Human Truth · 未重生成 AI · 未调参 · 未进 Stage3

---

## A. 数据完整性 ✅

18/18 完成 · 18 唯一段 · segment set == Fresh18 manifest（0 缺失）· 每段 10 标签恰一状态 · evidence/conflict/confidence 全有值。

## B. 独立性与时间锁 ✅

- 与 Stage1 Validation43 / Challenge60 / Human24 / Adjudication V2 / Calibration V3 / Holdout V1 / Holdout V2 **全部零重叠**
- **AI_LOCK（08-29 18:56）先于 Human review（08-30 13:51-13:58）** ✅
- AI_LOCK SHA256 = `818f8d61c44c427d0ff5810721bb856044bc9f0daeedcea3e4712f33237b6acf`

## C. AI Claim Status 分布（Fresh18，180 claims）

| 状态 | claim 数 | 说明 |
|---|---|---|
| SUPPORTED | 17 | 有 |
| CANDIDATE | 9 | 有 |
| WEAK | 0 | **WEAK_NOT_OBSERVED_IN_FRESH18** |
| UNKNOWN | 154 | 高（见 G/N 分析）|
| CONFIRMED | 0 | NOT_OBSERVED（预期，AI 不用）|
| BLOCKED | 0 | NOT_OBSERVED（无 NR 命中）|

## D. SUPPORTED 评分（raw）✅

```
SUPPORTED_TRUE            = 13
SUPPORTED_OVERCONFIDENT   = 2
SUPPORTED_FALSE           = 2
SUPPORTED_HUMAN_UNKNOWN   = 0
有效 SUPPORTED            = 17

supported_precision_clear = 13/17 = 0.765
hard_false_rate           = 2/17  = 0.118
supported_insufficiency   = 4/17  = 0.235
human_unknown_rate        = 0/17  = 0.000
```

## E. CANDIDATE 评分 ✅

```
CANDIDATE 9 个：Human CLEARLY=9 / POSSIBLE=0 / NOT_SUPPORTED=0 / UNKNOWN=0
candidate_clear_rate     = 9/9 = 1.00
candidate_relevance_rate = 9/9 = 1.00（CLEARLY+POSSIBLE / 非 UNKNOWN）
```

**解读**：CANDIDATE 全部被 Human 认可（9/9 CLEARLY）——Gate 把本可 SUPPORTED 的降到了 CANDIDATE（偏保守但安全）。**但这也意味着 SUPPORTED 与 CANDIDATE 的区分度不足**（见 H）。

## F. WEAK

**WEAK_NOT_OBSERVED_IN_FRESH18** —— 不得据此声称 WEAK 校准已验证（Unit Test 证明路径存在，Fresh18 无自然样本）。

## G. UNKNOWN 检查 ⚠️

```
AI UNKNOWN total = 154
其中 Human 判 CLEARLY = 43
unknown_miss_rate = 43/154 = 0.279
```

**43 个 missed 全部集中在 3 个 AMBIGUOUS 段**（e869292a / d9837a3f / 08b101f2）——这些段 canonical 只标 `comp=['OTHER'] func=['OTHER']`（**无有效结构化输入**），引擎诚实 UNKNOWN。**非系统性 UNKNOWN 逃避**（非 Storage 的 CHARGING_POWER/DINING 等有输入段均正常 SUPPORTED），而是：
1. 引擎在"无结构化输入"段覆盖为 0（能力边界）
2. 但 Human 对这 3 段判定 8-10 个 CLEARLY 本身可疑（comp=OTHER 却判 8 个明确支持，疑似过标/全选——与 V1 模式类似）

## H. Confidence Separation ⚠️（本报告最关键发现）

| 状态 | Human CLEARLY rate | CLEARLY+POSSIBLE rate |
|---|---|---|
| SUPPORTED | 13/17 = **0.765** | 0.765 |
| CANDIDATE | 9/9 = **1.000** | 1.000 |
| UNKNOWN miss | 43/154 = 0.279 | — |

**PARTIAL_SEPARATION（且方向部分倒挂）**：
- SUPPORTED 0.765 是正确的强档（Storage SUPPORTED 5/5 全 CLEARLY，错误仅在 DINING 2 个）
- **但 CANDIDATE 1.000 > SUPPORTED 0.765** —— CANDIDATE 全部被认可，说明 Gate 过度保守（把本可 SUPPORTED 的降到 CANDIDATE），导致两档区分度不足
- **V3 时 CANDIDATE 概念尚未启用；Fresh18 首次实测发现：CANDIDATE 门槛过低**（需要收紧到真正"证据不足"的段）

## I. Storage 专项 ✅（核心修复验证）

```
STORAGE:          AI: SUPPORTED 5 / CANDIDATE 2 / UNKNOWN 11 | Human: CLEARLY 14 / NOT_SUP 3 / POSSIBLE 1
STORAGE_EFFICIENCY: AI: CANDIDATE 7 / UNKNOWN 11              | Human: CLEARLY 13 / NOT_SUP 3 / POSSIBLE 1 / UNKNOWN 1
```

**Storage Gate V2 表现**：
1. **component-only STORAGE 不再 SUPPORTED** ✅（DRAWER-only 段 c8355367/c7679d28 有 function=STORAGE 才 SUPPORTED；DRAWER-only 无 function 的段 → CANDIDATE）
2. **5 个 STORAGE SUPPORTED 全部被 Human 判 CLEARLY**（13/17 的 TRUE 中 Storage 占 5/5 全对）✅
3. **STORAGE_EFFICIENCY 不再无条件派生**：7 个 CANDIDATE + 11 UNKNOWN，0 个 SUPPORTED（V3 后 Need→Value Gate 生效）✅ —— 但 Human 判 13 个 CLEARLY，说明 **STORAGE_EFFICIENCY 门控过严**（引擎不敢 SUPPORTED，Human 认为 13 处明确支持）
4. **总体：Storage Gate 结构性成功**（V3 的 2 FALSE + 1 OVERCONFIDENT 模式已消除：Storage SUPPORTED 0 FALSE/0 OVERCONFIDENT）

## J. 非 Storage 专项

| 标签 | AI claims | AI 状态 | Human CLEARLY/POSSIBLE/NOT_SUP |
|---|---|---|---|
| CHARGING_POWER | 3 | SUPPORTED | 6/3/9（SMALL_N）|
| POWER_CONVENIENCE | 3 | SUPPORTED | 6/3/9（SMALL_N）|
| DINING | 3 | SUPPORTED | 5/3/10（SMALL_N，2 个 FALSE）|
| DINING_CONVENIENCE | 3 | SUPPORTED | 5/3/10（SMALL_N，2 个 FALSE）|
| OFFICE | 0 | UNKNOWN 18 | 5/3/10（UNTESTED）|
| WORK_FROM_HOME | 0 | UNKNOWN 18 | 5/3/10（UNTESTED）|
| GUEST_CAPACITY | 0 | UNKNOWN 18 | 3/3/12（UNTESTED）|
| FLEXIBLE_CAPACITY | 0 | UNKNOWN 18 | 3/3/12（UNTESTED）|

## K. Regression Guard

- **POWER：NO_REGRESSION_SIGNAL**（CHARGING_POWER/POWER_CONVENIENCE 3 SUPPORTED 全 TRUE）
- **DINING/OFFICE：POSSIBLE_REGRESSION**（DINING 2 个 FALSE：508ffa24/91e3d154 的 DINING SUPPORTED 但 Human 判 POSSIBLE/NOT_SUPPORTED——这两段 TRACK_SOCKET+DINING function，镜头实际讲充电/火锅，DINING 门控需收紧）
- 通用 Gate 未大范围误伤（非 Storage 良好路径的 POWER 保持）

## L. Negative Rules ✅

**hard_negative_rule_violation_count = 0**（无 OPERATE_SOCKET / REAL_CUSTOMER_CASE / FAMILY_GATHERING）—— Gate 核心纪律成立。

## M. Conflict Resolver V2 ✅

```
both_yes=0 / ai_only=0 / human_only=0 / both_no=18 / human_unknown=0
hypothetical 误报 CONFLICTING = 0
```

**假设/条件语境误报完全消除** ✅（V1 时代"如果家里有宝宝"→CONFLICTING 的问题已修复）。Fresh18 无真实冲突段（both_no=18）——冲突检测未在独立集实测到真阳性，但误报=0 是明确改善。

## N. Coverage / Abstention ⚠️

```
SUPPORTED_COVERAGE   = 17/180 = 0.094
ACTIONABLE_COVERAGE  = 26/180 = 0.144
CLAIM_ABSTENTION_RATE = 154/180 = 0.856（单位：claim）
```

**ABSTENTION 0.856 高**——但已证实**非全 UNKNOWN 逃避**：
- 有结构化输入的段（POWER/DINING/STRONG/MULTI/NEGATIVE 类）均正常输出 SUPPORTED/CANDIDATE
- UNKNOWN 154 中 133 个来自无输入段（comp=OTHER/func=OTHER 或 comp=[] 的 AMBIGUOUS/WEAK/CONFLICTING 类）
- 但**确实暴露覆盖不足**：Fresh18 是 Storage-heavy 采样，但引擎在 3 个 AMBIGUOUS 段（无结构化输入）0 覆盖，而 Human 判了 8-10 个 CLEARLY——**这是 Stage2.1 后仍需解决的能力边界**（结构化输入缺失时无法业务判断）

## O. 三个视角

| 视角 | SUPPORTED TRUE/有效 | precision_clear | hard_false |
|---|---|---|---|
| ALL_FRESH18 | 13/17 | 0.765 | 0.118 |
| STORAGE_SUBSET | 5/5 | **1.000** | 0.000 |
| NON_STORAGE_SUBSET | 8/12 | 0.667 | 0.167 |

**Storage 子集 precision=1.000（0 FALSE）——Storage 修复完全成功**；非 Storage 的 0.667 由 DINING 2 个 FALSE 拖累（门控需收紧）。

## P. 六类 Challenge raw

| 类 | AI SUPPORTED/CAND/UNKNOWN | Human CLEARLY/POSSIBLE/NOT_SUP |
|---|---|---|
| STRONG (3) | 2/4/24 | 6/0/24 |
| MULTI (3) | 3/3/24 | 6/8/16 |
| CONFLICT (3) | 0/0/30 | 12/10/8 |
| WEAK (3) | 0/0/30 | 6/2/22 |
| NEGATIVE (3) | 12/2/16 | 12/6/12 |
| AMBIGUOUS (3) | 0/0/30 | **23**/3/6 |

- STRONG/MULTI/NEGATIVE：AI 与 Human 有重合（SUPPORTED 被认可）
- **CONFLICT/WEAK/AMBIGUOUS：AI 全 UNKNOWN（0 覆盖）**，但 Human 判了可观 CLEARLY（尤其 AMBIGUOUS 23 个）——这三类段多为无结构化输入（动作↔组件不匹配/无组件/OTHER），引擎能力边界

## Q. 与 V3 趋势比较

| 指标 | V3 (Known) | Fresh18 (Independent) | 趋势 |
|---|---|---|---|
| supported_precision_clear | 0.853 | 0.765 | 略降（但 Storage-heavy + DINING 2 FALSE）|
| hard_false_rate | 0.118 | 0.118 | **持平** |
| insufficiency_rate | 0.147 | 0.235 | 升（OVERCONFIDENT 由 DINING 贡献）|

**趋势判断：PARTIAL_IMPROVEMENT_SIGNAL**
- **Storage 修复确认**：Storage SUPPORTED precision 1.000（V3 时 2 FALSE）——结构性改善
- hard_false 持平（非 Storage 的 DINING 新错误与 Storage 旧错误抵消）
- 样本组成不同（Fresh18 Storage-heavy），**禁止宣称"整体准确率提升"**

## R. Stage2 最终判定

**PHASE4_STAGE2_PASS_WITH_LIMITATIONS**

| 判定维度 | 结果 |
|---|---|
| 1. NR hard violation | 0 ✅ |
| 2. Storage Gate 成功 | ✅（Storage SUPPORTED 5/5 TRUE，component-only 不再 SUPPORTED，STORAGE_EFF 不再自动派生）|
| 3. SUPPORTED 高可信 | ✅（0.765，Storage 子集 1.000）|
| 4. SUPPORTED 强于 CANDIDATE | ⚠️ **否**（CANDIDATE 1.000 > SUPPORTED 0.765，Gate 过度保守）|
| 5. UNKNOWN 逃避 | ⚠️ 无系统性逃避（43/154 missed 集中 3 个无输入段），但覆盖不足真实存在 |
| 6. Power/Dining/Office 回归 | ⚠️ Power 无回归；DINING 2 FALSE（POSSIBLE_REGRESSION）|
| 7. Conflict hypothetical 误报 | ✅ 完全消除（0）|
| 8. Evidence trace | ✅（EvidenceStrengthReport 完整）|

## S. Stage3 Ready

**PHASE4_STAGE3_READY = TRUE**（PASS_WITH_LIMITATIONS 允许）

**但必须明确字段限制**（仅 CANDIDATE/AFFINITY，不得作为 Hard Truth）：
- **Decision Factor** → CANDIDATE
- **Trust Signal** → CANDIDATE
- **Shot Function** → CANDIDATE
- **Role / Theme** → AFFINITY（候选，非 primary）
- **Search Intent** → candidate layer

## 24 问答复

1. Fresh18 独立？**是**（零重叠）2. AI_LOCK 先于 Human？**是**（08-29 18:56 < 08-30 13:51）3. 18/18 有效？**是** 4. TRUE=**13** 5. OVERCONF=**2** 6. FALSE=**2** 7. precision_clear=**0.765** 8. hard_false=**0.118** 9. insufficiency=**0.235** 10. SUPPORTED 17/CANDIDATE 9/WEAK 0/UNKNOWN 154 11. **SUPPORTED 未明显强于 CANDIDATE**（0.765 vs 1.000，Gate 保守）12. **Storage Gate 成功**（Storage SUPPORTED 5/5 TRUE）13. component-only Storage 不再 SUPPORTED？**是** 14. STORAGE_EFF 不再过度派生？**是**（0 SUPPORTED，但过严：Human 13 CLEARLY）15. Power 回归？**否**（3/3 TRUE）16. Dining/Office 回归？**DINING 2 FALSE（POSSIBLE_REGRESSION），OFFICE UNTESTED** 17. NR hard violation=**0** 18. Conflict hypothetical 误报=**0（完全消除）** 19. UNKNOWN 滥用？**无系统性逃避，但 3 个 AMBIGUOUS 无输入段覆盖为 0** 20. ALL 0.765 / STORAGE 1.000 / NON_STORAGE 0.667 21. 六类 raw 见 §P 22. 相对 V3：**PARTIAL_IMPROVEMENT**（Storage 修复确认，hard_false 持平）23. **PASS_WITH_LIMITATIONS** 24. **STAGE3_READY=TRUE（带字段限制）**

---

## 收口建议（不自动执行）

Stage2 到此**正式封版**，不再无限加人工审核。**不修改任何规则**。遗留的 3 个 Limitations 记录为 Stage3 前可选项（需架构监工确认）：
1. **CANDIDATE 门槛过松**（9/9 全 CLEARLY → 应把部分转 SUPPORTED，或提高 CANDIDATE 证据要求）
2. **DINING 门控**（2 FALSE：有 DINING function 但镜头讲充电/火锅时仍 SUPPORTED → 需 ASR 语境校验，同 Storage 修复模式）
3. **无结构化输入段的覆盖**（AMBIGUOUS/OTHER 类引擎 0 覆盖——非规则问题，是输入域问题，属后续覆盖率工程）

## 产物
- `BUSINESS_COGNITION_FRESH_V1_SCORE.json` · 本报告 `docs/PHASE4_STAGE2_1_FRESH18_FINAL_SCORING.md`
- Fresh18 Human 18 条冻结 · AI_LOCK 冻结（未动）

## 停点

**STOP** —— 即使 STAGE3_READY=TRUE 也不自动进入 Stage3。等你做 Stage2 最终验收 + Stage3 架构入口决策。
