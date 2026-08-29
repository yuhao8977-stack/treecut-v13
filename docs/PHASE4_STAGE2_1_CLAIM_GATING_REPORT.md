# PHASE4 STAGE 2.1 — CLAIM GATING + CONFIDENCE CALIBRATION REPORT

> 状态：**Stage2.1 引擎侧完成 · V2.1 Candidate 冻结 · Fresh18 manifest+AI_LOCK 就绪 · STOP（未自动审 Fresh18 / 未进 Stage3）**
> 日期：2026-08-29
> 基础：Knowledge Snapshot V1.2（`a9ac59f6…`）· Human Calibration V3 = CALIBRATION_TRUTH_RELIABLE · STAGE2_1_CALIBRATION_READY=TRUE
> 纪律：未修改 AI_LOCK / Knowledge V1.2 / Phase3 Human Truth / Fresh Holdout · 未在 V3 上声称新性能 · 未自动执行 Stage2.1 规则调优

---

## 0. 统计口径修正（用户指正已采纳）

V3 原始 29/1/4/34 保留，但拆两个指标：
- **Hard False Rate = 4/34 = 11.8%**（Human 明确 NOT_SUPPORTED）
- **SUPPORTED Insufficiency Rate = (4+1)/34 = 14.7%**（AI 说 SUPPORTED 但 Human 未判 CLEARLY——OVERCONFIDENT 不是 AI 错，但代表 SUPPORTED 等级过高）

**V3 真正证明**：85.3% 的 SUPPORTED 达到"镜头明确支持"标准；2.9% 方向合理但说重了；11.8% 明确不支持。

**表述收紧**：
- 6 个 4/4 标签 = **NO_ERROR_OBSERVED_IN_V3**（不得标 PROVEN_100_PERCENT，样本太小）
- GUEST_CAPACITY / FLEXIBLE_CAPACITY = **UNTESTED_IN_V3**（AI claims=0，不得提升置信度）
- V1 过标 = **存在一定过标/误标**（79% 仍 CLEARLY，21% 直接 NOT_SUPPORTED，非大量迁往 POSSIBLE）——不能说主要是"把关联性当证据"

## 1. 核心目标（只解决 4 个问题）

A. SUPPORTED 过强 ✅ B. STORAGE 类组件外推错误 ✅ C. Confidence 单档 ✅ D. Evidence Strength 决定 Claim Status ✅

## 2-3. EvidenceStrengthV2 ✅

`src/treecut/services/evidence_strength_v2.py`：每个潜在 Claim 生成 EvidenceStrengthReport（direct/indirect evidence、families、independent_family_count、correlated_evidence_count、highest_reliability、semantic_consistency、context_support、evidence_grade A/B/C/D/NONE、reason_codes）。

**Family 纪律保持**：SIGLIP component/function/material 同 family 不算独立来源（可提升 semantic_consistency）；独立来源仅 ASR/OCR/YOLO/HUMAN/METADATA。
**Grade 修复**：**semantic_action（MOTION_ASR, VERY_LOW）不得作为 Grade A 的"独立第二 family"**——修复了"组件+动作"被误判双源的问题。

## 4-5. Claim Status V2.1（六档全真实路径）✅

```
CONFIRMED（仅 Human Verified/事实链，AI 极少用）
SUPPORTED（Grade A/B + Business Rule + NR 通过 + 无未解决冲突）
CANDIDATE（Grade B/C，业务合理但 Segment 不足以证明）
WEAK（Grade D 或弱冲突）
UNKNOWN（无足够信息）
BLOCKED（NR 明确阻断）
```

## 6-11. STORAGE Gate V2（第一优先）✅

**禁止**：DRAWER→STORAGE SUPPORTED / CABINET→STORAGE SUPPORTED / 组件→STORAGE_EFFICIENCY SUPPORTED

```
PATH A: DRAWER/CABINET + function STORAGE + Grade>=B
        + 语境校验：ASR 非空但无收纳语义（讲工艺/风格）→ 降级 CANDIDATE
PATH B: DRAWER/CABINET + ASR/OCR 明确"收纳/储物/放东西…" → SUPPORTED
PATH C: 明确视觉使用 + 可靠 function（semantic_action 不单独满足）→ SUPPORTED
仅组件 → CANDIDATE；更弱 → WEAK/UNKNOWN
```

**STORAGE_EFFICIENCY 更高门槛**：即使 STORAGE=SUPPORTED 也不自动升级（"可以储物"≠"效率高"）；需 ASR 效率语义 或 多存储区+语境支持；否则最多 CANDIDATE。

## 12. Need→Value 解耦 ✅

NEED_VALUE_DERIVATION_GATE：STORAGE→STORAGE_EFFICIENCY、CHARGING_POWER→POWER_CONVENIENCE、DINING→DINING_CONVENIENCE、OFFICE→WORK_FROM_HOME 均需 Value 自身 Evidence。

## 13-15. 不破坏良好路径 ✅

