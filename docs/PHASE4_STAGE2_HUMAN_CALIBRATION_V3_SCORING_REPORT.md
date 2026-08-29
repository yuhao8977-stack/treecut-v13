# PHASE4 STAGE 2 — HUMAN CALIBRATION V3 SCORING REPORT

> 状态：**V3 12/12 有效冻结 · 评分完成 · CALIBRATION_TRUTH_RELIABLE · STAGE2_1_CALIBRATION_READY=TRUE（本轮不改规则）· STOP**
> 日期：2026-08-29
> 数据：`HUMAN_CALIBRATION_V3_SCORE.json` · `stage2_business_cognition_calibration_v3` 表（12 行，schema_version=CALIBRATION_V3）
> 纪律：未修改 AI_LOCK / Business Rules / Knowledge / Engine · 未调参 · 未重生成 AI answers · 未执行 Stage2.1 · 未进 Stage3

---

## A. V3 数据质量检查 ✅

| 检查项 | 结果 |
|---|---|
| 12/12 完成 | ✅ |
| 12 唯一段 | ✅ |
| segment set == V3 manifest | ✅（set 相等）|
| schema_version | 全部 `CALIBRATION_V3` ✅ |
| 每段 10 标签恰一状态 | ✅ 无 missing/duplicate/invalid |

**状态分布（120 标签 = 12 段 × 10）**：
| | CLEARLY | POSSIBLE | NOT_SUPPORTED | UNKNOWN |
|---|---|---|---|---|
| 总体 | 49 | 6 | 61 | 4 |
| needs(60) | 24 | 4 | 31 | 1 |
| values(60) | 25 | 2 | 30 | 3 |

## B. Human Review 质量 ✅

**每段 CLEARLY（证据导向，符合期望）**：
| | avg | median | min | max |
|---|---|---|---|---|
| CLEARLY needs | **2.0** | 3 | 0 | 4 |
| CLEARLY values | **2.08** | 3 | 0 | 4 |
| POSSIBLE（needs+values）| 0.5 | 0 | 0 | 6 |
| UNKNOWN | 0.33 | 0 | 0 | 3 |

- **对比 V1（8.2/7.8）与 V2 污染版（5.67/5.83）→ V3 降到 2.0/2.08，进入 2~4 期望区间** ✅
- **无 V2 式重叠/全选污染**：状态分布健康，无 21/21 全选段 ✅
- **evidence_sufficiency**：SUFFICIENT 11 / PARTIAL 1（有区分度，不再 12/12 全 SUFFICIENT）✅
- **review_confidence**：MEDIUM 12（未用 HIGH/LOW，合法但单一——小瑕疵）
- **review_duration**：median 38s / min 20.3s / max 113.1s（40d5fdbe=113s 为异常值，仅诊断）

## C. AI SUPPORTED Calibration（raw 数字）✅

```
SUPPORTED_TRUE            = 29
SUPPORTED_OVERCONFIDENT   = 1
SUPPORTED_FALSE           = 4
SUPPORTED_HUMAN_UNKNOWN   = 0
分母（TRUE+OVERCONF+FALSE）= 34

supported_precision_clear = 29/34 = 0.853
overconfidence_rate       = 1/34  = 0.029
false_claim_rate          = 4/34  = 0.118
human_unknown_rate        = 0/34  = 0.000
```

## D. 每 Label 评分

| Label | AI claims | CLEARLY | POSSIBLE | NOT_SUP | UNKNOWN | TRUE | OVERCONF | FALSE |
|---|---|---|---|---|---|---|---|---|
| STORAGE | 5 | 2 | 1 | 2 | 0 | **2** | 1 | **2** |
| CHARGING_POWER | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| DINING | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| OFFICE | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| GUEST_CAPACITY | 0 | — | — | — | — | 0 | 0 | 0 |
| STORAGE_EFFICIENCY | 5 | 3 | 0 | 2 | 0 | **3** | 0 | **2** |
| POWER_CONVENIENCE | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| DINING_CONVENIENCE | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| FLEXIBLE_CAPACITY | 0 | — | — | — | — | 0 | 0 | 0 |
| WORK_FROM_HOME | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 |

