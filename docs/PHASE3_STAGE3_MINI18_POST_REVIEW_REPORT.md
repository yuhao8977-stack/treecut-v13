# PHASE3 STAGE3 — MINI18 POST-REVIEW FREEZE & DISCOVERY VALUE AUDIT

> 状态：**Mini18 已冻结；三类发现器全部 FAILED_DISCOVERY（precision 0%）—— 诚实结果**
> 日期：2026-08-29
> 纪律：未训练/未调参/未改模型/Prompt/Routing/Policy/People threshold/Semantic Action/未建 Bundle V2/Fresh Holdout V2/未进 Phase4/未建新人工批

---

## STEP 1-2：完整性 + Human Truth Lock ✅

**Mini18 = 18/18 完整**（missing=0 / extra=0 / duplicate=0，严格 segment_id JOIN）。
- status：REVIEWED 18（无 GOLD/NEEDS_SECOND_REVIEW/EXCLUDED）
- confidence：MEDIUM 18（无 HIGH/LOW）
- dictionary：ANNOTATION_DICTIONARY_V2_1 全 18

✅ **Human Truth 已冻结**：`TARGETED_REVIEW_STAGE3_MINI_V1_HUMAN_LOCK.json`
**human_truth_sha256 = `9838bf58e010960cd971c3b2c73569afc7ba5c60b42d65409bf7b96322f4143a`**
守卫：DO_NOT_OVERWRITE；修订走 revision/adjudication。

---

## STEP 3-6：三类候选发现器真实命中（核心结论）

| 类别 | 候选 | TP | TN | precision | 判定 |
|---|---|---|---|---|---|
| OPERATE_SOCKET | 8 | **0** | 8 | **0%** | FAILED_DISCOVERY |
| CUSTOMER_HOME | 5 | **0** | 5 | **0%** | FAILED_DISCOVERY |
| SOLID_WOOD | 5 | **0** | 5 | **0%** | FAILED_DISCOVERY |

**18 条全部是关键词/组件误命中，人工真值零命中采样目标。**

- **Q3/Q4 OPERATE_SOCKET**：8 候选 0 真命中（precision 0%）。真值里**没有任何一条**出现 OPERATE_SOCKET 动作 —— 画面有插座（TRACK_SOCKET/APPLIANCE_SLOT component 证据）≠ 人物操作插座。**FP 原因：COMPONENT_NOT_ACTION（8/8）**。
- **Q6/Q7 CUSTOMER_HOME**：5 候选 0 真命中（precision 0%）。5 条 scene_family **全部 FACTORY**（4 条 FACTORY_SHOWROOM + 1 FACTORY 默认）。ASR 出现"家里/客户"≠ 真实客户家。**FP 原因：SCENE_CONTEXT_FALSE_POSITIVE（5/5）**。
- **Q8/Q9 SOLID_WOOD**：5 候选 0 真命中（precision 0%）。5 条 material **全部岩板**。ASR 出现"实木杆结构"等短语 ≠ 主体是实木（SigLIP wood score 本就 -0.03~0.01 弱）。**FP 原因：WOOD_TEXTURE_FALSE_POSITIVE / LOCAL_MATERIAL_NOT_PRIMARY（5/5）**。

**Q10 三类主要 FP 原因**：插座=COMPONENT_NOT_ACTION（有插座无动作）；客户家=SCENE_CONTEXT_FALSE_POSITIVE（口语"家里"非场景）；实木=LOCAL_MATERIAL_NOT_PRIMARY（局部木纹/杆件非主体材质）。

---

## STEP 7：真实 support 更新（Cal333 + Stage3 + Mini18 分集合合并，无口径错误）

**重点字段（cal / stage3 / mini / combined）：**

