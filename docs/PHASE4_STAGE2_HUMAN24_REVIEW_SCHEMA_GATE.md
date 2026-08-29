# PHASE4 STAGE 2 — HUMAN24 REVIEW SCHEMA FINAL GATE

> 状态：**PASS · HUMAN24 = READY（Recall 真实可计算 · AI 零泄漏 · Human 可独立补标签）**
> 日期：2026-08-29
> 基础：Stage2 Engine Side = PASS · Challenge60 = LOCKED · AI Business Cognition 60/60 = LOCKED · Human24 Manifest = READY
> 纪律：未修改 Business Cognition Engine / Rules / Knowledge / AI_LOCK；仅修改 Human Review UI + schema + score adapter

---

## 背景：为什么必须 Gate

原表单为"三态判定（支持/不支持/不确定）"——若只是对 **AI 已提出的 claim** 逐条 accept/reject，则：
- **Precision 可计算**
- **Recall 是假的**：AI 没提出、但 Human 认为应存在的 claim 永远不会进入 Human Truth

例：AI={STORAGE}，Human 看完认为={STORAGE, CUSTOMIZATION, POWER}。若 UI 只问"STORAGE 支不支持？"→ 假 Precision=100%、假 Recall=100%。真实应为 P=100%、**R=33.3%**（FN=2）。

**Gate 判定：原实现不通过** → 已重写为**独立 Human Truth** 模型（见下）。

## 1-2. 独立 Human Truth + 完整固定 Taxonomy ✅

- **`BUSINESS_COGNITION_HUMAN_TAXONOMY_V1.json`**（新增，从 Knowledge Brain V1.2 P4 定义生成，**非 AI 生成**）：
  - user_needs **21** · business_values **18** · decision_factors **16** · search_intents **13** · shot_functions **15** · trust_signals **6**（content_roles TRUST typical_evidence + craft_trust 固定业务词典）
  - content_roles **4**（TRAFFIC/SEARCH/TRUST/CONVERSION）· mother_themes **5**（SPACE_SOLUTION/FAMILY_SCENE/DECISION_AVOID_PIT/AESTHETIC_STYLE/CRAFT_TRUST）· affinity_levels **5**（STRONG/MEDIUM/WEAK/NOT_SUPPORTED/UNKNOWN）
- **`_BusinessCognitionReviewForm` 重写**：6 个多标签字段全部显示**完整固定 Taxonomy**（Listbox 多选，点击即选/再点取消），Human 从全量独立勾选**所有成立的标签**——可包含 AI 从未预测的（如 CUSTOMIZATION/AESTHETICS）→ **Human Truth 独立于 AI claim**
- 三态判定已废弃；若未来需要 claim-level QA，仅作为 `human_claim_judgement_aux` 辅助，不是 Truth 来源

## 3. Human 可添加 AI 未预测的 label ✅

Smoke Test 实测：Human 勾选 `{STORAGE, CUSTOMIZATION}`，`CUSTOMIZATION` 是 AI_LOCK 中不存在的标签 → 保存成功、评分计入 FN。

## 4-5. Role 4 类 + Theme 5 类全部独立评级 ✅

- 表单对 **TRAFFIC/SEARCH/TRUST/CONVERSION 4 类**与 **SPACE_SOLUTION/FAMILY_SCENE/DECISION_AVOID_PIT/AESTHETIC_STYLE/CRAFT_TRUST 5 类**每一维度独立 5 级评级（不强求，允许 UNKNOWN）
- 评分支持：exact_affinity / within_one_level / macroF1 / strong_unsupported
- 注：AI 引擎仅 3 role（缺 TRAFFIC）→ 评分中 TRAFFIC 视 AI 未主张（不修改 AI 引擎，遵守纪律）

## 6. Sampling Class 对用户隐藏 ✅

`hide_sampling_class=True`：STRONG_SINGLE_EVIDENCE 等六类采样标签在 UI **不显示**（仅 manifest 保留供评分）。用户只见：题号、视频、Evidence Context、Business Review Form。

## 7. AI Claim 零泄漏 ✅

- 任务注册 `blind=True`；manifest 24 段**无任何** ai_claims/affinity/confidence/rule/knowledge/retrieval 字段（测试断言通过）
- 表单 Taxonomy 来自独立文件（非 AI_LOCK）；Smoke Test 验证 mock 段不在 AI_LOCK

## 8. L2 Evidence 明确标 MODEL + 可靠性 ✅

