# STAGE8 G1 — PRODUCTION SOURCE GATE 执行报告

生成：2026-09-02 18:44:23 ｜ 状态判定建议：**STAGE8_G1_PASS_WITH_LIMITATIONS**（最终以架构师 L3 裁决为准）

## 0. 首页速览（§32）

| 问题 | 答案 |
| --- | --- |
| G1 status（机器执行） | PASS_WITH_LIMITATIONS：A1/A3/A5/A6 达标；A2 有 1 条候选待 L3；A4 待 L3 锁定 |
| Role coverage | 100%（28252 media_files + 30 b007_assets = 28282） |
| PRODUCTION_CLEAN_RAW | 21170 |
| PRODUCTION_CLEAN_SEMI | 6594 |
| PUBLISHED_REFERENCE | 186（156 S5 + 30 B007 published） |
| NOT_PRODUCTION_SOURCE | 332（S3 剪映预设） |
| UNKNOWN | 0（UNKNOWN 属合法角色态，本批无） |
| Sample100 组成 | 干净54(S1/S2/S4各18) + 机器标记22 + S3负例6 + S5负例6 + B007 published 6 + 无OCR边界6 |
| Human L3 reviewed | 0（待架构师；子集 45 条已备） |
| Source role accuracy | 待 L3（样本量=已锁定数，不宣称全库90%） |
| 干净样本烧字幕污染 | 机器放行 0；独立 L2 复核候选 **1/54 = 1.85%**（idx35 待 L3）|
| 干净样本平台水印 | **0** |
| S2 混合内容 | 发现：S2 27 条烧字幕资产已逐条标记（未一刀切），全部进例外清单 |
| S3 全排除 | 是（角色 NOT_PRODUCTION_SOURCE + 测试覆盖） |
| 生产消费替换临时 pick_clean | 是（ProductionSourceService.select_clean_candidates；测试覆盖） |
| 发现 false-clean | 1 候选（idx35 待 L3 确认）|
| 剩余 G1 blocker | L3 人工裁决（A2 idx35 + A4 准确率锁定）|

## 1. 落库（A1）

- 新表 `b007_source_role_v1`（Canonical 迁移，非平行体系）：角色+依据+置信+污染5字段+证据+review_status+版本+时间戳
- 先验映射：S1/S2→CLEAN_SEMI、S3→NOT_PRODUCTION、S4→CLEAN_RAW、S5+Z+B007 published→PUBLISHED_REFERENCE
- 覆盖 100%；UNKNOWN 合法态为 0（全部有源可依）

## 2. 污染检测（复用 OCR，未整库重扫）

- 链路 `ocr_text→keyframes→segments→assets→media_files`；`subtitle_flag`+持久文本+促销/日期/平台特征词
- 结果（§13/14 PRESENT/ABSENT/UNCERTAIN）：S1 烧字幕16/水印1；S2 烧字幕27/水印1；S4 烧字幕77/浮层11；S3 烧字幕8
- review_required 共 8781（S4 无OCR 7823 为绝对主体 → 严格池不含这些；宽限池 22233 仅供显式选择）
- **严格合格池 13617 资产（48.15%）**：role CLEAN* + 全部污染 ABSENT + 未 REJECTED
- 环境文字（工厂横幅/实物印刷）单独 `environment_text_present` 记录，不判污染（§15）

## 3. SAMPLE100 与 L2/L3

- SAMPLE100：seed=20260717，可复现，100 条含负例
- L2（qwen2.5vl，**仅候选非真值**）：100/100 完成；首帧误报 22 条经换帧严格复核 → 21 回 ABSENT；机器×qwen 一致确认 15 条；机器假阳 0
- L3 子集 45 条（含全部机器标记 + false-clean 候选 idx35 + S2 对照 + 边界 + 参考负例），human_* 待架构师

## 4. 验收对照（A1–A6）

| 验收 | 结果 |
| --- | --- |
| A1 角色覆盖 100% | ✅ 28282/28282 |
| A2 干净池烧字幕 <5%（目标0） | 🟡 0 放行；1 候选(1.85%)待 L3；确认脏→扩围修复 |
| A3 平台水印 = 0 | ✅ 干净样本 0 |
| A4 role 准确率 ≥90%（L3 子集） | 🟡 待 L3 锁定（样本量=锁定数，明确说明） |
| A5 消费走 canonical 服务 | ✅ `src/treecut/services/production_source.py` |
| A6 中文报告 | ✅ 本文件 + JSON 全套 |

## 5. 例外与后续

- TREECUT_G1_EXCEPTIONS_V1.json：REVIEW_REQUIRED 8781 条（含 S1/S2 烧字幕 43 条、S4 77 条、无OCR 7823 条）——不进默认生产池
- 无OCR 资产（S4 大部）默认不静默入池；后续按需增量 OCR 后升级为可核状态
- V2 债务（D1–D7）已登记于 docs/TREECUT_STAGE8_V2_QUALITY_DEBT_V1.md，归属 G2–G5，G1 不修

## 6. 需架构师裁决

1. L3 审阅清单 45 条（TREECUT_G1_L3_REVIEW.html / JSON）——至少优先 idx35、水印候选、S2 混合项
2. idx35 若确认脏：授权扩围检测（品牌/标题条 + 底带持久文本，需 keyframe 尺寸归一化）后再跑 A2
3. 确认最终状态：STAGE8_G1_PASS / _PASS_WITH_LIMITATIONS / _NEEDS_REPAIR
