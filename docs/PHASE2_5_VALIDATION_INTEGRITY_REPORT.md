# Phase 2.5 Validation Integrity Finalization — 验证完整性终审报告

- **日期**：2026-08-27 18:55 ｜ **仓库**：main @ `7ccc18f`
- **数据根**：`E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1`
- **范围**：VALIDATION_SNAPSHOT_V1（300 段，seed 42，冻结）+ SECOND_REVIEW_V1（60 条二次盲复核，seed 7）
- **性质**：本报告只读重算；**未修改任何规则/模型/知识/标签**；所有改进建议均标注 OBSERVATION / CANDIDATE
- **判定**：见 §9（Phase 2.5 通过条件）；Phase 3 未启动

## 1. 执行摘要

| 项 | 结论 |
|---|---|
| 二次复核完成度 | 60/60 落库（`human_annotation_v2`），0 缺漏；其中 42 条 v1 已标注（双盲交叉可比）、18 条 v1 未标注（v2 补齐初标） |
| 人工标签可靠性 | **6 个语义字段（除 shot_type）归一化一致率 86.9%（hier 89.3%）**；material/product/scene/people 高可靠；action 偏弱（61.9%）；shot_type 两轮词典重构、不可比 |
| AI 有效正确率 | pooled **9.0%**（AI 大量 UNKNOWN 所致）；conditional 34.2% |
| people_presence 0% bug | 确认 V1 报告 SQL 别名错误所致；已修复并重算（conditional 23.0% / effective 24.6%） |
| Confidence 校准 | **NOT_CALIBRATED_SCORE**：0.8-0.9 桶 38.5% 正确率 < 0.0-0.5 桶 29.3%？非单调 → 原始分数不可当概率 |
| 可安全学习的数据 | **CALIBRATION_CORPUS_V1 = 332 段**（v1 274 + v2 58；排除 28 条） |
| 覆盖矩阵 | 106 个维度组合：GOOD 35 / MEDIUM 15 / LOW 56 / EMPTY 0 |
| Phase 3 就绪度 | **有条件就绪**：先统一 Schema V2 词典（消除 v1/v2 词典漂移），再进入视觉/动作认知 |

## 2. 数据基线

- 快照：`{"snapshot_id": "VALIDATION_SNAPSHOT_V1", "git_commit": "5c99564", "model_name": "rules+clip-v1", "model_version": "1.0", "algorithm_version": "segment-cognition-v1", "sample_count": 300, "created_at": 1787824316.4176238, "notes": "Phase2 冻结基线：AI先答题后人工审核。永久只读，禁止覆盖。后续重预测须新建snapshot。"}`
- 唯一段 360 = v1 人工 300 + v2 复核 60（60 全在 300 内）；v1 未标注 18 条（§4.2）
- boundary：300/300 已审；`usable_as_edit_unit` = 1 共 275 条、0 共 9 条、-1 共 16 条
- 真值缺口 2 条（见 §4.3），均已从 CALIBRATION 排除

## 3. V1 指标重算（AI vs 第一轮人工，300 段）—— 回答 Q1/Q2/Q3

定义：`conditional_accuracy` = AI 非 UNKNOWN 回答中的正确率；`effective_correct_rate` = 正确覆盖 / 人工真值总数（**真实指标**）。

| 字段 | 人工有效 n | AI 回答 n | AI UNKNOWN n | 正确 n | conditional % | **effective %** | UNKNOWN 但人工可判 |
|---|---|---|---|---|---|---|---|
| scene | 282 | 25 | 275 | 14 | 56.0 | **5.0** | 259 |
| product | 282 | 114 | 186 | 48 | 42.1 | **17.0** | 176 |
| material | 282 | 4 | 296 | 0 | 0.0 | **0.0** | 279 |
| function | 282 | 51 | 249 | 29 | 56.9 | **10.3** | 232 |
| action | 282 | 26 | 274 | 18 | 69.2 | **6.4** | 256 |
| shot_type | 282 | 0 | 300 | 0 | 0.0 | **0.0** | 282 |
| people_presence | 281 | 300 | 0 | 69 | 23.0 | **24.6** | 0 |

**总体**：pooled effective **9.0%**（1973 有效格中仅正确 178）；pooled conditional 34.2%；AI 共 1580 格 UNKNOWN，其中 1484 格人工可判 → **AI 的主要问题是"不敢答"而非"答错"**。

