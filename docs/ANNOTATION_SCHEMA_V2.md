# Annotation Schema V2 — 标注词典冻结文档（ANNOTATION_DICTIONARY_V2）

- **冻结日期**：2026-08-27 19:24 ｜ 仓库 `6e6198d` ｜ 迁移 `0006_annotation_schema_v2_truth`
- **性质**：正式冻结。Phase 3 起所有 human/AI/calibration/validation 标注必须记录 `dictionary_version`
- **冻结范围**：业务维度与枚举；**不修改任何历史标签**（v1/v2 表原样保留，canonical 按映射归一化）

## 1. 维度结构与枚举

### scene
| 维度 | 枚举 |
|---|---|
| scene_family | FACTORY / CUSTOMER_HOME / SHOWROOM / INSTALLATION_SITE / OTHER / UNKNOWN |
| scene_subtype | FACTORY_WORKSHOP / FACTORY_SHOWROOM / FACTORY_WAREHOUSE / FACTORY_OTHER / NOT_APPLICABLE / UNKNOWN |

- "工厂展示区" 是 FACTORY 的子类（FACTORY_SHOWROOM），**不得与 FACTORY 同层互斥**

### product
| 维度 | 枚举 |
|---|---|
| product_family | ISLAND / BAR / SIDEBOARD / DINING_TABLE / OTHER / UNKNOWN |
| product_variant | STANDARD_ISLAND / EXTENDABLE_ISLAND / FLOATING_ISLAND / FLOOR_ISLAND / NOT_APPLICABLE / OTHER / UNKNOWN |

- 岛台（family）与 伸缩岛台（variant）**分层**，不再平级

### material
`岩板 / 实木 / 奢石 / 大理石 / 肤感 / 不锈钢 / 玻璃 / 其他 / UNKNOWN`（业务中文枚举）

### component / function（强制分离）
| 维度 | 枚举 |
|---|---|
| component | DRAWER / CABINET_DOOR / TRACK_SOCKET / COUNTERTOP / SINK / APPLIANCE_SLOT / ACRYLIC_SUPPORT / OTHER / UNKNOWN / NOT_APPLICABLE |
| function | STORAGE / EXTENDABLE / POWER / DINING / OFFICE / WATER_BAR / EMBEDDED_APPLIANCE / CHILD_SAFETY / OTHER / UNKNOWN / NOT_APPLICABLE |

- **DRAWER 禁止再作为 function**（组件词归 component，功能语义归 function）

### action（分组 + 原子，支持 sequence）
| 维度 | 枚举 |
|---|---|
| action_group | STATIC / SPEAKING / EXTEND / DRAWER / CABINET / POWER_INTERACTION / WATER_INTERACTION / OTHER / UNKNOWN |
| atomic_action | STATIC_DISPLAY / PERSON_SPEAKING / PULL_OUT / RETRACT / PULL_OUT_THEN_RETRACT / RETRACT_THEN_PULL_OUT / OPEN_DRAWER / CLOSE_DRAWER / OPEN_THEN_CLOSE_DRAWER / OPEN_CABINET / CLOSE_CABINET / OPERATE_SOCKET / OPEN_SINK_COVER / OTHER / UNKNOWN / NOT_APPLICABLE |

- 组合动作（如 拉出→缩回）允许 sequence 结构（`PULL_OUT_THEN_RETRACT` 为当前原子，未来扩展不写死为无限枚举）

### shot（拆成两个维度）
| 维度 | 枚举 |
|---|---|
| shot_scale | WIDE / MEDIUM / CLOSE / CLOSE_UP / UNKNOWN |
| shot_role | PERSON_TALKING / FUNCTION_DEMO / SPACE_OVERVIEW / PRODUCT_SHOWCASE / DETAIL_SHOWCASE / CRAFT_SHOWCASE / INSTALLATION / OTHER / UNKNOWN |

- **近景（scale）与 功能演示（role）分列**，禁止同字段混用（本次 42 段 shot_type 词典重构即因此不可比）

### 其他
`people_presence`: YES / NO / UNKNOWN
`product_visibility`: UNKNOWN（v1 全为 -1.0 占位，未实际采集）
`quality`: REAL（v1 quality_score）

## 2. 词典映射（v1/v2 历史中文 → V2 枚举，审计性质）

| 旧值 | family/variant 或 (component, function) | 说明 |
|---|---|---|
| 岛台 | ISLAND / UNKNOWN | v1 粗词无法区分变体 |
| 伸缩岛台 | ISLAND / EXTENDABLE_ISLAND | |
| 悬浮岛台 / 落地岛台 | ISLAND / FLOATING_ISLAND / FLOOR_ISLAND | |
| 吧台 / 餐边柜 / 茶桌 | BAR / SIDEBOARD / DINING_TABLE | |
| 抽屉 / 抽屉收纳 | (DRAWER, STORAGE) | 组件词迁移 |
| 收纳 | (NOT_APPLICABLE, STORAGE) | |
| 伸缩 | (NOT_APPLICABLE, EXTENDABLE) | |
| 轨道插座 / 用电 | (TRACK_SOCKET, POWER) / (UNKNOWN, POWER) | |
| 水槽 / 水吧 | (SINK, WATER_BAR) / (UNKNOWN, WATER_BAR) | |
| 嵌入电器 / 隐藏电器 | (APPLIANCE_SLOT, EMBEDDED_APPLIANCE) | |
| 讲解/演示、人物讲解 | (SPEAKING, PERSON_SPEAKING) | 同义归一 |
| 拉出/展开、拉出、展开 | (EXTEND, PULL_OUT) | v1 粗类（审计假设） |
| 缩回、收纳/关闭、收起 | (EXTEND, RETRACT) | v1 粗类（审计假设） |
| 打开抽屉 / 关闭抽屉 / 打开+关闭抽屉 | (DRAWER, OPEN_DRAWER / CLOSE_DRAWER / OPEN_THEN_CLOSE_DRAWER) | |
| 打开柜门 | (CABINET, OPEN_CABINET) | |
| 静态展示 | (STATIC, STATIC_DISPLAY) | |
| 全景/中景/近景/特写 | shot_scale = WIDE/MEDIUM/CLOSE/CLOSE_UP | 仅 scale |
| 人物讲解/功能演示/空间扫镜/其他-产品扫镜 | shot_role = PERSON_TALKING/FUNCTION_DEMO/SPACE_OVERVIEW/PRODUCT_SHOWCASE | 仅 role |

> 映射属审计假设（CANDIDATE）：v1 粗类"拉出/展开"与 v2 原子"打开抽屉"在 action_group 层不可可靠对齐 → 相应 34 段标记 NEEDS_ADJUDICATION，等 V3 裁决，**不强行归并**。

## 3. 版本与治理要求

1. 所有 future 标注（human/AI/calibration/validation）必须记录 `dictionary_version = ANNOTATION_DICTIONARY_V2`
2. 禁止无版本混用两套词典（v1/v2 漂移是 Phase 2.5 发现的根因）
3. UI 审核必选 human_confidence（HIGH/MEDIUM/LOW）与 review_status；空提交自动 NEEDS_SECOND_REVIEW；UNPLAYABLE → EXCLUDED
4. AI 置信度命名：**HEURISTIC_CONFIDENCE_V1 / EVIDENCE_SCORE_V1**（非概率，禁止"85%概率"表述）；Phase 3 模型概率另建 model_confidence 独立校准
5. Schema 变更必须走 MigrationManager（下个版本 0007 起），遵守备份/测试/文档/回滚纪律
