# Stage8 · G1 PRODUCTION SOURCE GATE — 实施计划

> 提交依据：docs/TREECUT_ROADMAP_MASTER_V1.md（唯一主路线图冻结）。
> 本文件 = G1 实施计划（含复用现状/验收集/时间估计）。**未执行任何 G2 内容；等 G1 验收。**

## 0. 目标（一句话）

把 **PUBLISHED_REFERENCE（学习资料）** 与 **PRODUCTION_CLEAN（可剪素材）** 彻底分开，落到 Canonical 数据层，
让正式选镜只允许 CLEAN RAW / CLEAN SEMI，并给出可验收的准确率与污染率数字。

## 1. 现状（已核实，非假设）

### 1.1 源与角色现状（`sources` 表 + `media_files`）

| source_id | 路径根 | 文件数 | 当前 media_files.category | 建议角色（G1 基线） |
| --- | --- | --- | --- | --- |
| 1 | X1 已处理\卖点展示类素材 | 3025 | unclassified（全库 28252 均 unclassified） | PRODUCTION_CLEAN_SEMI |
| 2 | X1 已处理\效果展示类素材 | 3569 | unclassified | PRODUCTION_CLEAN_SEMI（待抽样复核） |
| 3 | X1 已处理\JianyingPro Presets | 332 | unclassified | NOT_PRODUCTION_SOURCE（剪映预设，排除出生产池） |
| 4 | X1 未处理\【工厂】 | 21170 | unclassified | PRODUCTION_CLEAN_RAW |
| 5 | E: platform_reference（B003_PLATFORM_REFERENCE） | 156 | unclassified | PUBLISHED_REFERENCE |

另：B007 published 媒体（`b007_media_asset_v1` 30 条 + 恢复链路 E→Z，`b007_published_media_recovery_v1`）→ **PUBLISHED_REFERENCE**。

现状缺口：角色只存在于 `B007_PRODUCTION_SOURCE_ROLE_V1.json`（4 行粗粒度映射，未落库、无 per-file/segment 证据、无准确率数字）；
V2 选镜（`b007_v091_v2.py::pick_clean`）用“source_id∈(1,2) + 路径关键词”临时过滤——正是 G1 要替换掉的临时逻辑。

### 1.2 可直接复用的数据（污染检测“弹药”已存在）

- 旧管道 OCR 已覆盖 X1：`ocr_text`（289218 行；S1 36451 / S2 69357 / S3 3376 / S4 180034），
  经链 `ocr_text.frame_id → keyframes.frame_id → segments.segment_id → assets.asset_id → media_files` 可回溯到 source。
- `ocr_text` 含 **subtitle_flag / bbox / coverage / confidence / text** → 硬字幕/水印检测所需信号齐备。
- `keyframes` 覆盖：S1 13833 / S2 14772 / S3 1396 / S4 95198。
- `segments` 覆盖：S1 4611 / S2 4924 / S3 466 / S4 31813 / S5 20。
- `media_files` 已有 `category / category_source` 列（空置可用，不动 schema 主结构也可新增独立角色表）。
- 干净审计方法学：`scripts/b007_v091_clean_audit.py`（V0.9.1 已跑出 X1 卖点/效果/工厂样本污染≈0 的基线）；
  候选产物 `reports/storage/B007_CLEAN_SOURCE_CANDIDATES_V1.json`、`B007_PRODUCTION_SOURCE_ROLE_V1.json` 作为复验基线。
- 视觉复核链路：ollama `qwen2.5vl:7b`（本地，已用于 V2 字幕/画面证据）→ 100 段抽样标注的 ground-truth 来源。

### 1.3 复用脚本清单

| 复用对象 | 用途 |
| --- | --- |
| `scripts/b007_v091_clean_audit.py` | 污染扫描方法学（OCR 关键词+区域规则）迁移为正式检测器 |
| V0.7 链（segments/keyframes/ocr_text 生产者） | 数据不再重扫；缺失段增量补 OCR |
| `scripts/b007_v091_v2.py::pick_clean` | 被替换对象：改为角色表过滤 |
| qwen2.5vl 视觉（V2 已用） | 100 段抽样 ground-truth 标注 + 检测结果抽检 |
| E→Z 恢复链路（b007_v062） | PUBLISHED_REFERENCE 资产回溯 provenance |

## 2. 角色体系（G1 冻结）

```
PRODUCTION_CLEAN_RAW     未处理原片（X1 未处理\【工厂】…）
PRODUCTION_CLEAN_SEMI    已处理半成品/卖点段（X1 已处理\卖点/效果…）
PUBLISHED_REFERENCE      已发布平台视频（platform_reference / B007 published / 恢复媒体）
PRODUCTION_REPAIRED      经修复可入生产池的素材（本 Gate 仅预留，不默认产生）
NOT_PRODUCTION_SOURCE    剪映预设等不可剪对象（S3）
UNKNOWN                  无法判定（置信不足，禁止进生产池）
```