### 3.1 Q2 — people_presence 0% bug 结论
确认根因：V1 报告 SQL 别名 `a_people` 与代码查找 `a_people_presence` 不一致 → ai_answered 恒 0 → 0%。
已修复（`segment_validation_report.py` 映射 `people_presence → a_people`，测试 `test_people_normalization` 覆盖）。重算：**conditional 23.0% / effective 24.6%**（300 回答，69 正确，281 人工有效）。people 是 AI 覆盖最好但正确率偏低的字段——符合"AI 永远答 yes/no、不答 UNKNOWN"的行为画像。

### 3.2 Q3 — Confidence 统计正确性
原始 `CONFIDENCE_SCORE_UNCALIBRATED` 分桶（跨 7 字段 AI 回答）：

| 桶 | 回答 n | 正确 n | conditional % |
|---|---|---|---|
| 0.0-0.5 | 147 | 43 | 29.3 |
| 0.5-0.6 | 4 | 0 | 0.0 |
| 0.7-0.8 | 29 | 4 | 13.8 |
| 0.8-0.9 | 340 | 131 | 38.5 |

**结论**：正确率与置信度不单调（0.0-0.5 桶 29.3% 反而高于 0.7-0.8 桶 13.8%），且 0.8-0.9 桶占 340/520 回答、其余桶样本极小 → **该分数不可校准、不可当概率**（`NOT_CALIBRATED_SCORE` 判定成立）。置信度仅在"相对排序"上有弱参考价值。CANDIDATE：Phase 3 前需温度缩放 + 校准集重标。

## 4. 第一轮 vs 第二轮人工一致率 —— 回答 Q4/Q5

### 4.1 词典漂移（必须先于一致率理解的事实）
SECOND_REVIEW_V1 界面使用了**不同版本标签词典**：

| 字段 | v1 词典（粗粒度） | v2 词典（原子/子场景） |
|---|---|---|
| scene | 工厂 279 / 展厅 2 / 客户家 1 | 工厂 2 / **工厂展示区 56** / 空 2 |
| action | 讲解/演示 116 / 拉出/展开 61 / 收纳/关闭 31 / 其他 74 | **人物讲解 21 / 静态展示 15 / 打开抽屉 7 / 打开+关闭抽屉 6 / 关闭抽屉 2 / 打开柜门 2 / 拉出 1 / 拉出+缩回 1 / 缩回+拉出 1 / 打开抽屉+关闭抽屉 1 / 打开水槽盖拿起水龙头 1** |
| shot_type | 近景/中景/特写等（**景别**） | 人物讲解/功能演示/空间扫镜/其他-产品扫镜（**镜头内容**）→ 语义重构 |
| function | 抽屉 53 / 伸缩 44 / 收纳 41 / 轨道插座 31 / 其他 111 | 收纳 23 / 其他 19 / 伸缩 4 / 抽屉收纳 3 / 轨道插座 3 / 用电 3 / 嵌入电器 1 / 未展示功能 1 / 水槽 1 |

因此**字符串精确一致率被系统性低估**。审计采用显式归一化映射（`DICT_V1_TO_V2_MEMBERS`，标注 **CANDIDATE**，不改任何标签）后给出三层一致率。

### 4.2 Q4 — 两层一致率（42 条可比子集；18 条 v1 未标注段由 v2 补齐，另计）

| 字段 | raw 精确一致 % | 归一化一致 % | 层级兼容 % | 说明 |
|---|---|---|---|---|
| scene | 0.0 | 95.2 | 95.2 | 工厂展示区→工厂 归一化后 40/42；2 条真分歧 |
| product | 83.3 | 83.3 | 97.6 | 岛台↔伸缩岛台 父-子兼容 41/42；1 条真分歧 |
| material | 97.6 | 97.6 | 97.6 | 41/42 一致；最可靠字段 |
| function | 35.7 | 90.5 | 90.5 | v1 组件词"抽屉"→v2"收纳" 归一化后 38/42；4 条真分歧 |
| action | 0.0 | 61.9 | 61.9 | v2 原子动作归 v1 粗类后 26/42；16 条真分歧 — 动作识别是弱项 |
| shot_type | 4.8 | 4.8 | 4.8 | v1 景别 vs v2 镜头内容，词典重构，不可比 |
| people_presence | 92.9 | 92.9 | 92.9 | 39/42；3 条 yes/no 真分歧 |

