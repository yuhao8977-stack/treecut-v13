# Annotation Taxonomy Audit — 标注本体审计（Phase 2.5）

- **日期**：2026-08-27 18:55 ｜ 范围：360 段（v1 300 + v2 60）truth 表；**只读审计，未修改任何标签**
- **审计方法**：`AnnotationService.taxonomy_audit` 扩展 + 词典漂移对比；改进建议均标注 OBSERVATION / CANDIDATE

## 1. 跨层混用

| 类型 | 值 | truth 表计数 | 建议（CANDIDATE） |
|---|---|---|---|
| OBJECT_FUNCTION_MIX（function 字段出现组件/物体） | 抽屉 | 30 | Schema V2 拆 `component` 列（抽屉=组件，收纳=功能） |
| OBJECT_FUNCTION_MIX | 水槽 | 1 | 同上 |
| ACTION_FUNCTION_MIX（action 字段出现功能词） | 无 | 0 | v2 已原子化，无此问题 |

## 2. 词典漂移（v1 vs v2）

### scene
- v1：工厂 279 / 展厅 2 / 客户家 1
- v2：工厂 2 / 工厂展示区 56 / 空 2
- 结论：**"工厂展示区"是"工厂"的子场景**，v2 引入子类 → scene 需层级化（OBSERVATION）

### action（粒度重构）
- v1：4 个粗类（讲解/演示、拉出/展开、收纳/关闭、其他）
- v2：11 个原子描述（人物讲解、静态展示、打开抽屉、打开+关闭抽屉、打开柜门、拉出、拉出+缩回、缩回+拉出、关闭抽屉、打开抽屉+关闭抽屉、打开水槽盖拿起水龙头）
- 结论：**v2 原子动作是 Schema V2 的正确粒度**；v1 粗类应映射为"动作组"而非独立标签（OBSERVATION → CANDIDATE）

### shot_type（语义重构）
- v1：景别（近景/中景/特写）
- v2：镜头内容（人物讲解/功能演示/空间扫镜/其他-产品扫镜）
- 结论：**两轮不可比**；Schema V2 需决策 shot_type 究竟表达"景别"还是"镜头功能"，二者应分列（OBSERVATION）

### function
- v1：其他 111 / 抽屉 53 / 伸缩 44 / 收纳 41 / 轨道插座 31 / 隐藏电器 2
- v2：其他 19 / 收纳 23 / 伸缩 4 / 抽屉收纳 3 / 轨道插座 3 / 用电 3 / 嵌入电器 1 / 未展示功能 1 / 水槽 1
- 结论：v2 把"抽屉"细化为"收纳/抽屉收纳"，组件与功能分离趋势正确

## 3. 产品族 / 变体

truth 表 product 分布：岛台 170 / 伸缩岛台 127 / 吧台 1 / 空 2。
- **岛台 vs 伸缩岛台 是"族-变体"关系**（127 条子类，不可当两个平级产品）
- CANDIDATE：Schema V2 拆 `product_family`（岛台/吧台）+ `product_variant`（伸缩岛台/悬浮岛台/标准岛台）

## 4. UNKNOWN 分析

| 来源 | material | shot_type | action |
|---|---|---|---|
| AI（300 段 candidate） | 98.7% | 100.0% | 91.3% |
| human truth（360 段） | 基本 0%（仅 2 条坏段） | 基本 0% | 基本 0% |

结论：**UNKNOWN 是 AI 侧问题，不是标注侧问题**；人工真值完整可作校准。AI 的 UNKNOWN 主要源于"不敢答"（1484/1580 UNKNOWN 格人工可判）。

## 5. Schema V2 建议（CANDIDATE，未执行）

1. `product_family` / `product_variant` 分离（迁移 0006+）
2. `component` 新列承接 function 中的组件词（抽屉/水槽/柜门/台面/插座/轨道）
3. `action` 原子化枚举（采用 v2 的 11 原子 + 组合语义）
4. `scene` 层级化（工厂 ⊃ 工厂展示区；展厅；客户家）
5. `shot_type` 决策：景别 vs 镜头功能分列
6. 全字段支持 UNKNOWN / OTHER / NOT_APPLICABLE
7. 标注界面强制：v2 空提交校验 + human_confidence 必选
8. 词典版本化：每条标注记录 `dictionary_version`，禁止两套词典并存（OBSERVATION：本次漂移根因）

> 本审计不改历史标签；Schema V2 迁移属后续阶段，需走迁移纪律（备份/测试/文档/git/回滚）。
