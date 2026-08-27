# Phase 2.5.1 — Canonical Human Truth & Schema V2 Freeze 报告

- **日期**：2026-08-27 19:24 ｜ 仓库 `6e6198d`（main）
- **判定依据**：架构监工终审 `PASS WITH DATA-FIX REQUIRED` → 本阶段只做数据治理与 Schema 冻结
- **禁止项确认**：未修改 AI 认知规则 / CLIP / EvidenceBuilder / 未自动学习 / 未更新 knowledge / 未训练模型 / 未重跑 VALIDATION_SNAPSHOT_V1 / **Phase 3 未启动**

## 1. 核心修复：332 口径审计（回答 Q1/Q2）

**旧口径（V1 manifest）**：`v1 合格 274 + v2 合格 58 = 332` 被称作"332 段"——**错误**。
60 条 SECOND_REVIEW_V1 全部来自原始 300 segment，332 是 **annotation records（标注记录）**，不是独立 Segment。

**唯一口径（V2 manifest）**：

| 口径 | 数值 | 说明 |
|---|---|---|
| v1 记录 | 300 | human_annotations 全部 |
| v2 记录 | 60 | human_annotation_v2 全部 |
| 合格记录（旧规则 字段完整+boundary） | v1 274 + v2 41 = **315** | 旧 332 中 v2 58 有 17 条 boundary 不可用 → 315 |
| **唯一 segment** | **300** | COUNT(DISTINCT segment_id) = 300 |
| 旧 332 记录去重后唯一段 | **291** | 274 + 17（v2-only 补齐段） |
| **可训练唯一段** | **240** | canonical 合格 ∩ boundary usable |
| 需人工第三次裁决 | 34 | NEEDS_ADJUDICATION |
| 排除 | 26 | 2 无真值 + 24 boundary 不可用 |

**回答 Q1**：332 条记录对应 **291 个唯一 segment**（332 记录 − 41 条 v1/v2 指向同一段的重复记录）；其中 **51 个段不可训练**（34 冲突 + 17 boundary 不可用）。
**回答 Q2**：重建后真正可训练唯一 segment = **240**（300 − 34 − 26）。

## 2. Canonical Human Truth 建立（回答 Q4）

迁移 `0006_annotation_schema_v2_truth`（备份 `pre_0006_20260827_191730.db`，integrity ok）新建：
- `canonical_human_truth`：**每 segment_id 恰好 1 行**，Schema V2 字段 + 证据元数据
- `annotation_dictionary`：ANNOTATION_DICTIONARY_V2 冻结快照

**Truth Resolution Policy 执行结果**：

| truth_source | 段数 | 含义 |
|---|---|---|
| SINGLE_REVIEW | 257 | 仅一次有效人工审核（含 16 条 v2 补齐初标） |
| DOUBLE_REVIEW_AGREED | 0 | 两次审核 Schema V2 口径完全一致 |
| DOUBLE_REVIEW_HIERARCHICAL | 7 | 族/变体层级补全（如 v1 岛台 + v2 伸缩岛台 → EXTENDABLE_ISLAND） |
| NEEDS_ADJUDICATION | 34 | 字段级真冲突 → 不进入训练 |
| EXCLUDED | 2 | `b3757ee9…`（视频无法播放）、`e78ac11c…`（people 缺失） |

**解析原则**：不简单让 v2 覆盖 v1；按 一致性 → 层级兼容 → 具体性 决定；无法可靠决定 → NEEDS_ADJUDICATION。
**历史保留**：v1/v2 表原样不动；canonical 只增不改。

## 3. 需要第三次裁决的 34 段（回答 Q5）

**34 段 NEEDS_ADJUDICATION**（42 条双盲可比段中，除 7 条层级兼容、1 条单审外全部冲突）：

冲突构成（v1 vs v2 原始标签）：
- **action 100% 不同（34/34）**：v1 粗类（拉出/展开、讲解/演示、其他）vs v2 原子动作（打开抽屉、静态展示、关闭抽屉…）→ 主因，属词典粒度无法可靠对齐
- function 71% 不同（24/34）：v1 组件词（抽屉）vs v2 功能词（收纳）等
- scene/other 零星：工厂展示区 vs 工厂 等（部分已在 Schema V2 拆分后自动消解）

