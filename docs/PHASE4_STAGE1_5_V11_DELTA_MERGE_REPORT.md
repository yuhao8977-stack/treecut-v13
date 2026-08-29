# PHASE4 STAGE 1.5 — V1.1 DELTA MERGE + SOURCE REQUIREMENT RECLASSIFICATION

> 状态：**Stage 1.5 完成 · PHASE4_STAGE2_READY = TRUE（待监工确认）**
> 日期：2026-08-29
> 基础快照：V1（`2111b0b3…`，保留）→ 新快照 **V1.1（`36b40ea7…`）**
> 纪律：未重导 V1.0 旧 186 / 未覆盖 V1 快照 / 未进 Stage2 / 未碰 Holdout

---

## STEP 1-2：V1.1 Source 登记 + DELTA MERGE ✅

**V1.1 主源**：`TreeCut_V11_Phase4.xlsx`（USER_CURATED_STRUCTURED_KB，sha `07AE586D…`，extends V1.0）
**合并结果（361 条）**：以 V1.1 主表 + P4 Taxonomy + 映射/负规则 + EvidencePolicy + 模板统一导入，**未重复导入原 186**（V1.1 已含全部）。

**Delta 统计**：
- v1_existing（V1.1 含原语义）：186 条保留
- v1_1_new：175 条新增（P4 Taxonomy 92 + 映射/负规则 27 + EvidencePolicy 50 + 模板新增 CT06-12 7 + 其他）
- 重复阻止：knowledge_id 去重（旧 content_role/professional 残留已清）
- conflict：真冲突 **0**（同 namespace 同前缀）；semantic_dup 6（KB 主表 vs P4 Taxonomy 同概念，记录不删）；cross-ns RELATED 8（合法跨层）

## STEP 3：V1.1 新增结构确认 ✅

| 结构 | 状态 |
|---|---|
| KnowledgeRecord 统一字段 | ✅（knowledge_id/namespace/knowledge_type/status/confidence） |
| Mother Themes | ✅ 5 类（HYPOTHESIS/DRAFT） |
| Search Intent / Decision Factor | ✅（P4 Taxonomy，semantic_mappings/dimensions_decisions） |
| Shot Function | ✅（shot_ontology 37 条含 P4 叙事功能） |
| Business Cognition Schema | ✅（之前已建） |
| Semantic Business Mapping | ✅ MAP-001~004+ |
| Evidence Reliability | ✅ 50 条（EvidenceReliabilityPolicy） |
| Negative Rules | ✅（negative_rules 30 含 P4） |
| Template Schema + CT06-CT12 | ✅（CT06-12 全部 HYPOTHESIS/DRAFT/UNVALIDATED） |

## STEP 4：模板纪律 ✅

CT01-CT05（原 V1.0，REVIEWED_SEED）· CT06-CT12（V1.1 新增）**全部 HYPOTHESIS / DRAFT / UNVALIDATED**，未自动 ACTIVE；future_validation = HISTORICAL_PERFORMANCE_TEST。

## STEP 5-9：SOURCE_REQUIREMENT 重分类 ✅

| class | 条数 | 说明 |
|---|---|---|
| **EXTERNAL_SOURCE_REQUIRED** | **12** | 专业知识 7（NKBA 尺寸/规范）+ 尺寸类 5 —— 真正需外部来源 |
| **INTERNAL_VALIDATION_REQUIRED** | **175** | TreeCut 业务模型（role/theme/shot function/taxonomy/映射）→ 内部验证 |
| PLATFORM_SOURCE_REQUIRED | 10 | 平台合规（TTL 30 天，无 STALE） |
| SOURCE_PRESENT | 77 | 业务词典/平台官方有源 |
| NO_EXTERNAL_SOURCE_NEEDED | 87 | 系统设计/负规则/EvidencePolicy |

**Q11 真正需用户/外部补的**：12 条（厨房尺寸标准、通道/人体工学、材料物理性能、安全规范、电气规范）—— **其余 163 条不再误标 NEEDS_SOURCE**。

## STEP 10-11：BUSINESS_RULE 修复 ✅

**为什么之前 BUSINESS_RULE=0**：V1.0 导入分类器把所有业务语义（product/material/function 等"已业务验证"项）归为 FACT，运营假设归 HYPOTHESIS —— 漏了 BUSINESS_RULE 类。
**修复**：V1.1 主表已显式标注 knowledge_type → 重分类后 **BUSINESS_RULE 320**（产品/材质/工艺/功能/场景/需求/内容/镜头/脚本/负规则全部业务规则化）。
**BUSINESS_RULE 纪律**：SYSTEM_GUARDRAIL（负规则，ACTIVE）· BUSINESS_VERIFIED（业务词典，ACTIVE/REVIEWED）· BUSINESS_SEED（Taxonomy，DRAFT）· 未验证的不 ACTIVE。

## STEP 12-13：重新 Audit ✅