**Pooled（42 段 × 7 字段 = 294 格）**：
- raw 精确一致：**44.9%**
- 归一化一致：**75.2%**
- 层级兼容：**77.2%**
- 真分歧格子：**67**（action 16 / shot_type 40 / function 4 / people 3 / scene 2 / product 1 / material 1）

**去 shot_type（词典重构不可比）后 6 字段（252 格）**：raw 51.6% / 归一化 **86.9%** / 层级 **89.3%**。
→ **人工标签可靠性主口径：6 语义字段归一化一致率 86.9%**；真实分歧集中在 action（16）与 people（3），其余字段近乎一致。

### 4.3 18 条 v1 未标注段（SECOND_REVIEW_V1 "18 pending"）
v1 人工审核跳过的 18 段（7 字段全空）已由 v2 盲复核补齐初标。其中 **2 条 v2 空提交**：
- `b3757ee9…`：v2 备注"视频无法播放"（quality_score=0.0，疑似坏段），双轮均无法标注
- `fc404d7b…`：v2 空提交无备注；v1 有有效标注（工厂/岛台/其他）→ truth 回退 v1

真值缺口 2 条：`b3757ee9…`、`e78ac11c…`（仅 people 缺失）。OBSERVATION：v2 审核表单未做必填校验，允许空提交 → CANDIDATE：表单必填 + 空提交自动置 NEEDS_SECOND_REVIEW。

## 5. Human Label Reliability — 回答 Q5（详见 HUMAN_LABEL_RELIABILITY_V1.md）

- **最可靠**：material（97.6%）、product（层级 97.6%）、people_presence（92.9%）、scene（归一化 95.2%）
- **一般**：function（归一化 90.5%）
- **偏弱**：action（归一化 61.9%）→ 动作语义是行业难点，也解释了 AI action 91.3% UNKNOWN
- **不可比**：shot_type（词典重构）
- v2 全部 `MEDIUM/REVIEWED` → **无法按 human_confidence/status 分层**（OBSERVATION：置信度字段未实际使用，需在 UI 中强制选择并校准口径）

## 6. Annotation Taxonomy 审计（360 段 truth 表）—— 回答 Q6（详见 ANNOTATION_TAXONOMY_AUDIT.md）

| 问题 | 数量/比例 | 处置（仅建议，未执行） |
|---|---|---|
| OBJECT_FUNCTION_MIX：function=组件词 | 抽屉 30、水槽 1 | Schema V2 拆 component 列 |
| product 族/变体混用 | 岛台 170 / 伸缩岛台 127 / 吧台 1 | product_family + product_variant |
| scene 子场景 | 工厂 240 / 工厂展示区 56 | scene 层级化 |
| v1/v2 词典漂移 | scene/action/shot_type 全量 | Schema V2 统一枚举，禁止两套词典并存 |
| AI UNKNOWN 泛滥 | material 98.7% / shot_type 100% / action 91.3% | Phase 3 视觉认知 + 提示词工程 |
| human truth 完整性 | v2 补齐后仅 2 条坏段 | 坏段清理流程（OBSERVATION） |

## 7. CALIBRATION_CORPUS_V1 —— 回答 Q7

资格规则：v1 = 7 字段完整 + boundary `usable==1`（默认 MEDIUM/REVIEWED）；v2 = 7 字段完整 + HIGH/MEDIUM + REVIEWED/GOLD。

- **300 段中合格 274 条**；+ v2 合格 58 条 → **CALIBRATION_CORPUS_V1 共 332 段**
- 排除 28 条：
  - v1 字段缺失:['scene', 'product', 'material', 'function', 'action', 'shot_type', 'people_presence']: 18 条
  - boundary usable!=1: 7 条
  - v1 字段缺失:['people_presence']: 1 条
  - v2 空提交:视频无法播放: 1 条
  - v2 空提交:无备注: 1 条