清单（34 段）：
  - `0083d4f77bc64b18…`
  - `09f514b80e394bda…`
  - `1c158078417e41cf…`
  - `2097188911a34164…`
  - `217f7f6338ae479a…`
  - `3dfe55e5021f4e15…`
  - `4379f2ae96314598…`
  - `49e0fded71aa4b35…`
  - `4c9c09937db34cda…`
  - `55d1f1bead294920…`
  - `5689b90934f6429e…`
  - `5dd6892a20f84bb6…`
  - `5e8708a3b2874b12…`
  - `5fe361e76bb14a50…`
  - `6405383043ee4080…`
  - `7269064d8a394437…`
  - `7426f81dd3c7401a…`
  - `8cd9ae96dc8c4cf6…`
  - `a077c5a01a8645ce…`
  - `a3c737486ba645d6…`
  - `a60b0d13fa074204…`
  - `a654170c9ab246d4…`
  - `a707191d89864373…`
  - `b7cb2548e0d74b19…`
  - `be4319496d344c45…`
  - `bf686b31816e47b6…`
  - `c37c6f3f0e784b8b…`
  - `c96c0ae714074f6b…`
  - `ced9eba9a20e4b78…`
  - `d28d49c2eba548f6…`
  - `e4d1f491ef304da8…`
  - `ec651e9e628a4a43…`
  - `f66be8aafd40470b…`
  - `fdfabdd7c04e4d9c…`

处置（CANDIDATE，未执行）：Phase 3 前或期间以 Schema V2 字典 + 视频回放做第三次裁决（V3），裁决后按 DOUBLE_REVIEW_AGREED 语义回填 canonical。

## 4. CALIBRATION_CORPUS_V1_MANIFEST_V2（唯一口径）

- 训练单位 = **1 segment_id + 1 canonical_human_truth**，共 **240** 条
- 证据分层：单审 233 + 双审层级 7 + 双审一致 0
- 已写入 `CALIBRATION_CORPUS_V1_MANIFEST_V2.json`（data root）
- **禁止**：同一 segment 因审核两次被训练两次；NEEDS_ADJUDICATION/EXCLUDED 段不进训练

## 5. COVERAGE_MATRIX_V2（回答 Q3）

**旧 V1 Coverage 审计结论**：
- 旧组合计数**已按 segment set 去重**（291 段），未因 v1+v2 双计放大（组合级对比膨胀 = 0）
- 但旧 291 段中混入 **51 个不可训练段**（34 冲突 + 17 boundary 不可用）→ GOOD 覆盖虚高
- 旧状态：GOOD 35 / MEDIUM 15 / LOW 56（106 组合，中文维度）
- 旧 `COVERAGE_MATRIX_V1.json` 标记 **DEPRECATED_FOR_DOUBLE_COUNT_RISK**（未删除）

**新 V2 Coverage（canonical_human_truth 唯一 segment（eligible 240，boundary usable））**：
- 34 组合 = GOOD 21 / MEDIUM 0 / LOW 13 / EMPTY 0
- **Top 强度**：ISLAND×岩板=238; FACTORY×ISLAND=237; FACTORY×岩板=237; FACTORY×SPEAKING=105; ISLAND×SPEAKING=104; 岩板×OTHER=100
- **Top 缺口**：实木×STORAGE=1; BAR×岩板=1; ISLAND×实木=1; BAR×OTHER=1; BAR×SPEAKING=1; FACTORY×BAR=1
- 与 V1 对比（人口级）：332 记录 → 291 段 → **240 可训练段**（reduced 51）

**回答 Q3**：旧 Coverage **组合计数未被重复审核记录放大**（脚本已 set 去重），但**人口与资格错误**——混入 51 个不可训练段导致 GOOD 虚高；V2 已按 canonical+240 唯一段重建，作为 Phase 3 正式采样依据。