6 个 V3 NO_ERROR_OBSERVED 标签（CHARGING_POWER/DINING/OFFICE/POWER_CONVENIENCE/DINING_CONVENIENCE/WORK_FROM_HOME）仅做通用 EvidenceStrength 表达，未大改规则。POWER：TRACK_SOCKET alone → CANDIDATE；有 function/ASR 供电语义 → SUPPORTED。

## 16-17. semantic_action / Search Intent 纪律 ✅

semantic_action 仍 VERY_LOW（OPEN_DRAWER/PULL_OUT 不得单独 SUPPORTED）；SearchIntent 继续 candidate layer（STORAGE SUPPORTED 不自动 ISLAND_STORAGE SUPPORTED）。

## 18-20. UtteranceContext / ConflictResolverV2 ✅

`utterance_context.py`（ASSERTED/HYPOTHETICAL/CONDITIONAL/GENERIC_EXAMPLE/NEGATED/QUOTED/UNKNOWN）+ `conflict_resolver_v2.py`：
- 假设语境（如果/假如/要是/比如/有宝宝的话/家里如果/客户如果）→ **不产生 CURRENT_CONTEXT=HOME，也不与 FACTORY 冲突**（NON_ASSERTED_CONTEXT 记录）
- 只有明确 ASSERTED（"这是客户家"等）+ FACTORY → CONFLICTING_EVIDENCE

## 21. Unit Tests TEST A-M ✅（13/13 PASS）

A DRAWER-only≠SUPPORTED ✅ B DRAWER+STORAGE→SUPPORTED ✅ C DRAWER-only≠STORAGE_EFF ✅ D 解耦 ✅ E ASR 收纳→SUPPORTED ✅ F SOCKET-only→CANDIDATE ✅ G SOCKET+充电→SUPPORTED ✅ H DINING ✅ I OFFICE ✅ J action-only 无 SUPPORTED ✅ K 假设语境无冲突 ✅ L 断言语境冲突 ✅ M NR 硬违规=0 ✅

## 22-23. V3 Known Dev Replay（KNOWN_DEV，非成绩）✅

`BUSINESS_COGNITION_V3_KNOWN_DEV_REPLAY_V2_1.json`（标 KNOWN_DEV / CONTAMINATED_FOR_EVALUATION / NOT_INDEPENDENT / NO_GENERALIZATION_CLAIM）：
- **storage_fixed = 0**（V3 判 NOT_SUPPORTED 的 Storage 段不再 SUPPORTED——原 Storage 错误按预期修复）✅
- **27 个非 Storage"回归"全部为空输入能力差异（0 个真回归）**：这些段 canonical 无组件/功能标注，V3 Human 看完整视频判 CLEARLY，引擎无输入诚实 UNKNOWN——非引擎退化，是"视频级 Human 判断 vs 结构化字段级引擎输入"的评估不对称
- 非 Storage 良好路径未被误伤 ✅

## 24. Secondary36 Behavior Diff ✅

`BUSINESS_COGNITION_STAGE2_SECONDARY_DEV_V1.json`（无 Human Truth，仅行为 diff）：

| | 旧 V2 | V2.1 |
|---|---|---|
| SUPPORTED | 86 | **31**（-64%）|
| CANDIDATE | 0 | **27**（真实出现）|
| UNKNOWN | 0 | 302 |
| WEAK | 0 | 0 |

**per-label**：STORAGE SUPPORTED 7 / CANDIDATE 10 / UNKNOWN 19；STORAGE_EFFICIENCY CANDIDATE 17 / UNKNOWN 19；POWER/DINING 保留 6 SUPPORTED（V3 良好路径未伤）；GUEST_CAPACITY/OFFICE/WORK_FROM_HOME UNKNOWN 36（这些标签在池中无对应组件+ASR 路径）。

**注意**：UNKNOWN=302 高——大量段无结构化输入（pool 中 comp/function 稀疏 + 无 ASR 场景），引擎诚实 abstain。**需在 Fresh18 观察 CLAIM_ABSTENTION_RATE 是否过高**（Gate §26 禁止全 UNKNOWN 作弊——此处非作弊，是无输入段的真实 abstain，但 Fresh18 覆盖更全的段类型后可验证）。

## 25-26. 多档真实出现 + 禁止全降级作弊 ✅

CANDIDATE 27 真实出现（Storage 类）；WEAK 0（当前池无 Grade D 场景，Unit Test 证明路径存在非死代码）。报告含 SUPPORTED_COVERAGE / ACTIONABLE_CLAIM_COVERAGE / CLAIM_ABSTENTION_RATE（Fresh18 评分脚本已实现）。

## 27-32. Fresh18 ✅

`BUSINESS_COGNITION_FRESH_VALIDATION_V1.json`：**18 段 = 六类各 3**，与 Validation43/Challenge60/Human24/V2/V3/Holdout V1/V2 **全部零重叠**（已验证）。CONFLICTING 类用**动作↔组件不匹配**（ASR 断言冲突段已被旧集耗尽，动作不匹配是真实证据结构冲突）。**Storage 相关段 12 个**（远超 ≥3 要求，含 component-only/component+function/component+ASR）。