| 字段 | cal333 | stage3 | mini18 | **combined** |
|---|---|---|---|---|
| OPERATE_SOCKET | 2 | 0 | 0 | **2**（INSUFFICIENT） |
| OPEN_SINK_COVER | 1 | 3 | 0 | **4**（INSUFFICIENT） |
| CLOSE_DRAWER | 3 | 4 | 0 | **7**（LIMITED） |
| OPEN_DRAWER | 9 | 3 | **1** | **13**（READY） |
| OPEN_CABINET | 4 | 7 | **3** | **14**（READY） |
| CLOSE_CABINET | 4 | 6 | **1** | **11**（READY） |
| PULL_OUT | 50 | 2 | 0 | 52（READY） |
| RETRACT | 35 | 1 | 0 | 36（READY） |
| CUSTOMER_HOME(scene) | 1 | 1 | 0 | **2**（INSUFFICIENT） |
| 实木(material) | 1 | 0 | 0 | **1**（INSUFFICIENT） |
| FACTORY(scene) | 327 | 54 | 18 | **398**（≤ 333+59+18=410 ✓ 无口径错误） |

✅ **无 support>unique 错误**（FACTORY 398 = 327+54+17 有效+18 mini，均 ≤ 各自 unique）。

**意外收获**：Mini18 完整 Schema 标注顺带补了非采样目标动作 —— OPEN_DRAWER +1、OPEN_CABINET +3、CLOSE_CABINET +1、STATIC_DISPLAY +1（`4adae4bd`/`0825c0f6`/`4482e6f7`/`6cc55fcb`/`c7221899`）。OPEN_CABINET 因此从 11→**14**、CLOSE_CABINET 10→**11**，双双更稳 READY。

---

## STEP 8-9：发现器最终价值判定

| 发现器 | precision | 判定 | 是否值得继续主动学习采样 |
|---|---|---|---|
| OPERATE_SOCKET | 0% | **FAILED_DISCOVERY** | **否** —— component 证据 ≠ 动作；需动作级证据（手部交互） |
| CUSTOMER_HOME | 0% | **FAILED_DISCOVERY** | **否** —— ASR"家里/客户"口语误命中；需视觉场景判断 |
| SOLID_WOOD | 0% | **FAILED_DISCOVERY** | **否** —— ASR"实木"短语 + 弱视觉分数全误；需主体材质判断 |

**FP 原因分类**：OPERATE_SOCKET→COMPONENT_NOT_ACTION(8) · CUSTOMER_HOME→SCENE_CONTEXT_FALSE_POSITIVE(5) · SOLID_WOOD→WOOD_TEXTURE_FALSE_POSITIVE(5)。**本轮不修改发现器，仅分析。**

---

## STEP 10：Mini18 对 Semantic Action 的影响

**OPERATE_SOCKET 新增真值 = 0**（combined 仍 2）→ **INSUFFICIENT_SAMPLE**。
⚠ **Mini18 不能解决 OPEN/CLOSE_DRAWER/CABINET/PULL_OUT/RETRACT 的 state-change 问题** —— 这些核心瓶颈仍是"模型看不懂 BEFORE→AFTER 细粒度结构状态变化"，与 Mini18 无关，**不得把 Mini18 结果归功于 SemanticActionV2**（V2 本就如实 EXPERIMENTAL）。

---

## STEP 11：是否还需人工审核

**判定：NO_MORE_MANUAL_REVIEW_FOR_STAGE3。**
- OPERATE_SOCKET(2) / OPEN_SINK_COVER(4) / CUSTOMER_HOME(2) / 实木(1) 均为 INSUFFICIENT
- CLOSE_DRAWER(7) LIMITED 但**候选池 0 素材**；OPEN_SINK_COVER 候选仅 2 asset；OPERATE_SOCKET 候选多(908) 但 support=2 <5 触发门槛
- **结论**：没有任何类别满足"support 5-9 且候选池≥20"的补充批触发条件 → **不再生成任何人工批**（20/30/60 全禁）。未来素材库新增真实插座操作/客户家/实木主体素材时再评估 ≤10 条补充（当前不触发）。