**核心模式**：**CHARGING_POWER/DINING/OFFICE/POWER_CONVENIENCE/DINING_CONVENIENCE/WORK_FROM_HOME 全部 4/4 TRUE（100%）**；问题集中在 **STORAGE / STORAGE_EFFICIENCY**（各 2 个 FALSE）。样本小，不作强结论，但方向明确。

## E. 原 6 FP 最终重判（V3 唯一裁决）✅

| 原 FP | V3 终判 | 归类 |
|---|---|---|
| d780c9ed STORAGE | NOT_SUPPORTED | **TRUE_FP**（AI 错）|
| bf686b31 STORAGE_EFFICIENCY | NOT_SUPPORTED | **TRUE_FP**（AI 错）|
| 40d5fdbe STORAGE | POSSIBLE_BUT_INSUFFICIENT | **OVERCONFIDENT**（AI 方向对但 SUPPORTED 过强）|
| 40d5fdbe STORAGE_EFFICIENCY | CLEARLY_SUPPORTED | **FALSE_FP_V1_HUMAN_MISS**（AI 对，V1 漏标）|
| a1223854 CHARGING_POWER | CLEARLY_SUPPORTED | **FALSE_FP_V1_HUMAN_MISS**（AI 对，V1 漏标）|
| 80f182c8 POWER_CONVENIENCE | CLEARLY_SUPPORTED | **FALSE_FP_V1_HUMAN_MISS**（AI 对，V1 漏标）|

**洗牌：2 TRUE_FP + 3 FALSE_FP（AI 其实对）+ 1 OVERCONFIDENT**

**原 UCR=15% 判定：高估** ✅
- 6 个原 FP 中 **3 个是 V1 漏标（AI 对）** → 这 3 个根本不该算 FP
- 1 个是 OVERCONFIDENT（POSSIBLE）→ 也不该算硬 FP
- 真实 FP 只有 2 个（STORAGE 类）→ **真实 UCR 应远低于 15%**（若按 V3：FALSE=4/34=11.8%，且其中含非原 FP 的新样本）

## F. V1 → V3 迁移（仅 10 标签范围）✅

**V1 标签(校准域) 53 个 → V3：CLEARLY=42 · NOT_SUPPORTED=11 · POSSIBLE=0 · UNKNOWN=0**

- **关键回答**：V1 的 53 个标签中 **42 个（79%）在 V3 仍为 CLEARLY**，11 个（21%）被 V3 判 NOT_SUPPORTED
- **V1 过标幅度**：21% 的 V1"明确支持"被 V3 推翻（association→evidence 过标确实存在，但比预期的轻——主要发生在 STORAGE 类，与 V1 疲劳集中在 40d5fdbe/75c6e986 等段一致）
- 注意：V1 里被标 POSSIBLE 的标签数 = 0（V3 只有 1 个 POSSIBLE 与 AI 主张重叠，不在 V1 selected 中）——V1 的"关联性多选"主要体现在 42 个仍 CLEARLY 中偏宽松的部分

## G. V2 处理 ✅

**V2 保持 UI_CONTAMINATED / INVALID_FOR_CALIBRATION**，不参与性能计算，仅作 UI_FAILURE_DIAGNOSTIC。

## H. Calibration Truth Reliability

**CALIBRATION_TRUTH_RELIABLE** ✅ 理由：
1. **label sparsity 健康**：CLEARLY 2.0/2.08（证据导向），无全选段
2. **CLEARLY/POSSIBLE 结构清晰**：49/6/61/4 分布合理，无重叠
3. **evidence sufficiency 有区分度**（SUFFICIENT 11 / PARTIAL 1），非全默认
4. **review confidence**：全 MEDIUM（单一但合法，不构成污染）
5. **duration 正常**：median 38s（比 V2 的 104s 更专注），仅 1 个异常值（113s，诊断用）
6. **UNKNOWN 使用**：4 个（合理克制）
7. **内部语义一致**：冲突观察 1 段 YES（b2f971）与 V1 该段 overall_unknown=YES 相符
8. **无 V2 式污染**：dict 单值结构 + 校验，结构级保证

