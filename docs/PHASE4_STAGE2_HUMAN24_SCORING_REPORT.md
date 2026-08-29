# PHASE4 STAGE 2 — HUMAN24 SCORING REPORT（AI_LOCK vs 独立 Human Truth）

> 状态：**评分完成 · 冻结 Human24 Business Truth · 未修改任何 Rule/Knowledge/Engine · 未重生成 AI · 未进 Stage3**
> 日期：2026-08-29
> 评审：Human Business Review 24/24（4×6 平衡，blind，独立 Human Truth）
> 数据：`BUSINESS_COGNITION_STAGE2_SCORE_V1.json` · `stage2_business_cognition_review_v1` 表
> 修复：评审期发现 role/theme 亲和度中文值入库 → 已一次性迁移为英文（仅改字段编码，未动任何判断）

---

## 0. 数据完整性与质量检查

- **24/24 入库**，无缺失、无重复、全部属于 Human24 manifest
- 24 段视频全部可播放（评分前预检）
- 修复：`role_affinity`/`theme_affinity` 存库时是中文（表单 collect 未反查）→ 一次性迁移为英文（STRONG/MEDIUM/WEAK/NOT_SUPPORTED/UNKNOWN），表单已修复防止复发

## 1. 多标签 Set Comparison（AI_LOCK vs 独立 Human Truth）

| 字段 | TP | FP | FN | TN | Precision | Recall | F1 | UCR |
|---|---|---|---|---|---|---|---|---|
| user_needs | 17 | 3 | 181 | 303 | 0.850 | 0.086 | 0.156 | 0.150 |
| business_values | 17 | 3 | 170 | 242 | 0.850 | 0.091 | 0.164 | 0.150 |
| search_intents | 9 | 3 | 155 | 145 | 0.750 | 0.055 | 0.102 | 0.250 |
| shot_functions | 0 | 0 | 62 | 298 | — | 0.000 | — | — |
| decision_factors | 0 | 0 | 123 | 261 | — | 0.000 | — | — |
| trust_signals | 0 | 0 | 52 | 99 | — | 0.000 | — | — |
| **needs+values 合并** | **34** | **6** | **351** | **545** | **0.850** | **0.088** | **0.160** | **0.150** |

### ⚠️ 关键方法学发现：全量 Recall 被"词汇表外标签"稀释

- **AI 引擎词汇表**（SEM_001-007 可输出）仅 5 needs + 5 values = 10 个标签
- **Human Taxonomy** 21 needs + 18 values = 39 个标签；Human 实际勾选到了全部 21 个 needs
- Human 每段平均勾选 **8.2 needs / 7.8 values**（AI 每段平均 0.8 / 2.3）
- 大量 FN 来自 **AI 词汇表根本没有的标签**（AESTHETICS/CUSTOMIZATION/DURABILITY 等 16 个）—— 这不是"AI 漏检"，而是 **AI 引擎当前覆盖范围远小于 Human Taxonomy**

### ✅ 受控口径（AI 词汇表内 10 标签，Recall 真正可比）

```
TP=34  FP=6  FN=76
Precision = 0.850
Recall    = 0.309   ← AI 能输出的标签里，Human 认可的 30.9%
UCR       = 0.150
```

## 2. UNSUPPORTED_CLAIM_RATE（用户核心问题 1）

**needs+values 合并 UCR = 0.150**（6/40 AI 主张不被 Human 支持）
**含 search_intents 全量 UCR = 0.184**（9/49：unsupported_claims 共 9 条）

6 个 needs+values FP 明细（AI 主张但 Human 未勾选）：
| 段 | 主张 | 类别 |
|---|---|---|
| d780c9ed… | STORAGE | need（CONFLICTING 类）|
| 40d5fdbe… | STORAGE | need（MULTI 类）|
| 40d5fdbe… | STORAGE_EFFICIENCY | value（MULTI 类）|
| a1223854… | CHARGING_POWER | need（NEGATIVE 类）|
| 80f182c8… | POWER_CONVENIENCE | value（NEGATIVE 类）|
| bf686b31… | STORAGE_EFFICIENCY | value（STRONG 类）|

另 3 个 search_intent FP：ISLAND_STORAGE ×3（40d5fdbe/bf686b31/9df423b8——AI 由 STORAGE 派生搜索意图，Human 未确认对应段有该搜索意图）。

**解读**：UCR 15-18% 属**中等水平**，无"硬虚构"（无凭空捏造的业务意义）。FP 集中于 STORAGE/STORAGE_EFFICIENCY/CHARGING_POWER —— 属于**证据强度不足**（可能只有单组件无功能确认、或 ASR 语境不支持），不是 NR 级硬违规。这正是 Stage2 要收紧的：**组件存在 ≠ 用户需求成立**（与 NR001/NR009 精神一致）。