---

## STEP 12：Stage3 Final Consolidation 输入

| 字段 | 状态 |
|---|---|
| people_presence | **READY_CANDIDATE** |
| product_family | **READY_CANDIDATE** |
| component | **READY_CANDIDATE** |
| function | **READY_CANDIDATE** |
| scene_family | LIMITED |
| material | EXPERIMENTAL |
| shot_role | EXPERIMENTAL |
| product_variant | LIMITED |
| semantic_action | EXPERIMENTAL |

本轮**未修改任何 Routing**，仅形成 FINAL_CONSOLIDATION_INPUT（`STAGE3_FINAL_CONSOLIDATION_INPUT.json`）。

---

## 16 问答复

1. **Mini18 完整 18/18？** → 是（missing/extra/duplicate=0）
2. **human_truth_sha256？** → `9838bf58e010960cd971c3b2c73569afc7ba5c60b42d65409bf7b96322f4143a`
3. **OPERATE_SOCKET 8 候选真命中？** → **0**
4. **OPERATE_SOCKET precision？** → **0%**（FAILED_DISCOVERY；COMPONENT_NOT_ACTION 8/8）
5. **OPERATE_SOCKET combined？** → **2**（INSUFFICIENT_SAMPLE）
6. **CUSTOMER_HOME 5 候选真命中？** → **0**（5 条全 FACTORY）
7. **CUSTOMER_HOME precision？** → **0%**（SCENE_CONTEXT_FALSE_POSITIVE 5/5）
8. **SOLID_WOOD 5 候选真命中？** → **0**（5 条全岩板）
9. **SOLID_WOOD precision？** → **0%**（LOCAL_MATERIAL_NOT_PRIMARY 5/5）
10. **三类 FP 原因？** → 插座=COMPONENT_NOT_ACTION；客户家=SCENE_CONTEXT_FALSE_POSITIVE；实木=LOCAL_MATERIAL_NOT_PRIMARY
11. **哪些缺口真正补上？** → 采样目标三类**均未补上**；意外补上 OPEN_DRAWER+1 / OPEN_CABINET+3 / CLOSE_CABINET+1 / STATIC_DISPLAY+1
12. **仍 LIBRARY_GAP？** → CUSTOMER_HOME(2)/实木(1) 素材不足；FLOATING/FLOOR/奢石/大理石/不锈钢/玻璃/INSTALLATION_SITE 仍 0
13. **Mini18 是否改变 Semantic Action 状态？** → **否**（OPERATE_SOCKET 仍 2；state-change 核心未解决，V2 保持 EXPERIMENTAL）
14. **是否还需人工审核？** → **否**（NO_MORE_MANUAL_REVIEW_FOR_STAGE3；无类别满足"support 5-9 且候选≥20"触发）
15. **如需最多多少条？** → 0（当前不触发；未来素材库新增再评估 ≤10）
16. **可否进入 Stage 3 Final Consolidation？** → **是**（FINAL_CONSOLIDATION_INPUT 已生成，9 字段状态就绪）

---

## 产物清单

- `TARGETED_REVIEW_STAGE3_MINI_V1_HUMAN_LOCK.json`（sha256 `9838bf58…`）
- `STAGE3_MINI18_DISCOVERY_PRECISION.json`（STEP 3-10）
- `STAGE3_FINAL_LABEL_SUPPORT.json`（Cal333+Stage3+Mini18 分集合合并）
- `STAGE3_FINAL_CONSOLIDATION_INPUT.json`（STEP 12）
- 本报告 `docs/PHASE3_STAGE3_MINI18_POST_REVIEW_REPORT.md`

## 纪律确认

未训练 / 未调参 / 未改模型 / Prompt / Routing / Policy / People threshold / Semantic Action / 未建 Bundle V2 / Fresh Holdout V2 / 未进 Phase4 / 未建新人工批 / Fresh Holdout V1 仅 READ-ONLY。
