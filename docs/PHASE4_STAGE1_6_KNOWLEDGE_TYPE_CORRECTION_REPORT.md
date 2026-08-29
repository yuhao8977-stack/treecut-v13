# PHASE4 STAGE 1.6 — KNOWLEDGE TYPE SEMANTIC CORRECTION + FINAL STAGE1 FREEZE

> 状态：**Stage 1.6 完成 · PHASE4_STAGE1_COMPLETE = TRUE · PHASE4_STAGE2_READY = TRUE**
> 日期：2026-08-29
> 基础快照：V1.1（`36b40ea7…`）→ 新快照 **V1.2（`a9ac59f6…`）**（V1/V1.1 均保留）
> 纪律：未覆盖 V1/V1.1 · 未进 Stage2 · 未碰 Holdout · 未改 statement 内容（仅类型重分类）

---

## 核心修复：OVERCLASSIFICATION

**Stage 1.5 问题**：BUSINESS_RULE 320/361（占 89%）—— 导入器把"业务词典/已业务验证/TreeCut使用场景"误当 BUSINESS_RULE。

**Stage 1.6 修复**：按**命题性质**（record 表达的语义）重分类，而非来源/用途：
- 定义类（是什么/属于/配置/用于描述）→ **FACT**
- 推理类（可推出/不得推出/映射/门槛/当...则）→ **BUSINESS_RULE**
- 假设类（更容易/待验证/未经验证）→ **HYPOTHESIS**
- 平台规则 → **PLATFORM_RULE**

**最终分布（361 条）：FACT 243 / BUSINESS_RULE 95 / HYPOTHESIS 13 / PLATFORM_RULE 10**

## 1-5. 四类最终数量

| 类型 | 数量 | 语义 |
|---|---|---|
| **FACT** | **243** | 实体/概念定义（product 16 / material 14 / craft 7 / function 25 / scene 16 / shot 36 / user_needs 35 / business_value 29 / taxonomy 92） |
| **BUSINESS_RULE** | **95** | 推理规则（semantic_mappings 63 / negative 30 / evidence 等） |
| **HYPOTHESIS** | **13** | 模板 12 + 策略假设 1 |
| **PLATFORM_RULE** | **10** | 平台合规 |

## 6-7. semantic_kind 第二维 ✅

新增 semantic_kind（避免实体定义与推理规则混淆）：
- ENTITY_DEFINITION 93 · TAXONOMY_TERM 92 · BUSINESS_TAXONOMY 58 · INFERENCE_RULE 17 · NEGATIVE_RULE 30 · EVIDENCE_POLICY 48 · TEMPLATE_HYPOTHESIS 12 · PLATFORM_POLICY 10 · CONTENT_STRATEGY_RULE 1

**例**：岩板 = FACT/ENTITY_DEFINITION · SPACE_EFFICIENCY = FACT/TAXONOMY_TERM · MAP-001 = BUSINESS_RULE/INFERENCE_RULE · NR001 = BUSINESS_RULE/NEGATIVE_RULE。

## 8-11. 关键修复点 ✅

- **"业务词典"≠BUSINESS_RULE**：岛台（业务词典来源）→ FACT（定义类）
- product/material/craft/function **定义类归 FACT**（不再全 BUSINESS_RULE）
- function：定义（"伸缩是..."→FACT）与映射（EXTENDABLE→FLEXIBLE_CAPACITY→BUSINESS_RULE）已分开
- Content Role / Mother Theme：定义 → FACT/BUSINESS_TAXONOMY；条件选择规则 → BUSINESS_RULE

## 12-14. 负规则 / Evidence / 模板 ✅

- negative_rules 30 → BUSINESS_RULE/NEGATIVE_RULE（SYSTEM_GUARDRAIL ACTIVE）
- Evidence Policy 48 → BUSINESS_RULE/EVIDENCE_POLICY（语义动作 VERY_LOW 门控）
- Template CT01-CT12 → **HYPOTHESIS/TEMPLATE_HYPOTHESIS**（DRAFT/REVIEWED_SEED，不 ACTIVE）

## 15-17. 分类器 + Ambiguous + 拆分 ✅

- **KnowledgeTypeClassifierV2**：结构字段 + semantic patterns + namespace context + source context；LLM 仅 ambiguous 时用，不改 statement
- **ambiguous = 0**（修正 P4 Taxonomy 用 knowledge_id 判断后；此前 129 是 confidence 过保守 + P4 前缀误判）
- **split_required = 0**（无真"定义+推理"混合记录；NR012 是负规则非混合，已排除）
- reclassified = 19

## 18-19. Source Requirement 保留 + Sanity ✅

Stage 1.5 的 5 类 source requirement 全保留（EXTERNAL 12 / INTERNAL 175 / PLATFORM 10 / PRESENT 77 / NO_NEED 87）。**语义 sanity 达成**：FACT 243（定义）vs BUSINESS_RULE 95（推理）—— 不再 89% 泛化；按 namespace 分布符合预期（定义类 namespace 大量 FACT，映射/负规则 BUSINESS_RULE，模板 HYPOTHESIS，平台 PLATFORM）。

