# PHASE4 STAGE 2 — BUSINESS COGNITION HARDENING REPORT

> 状态：**Stage 2 引擎侧完成（AI_LOCK 60/60 已冻结）· Human Business Review 24 已就绪待人工执行 · STOP（未自动开始人工审核 / 未进 Stage 3）**
> 日期：2026-08-29
> 知识快照：V1.2（`a9ac59f60e13a0bc8bb6949f99884202d3e3e3872d7c3c153e09cc00b5e79eec`）
> 引擎：BusinessCognitionServiceV2 + EvidenceResolverV1 + ConflictResolverV1 + BusinessClaimV2
> 纪律：未改 Bundle V2 / 未碰 Holdout V1+V2 / 未改 Phase3 Human Truth / 未做 knowledge→visual 反推 / 未用 Hypothesis 硬推理 / semantic_action 不单独进高置信结论

---

## PRE-STEP 0 — V1.2 真正从头 Replay 43 Validation ✅

**不得复用 V1.1 旧 output**：从 Knowledge Snapshot V1.2 完整重跑 43 条（Evidence 归一 → retrieve_facts → retrieve_business_rules → negative rules → cognition）。

- **`BUSINESS_COGNITION_V12_REPLAY43.json`**：43 条 · user_needs 34 / business_values 34
- **critical_regression_count = 0**（无 user_needs/business_values 丢失）
- 负规则过滤不恶化：V1.1 无 OPERATE_SOCKET 的段现在仍无
- 仅 retrieved knowledge identity 因 V1.2 类型修正允许变化

## 1-3. EvidenceResolverV1 + 证据家族防重复计票 ✅

`src/treecut/services/evidence_resolver.py`：统一证据包 `normalized_evidence / family_counts / independent_sources / provenance`。

- **同源不算多票**：SigLIP 家族（component/function/material/product_family…）同属 SIGLIP，只能计 1 个独立来源；独立来源仅按 family 计数（YOLO / SIGLIP / ASR / OCR / MOTION_ASR / HUMAN / METADATA）
- **action_sequence/semantic_action 强制 VERY_LOW**（Phase3 纪律，NR005 依赖）
- FIELD_RELIABILITY 与 Phase3 基准一致：people=HIGH · component/function=MEDIUM_HIGH · product_family=MEDIUM · scene/variant=LIMITED · material/shot_role=LOW · semantic_action=VERY_LOW

## 4-5. ConflictResolverV1 ✅

`src/treecut/services/conflict_resolver.py`：

- **CONFLICTING_EVIDENCE**：ASR 出现 客户家/家里/入户/客厅/卧室 而 scene=FACTORY → `CUSTOMER_HOME=UNKNOWN`（不强行二选一）
- **WEAK_EVIDENCE_CONFLICT**：material LOW 可靠 + ASR 实木/原木/大理石 → `MATERIAL_CLAIM=WEAK/UNKNOWN`（NR003）
- 输出 `conflicts / conflict_count / supported_count / weak_count`

## 6-7. BusinessClaimV2 + 六态 claim_status ✅

`src/treecut/services/business_cognition_v2.py`：

- `BusinessClaimV2`：claim_id / claim_category / claim_value / **context_scope=SEGMENT_SCOPE** / claim_status / confidence / evidence_refs / knowledge_refs / rule_refs / negative_rule_checks / reason_codes
- **claim_status 六态**：CONFIRMED / SUPPORTED / WEAK / CANDIDATE / UNKNOWN / BLOCKED（BLOCKED 命中负规则后移除）
- confidence 映射：CONFIRMED→HIGH · SUPPORTED→MEDIUM_HIGH · WEAK/CANDIDATE→LOW · UNKNOWN→UNKNOWN · BLOCKED→BLOCKED

## 8-9. Segment 只出 affinity / candidates，绝不输出 primary ✅

- `content_role_affinity[]`（ROLE_001-003，MEDIUM 候选）· `mother_theme_affinity[]`（THEME_001-005）· `search_intent_candidates[]` · `shot_function_candidates[]`
- **无 primary_role / primary_theme 字段**（AI_LOCK 全量检查通过：has primary = False）
- 最终 Content Role / Mother Theme 由 **Script + Template + Production 上下文**决定（未来阶段）

## 10-12. Challenge60 冻结（六类各 10，非 Holdout，不与 Validation43 重叠）✅

`BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json`：

| 类别 | 采样特征（按 evidence 结构，非按预测） | 数量 |
|---|---|---|
| STRONG_SINGLE_EVIDENCE | 单组件 + 匹配功能（DRAWER+STORAGE 等） | 10 |
| MULTI_SOURCE_AGREEMENT | 多组件 / 多功能域一致 | 10 |
| CONFLICTING_EVIDENCE | ASR 话语（家里/客户家）vs FACTORY 场景矛盾 | 10 |
| WEAK_EVIDENCE | 无组件弱信号 | 10 |
| NEGATIVE_RULE_TRIGGER | TRACK_SOCKET 触发 NR001/005 | 10 |
| AMBIGUOUS_MULTI_PURPOSE | OTHER/OTHER、多用途多义 | 10 |

- 池 394（Cal/Stage3/Mini，排除 Holdout 60 + Validation43 43）
- manifest 含冻结证据（组件/功能/场景/材料/动作/ASR 原文），供 Human 评审使用

## 13-14. AI Business Cognition 60/60 锁定（AI_LOCK）✅

`BUSINESS_COGNITION_STAGE2_AI_LOCK.json`（60/60，缺失 0）：

- claims 137（全 SUPPORTED 级；WEAK/AMBIGUOUS 类 0 claims = 不硬编结论）
- **负规则生效**：全量无 OPERATE_SOCKET / REAL_CUSTOMER_CASE / FAMILY_GATHERING（NR001/002/004）
- **CONFLICTING 类 10/10 触发场景冲突**；STRONG 类 10/10 有 needs；WEAK 类 0 needs/0 claims（诚实优先）
- 覆盖：user_needs 35 / business_values 35 / role_affinity 35 / theme_affinity 10 / search_intent 34
- 已知冗余（非错误）：SEM_003 与 SEM_004 均对 TRACK_SOCKET 产出 POWER_CONVENIENCE；business_values 用 set 聚合去重，不影响结论

## 15. Human Business Review 24（4×6 平衡，盲审，就绪待执行）✅

- **`BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json`**：24 条 = 六类各 4；**blind=true**（无 AI claims/affinity/confidence，只给候选清单 + 冻结证据）
- **评审目标 = 业务认知判定**（用户需求/商业价值主张是否被视频支持），非视觉重标注
- Review Center 新任务 `TARGETED_REVIEW_STAGE2_BUSINESS_COGNITION_V1`：新表单 `_BusinessCognitionReviewForm`（三态判定：支持/不支持/不确定 + 冲突观察 + 备注），保存到 `stage2_business_cognition_review_v1` 表（AnnotationService.save_business_cognition_review）
- **打分脚本 `stage4_human24_score.py`**：AI_LOCK vs Human24 → precision / recall / F1 / **UNSUPPORTED_CLAIM_RATE**（最重要指标）/ 六类分桶 / 冲突观察一致性 → `BUSINESS_COGNITION_STAGE2_SCORE_V1.json`（冒烟验证通过：AI≡Human 模拟 → P=1.0、UCR=0；模拟数据已清除）
- **纪律**：24 条只打分不重调规则；同一 24 将成为 KNOWN_DEV_BENCHMARK；剩余 36 为 STAGE2_SECONDARY_DEV（显式非 Fresh Holdout）

## 16. 测试 ✅

**224/224 PASS**（原 213 + Stage2 新增 11：evidence family 防重复计票 · semantic_action VERY_LOW · scene/ASR 冲突 · material/ASR 冲突 · V2 无 primary · search intent candidate · negative 阻断 OPERATE_SOCKET · semantic_action 非硬证据 · drawer+storage claims · V12 replay43 无 critical regression）

## 17-18. 规则落地 + 冻结

- **`knowledge/business_rules_v2/knowledge.json`**：24 条 Stage2 认知引擎规则（EVIDENCE_POLICY 4 · BUSINESS_RULE 7 · NEGATIVE_RULE 4 · CONTENT_STRATEGY_RULE 9）—— EF001/EF002 证据家族、CF001/CF002 冲突策略、SEM_001-007、NR001/002/004/005、THEME_001-005、ROLE_001-003、SF001
- 规则 yield/dormancy 纪律：从未触发的规则标记 **UNTESTED（不删除）**；高触发低 precision → **NEEDS_REWORK**（Human24 打分后执行，不在 24 上重调）

