# -*- coding: utf-8 -*-
"""Phase 2.5.1 — 生成交付报告（docs/ + 桌面）。"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
REPO = r"C:\Users\admin\github\treecut-v13"
DOCS = os.path.join(REPO, "docs")

commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True, encoding="utf-8").stdout.strip()
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

m = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V1_MANIFEST_V2.json"), encoding="utf-8"))
cv = json.load(open(os.path.join(DATA_ROOT, "COVERAGE_MATRIX_V2.json"), encoding="utf-8"))
cnt = m["counts"]
ev = m["evidence"]

na_segs = m["needs_adjudication_segments"]
excl_segs = m["excluded_segments"]
boundary_segs = m.get("boundary_blocked_segments", [])

R = []
R.append(f"""# Phase 2.5.1 — Canonical Human Truth & Schema V2 Freeze 报告

- **日期**：{NOW} ｜ 仓库 `{commit}`（main）
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
| 合格记录（旧规则 字段完整+boundary） | v1 {cnt['annotation_records']['v1_eligible_records_old_rule']} + v2 {cnt['annotation_records']['v2_eligible_records_old_rule']} = **{cnt['annotation_records']['combined_eligible_records_old_rule']}** | 旧 332 中 v2 58 有 17 条 boundary 不可用 → 315 |
| **唯一 segment** | **{cnt['unique_segments']}** | COUNT(DISTINCT segment_id) = 300 |
| 旧 332 记录去重后唯一段 | **291** | 274 + 17（v2-only 补齐段） |
| **可训练唯一段** | **{cnt['eligible_unique_segments']}** | canonical 合格 ∩ boundary usable |
| 需人工第三次裁决 | {cnt['needs_review_unique_segments']} | NEEDS_ADJUDICATION |
| 排除 | {cnt['excluded_unique_segments']} | 2 无真值 + 24 boundary 不可用 |

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
| DOUBLE_REVIEW_AGREED | {ev['double_review_agreed']} | 两次审核 Schema V2 口径完全一致 |
| DOUBLE_REVIEW_HIERARCHICAL | {ev['double_review_hierarchical']} | 族/变体层级补全（如 v1 岛台 + v2 伸缩岛台 → EXTENDABLE_ISLAND） |
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
""".rstrip() + "\n" + "\n".join(f"  - `{s[:16]}…`" for s in na_segs) + f"""

处置（CANDIDATE，未执行）：Phase 3 前或期间以 Schema V2 字典 + 视频回放做第三次裁决（V3），裁决后按 DOUBLE_REVIEW_AGREED 语义回填 canonical。

## 4. CALIBRATION_CORPUS_V1_MANIFEST_V2（唯一口径）

- 训练单位 = **1 segment_id + 1 canonical_human_truth**，共 **{cnt['eligible_unique_segments']}** 条
- 证据分层：单审 {ev['single_review']} + 双审层级 {ev['double_review_hierarchical']} + 双审一致 {ev['double_review_agreed']}
- 已写入 `CALIBRATION_CORPUS_V1_MANIFEST_V2.json`（data root）
- **禁止**：同一 segment 因审核两次被训练两次；NEEDS_ADJUDICATION/EXCLUDED 段不进训练

## 5. COVERAGE_MATRIX_V2（回答 Q3）

**旧 V1 Coverage 审计结论**：
- 旧组合计数**已按 segment set 去重**（291 段），未因 v1+v2 双计放大（组合级对比膨胀 = 0）
- 但旧 291 段中混入 **51 个不可训练段**（34 冲突 + 17 boundary 不可用）→ GOOD 覆盖虚高
- 旧状态：GOOD 35 / MEDIUM 15 / LOW 56（106 组合，中文维度）
- 旧 `COVERAGE_MATRIX_V1.json` 标记 **DEPRECATED_FOR_DOUBLE_COUNT_RISK**（未删除）

**新 V2 Coverage（{cv['population']}）**：
- {cv['total_combos']} 组合 = GOOD {cv['state_counts'].get('GOOD',0)} / MEDIUM {cv['state_counts'].get('MEDIUM',0)} / LOW {cv['state_counts'].get('LOW',0)} / EMPTY {cv['state_counts'].get('EMPTY',0)}
- **Top 强度**：""" + "; ".join(f"{s['dim1_value']}×{s['dim2_value']}={s['sample_count']}" for s in cv["top_strengths"][:6]) + f"""
- **Top 缺口**：""" + "; ".join(f"{g['dim1_value']}×{g['dim2_value']}={g['sample_count']}" for g in cv["top_gaps"][:6]) + f"""
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
""")
report = os.path.join(DOCS, "PHASE2_5_1_CANONICAL_TRUTH_REPORT.md")
with open(report, "w", encoding="utf-8") as f:
    f.write("\n".join(R))

# ---- ANNOTATION_SCHEMA_V2.md ----
S = []
S.append(f"""# Annotation Schema V2 — 标注词典冻结文档（ANNOTATION_DICTIONARY_V2）

- **冻结日期**：{NOW} ｜ 仓库 `{commit}` ｜ 迁移 `0006_annotation_schema_v2_truth`
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
""")
schema_report = os.path.join(DOCS, "ANNOTATION_SCHEMA_V2.md")
with open(schema_report, "w", encoding="utf-8") as f:
    f.write("\n".join(S))

desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\admin"), "Desktop")
for src in (report, schema_report):
    try:
        shutil.copy2(src, os.path.join(desktop, os.path.basename(src)))
        print("copied ->", os.path.join(desktop, os.path.basename(src)))
    except Exception as e:
        print("FAIL", src, e)
print("REPORTS:", report, schema_report)