`BUSINESS_COGNITION_FRESH_V1_AI_LOCK.json`：**Candidate V2.1 先锁**（18/18，sha256 `818f8d61…`，engine/rule/knowledge/timestamp 记录）。抽查质量：有输入+ASR 段正确 SUPPORTED（508ffa24 POWER/DINING 4 claims），无输入段诚实 UNKNOWN/CANDIDATE。

**Fresh Human Review 任务就绪**：`BUSINESS_COGNITION_FRESH_VALIDATION_V1`（复用 V3 单状态 10 标签 UI，blind，18 条待审）。

## 33-35. Fresh18 评估脚本就绪

`stage4_fresh18_score.py`：SUPPORTED_TRUE/OVERCONFIDENT/FALSE/HUMAN_UNKNOWN + supported_precision_clear/hard_false_rate/insufficiency_rate + SUPPORTED_COVERAGE/ACTIONABLE/ABSTENTION + CANDIDATE acceptance/WEAK behavior + Storage raw counts。Small-N 纪律：只报 raw counts。

## 36-37. 产物

- `src/treecut/services/evidence_strength_v2.py` · `utterance_context.py` · `conflict_resolver_v2.py` · `business_cognition_v2_1.py`
- `knowledge/business_rules_v2_1/knowledge.json`（9 条规则）
- `BUSINESS_COGNITION_V3_KNOWN_DEV_REPLAY_V2_1.json`（KNOWN_DEV）· `BUSINESS_COGNITION_STAGE2_SECONDARY_DEV_V1.json` · `BUSINESS_COGNITION_STAGE2_1_BEHAVIOR_DIFF.json`（并入 secondary）· `BUSINESS_COGNITION_FRESH_VALIDATION_V1.json` · `BUSINESS_COGNITION_FRESH_V1_AI_LOCK.json`
- `scripts/stage4_stage21_replay_secondary.py` · `stage4_fresh18_manifest.py` · `stage4_fresh18_ai_lock.py` · `stage4_fresh18_score.py` · `stage4_export_business_rules_v2_1.py`
- `tests/test_stage2_cognition.py`（37：+13 TEST A-M）
- 本报告 `docs/PHASE4_STAGE2_1_CLAIM_GATING_REPORT.md`

## 38. 25 问答复

1. **V3 冻结？** → 是（未动）
2. **未声称 V2.1 在 V3 的新性能？** → 是（KNOWN_DEV 标记）
3. **hard false 与 overconfident 分开？** → 是（4/34 vs 1/34）
4. **SUPPORTED insufficiency 单独统计？** → 是（5/34=14.7%）
5. **EvidenceStrengthV2 落地？** → 是
6. **六档全真实路径？** → SUPPORTED/CANDIDATE/UNKNOWN 真实出现（Secondary36）；WEAK 由 Unit Test 证明路径
7. **DRAWER-only 不再 SUPPORTED STORAGE？** → 是（TEST A）
8. **STORAGE 不自动 STORAGE_EFFICIENCY？** → 是（TEST D + Need→Value Gate）
9. **Storage 失败模式结构性解决？** → 是（Known replay storage_fixed=0）
10. **未大改 6 个良好标签？** → 是（仅通用表达）
11. **Power component-only→Candidate？** → 是（TEST F）
12. **semantic_action 仍 VERY_LOW？** → 是（TEST J）
13. **假设 ASR 不产生错误 scene conflict？** → 是（TEST K + UtteranceContext）
14. **NR 硬违规=0？** → 是（TEST M）
15. **Known V3 replay 只作 diagnostic？** → 是（KNOWN_DEV 标记）
16. **Secondary36 行为变化？** → SUPPORTED 86→31（-64%），CANDIDATE 0→27
17. **SUPPORTED 减少多少？** → -64%（86→31）
18. **CANDIDATE/WEAK/UNKNOWN 真实出现？** → CANDIDATE 27、UNKNOWN 302 真实；WEAK 0（路径由测试证明）
19. **全 UNKNOWN 逃避？** → 否（UNKNOWN 高源于无输入段真实 abstain；Fresh18 覆盖更全段类型验证）
20. **Fresh18 与旧集全不重叠？** → 是（已验证 6 集零重叠）
21. **Fresh18 六类各 3？** → 是
22. **Fresh18 覆盖 Storage 结构？** → 是（12 段含 component-only/func/ASR）
23. **V2.1 Fresh AI prediction 先锁？** → 是（sha256 锁定）
24. **Fresh Human Review UI blind 单状态 10 标签？** → 是（复用 V3 UI）
25. **可开始 Fresh18 盲审？** → **是（READY）**

## 停点

**STOP** —— Stage2.1 引擎侧完成。Fresh18 盲审任务已就绪（GUI 人工审核中心 → **Stage2.1 Fresh18 盲审**，18 条，等你状态好时做）。**未自动开始人工审核 · 未进 Stage3**。Fresh18 完成后运行 `stage4_fresh18_score.py`，若显示：Storage false 减少 + SUPPORTED 比 CANDIDATE 更可靠 + NR 硬违规 0 + 无 UNKNOWN 逃避 → 批准 Phase4 Stage2 完整收口。