Review Center `_load` 冻结证据展示（`show_frozen_evidence`）：
- `[MODEL] 组件 (MEDIUM_HIGH/SIGLIP)` · `[MODEL] 功能 (MEDIUM_HIGH/SIGLIP)`
- `[MODEL] 场景 (LOW/SIGLIP)` · `[MODEL] 材质 (LOW/SIGLIP)` · `[MODEL] 动作 (VERY_LOW/MOTION_ASR)`
- `[ASR] 讲解原文`；若有人工核验证据 → `[HUMAN_VERIFIED]`
- Human 不重标视觉事实（scene/component/function/material/people/action 仍是 Frozen Evidence Context）

## 9-10. Human-only label → FN；Recall 真正可计算 ✅

`stage4_human24_score.py` 重写为 **set comparison**（AI_LOCK vs 独立 Human Truth）：
- 多标签字段：TP=AI∩Human · FP=AI−Human · FN=Human−AI · TN=Taxonomy−(AI∪Human)
- **UNSUPPORTED_CLAIM_RATE = FP/(TP+FP)**（Stage2 最重要指标）
- 评分 dry-run 实测（模拟每段 Human=AI+1 个额外标签）：**Recall=0.455（非假 1.0），FN=48**，证明 Human 漏检被真实捕捉
- Affinity 评分：exact/within-one/macroF1/strong unsupported

## 11. Temporary Mock Smoke Test ✅（PASS 五项）

`scripts/stage4_human24_smoke.py`（全自动，跑完即删）：
- **A** mock 不在 AI_LOCK（无 AI answer 泄漏路径）✅
- **B** 用户可勾选 AI 未预测的 CUSTOMIZATION ✅
- **C** DB 正确记录 human-only label（`user_needs=['STORAGE','CUSTOMIZATION']`）✅
- **D** 评分逻辑 TP=1 FN=1（CUSTOMIZATION 计入 FN）✅
- **E** mock 已删除（表剩余 0 行）✅

## 12. 正式 Human24 判定

**READY ✅** —— Recall 真实可计算 + AI 零泄漏 + Human 可独立补标签全部达成。

## 13-15. Lock Discipline ✅

- `BUSINESS_COGNITION_STAGE2_AI_LOCK.json` **未变**（未重跑 AI cognition）
- Human24 manifest 24 段 **segment identity 与 Gate 前完全一致**（确定性采样），仅新增 taxonomy 引用
- 未修改 Business Cognition Engine / Rules / Knowledge / AI_LOCK；仅改 Human Review UI + schema + score adapter

## 16. 输出 · 12 问答复

1. **Human Review 独立于 AI Claim？** → **是**：完整固定 Taxonomy 多选，Human 独立勾选全量（可含 AI 未预测）
2. **Multi-label 显示完整固定 Taxonomy？** → **是**（21/18/16/13/15/6，来自知识库非 AI）
3. **Human 可添加 AI 未预测 label？** → **是**（CUSTOMIZATION 实测）
4. **Role 四类全部独立评级？** → **是**（TRAFFIC/SEARCH/TRUST/CONVERSION × 5 级）
5. **Theme 五类全部独立评级？** → **是**（5 类 × 5 级）
6. **Sampling class 对用户隐藏？** → **是**（hide_sampling_class）
7. **AI Claim 零泄漏？** → **是**（blind manifest + 独立 taxonomy 文件）
8. **L2 Evidence 明确标模型证据/可靠性？** → **是**（[MODEL] + MEDIUM_HIGH/LOW/VERY_LOW）
9. **Human-only label 形成 FN？** → **是**（set comparison，dry-run Recall=0.455）
10. **Recall 真正可计算？** → **是**
11. **Temporary mock 测试？** → **PASS（A-E 五项）**
12. **可正式开始 Human24？** → **是（READY）**

---

## 产物

- `BUSINESS_COGNITION_HUMAN_TAXONOMY_V1.json`（固定 Taxonomy，知识库生成）
- `BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json`（24 段，blind，内嵌 taxonomy）
- `src/treecut/services/phase3_review_ui.py`（`_BusinessCognitionReviewForm` 独立 Truth 重写）
- `src/treecut/services/review_center.py`（hide_sampling_class + MODEL evidence 标注 + taxonomy 加载）
- `src/treecut/services/annotation_governance.py`（`save_business_cognition_review` 新 schema：user_needs/business_values/decision_factors/trust_signals/search_intents/shot_functions/role_affinity/theme_affinity/overall_unknown）
- `scripts/stage4_human_taxonomy.py` · `stage4_human24_manifest.py` · `stage4_human24_score.py`（set comparison）· `stage4_human24_smoke.py`
- `tests/test_stage2_cognition.py`（+3：taxonomy 完整性 / manifest blind 平衡 / human-only → FN）
- 本报告 `docs/PHASE4_STAGE2_HUMAN24_REVIEW_SCHEMA_GATE.md`

## 停点

**STOP** —— Gate 通过，Human24 正式可审。未自动开始人工审核 / 未进 Stage3。
