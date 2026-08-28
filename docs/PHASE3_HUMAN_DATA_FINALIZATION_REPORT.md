# Phase 3 Human Data Finalization — 94 条人工数据结算报告

- **日期**：2026-08-28 16:11 ｜ 仓库 `2714a9a` ｜ 词典：ANNOTATION_DICTIONARY_V2_1
- **冻结确认**：THIRD_ADJUDICATION_V1 = **34/34**、TARGETED_REVIEW_BATCH_V1 = **60/60** 全部落库
  （`human_annotation_v3` 34 行、`targeted_human_review_v1` 60 行；以后不得覆盖）
- **纪律**：未自动学习、未修改 AI 规则/权重/模型/CLIP；未创建 FRESH_HOLDOUT；未进入 Stage 2/Phase 4

## 1. 34 条 V3 裁决结算（A2/A3）

基于 V2.1 词典解析 V1/V2/V3 三层，写入 canonical_human_truth **新版本**（truth_version 2，历史保留）：

| 项 | 数 | 说明 |
|---|---|---|
| **resolved** | **33** | V3 = MEDIUM + REVIEWED → truth_source=THIRD_ADJUDICATION，更新 current canonical（version 2） |
| **still_needs_review** | **1** | `09f514b8…`（MEDIUM + NEEDS_SECOND_REVIEW，看不清未硬猜）→ 保持 NEEDS_ADJUDICATION |
| excluded | 0 | — |

> V1/V2 冲突（主要 action 粗类 vs 原子）经 V3 独立裁决消解 33 条；canonical 版本链完整（可查 V1/V2/V3/current）。

## 2. 60 条 TARGETED 新样本结算（A4）

- 60 条 = 新 unique Segment，与原 300 **零重叠**（`Targeted ∩ 原300 = 0`）
- 全部 `MEDIUM + REVIEWED` → **60/60 CALIBRATION_ELIGIBLE**（truth_source=TARGETED_SINGLE_REVIEW）
- 新样本无 boundary 记录（boundary 仅覆盖原 300），可用性改用技术指标（keyframes 存在 + duration>0）——60 条全部通过
- 属性：Active Learning / Calibration 数据，**禁止当 holdout/test**

## 3. CALIBRATION_CORPUS_V2（A5）—— unique segment 口径

| 项 | 数 |
|---|---|
| previous eligible（V1） | 240 |
| V3 resolved 新增 | +33 |
| Targeted eligible 新增 | +60 |
| **新总 unique eligible** | **333** |
| needs_review | 1（09f514b8…） |
| excluded | 27（2 无真值 + 24 boundary + 1 其他） |

- 训练单位 = `segment_id + current canonical_human_truth`；同段多轮审核只计 1 次
- 已输出 `CALIBRATION_CORPUS_V2_MANIFEST.json`

## 4. 人工数据质量（A7）

- V3：MEDIUM 34（33 REVIEWED + 1 NEEDS_SECOND_REVIEW）
- Targeted：**MEDIUM 60 / REVIEWED 60（全部默认 MEDIUM+REVIEWED）**
- ⚠ **异常保留**：两批仍全部 MEDIUM（无 HIGH/LOW 分层）、Targeted 全部 REVIEWED（无 GOLD/需复核/排除）——**confidence/status 字段仍未产生区分价值**（UI 强制必选解决了"漏选"，但用户统一选"中/已审核"）。如实报告，**未自动修改**；后续可考虑在 UI 增加引导（如"明显把握大选高、看不清选低"）。

## 5. COVERAGE_MATRIX_V3（A6）—— V2 vs V3 对比

**状态分布**：GOOD 23 / MEDIUM 2 / LOW 16 / EMPTY 0（41 组合，人口 333 段）

**A6 八问（诚实回答）**：

1. **非工厂场景增加多少？** 几乎无增加——V3 场景分布：FACTORY **327/333（98.2%）**、SHOWROOM 1、CUSTOMER_HOME 1、OTHER 1。**素材库本身 98%+ 是工厂**，可采的非工厂真实存在极少。
2. **不同材质增加多少？** 岩板 331/333，实木仅 1。素材库实木类 asset 仅 21 个（discover 实测），采样配额实木 4 仅采到 1——**稀有是素材库分布，非采样器问题**。
3. **不同 component 增加？** 见 `COVERAGE_MATRIX_V3.json` diversity；轨道插座/抽屉等在新样本中有出现（V3 combos 增加）。
4. **不同 function 增加？** 收纳/伸缩/用电为主；水槽/办公等仍 ≤1。
5. **纯视觉/弱 ASR 样本增加？** 新增 60 条含纯视觉配额 6 条 + 低证据 6 条（rev3 类别配额）→ 是主要结构性增量。
6. **action_sequence 覆盖增加？** 有增加（V3 中带 sequence 的段计入），但 333 段中序列覆盖仍集中于 SPEAKING/EXTEND。
7. **最大 10 个 Coverage Gap**：实木×STORAGE、BAR×岩板、ISLAND×实木、BAR×OTHER、BAR×SPEAKING、FACTORY×BAR、SHOWROOM×ISLAND、CUSTOMER_HOME×ISLAND、SHOWROOM×EXTEND、CUSTOMER_HOME×OTHER（均样本=1）。
8. **主动学习 60 条是否真正改善长尾？** **部分改善、总体有限**：组件/功能/纯视觉维度有增量；但场景/材质维度受**素材库先天偏科**限制（工厂×岛台×岩板占 98%+），60 条无法改变整体分布。**这不是采样失败，是素材库真实分布**——如需真正补长尾，需先扩充素材库（实木/客户家/展厅类素材）或接受偏科现实。

## 6. 六问总结（A8）

1. **34 条 V3 解决多少冲突？** 33/34（剩余 1 条 09f514b8 需复核，未硬判）
2. **还剩多少 NEEDS_ADJUDICATION？** 1（09f514b8…）
3. **60 条 Targeted 多少可进 Calibration？** **60/60**
4. **最新可学习 unique segment 总数？** **333**
5. **Coverage 是否明显改善？** 组合数增加、组件/功能/纯视觉维度改善；**场景/材质维度改善有限（素材库偏科所致）**
6. **哪些字段仍严重缺数据？** 材质（实木/奢石/大理石/不锈钢）、非工厂场景（客户住宅/展厅/安装）、吧台/餐边柜/茶桌产品、水槽/办公/就餐功能、action 原子序列多样

## 7. 交付物

- `CALIBRATION_CORPUS_V2_MANIFEST.json`（333 段）
- `COVERAGE_MATRIX_V3.json`
- `PHASE3_FINALIZATION_SUMMARY.json`

> 本阶段仍**禁止学习**；下一步（Stage 2）需先解决 GPU + 真实视觉模型，再谈从 333 段学习。审核系统产品化（PART B-D）另行报告。