## I. Stage2.1 Gate

**STAGE2_1_CALIBRATION_READY = TRUE** ✅
（V3 Human Truth = CALIBRATION_TRUTH_RELIABLE，明确可用于当前 10 标签 SUPPORTED 校准）

**但本轮不得自动修改 Rule** —— 冻结，等架构监工确认 Stage2.1 方案。

---

## 18 问答复

1. **V3 12/12 有效冻结？** → **是**（12 行、唯一、set 相等、schema=CALIBRATION_V3、10 标签每恰一状态）
2. **V2 式重叠/全选污染？** → **无**（dict 单值结构，状态分布健康）
3. **CLEARLY 平均每段？** → needs **2.0** / values **2.08**（V1 是 8.2/7.8）
4. **POSSIBLE 平均每段？** → **0.5**
5. **Evidence Sufficiency？** → SUFFICIENT 11 / PARTIAL 1
6. **Confidence？** → MEDIUM 12（全 MEDIUM，单一但合法）
7. **SUPPORTED_TRUE？** → **29**
8. **OVERCONFIDENT？** → **1**
9. **SUPPORTED_FALSE？** → **4**
10. **supported_precision_clear？** → **0.853**（29/34）
11. **overconfidence_rate？** → **0.029**（1/34）
12. **false_claim_rate？** → **0.118**（4/34）
13. **原 6 FP 洗牌？** → **2 TRUE_FP + 3 FALSE_FP（AI 对，V1 漏标）+ 1 OVERCONFIDENT**
14. **原 UCR=15% 高估？** → **是，明显高估**（3 个假 FP 转正 + 1 个 OVERCONFIDENT，真实 FP 仅 2）
15. **V1→V3 迁移到 POSSIBLE？** → **0**（V1 selected 标签无迁往 POSSIBLE；42 仍 CLEARLY，11 变 NOT_SUPPORTED）
16. **确认 V1 存在"关联性→证据性"过标？** → **部分确认**：21%（11/53）的 V1 明确支持被 V3 推翻，集中在 STORAGE 类；但 79% 仍成立，过标比 V2 显示的要轻
17. **V3 Reliability verdict？** → **CALIBRATION_TRUTH_RELIABLE**
18. **STAGE2_1_CALIBRATION_READY？** → **TRUE（本轮不改规则）**

---

## 核心结论（用户最关心的问题）

**当前 Knowledge Brain 输出 SUPPORTED 时，是真的"有充分证据"还是只是"业务上说得通"？**

**V3 首次给出可靠答案：SUPPORTED 的 85.3% 是"有充分证据"（precision_clear=0.853），11.8% 是"说得通但镜头没证明"（false），2.9% 是"方向对但过强"（overconfident）。**

- **强项**：CHARGING_POWER/DINING/OFFICE/POWER_CONVENIENCE/DINING_CONVENIENCE/WORK_FROM_HOME 六个标签 **100% TRUE**——引擎对插座/餐桌/办公类的 SUPPORTED 判断可靠
- **弱项**：**STORAGE / STORAGE_EFFICIENCY**（各 2 FALSE）——组件存在（DRAWER/柜门）被过度外推为用户需求，这是 Stage2.1 最需要收紧的 Gate
- **原 UCR=15% 高估确认**：真实 UCR ≈ 11.8%（且主要来自 STORAGE 类），CHARGING_POWER/POWER_CONVENIENCE 的"FP"实为 V1 漏标

---

## 产物
- `HUMAN_CALIBRATION_V3_SCORE.json`（完整评分）
- `docs/PHASE4_STAGE2_HUMAN_CALIBRATION_V3_SCORING_REPORT.md`（本报告）
- V3 12 条冻结保留 · 未修改任何 AI/Rules/Knowledge/Engine

## 停点

**STOP** —— **STAGE2_1_CALIBRATION_READY=TRUE**，但本轮未自动修改任何规则。等你确认 Stage2.1 Claim Gating 方案后执行（STORAGE 类外推收紧方向已明确：组件存在 ≠ 用户需求成立）。