## 3. Negative Rule 违规（用户核心问题 2）

**硬违规 = 0** ✅
- AI_LOCK 全量无 OPERATE_SOCKET / REAL_CUSTOMER_CASE / FAMILY_GATHERING
- NR001（插座≠操作）/ NR002（工厂≠客户案例）/ NR004（有人≠聚会）全部生效
- 24 条人审中 conflict_observed 与 AI conflicts 对照见 §7

## 4. Confidence Calibration（用户核心问题 3）

**⚠️ 无法直接验证 SUPPORTED vs WEAK**：
- AI_LOCK 中 claim 状态分布：**CONFIRMED=0 · SUPPORTED=137 · WEAK=0 · CANDIDATE=0 · UNKNOWN=0 · BLOCKED=0**
- BusinessCognitionV2 的 SEMANTIC_MAPPINGS **只产出 SUPPORTED 级** claims —— 引擎没有 WEAK/CANDIDATE 输出路径
- 因此"SUPPORTED 是否比 WEAK 更可信"**当前无法在引擎层面对比**（无 WEAK 样本）
- **替代验证**：SUPPORTED 的实际 precision = **0.850**（40 个 AI 主张中 34 个获 Human 支持）→ SUPPORTED 级可信度可观，但 15% 假阳性说明 SUPPORTED 仍需收紧

**结论**：置信度系统当前**只有一档（SUPPORTED）**，校准无效性风险存在 —— 若 Human24 显示 SUPPORTED≈WEAK 精度相近则系统无效。当前 SUPPORTED=0.85 是合理基线，但**缺少多档对照**是 Stage2 后续必须补的。

## 5. Affinity 评分（Role 4 类 / Theme 5 类，全维度独立评级）

| 维度 | exact | within_one | TP | FP | FN | strong_unsupported |
|---|---|---|---|---|---|---|
| role（4 类） | 15/96 | 15/96 | 15 | 0 | 66 | 0 |
| theme（5 类） | 2/120 | 4/120 | 3 | 1 | 104 | 0 |

- **strong_unsupported = 0**（AI 主张的 role/theme 无被 Human 判 NOT_SUPPORTED 的）✅
- **Human 评级分布**：role = MEDIUM 81 / WEAK 11 / UNKNOWN 4（无 STRONG）；theme = MEDIUM 101 / UNKNOWN 10 / STRONG 6 / WEAK 3 —— **Human 倾向 MEDIUM 中间档**（保守评级，符合"不确定=不硬选"纪律，但中间档过密会稀释 exact/within-one 区分度）
- **UNKNOWN 纪律验证**：2 段 overall_unknown=YES（Human 主动标注证据不足，未被迫硬选）✅
- role/theme 的 FN 极高：AI 引擎仅 3 role（缺 TRAFFIC）+ Human 大量 MEDIUM → **AI 主张面窄 + Human 评级宽松**双重原因
- exact 低（theme 2/120）：AI 只主张少数维度，未主张维度计入 FN，使精确对齐失真；**affinity 指标在 AI 输出面过窄时参考价值有限**

## 6. 六类 Challenge 分桶（needs+values+intents 合并，来自 score 文件 by_class）

| 类别 | TP | FP | FN |
|---|---|---|---|
| STRONG_SINGLE_EVIDENCE | 9 | 3 | 59 |
| MULTI_SOURCE_AGREEMENT | 7 | 3 | 82 |
| CONFLICTING_EVIDENCE | 13 | 1 | 190 |
| WEAK_EVIDENCE | 0 | 0 | 94 |
| NEGATIVE_RULE_TRIGGER | 14 | 2 | 185 |
| AMBIGUOUS_MULTI_PURPOSE | 0 | 0 | 133 |

- **STRONG_SINGLE FP=3 / 主张精度 9/12=0.75**：单组件+功能匹配的强证据主张大部分获 Human 支持，3 个 FP 为组件存在但 Human 认为需求不成立
- **WEAK/AMBIGUOUS TP=0**（AI 未主张 → 不硬编结论，符合纪律）
- **CONFLICTING FP=1**：场景冲突段 AI 仍主张某 value 未获支持（冲突时应收紧）
- 注：FN 极高是"全字段 + 词汇表外标签"稀释的产物（见 §1 方法学发现），**跨类比较仅看 TP/FP 相对形态有效**

## 7. Conflict Handling