- 证据分层：双盲复核 42 段 ｜ v2 补齐 18 段 ｜ 单次审核 272 段
- 已输出 `CALIBRATION_CORPUS_V1_MANIFEST.json`（含逐段 segment_id 清单）
- **使用限制**：CALIBRATION_CORPUS_V1 是 VALIDATION_SNAPSHOT_V1 的逻辑子集；一旦用于校准/微调，这些段不再作为独立验证集；不得回写快照。

## 8. COVERAGE_MATRIX_V1 —— 回答 Q8（详见 COVERAGE_MATRIX_V1.json）

在 CALIBRATION_CORPUS_V1（332 段）上计算 8 个维度组合 × 值对：106 个组合 = GOOD 35 / MEDIUM 15 / LOW 56 / EMPTY 0（阈值 EMPTY<5 / LOW<20 / MEDIUM<50 / GOOD>=50）。

**Top 10 覆盖缺口（LOW，样本 1）**：
  1. `material=岩板 × function=未展示功能`（1）
  2. `material=岩板 × function=嵌入电器`（1）
  3. `material=岩板 × function=水槽`（1）
  4. `material=实木 × function=抽屉`（1）
  5. `product=岛台 × material=实木`（1）
  6. `product=吧台 × material=岩板`（1）
  7. `product=岛台 × function=未展示功能`（1）
  8. `product=岛台 × function=嵌入电器`（1）
  9. `product=岛台 × function=水槽`（1）
  10. `product=伸缩岛台 × function=抽屉`（1）

**Top 10 覆盖强度（GOOD）**：
  1. `scene=工厂 × material=岩板`（232）
  2. `product=岛台 × material=岩板`（165）
  3. `scene=工厂 × product=岛台`（132）
  4. `product=伸缩岛台 × material=岩板`（124）
  5. `material=岩板 × function=其他`（115）
  6. `scene=工厂 × product=伸缩岛台`（100）
  7. `scene=工厂 × action=讲解/演示`（99）
  8. `scene=工厂 × shot_type=全景`（68）
  9. `scene=工厂 × action=其他`（61）
  10. `scene=工厂 × shot_type=近景`（59）

**解读**：数据呈"长尾稀疏"——岩板×岛台×工厂 是主干（单点 ≥100），但**材质（实木/石英石）、功能（水槽/用电/嵌入电器/抽屉）、非工厂场景**均样本 ≤1，AI 从主干学不到多样性；这也与 material 98.7% UNKNOWN 互为因果。

## 9. 结论：Phase 2.5 判定与 Phase 3 优先级 —— 回答 Q9/Q10

**Phase 2.5 通过条件评估**（三项均达成）：
1. ✅ 指标可信：V1 指标重算口径正确（effective_correct_rate 为主），people bug 修复有测试，confidence 判定 NOT_CALIBRATED
2. ✅ 人工标签可靠：6 语义字段归一化一致率 86.9%，可作校准真值（action 需标注弱项认知）
3. ✅ 安全可学数据：CALIBRATION_CORPUS_V1 332 段（含排除清单与证据分层），快照只读不回写

**Phase 3 优先级（CANDIDATE，未执行）**：
1. **Schema V2 词典统一**（前置）：合并 v1/v2 词典，product_family/variant、component、原子 action、scene 层级 —— 否则后续训练沿用漂移词典
2. **action 原子动作认知**：AI UNKNOWN 91.3% + 人工一致率 61.9% 双弱；v2 已演示 11 种原子动作
3. **material 视觉识别**：UNKNOWN 98.7%，覆盖缺口最大
4. **伸缩岛台变体建模**：127 条子类（52 条级联差异），product_family 分离
5. **function 组件识别**：抽屉等组件词 30 条迁 component 列
6. **scene 子场景**：工厂展示区 56 条层级化
7. **坏段/表单治理**：2 条坏段清理流程 + v2 表单必填校验

**Phase 3 就绪度**：**有条件就绪**（见下）。就绪前置项：
- 完成 Schema V2 枚举定义并迁移（迁移 0006 起，遵循备份/测试/文档/回滚纪律）
- 修复 v2 空提交校验；明确 human_confidence 实际使用
- CALIBRATION_CORPUS_V1 学习计划（先学 42 条双盲 + 274 单审，再决定是否追加）

> 本报告所有数字可由 `scripts/phase25_finalize_analyze.py` 复现；改进建议均为 OBSERVATION/CANDIDATE，未改动任何规则/模型/知识/标签。Phase 3 未启动。