361 条 · BUSINESS_RULE 320 / HYPOTHESIS 24（**全 DRAFT ✓**）/ FACT 7 / PLATFORM_RULE 10 · 重复 0 · 真冲突 0 · stale 0 · **未验证 FACT 却 ACTIVE HIGH = 0 ✓** · confidence HIGH 112/MEDIUM 239/LOW 12 · status ACTIVE 143/REVIEWED 29/DRAFT 191。

## STEP 14-16：测试 + Validation ✅

**16/16 核心测试全 PASS**（原 10 + TEST 11-16）：
- TEST 11 weak semantic_action 不升级 hard fact ✓ · TEST 12 插座→POWER_CONVENIENCE 非 OPERATE_SOCKET ✓ · TEST 13 伸缩→FLEXIBLE_CAPACITY 非 SMALL_APARTMENT ✓ · TEST 14 BUSINESS_RULE/FACT 可区分 ✓ · TEST 15 HYPOTHESIS 不进 hard rule ✓ · TEST 16 平台 TTL 生效 ✓

**43 条 Validation 重跑（V1.1）**：34 有 user_needs / 34 有 business_values / **regressions vs V1 = 0**（无 unexpected regression / new conflict / over-inference）。
**STEP 16 A-H 能力验证**：全部 PASS（DRAWER→STORAGE、TRACK_SOCKET→POWER 非动作、EXTENDABLE→FLEXIBLE 非小户型、FACTORY→TRUST 非真实案例、people 不推家庭、弱材质不推实木、semantic_action 不单独触发、同一证据可 SEARCH/CONVERSION 双角色）。

## STEP 17：Snapshot V1.1 ✅

**KNOWLEDGE_SNAPSHOT_V1_1.json**（V1 保留未覆盖）：361 条 / 26 文件 / base V1 / delta V1.1 / **knowledge_snapshot_sha256 = `36b40ea7bdcbd9e8c3c737871d653bc50f79a92ff152aac3d25b3fb43473ce98`**

---

## 17 问答复

1. **V1.1 新增多少条？** → **175**（Taxonomy 92 + 映射/负规则 27 + EvidencePolicy 50 + 模板 CT06-12 7 等）
2. **更新多少条？** → 186 条原语义保留（knowledge_id 规范化）
3. **阻止多少重复？** → knowledge_id 去重全量；V1.0 残留 content_role/professional 已清
4. **BUSINESS_RULE 最终？** → **320**
5. **为何之前=0？** → V1.0 分类器漏了业务规则类（归 FACT/HYPOTHESIS）；V1.1 显式标注后修复
6. **FACT？** → 7（专业知识） 7. **HYPOTHESIS？** → 24（全 DRAFT） 8. **PLATFORM_RULE？** → 10
9. **EXTERNAL_SOURCE_REQUIRED？** → **12** 10. **INTERNAL_VALIDATION_REQUIRED？** → **175**
11. **真正需补证据？** → 12 条（尺寸/安全/材料性能/电气/厨房规范）；其余内部验证
12. **CT06-CT12 以 DRAFT 导入？** → 是（HYPOTHESIS/DRAFT/UNVALIDATED）
13. **16 个核心测试？** → **全 PASS（16/16）**
14. **43 条 Validation 无严重回归？** → **是（regressions=0）**
15. **新 snapshot sha256？** → **`36b40ea7bdcbd9e8c3c737871d653bc50f79a92ff152aac3d25b3fb43473ce98`**
16. **还需用户补知识文件？** → 暂不需要（V1.1 结构完整；12 条外部来源待联网核验，非阻塞）
17. **可进 STAGE2？** → **是**（A-I 条件全满足）

---

## Stage 1 Final Gate

**判定：PASS_WITH_LIMITATIONS · PHASE4_STAGE2_READY = TRUE**
- ✅ V1.1 delta 成功并入 · ✅ BUSINESS_RULE 分类合理（320）· ✅ source requirement 重分类完成 · ✅ 未验证 FACT 不进 hard reasoning · ✅ HYPOTHESIS 不冒充规则 · ✅ 平台 TTL 生效 · ✅ 16 测试 PASS · ✅ 43 Validation 无回归 · ✅ Snapshot V1.1 冻结
- ⚠ 限制：12 条 EXTERNAL_SOURCE_REQUIRED 待联网核验（非阻塞）；6 条 KB/P4 语义重复待后续合并决策

## 产物

- `knowledge/knowledge_delta_v1_to_v1_1.json`（Delta 明细）
- `knowledge/source_requirement_audit.json`（重分类）
- `knowledge/knowledge_audit_v1_1.json` · `knowledge/knowledge_manifest.json`（V1.1）
- `KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS_V1_1.json`（DATA_ROOT）
- `KNOWLEDGE_SNAPSHOT_V1_1.json`（`36b40ea7…`）
- 本报告 `docs/PHASE4_STAGE1_5_V11_DELTA_MERGE_REPORT.md`

## 第一停点

**STOP** —— 等架构监工确认后进 STAGE2（BUSINESS COGNITION HARDENING）。未自动进 Stage2 / 未账号 DNA / 未投流学习 / 未模板验证 / 未 Script Intelligence / 未 Director / 未剪辑。