正式选镜默认过滤：`role ∈ {PRODUCTION_CLEAN_RAW, PRODUCTION_CLEAN_SEMI}` 且 `contamination=0`。

## 3. 实施步骤（每步停点产出证据）

### Step 1 — 角色注册表落库（预计 1～2h）
- 新表 `b007_source_role_v1`（或填 `media_files.category/source_role` 两列 + 证据列）：
  `file/media 维度：source_role, role_confidence, role_basis(路径规则|OCR|视觉|人工), assigned_by, assigned_at`
- 基线规则映射：S1/S2→CLEAN_SEMI、S4→CLEAN_RAW、S3→NOT_PRODUCTION、S5+Z+published→PUBLISHED_REFERENCE（路径语义为先行先验，非终判）。
- 产出：迁移脚本 + 全量 28252+ 文件角色回填 + 计数表。
- 停点：计数表与你核对。

### Step 2 — 污染/水印检测器正式化（预计 2～4h）
- 复用现有 `ocr_text`：段内多帧 `subtitle_flag=1` 或 底部/居中 bbox 持续文本 → **OLD_HARD_SUBTITLE 候选**；
  四角/边沿持续文本+特征词（小红书/@/关注/账号 等）→ **PLATFORM_WATERMARK 候选**。
- 对缺 OCR 的段增量补跑（限制在 CLEAN 候选池 + S5）。
- 100% 硬闸检测跑在“生产候选池”上；结果存段级 `contamination_flag / watermark_flag / 证据(帧+bbox+文本)`。
- 停点：给出按 source 的候选污染段清单（预期极少，须逐条人工/视觉复核）。

### Step 3 — 100 段验收抽样标注（预计 1～2h 机时 + 你的抽查）
- 抽样：生产候选池随机 100 段（S1/S2/S4 按占比 + S5 全部作对照），段中帧抽图。
- ground-truth：qwen2.5vl 逐帧判定（有无旧硬字幕 / 有无平台水印 / 素材类别 raw|semi|finished）；
  与 `B007_CLEAN_SOURCE_CANDIDATES_V1.json` 基线交叉。
- 你人工抽查 ≥20 段锁定标签（追加式，不改已有 L3）。

### Step 4 — 准确率评估与报告（预计 1～2h）
- 指标（按你给的口径）：
  1. 旧硬字幕明显污染率 = 检出段 / 100 段，**目标 <5%（最好 0）**；
  2. 小红书水印 = **0**（生产池）；
  3. source_role 准确率 = 角色判定与 ground-truth 一致率，**目标 ≥90%**。
- 产出：`G1_SOURCE_GATE_REPORT.html`（中文，逐段证据表）+ JSON + 角色表刷新 + `TREECUT_PROJECT_STATE_V1.json` 更新（G1: PASS/FAIL）。
- 停点：**G1 验收** —— 达标才进入 G2；不达标回到对应 Step 修复。

### Step 5 — 消费点替换（随验收后）
- `b007_v091_v2.py::pick_clean` → 角色表过滤（`role IN CLEAN* AND contamination=0`）；
- 检索候选（Stage6/G3）后续统一走角色视图。

## 4. 验收集（G1 完成判定）

| # | 验收项 | 目标 |
| --- | --- | --- |
| A1 | 全量源文件角色落库且有依据 | 覆盖 100%（28252+156+published 30 等） |
| A2 | 随机 100 生产候选段抽样 | 旧硬字幕污染率 <5%（目标 0） |
| A3 | 同上 | 小红书水印 = 0 |
| A4 | source_role 判定 vs ground-truth | 准确率 ≥90% |
| A5 | 生产默认过滤改走角色表 | V2 选镜代码不再用临时关键词源过滤 |
| A6 | 报告产物 | G1_SOURCE_GATE_REPORT.html + JSON + 状态更新 |

## 5. 风险与需你拍板的点

1. **S3（JianyingPro Presets）**：建议角色 NOT_PRODUCTION_SOURCE（排除出池）——是否同意？
2. **S2（效果展示类）**：V0.9.1 干净审计样本为 0 污染，但“效果展示”可能含近成片内容 → 抽样必须含 S2，若发现带品牌剪辑内容则改判或划 CLEAN_SEMI 细分。
3. **水印检测能力边界**：老平台水印样式多样；检测器给出“候选”后由视觉/人工复核兜底，**不宣称 100% 自动检出**（NO FALSE PASS）。
4. 预计 0.5～1 个有效开发日（机时约 5～8h），符合你给的 0.5～1.5 天。

## 6. 明确不做（本 Gate 边界）

- 不做旧字幕清除/修复算法（PRODUCTION_REPAIRED 仅预留角色位，不实现修复能力）。
- 不做动作窗口（G2）、Claim→Visual（G3）、音频字幕 QA 化（G4）、QA 闸门化（G5）——依次排队。
- 不进入 Stage9 / 不扩模板 / 不扩样本 / 不动 UI / 不换大模型。