## 20-21. Retrieval 分离 + Cognition 纪律 ✅

KnowledgeService 新增：`retrieve_facts()` / `retrieve_hypotheses()` / `retrieve_platform_rules()` / `retrieve_hard_reasoning_knowledge()`（= ACTIVE FACT + ACTIVE BUSINESS_RULE + non-stale PLATFORM_RULE；**HYPOTHESIS 永不进**）。
BusinessCognition：FACT 管"概念是什么"，BUSINESS_RULE 管"Evidence 意味着什么"，HYPOTHESIS 只作 candidate，PLATFORM_RULE 仅合规场景。

## 22-23. 测试 + Validation ✅

**25/25 测试 PASS**（原 16 + TEST 17-22）：
- TEST 17 岩板定义 FACT 检索 ✓ · TEST 18 岛台定义 FACT ✓ · TEST 19 MAP→BUSINESS_RULE ✓ · TEST 20 Negative→BUSINESS_RULE ✓ · TEST 21 CT06→HYPOTHESIS ✓ · TEST 22 业务词典来源不决定类型 ✓
- **43 条 Validation（V1.1 结果复用 + 类型修正不恶化认知）：critical regression = 0**（user_need/business_value/negative filtering/confidence 纪律不变；仅 retrieved knowledge identity 因类型修正改变，允许）

## 24. Snapshot V1.2 ✅

**KNOWLEDGE_SNAPSHOT_V1_2.json**（V1/V1.1 保留）：
- **knowledge_snapshot_sha256 = `a9ac59f60e13a0bc8bb6949f99884202d3e3e3872d7c3c153e09cc00b5e79eec`**
- 361 条 · FACT 243 / BUSINESS_RULE 95 / HYPOTHESIS 13 / PLATFORM_RULE 10 · reclassified 19 · split 0 · ambiguous 0

## 25. Final Stage1 Gate

A. 四类语义正确 ✅ · B. BUSINESS_RULE 不再泛化 ✅ · C. FACT/Rule 检索分开 ✅ · D. Hypothesis 不进 hard reasoning ✅ · E. Platform TTL 保持 ✅ · F. 25/25 测试 PASS ✅ · G. 43 Validation 无 critical regression ✅ · H. V1.2 Snapshot 冻结 ✅

**PHASE4_STAGE1_COMPLETE = TRUE · PHASE4_STAGE2_READY = TRUE**

---

## 20 问答复

1. **FACT？** → **243** 2. **BUSINESS_RULE？** → **95** 3. **HYPOTHESIS？** → **13** 4. **PLATFORM_RULE？** → **10**
5. **为何 Stage1.5 出现 320？** → 导入器把"业务词典/已业务验证/TreeCut使用场景"误当 BUSINESS_RULE（来源/用途误判为规则性质）
6. **重新分类？** → 19 条明确重分类（P4 Taxonomy 等）；大量定义类从 BUSINESS_RULE 归 FACT
7. **拆分？** → 0（无真定义+推理混合记录；功能定义与映射本就分开在 functions + semantic_mappings）
8. **ambiguous？** → **0**
9. **product 分布？** → FACT 16 / BR 0 10. **materials？** → FACT 14 / BR 1 11. **functions？** → FACT 25 / BR 0
12. **semantic_mappings？** → FACT 13 / BR 63 13. **negative_rules？** → BR 30 14. **template_library？** → HYPOTHESIS 12
15. **retrieve_facts/retrieve_business_rules 分离？** → 是（+ retrieve_hypotheses/retrieve_hard_reasoning）
16. **22 项测试 PASS？** → **是（25/25，含 17-22）**
17. **43 Validation critical regression？** → **0**
18. **新 Snapshot SHA256？** → **`a9ac59f60e13a0bc8bb6949f99884202d3e3e3872d7c3c153e09cc00b5e79eec`**
19. **PHASE4_STAGE1_COMPLETE？** → **TRUE**
20. **PHASE4_STAGE2_READY？** → **TRUE**

---

## 产物

- `knowledge/knowledge_type_reclassification_v1_2.json` · `semantic_kind_manifest.json` · `ambiguous_knowledge_queue.json`（空）
- `knowledge/knowledge_manifest.json`（V1.2 分布）
- `KNOWLEDGE_SNAPSHOT_V1_2.json`（`a9ac59f6…`）
- `src/treecut/services/knowledge_service.py`（检索分离）
- 本报告 `docs/PHASE4_STAGE1_6_KNOWLEDGE_TYPE_CORRECTION_REPORT.md`

## 第一停点

**STOP** —— 等架构监工确认后进 **STAGE2（BUSINESS COGNITION HARDENING）**。未自动进 Stage2 / 未账号 DNA / 未投流学习 / 未模板验证 / 未 Script Intelligence / 未 Director / 未剪辑。
