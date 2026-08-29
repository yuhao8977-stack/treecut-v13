# PHASE4 STAGE 2 — ADJUDICATION V2 SIMPLIFICATION GATE

> 状态：**V2b 简化复核 UI 完成 · Smoke PASS · 12 条复核就绪（等状态好时做）· STOP**
> 日期：2026-08-29
> 背景：V2 原完整 Taxonomy 表单认知负担过高（~98 项/条），未解决"可联想 vs 足以证明"混淆
> 纪律：12 segment identity 不变 · AI_LOCK 不变 · Human24 V1 不变 · Engine/Rules/Knowledge 不变 · 不执行 Stage2.1

---

## 1. 复核目标重新限定

12 条复核**不是**完整 Business Cognition 重新标注，唯一目标：验证 V1 的 **user_needs / business_values / evidence sufficiency / conflict** 是否可靠。

**不再审核**：decision_factors / trust_signals / search_intents / shot_functions / content_role_affinity / mother_theme_affinity —— 这些在 V2b 中为 **NOT_REVIEWED_IN_ADJUDICATION_V2**，**不得用旧 V1 值填充为 V2 Truth**（V2b 表只存简化字段，无这些列）。

## 2. 复核字段（只保留 6 项）

| 字段 | 取值 |
|---|---|
| A. user_needs | 【明确支持】多选 + 【可能相关但证据不足】多选 + FIELD_UNKNOWN |
| B. business_values | 同上 |
| C. evidence_sufficiency | SUFFICIENT / PARTIAL / INSUFFICIENT / UNKNOWN |
| D. conflict_observed | YES / NO / UNKNOWN |
| E. review_confidence | HIGH / MEDIUM / LOW（质量诊断，不决定真值） |
| F. comment | 可选 |

## 3. 四态语义（核心改造）

每个 need/value 区分四种状态，**不再只有 selected/not-selected**：

| 状态 | 定义 |
|---|---|
| **CLEARLY_SUPPORTED**（明确支持） | 仅根据当前视频/冻结可靠 Evidence，该业务意义有明确直接支持 |
| **POSSIBLE_BUT_INSUFFICIENT**（可能但证据不足） | 业务上可以关联，但当前镜头本身证据不足，不能作为 SUPPORTED Claim |
| **NOT_REVIEWED / NOT_ASSERTED**（未选择默认） | Human 未主张，不计任何 Truth |
| **FIELD_UNKNOWN**（整字段无法判断） | 信息不足，Human 无法可靠判断 |

UI 实现为**两个多选区**【明确支持】/【可能相关但证据不足】+ 整字段"无法判断"勾选——**不是 39 行 × 四选一**（Gate §5）。

## 4. Ground Truth 评分口径

- **Human positive（Truth）** = `clearly_supported_needs ∪ clearly_supported_values`
- **POSSIBLE_BUT_INSUFFICIENT** 不得算 AI SUPPORTED 的 TP；未来 AI 的 CANDIDATE/WEAK 可单独比较
- 明确区分"能联想到"与"足以证明"

**Smoke 验证（Gate §12）**：CLEARLY={STORAGE} · POSSIBLE={CUSTOMIZATION} → Human supported truth={STORAGE}；AI SUPPORTED {STORAGE, CUSTOMIZATION} → TP={STORAGE}（CUSTOMIZATION 不计 TP）✅ mock 已删

## 5. UI 减负（一屏只显示）

```
视频 + 核心 Evidence 摘要
User Needs:   【明确支持】多选 + 【可能相关】多选 + 整字段无法判断
Business Values: 同
Evidence:  SUFFICIENT/PARTIAL/INSUFFICIENT/UNKNOWN
Conflict:  YES/NO/UNKNOWN
Confidence: HIGH/MEDIUM/LOW
```
**不显示** decision_factors / trust_signals / search_intents / shot_functions / role / theme。

## 6. Evidence 显示保持

[MODEL] 标注 provider/reliability：scene=LOW · material=LOW · semantic_action=VERY_LOW · component/function=MEDIUM_HIGH；Human Verified 单独标记。

## 7. V1 vs V2b 比较方式（修正）

- V1 user_needs **vs** V2 CLEARLY_SUPPORTED needs
- V1 business_values **vs** V2 CLEARLY_SUPPORTED values
- V1 overall_unknown **vs** V2 evidence sufficiency
- V1 conflict **vs** V2 conflict
- **额外报告** V2 POSSIBLE_BUT_INSUFFICIENT —— 解释 V1 为什么大量多选（"关联性"而非"证据性"）

## 8. Reliability 判定（不只 0.85 阈值）

同时报告：exact-set agreement · Jaccard · label additions · label removals · **CLEARLY↔POSSIBLE 迁移数** · HIGH-confidence 子集一致率 · LOW-confidence 数量。判定：≥0.85 → ADJUDICATED_HUMAN_TRUTH；0.70-0.85 → PARTIALLY_RELIABLE（结合迁移数）；<0.70 → UNRELIABLE_FOR_CALIBRATION。

## 9-10. 重点问题（12 条完成后回答）

1. V1 过多标签有多少在 V2 变 POSSIBLE_BUT_INSUFFICIENT？
2. 真正 CLEARLY_SUPPORTED 的 needs/value 平均每条多少？
3. V1 平均 8.2/7.8 是否主要来自"关联性"？
4. 原 6 个 AI FP 多少仍是明确 Human negative？
5. 多少其实属于 POSSIBLE_BUT_INSUFFICIENT？
6. V1 是否可靠到足以做 Claim Calibration？

## 11. Lock Discipline

- 12 segment identity 完全不变（与 Reliability Gate 版本一致，未重采样）
- 未重新生成 AI cognition · 未查看 V1 答案 · 未显示 AI 答案
- AI_LOCK / V1 / Engine / Rules / Knowledge 全部未动

## 12. Schema 历史

`ADJUDICATION_V2_SCHEMA_HISTORY.json`：`v2_full_taxonomy`（SUPERSEDED，表 stage2_business_cognition_adjudication_v2 保留空表）→ `v2b_simplified`（CURRENT，新表 stage2_business_cognition_adjudication_v2b）。

## 产物
- `src/treecut/services/phase3_review_ui.py`：`_AdjudicationV2bForm` + `validate_adjudication_v2b`（四态两区 UI）
- `src/treecut/services/annotation_governance.py`：`save_business_cognition_adjudication_v2b`（新表）
- `src/treecut/services/review_center.py`：V2b 任务（simplified_v2b 分支 + _save/_persist）
- `scripts/stage4_adjudication_v2b_smoke.py`（PASS）· `stage4_adjudication_v2_schema_history.py` · `stage4_human24_v1_vs_v2.py`（重写为 V2b 口径）
- `ADJUDICATION_V2_SCHEMA_HISTORY.json`（DATA_ROOT）
- `tests/test_stage2_cognition.py`（21：+2 V2b 四态语义 / schema 历史）
- 本报告 `docs/PHASE4_STAGE2_ADJUDICATION_V2_SIMPLIFICATION_GATE.md`

## 停点

**STOP** —— 等你状态正常时，GUI 人工审核中心 → **Stage2 Human24 复核（Adjudication V2b·12 条盲审·简化）** → 完成 12 条 → 运行 `stage4_human24_v1_vs_v2.py`。未自动开始复核 · 未执行 Stage2.1 · 未进 Stage3。
