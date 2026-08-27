# TreeCut Phase 2.5 标注治理审计报告（Annotation Governance）

> 阶段: Phase 2.5（Annotation Governance & Continuous Learning Foundation）
> 日期: 2026-08-26 | 架构监工: ENGINEERING=PASS / VALIDATION=PARTIAL 后的治理收尾
> 状态: **基础设施就绪，等待 SECOND_REVIEW_V1 二次复核 60 条**
> 禁止进入 Phase 3

---

## 目录

1. [执行摘要](#一执行摘要)
2. [1. VALIDATION_SNAPSHOT_V1 冻结](#二1-validation_snapshot_v1-冻结)
3. [2-4. Metrics Integrity Audit](#三2-4-metrics-integrity-audit)
4. [5-6. Taxonomy Audit + Schema V2](#四5-6-taxonomy-audit--schema-v2)
5. [7-8. Human Confidence + 二次复核](#五7-8-human-confidence--二次复核)
6. [11-13. 基础设施：队列/采样/覆盖](#六11-13-基础设施队列采样覆盖)
7. [16-17. Service Layer + Tests](#七16-17-service-layer--tests)
8. [18-19. 完成条件与等待事项](#八18-19-完成条件与等待事项)
9. [遗留问题](#九遗留问题)

---

## 一、执行摘要

Phase 2.5 目标：**不训练 AI**，先确保人工答案可信、评价指标可信、标签体系一致、
未来持续人工审核不制造噪声。

| 验收项 | 结果 |
|---|---|
| Migration | **0005**（4 新表：v2/队列/覆盖/快照注册表） |
| pytest | **80 passed / 0 failed** |
| 新测试 | 8 个（Phase 2.5） |
| coverage | annotation_governance 68% / validation_report 90% |
| DB integrity | ok（51 → 55 表） |
| Snapshot 冻结 | ✅ VALIDATION_SNAPSHOT_V1 注册 |
| SECOND_REVIEW_V1 | ✅ 60 条抽取（5 组分层） |

---

## 二、1. VALIDATION_SNAPSHOT_V1 冻结

| 项 | 值 |
|---|---|
| snapshot_id | **VALIDATION_SNAPSHOT_V1**（validation_snapshots 表） |
| git_commit | 5c99564 |
| model | rules+clip-v1 v1.0 / algorithm=segment-cognition-v1 |
| sample_count | 300 |
| 策略 | **永久只读，禁止覆盖；后续重预测须新建 snapshot** |

同时保留 `CALIBRATION_SET_V1_MANIFEST.json`（300 条 + seed=42）。

---

## 三、2-4. Metrics Integrity Audit

### 3.1 指标口径修正（V2.5）

| 指标 | 定义 |
|---|---|
| **conditional_accuracy** | AI 非 UNKNOWN 回答中的准确率（原"accuracy"） |
| **effective_correct_rate** | 正确预测 / 人工真值全部样本（关键指标） |
| **UNKNOWN 行** | Confusion Matrix 保留 UNKNOWN 行（不排除后展示） |
| **human_valid_n / ai_answered_n / ai_unknown_n / correct_n / wrong_n** | 每字段独立输出 |

### 3.2 people_presence 0% 异常——已查明是 Metrics Bug

**根因**：`_load_reviews` SQL 中 people 别名为 `a_people`，但统计代码用 `a_people_presence` 查找 → 永远取不到 → ai_answered=0 → accuracy 0%。

**修复**：字段映射 `people_presence → a_people`。

**修正后真实值**（5 条测试样本验证）：conditional=75%，effective=60%。

### 3.3 Confidence Reliability Table

- confidence 明确标注 **NOT_CALIBRATED_SCORE**（规则分数，非概率）
- 按 bucket（0-.49/.50-.69/.70-.79/.80-.89/.90-1.0）输出 answered/unknown/correct/wrong/conditional_accuracy

---

## 四、5-6. Taxonomy Audit + Schema V2

### Taxonomy 审计结果（300 条人工标签）

| 问题类型 | 数量 | 明细 |
|---|---|---|
| **OBJECT_FUNCTION_MIX** | 53 | function 字段出现部件词"抽屉"（53 次） |
| ACTION_FUNCTION_MIX | 部分 | action 字段出现功能词（收纳/伸缩/展示） |
| PARENT_CHILD_MIX | 明显 | product 字段"岛台 vs 伸缩岛台"混用（52 条 AI 错判佐证） |

**结论**：人工标签存在跨概念层混用（抽屉是部件，收纳是功能），
若不治理，持续审核会制造冲突答案。

### Annotation Schema V2（设计）

```
scene（工厂/工厂展示区/加工车间/客户住宅/展厅/安装现场/其他/UNKNOWN）
product_family（岛台/吧台/餐边柜/茶桌…）
product_variant（伸缩岛台/悬浮岛台/落地岛台…）   ← 与 family 分离
material（岩板/实木/奢石…）
component（抽屉/轨道插座/柜门/台面…）           ← 新增，独立于 function
function（伸缩/收纳/用电/多人就餐…）
action（拉出/展开/收起/打开抽屉…）
shot_type（全景/中景/近景/特写…）
people_presence / product_visibility / quality
```

**禁止**：把"抽屉"与"收纳"放同一概念层。

---

## 五、7-8. Human Confidence + 二次复核

### Human Confidence（V2 字段）

```
human_confidence: HIGH | MEDIUM | LOW
review_status:    REVIEWED | NEEDS_SECOND_REVIEW | GOLD | EXCLUDED
```

- LOW → 默认禁止进入训练/规则提炼
- 看不清 → 允许 UNKNOWN + NEEDS_SECOND_REVIEW（不被迫选）

### SECOND_REVIEW_V1（60 条抽取）

| 组 | 数量 |
|---|---|
| 当前待定（人工全空） | 18 |
| taxonomy conflict | 12 |
| high-confidence wrong | 10 |
| UNKNOWN 但人工可判 | 10 |
| 随机控制样本 | 10 |
| **合计** | **60** |

- 二次复核 UI **隐藏首次人工答案与 AI 答案**（防锚定）
- 结果存 `human_annotation_v2`（不覆盖 v1）
- manifest: `SECOND_REVIEW_V1_MANIFEST.json`（seed=7）

---

## 六、11-13. 基础设施：队列/采样/覆盖

### ReviewQueueService（主动学习队列）

- reason 支持 10 种：LOW_CONFIDENCE/UNKNOWN/MULTIMODAL_CONFLICT/
  NEW_VISUAL_CLUSTER/NEW_PRODUCT/NEW_MATERIAL/NEW_FUNCTION/
  PRODUCTION_REJECTED/HIGH_VALUE_CANDIDATE/RANDOM_AUDIT
- priority 排序 + pending/reviewed/skipped 状态
- **本 Phase 仅建基础设施，未自动批量填队列**

### Sampling Policy（配置化，不硬编码）

```
40% uncertainty / 20% multimodal conflict / 15% novelty /
15% production-high-value / 10% random audit
```

### CoverageService（覆盖矩阵）

- 按 dim1 × dim2 统计（scene/product/material/function/action 组合）
- 状态阈值：EMPTY(<5) / LOW(5-20) / MEDIUM(20-50) / GOOD(≥50)（配置化）
- 实测 gaps 例：`岛台 × 客户家` 仅 1 样本 [EMPTY]

---

## 七、16-17. Service Layer + Tests

### 新增服务（`services/annotation_governance.py`）

| 服务 | 功能 |
|---|---|
| AnnotationService | taxonomy 审计 / CALIBRATION eligibility / save_v2 |
| ReviewQueueService | 队列入队/取队/标记 |
| CoverageService | 覆盖矩阵计算/持久化 |

### 二次复核 UI（`services/second_review_ui.py`）

- 隐藏首答 + AI 答案
- 语义 7 字段 + human_confidence + review_status

### Tests（8 个新测试）

| 测试 | 验证 |
|---|---|
| metric_denominator | conditional vs effective（75% vs 60%） |
| people_normalization | people 0% bug 修复 |
| confidence_reliability | bucket 表 + NOT_CALIBRATED |
| calibration_eligibility | HIGH/MEDIUM+REVIEWED/GOLD 才合格 |
| second_review_immutability | v2 不覆盖 v1 |
| review_queue | 入队/优先级/状态 |
| coverage_matrix | 分布统计 |

**pytest 结果**：80 passed / 0 failed（新增 8 个）

---

## 八、18-19. 完成条件与等待事项

### 已就绪

```
✅ Metrics 口径修正（effective_correct_rate 等）
✅ people 0% bug 查明（Metrics Bug）
✅ Taxonomy 审计（53 条 OBJECT_FUNCTION_MIX）
✅ Schema V2 设计
✅ SECOND_REVIEW_V1 抽取 60 条
✅ 二次复核 UI
✅ 基础设施（队列/采样/覆盖）
✅ 测试 80 通过
```

### 等待事项

**请完成 SECOND_REVIEW_V1 的 60 条二次复核**：
```
python -m treecut.main --second-review-ui
```

60 条完成后运行：
```
python -m treecut.main --segment-validation-report   # 生成修正后指标
python -m treecut.main --coverage-status             # 覆盖矩阵
python -m treecut.main --taxonomy-audit              # Taxonomy 审计
```

生成 `docs/PHASE2_5_VALIDATION_INTEGRITY_REPORT.md` /
`docs/ANNOTATION_TAXONOMY_AUDIT.md` /
`docs/HUMAN_LABEL_RELIABILITY_V1.md`。

**禁止进入 Phase 3。**

---

## 九、遗留问题

| 项 | 说明 |
|---|---|
| 300 条 v1 无 human_confidence | 无法判断 v1 可信度；60 条 v2 复核可校准 |
| 二次复核未完成 | 人工标签可靠度未知（等 60 条） |
| Schema V2 未落库 | 待 60 条复核后按 V2 迁移字段 |
| Sampling Policy 仅配置 | 未自动生成队列 |
| 80 测试覆盖 82%（两模块） | 全库未测 |

---

*Phase 2.5 基础设施完成，等待 SECOND_REVIEW_V1 人工复核。*