- **AI 检测 vs Human 观察对照**（score 文件 `conflict_agreement`）：**agree=0 · ai_only=4 · human_only=1 · both_none=19**
- **AI 只在 4 段标记了冲突（conflict_count>0），Human 只在 1 段观察到了 SCENE_ASR_CONFLICT，两者零重叠**
- **解读**：
  - AI 的 4 段"冲突"（ASR 含 家里/客户家 等词 + FACTORY）Human 均未确认——ConflictResolverV1 的 home_words 命中多为**假设性语境**（"如果家里有宝宝"），Human 不视为真实场景矛盾 → **AI 冲突检测过度敏感**
  - Human 观察到的 1 段冲突 AI 未标记——Human 判断基于视频语境，AI 仅靠 ASR 关键词，**漏了语境型冲突**
  - 结论：**冲突检测需要语境理解（区分假设/真实断言），当前关键词规则精度不足**——这是 Stage2 冲突处理的重要发现，属引擎改进方向（非本 24 调参）

## 8. Rule Yield / Error Taxonomy

**Error Taxonomy（9 FP 归类：6 needs+values + 3 search_intents）**：
| 错误类型 | 数量 | 说明 |
|---|---|---|
| 组件→需求过度外推 | 4 | STORAGE/STORAGE_EFFICIENCY×3：单组件无功能确认时仍主张 |
| 能力词→需求 | 1 | CHARGING_POWER：ASR 提到充电但画面/功能证据不足 |
| 产品能力≠用户价值 | 1 | POWER_CONVENIENCE：插座存在但 Human 认为不足以构成价值主张 |
| 需求→搜索意图过度派生 | 3 | ISLAND_STORAGE×3：AI 由 STORAGE 自动派生搜索意图，Human 未确认对应段有该搜索意图（派生链需证据门控） |

**Rule Yield（从 AI_LOCK 60 段统计）**：
- SEM_002（DRAWER+STORAGE）与 SEM_003/004（TRACK_SOCKET→POWER）高触发
- SEM_001（EXTENDABLE_SECTION 组件）**从未触发**（Challenge60 池无 EXTENDABLE_SECTION 组件标注）→ 标记 **UNTESTED**（不删除）
- SEM_003/004 的 POWER_CONVENIENCE 2 次 FP → 建议未来 **NEEDS_REWORK**（但**不在本 24 上调**）

## 9. 三个核心问题的最终回答

**第一，UNSUPPORTED_CLAIM_RATE 多高？**
→ needs+values 合并 **15.0%**（6/40）。中等偏高，无硬虚构，集中于 STORAGE/CHARGING_POWER 证据强度不足型。**未达"高精度"标准，但无灾难性幻觉。**

**第二，Negative Rule 有没有硬违规？**
→ **0 次硬违规**（无 OPERATE_SOCKET/REAL_CUSTOMER_CASE/FAMILY_GATHERING）。✅ Gate 核心纪律成立。

**第三，SUPPORTED 是否明显比 WEAK/CANDIDATE 更可信？**
→ **无法判定**：引擎当前**只输出 SUPPORTED 一档**（137 SUPPORTED / 0 WEAK / 0 CANDIDATE），没有多档对照。SUPPORTED 实际精度 0.85 是可用基线，但**置信度系统只有单档 = 校准能力未建立**，这是 Stage2 最需要正视的缺口（不是调参能解决的，是引擎架构缺 WEAK/CANDIDATE 输出路径）。

## 10. 结论与纪律

- **Human24 冻结** ✅（24/24 入库，仅亲和度编码修复）
- **未修改 Rule / Knowledge / BusinessCognitionServiceV2 / 未重生成 AI answers / 未调参** ✅
- 同 24 条成为 **KNOWN_DEV_BENCHMARK**（不重调后重报）
- 剩余 36 条 = STAGE2_SECONDARY_DEV（显式非 Fresh Holdout）
- **评分后 STOP** —— 不进 Stage3

**Stage2 总体判定**：引擎架构与纪律（NR 硬违规=0、WEAK/AMBIGUOUS 不乱说、STRONG 高精度）**通过**；但 **UNSUPPORTED_CLAIM_RATE=15% 需收紧**、**置信度单档化（无 WEAK/CANDIDATE 对照）是明确缺口**。下一步决策在架构监工：是否在 Stage3 前补 WEAK/CANDIDATE 输出路径 + 收紧组件→需求外推（此为非 Human24 变更，需另行确认）。

---

## 产物
- `BUSINESS_COGNITION_STAGE2_SCORE_V1.json`（完整评分，含 conflict_agreement / per-segment 对照）
- `docs/PHASE4_STAGE2_HUMAN24_SCORING_REPORT.md`（本报告）
- 修复 1：`phase3_review_ui.py` collect() 亲和度中文→英文反查（`_affinity_to_en`）+ 已审 24 条一次性数据迁移（仅改字段编码，未动任何判断）
- 修复 2：`stage4_human24_score.py` per-segment 增加 human_conflict_observed / ai_conflict_count + conflict_agreement 汇总