## 6. Annotation Schema V2 冻结（回答 Q6）

详见 `ANNOTATION_SCHEMA_V2.md`。要点：
- `scene_family/scene_subtype`（FACTORY ⊃ FACTORY_SHOWROOM…）
- `product_family/product_variant`（ISLAND ⊃ EXTENDABLE_ISLAND…）
- `component`（DRAWER/CABINET_DOOR/TRACK_SOCKET/COUNTERTOP/SINK/APPLIANCE_SLOT/ACRYLIC_SUPPORT…）
- `function`（STORAGE/EXTENDABLE/POWER/DINING/OFFICE/WATER_BAR/EMBEDDED_APPLIANCE/CHILD_SAFETY…）—— **DRAWER 不再作为 function**
- `action_group`（STATIC/SPEAKING/EXTEND/DRAWER/CABINET/POWER_INTERACTION/WATER_INTERACTION/OTHER/UNKNOWN）+ `atomic_action`（16 项，组合动作允许 sequence）
- `shot_scale`（WIDE/MEDIUM/CLOSE/CLOSE_UP）+ `shot_role`（PERSON_TALKING/FUNCTION_DEMO/SPACE_OVERVIEW/PRODUCT_SHOWCASE/DETAIL_SHOWCASE/CRAFT_SHOWCASE/INSTALLATION/OTHER/UNKNOWN）—— **近景 与 功能演示 分列**
- `people_presence`、`product_visibility`、`quality`
- 全字段支持 UNKNOWN / NOT_APPLICABLE；**ANNOTATION_DICTIONARY_V2** 版本号已写入 canonical 与字典表

## 7. 治理修复（14/15/13 项）

| 项 | 状态 | 说明 |
|---|---|---|
| Human Confidence UI | ✅ | `human_confidence`/`review_status` 无默认值，保存前必选（`validate_submission`）；仅对未来审核生效，不重审现有 60 条 |
| 空提交治理 | ✅ | 关键字段全空禁止 REVIEWED/GOLD → 自动 NEEDS_SECOND_REVIEW；EXCLUDED 仅允许 + comment 含 UNPLAYABLE/无法播放 |
| Confidence 命名 | ✅ | AI 分数正式标记 **HEURISTIC_CONFIDENCE_V1 / EVIDENCE_SCORE_V1**（非概率）；不做 temperature scaling；Phase 3 模型概率另建 model_confidence 独立校准 |

## 8. 七问总结（回答 Q7）

1. **原 332 多少 unique segment？** → 291（332 记录含 41 条段级重复；其中 51 不可训练）
2. **真正可训练 unique segment？** → **240**
3. **旧 Coverage 是否重复计数？** → 组合计数未双计放大，但混入 51 不可训练段致 GOOD 虚高；已重建 V2
4. **Canonical Truth 如何解决双审？** → 段级唯一化 + 五类解析（§2），v1/v2 历史保留
5. **多少段需第三次裁决？** → **34**（action 粗类↔原子为主因，34/34 action 不同）
6. **ANNOTATION_DICTIONARY_V2 枚举？** → §6 + ANNOTATION_SCHEMA_V2.md
7. **Phase 3 前置满足？** → **满足**（数据口径修正 + Schema V2 冻结 + 表单治理 + 93 测试全过）；Phase 3 未启动，等待架构监工验收

## 9. 结论

- Phase 2.5.1 数据治理完成：唯一真值（canonical_human_truth 300 行）已落库；240 训练单位 manifest V2 已交付；覆盖矩阵 V2 已重建
- 冻结完成：ANNOTATION_DICTIONARY_V2（含映射规则与枚举）
- 未触碰：AI 规则 / CLIP / EvidenceBuilder / 知识库 / 模型训练 / VALIDATION_SNAPSHOT_V1
- **下一步：等待架构监工验收；验收通过后才进入 Phase 3（视觉/动作/镜头认知 + FRESH_HOLDOUT_V1 30 条未见样本）**