---

## 18 问答复

1. **V1.2 从头 Replay 43？** → 是，`BUSINESS_COGNITION_V12_REPLAY43.json`，**critical_regression = 0**（34/34 needs/values）
2. **EvidenceResolverV1？** → 是，`evidence_resolver.py`（family_counts / independent_sources / provenance）
3. **同源防重复计票？** → 是：SigLIP component+function+material = 1 票；仅按 family 计独立来源
4. **ConflictResolverV1？** → 是，`conflict_resolver.py`（scene/ASR → CUSTOMER_HOME=UNKNOWN；material/ASR → WEAK/UNKNOWN）
5. **BusinessClaimV2 六态？** → 是：CONFIRMED/SUPPORTED/WEAK/CANDIDATE/UNKNOWN/BLOCKED
6. **Segment 输出 primary？** → **否**，仅 content_role_affinity[] / mother_theme_affinity[] / search_intent_candidates[]（AI_LOCK 检查通过）
7. **Challenge60 六类各 10？** → 是（STRONG 10 / MULTI 10 / CONFLICTING 10 / WEAK 10 / NEG 10 / AMB 10），非 Holdout、非 Validation43
8. **AI Cognition 60/60 锁定？** → 是，`BUSINESS_COGNITION_STAGE2_AI_LOCK.json`（AI_LOCK，60/60）
9. **Human Business Review 24？** → 就绪待执行（manifest 4×6 平衡、blind、业务认知评审非视觉重标注）
10. **打分脚本？** → 是，`stage4_human24_score.py`（precision/recall/F1/**UNSUPPORTED_CLAIM_RATE**/六类分桶/冲突一致性）
11. **负规则纪律？** → AI_LOCK 全量无 OPERATE_SOCKET/REAL_CUSTOMER_CASE/FAMILY_GATHERING
12. **semantic_action 纪律？** → 强制 VERY_LOW，不单独触发高置信结论（EF002/NR005）
13. **规则落地？** → `knowledge/business_rules_v2/knowledge.json`（24 条）
14. **测试？** → **224/224 PASS**（+11 Stage2）
15. **模拟打分验证？** → 通过（AI≡Human → P=1.0, UCR=0），模拟数据已清除
16. **Human24 后是否重调规则？** → **否**（只打分；同 24 = KNOWN_DEV_BENCHMARK）
17. **剩余 36？** → STAGE2_SECONDARY_DEV（显式非 Fresh Holdout）
18. **是否自动开始人工审核 / 进 Stage3？** → **否，STOP**

---

## 产物

- `src/treecut/services/evidence_resolver.py` · `conflict_resolver.py` · `business_cognition_v2.py`（BusinessClaimV2 + affinity 模型）
- `src/treecut/services/knowledge_service.py`（retrieve_facts/hypotheses/platform_rules/hard_reasoning）
- `src/treecut/services/phase3_review_ui.py`（_BusinessCognitionReviewForm + validate_business_cognition）
- `src/treecut/services/review_center.py`（新任务注册）· `annotation_governance.py`（save_business_cognition_review）
- `scripts/stage4_v12_replay43.py` · `stage4_challenge60.py` · `stage4_challenge60_ai_lock.py` · `stage4_human24_manifest.py` · `stage4_human24_score.py` · `stage4_export_business_rules_v2.py`
- `tests/test_stage2_cognition.py`（11）
- `knowledge/business_rules_v2/knowledge.json`（24）
- DATA_ROOT：`BUSINESS_COGNITION_V12_REPLAY43.json` · `BUSINESS_COGNITION_STAGE2_CHALLENGE_V1.json` · `BUSINESS_COGNITION_STAGE2_AI_LOCK.json` · `BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json` · `BUSINESS_COGNITION_STAGE2_SCORE_V1.json`
- 本报告 `docs/PHASE4_STAGE2_BUSINESS_COGNITION_HARDENING_REPORT.md`

## 第一停点

**STOP** —— 等架构监工确认 + **人工执行 Human Business Review 24**（GUI 人工审核中心 → Stage2 业务认知评审）→ 运行 `stage4_human24_score.py` 出分。未自动开始人工审核 / 未进 Stage3 / 未账号 DNA / 未投流学习 / 未模板验证 / 未 Script Intelligence / 未 Director / 未剪辑。
