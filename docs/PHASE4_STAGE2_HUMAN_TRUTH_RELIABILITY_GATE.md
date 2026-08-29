# PHASE4 STAGE 2 — HUMAN TRUTH RELIABILITY GATE（Human24 V1 降级 + Adjudication V2 就绪）

> 状态：**HUMAN24_V1 = PROVISIONAL_NOISY_REVIEW（DIAGNOSTIC_ONLY）· HUMAN24_ADJUDICATION_V2 = READY（12 条）· STOP**
> 日期：2026-08-29
> 背景：审核者确认 Human24 审核过程存在明显疲劳、分多次完成、对部分判断缺乏把握
> 纪律：不删除/不覆盖/不修改 V1 数据与历史评分 · 禁止据此调 Rule/Gating/Conflict/Knowledge/Engine · 不自动开始人工审核 · 不执行 Stage2.1

---

## 1. 判定：Human24 V1 降级

**HUMAN24_V1 → `PROVISIONAL_NOISY_REVIEW`**（`HUMAN24_TRUTH_RELIABILITY_STATUS.json`）

- **数据保留**：24 条入库数据、`BUSINESS_COGNITION_STAGE2_SCORE_V1.json` 历史评分全部保留，不删除、不覆盖、不修改
- **指标降级为 DIAGNOSTIC_ONLY**：Precision 0.850 / Recall 0.088（全量）· 0.309（受控）· UCR 0.150 / 各 FP/FN —— 仅作"发现问题线索"，**不作精确成绩**
- **禁止**基于这些结果立即修改：Business Rules / Claim Gating / Conflict Rules / Knowledge / Engine
- **关键风险认知**：V1 的 6 个 FP 可能是"AI 判断合理但 Human 因疲劳未勾"造成的假 FP → 若据此收紧 STORAGE/POWER 规则反而会把正确规则改坏

## 2. 已暴露的结构问题（不只是疲劳）

Human 每段平均勾选 **8.2 needs / 7.8 values**（有段 21/21 全选）——一次判断 21+18+16+13+15+6+4+5 = **98 个选项**对几秒视频片段**过重**。暴露了人工标注定义未区分：
- "这个镜头可以让我联想到什么"（联想）
- "这个镜头本身有足够证据证明什么"（证据）

下一版人工审核应简化（先只问：明确支持什么 / 可能支持什么 / 哪些不能确定），不做完整业务考试。

## 3. HUMAN24_ADJUDICATION_V2（12 条）已建立 ✅

`BUSINESS_COGNITION_STAGE2_HUMAN_ADJUDICATION_V2.json`（12 条 = 9 error + 3 control）：

| # | segment_id | 入选理由 |
|---|---|---|
| 1 | 40d5fdbe… | FP: STORAGE/STORAGE_EFFICIENCY/ISLAND_STORAGE |
| 2 | 80f182c8… | FP: POWER_CONVENIENCE |
| 3 | 9df423b8… | FP: ISLAND_STORAGE |
| 4 | a1223854… | FP: CHARGING_POWER |
| 5 | bf686b31… | FP: STORAGE_EFFICIENCY/ISLAND_STORAGE |
| 6 | d780c9ed… | FP: STORAGE |
| 7 | b2f971fd… | 高影响: Human 观察冲突 AI 未检出 + unknown=YES |
| 8 | 31b98294… | 高影响: overall_unknown=YES（证据不足） |
| 9 | 66cc4382… | 高影响: AI 检冲突 Human 未确认（CONFLICTING） |
| 10 | 75c6e986… | 对照: TP=6（NEGATIVE） |
| 11 | d96ec717… | 对照: TP=4（MULTI） |
| 12 | 95d73053… | 对照: TP=2（STRONG） |

**blind 要求全部满足**：
- 不显示 AI 答案 / Human V1 答案 / 旧评分 / 错误类型 / sampling class（测试断言通过）
- 只显示：题号、视频、冻结证据（MODEL 标注）、完整固定 Taxonomy 表单

**降低认知负担**：
- 每条可保存 `review_confidence` = HIGH/MEDIUM/LOW（低=不确定，允许，不需硬选）
- 自动记录 `review_duration_seconds`（仅质量诊断，不决定真值）
- UI 一次只显示 1 条，不显示之前 Human Truth

## 4. 数据模型 + UI 接入

- 新表 `stage2_business_cognition_adjudication_v2`（独立表，与 V1 表隔离；含 review_confidence + review_duration_seconds）
- `AnnotationService.save_business_cognition_adjudication()`
- Review Center 新任务 `HUMAN24_ADJUDICATION_V2`（adjudication_mode=True → 表单加"把握度"字段；_load 记录起始时间、_save 计算时长）
- `_BusinessCognitionReviewForm` 支持 adjudication_mode

## 5. V1 vs V2 比较脚本 ✅

`scripts/stage4_human24_v1_vs_v2.py`（完成 12 条后运行）：
- **agreement_rate**（全 set 逐 label）· **high_impact_agreement_rate**（needs+values）
- **per-field agreement** · **label additions**（V2 新增）· **label removals**（V2 移除）
- **high-impact disagreement**（V1_only / V2_only 明细）· **confidence distribution**
- **判定**：needs+values 高影响一致率 ≥ 0.85 → **ADJUDICATED_HUMAN_TRUTH**；否则 → **UNRELIABLE_FOR_CALIBRATION**
- 冒烟已验证管道（V2 匹配、无崩溃、verdict 输出；模拟数据已清除）

## 6. 判定路线

| 情况 | 结论 |
|---|---|
| 12 条中仅 1~2 条变化 | V1 整体勉强可信 → V2 裁决覆盖真值层 → 继续 Stage2.1 |
| 12 条中出现 4~5+ 条明显变化 | Human24 V1 噪声大 → 重设计简化 Human Review 后重审 24 条 |

## 7. 测试

**19/19 PASS**（+4：V2 manifest 12 条 blind / V2 持久化 confidence+duration / V1vsV2 verdict 逻辑 / 既有 16）

## 产物
- `HUMAN24_TRUTH_RELIABILITY_STATUS.json`（V1 降级标记，数据保留）
- `BUSINESS_COGNITION_STAGE2_HUMAN_ADJUDICATION_V2.json`（12 条 blind manifest）
- `scripts/stage4_human24_v1_provisional.py` · `stage4_human24_adjudication_v2.py` · `stage4_human24_v1_vs_v2.py`
- `src/treecut/services/annotation_governance.py`（V2 表 + save 方法）· `review_center.py`（V2 任务 + 时长）· `phase3_review_ui.py`（adjudication_mode + 把握度）
- `tests/test_stage2_cognition.py`（19）
- 本报告 `docs/PHASE4_STAGE2_HUMAN_TRUTH_RELIABILITY_GATE.md`

## 停点

**STOP** —— 等你状态正常时，在 GUI 人工审核中心打开 **Stage2 Human24 复核（Adjudication V2·12 条盲审）** 完成 12 条，然后运行 `stage4_human24_v1_vs_v2.py` 出判定。未自动开始人工审核 · 未执行 Stage2.1 规则修改 · 未进 Stage3。
