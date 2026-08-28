# PHASE3 STAGE3 — MODEL DEVELOPMENT REPORT（DUAL TRACK）

> 状态：**MODEL DEVELOPMENT KICKOFF 完成（TRACK A + TRACK B）**
> 日期：2026-08-28
> 判定：POST-REVIEW DATA VALUE AUDIT = PASS → DUAL TRACK
> 纪律：不默认建 25/30/60 人工批；不建 Bundle V2 / Fresh Holdout V2 / Phase4 / 全量 41814；Fresh Holdout V1 仅 READ-ONLY 参考

---

## PRE-STEP 0：支持量口径核验 ✅（SUPPORT_COUNT_INTEGRITY_AUDIT.json）

**Q1. 为什么 Calibration333 出现 FACTORY 352 / 岩板 356？**

**答案：口径 bug —— 数字来自 canonical_human_truth is_current=1 全表 360 段，而非 Calibration333 manifest。**

| 来源 | unique 段 | 事实 |
|---|---|---|
| canonical360 全表（误用） | 360 | FACTORY 352 / 岩板 356 |
| **Calibration333（manifest 交集，正确）** | **333** | **FACTORY 327 / 岩板 331** |
| 多出的 27 段 | — | 早期批次 SINGLE_REVIEW 段（25 段 FACTORY），不在 manifest |

**修正后真实 support（Q2）**：Cal333 FACTORY=327、岩板 occurrence=331（均 ≤333 ✓ 无违规）；单标签各集合 sum=unique ✓；多标签明确标 occurrence。已修正 `STAGE3_POST_REVIEW_LABEL_SUPPORT.json` + 本报告。Action 门槛微调：PERSON_SPEAKING 211 / OPEN_CABINET 11 / CLOSE_CABINET 10 / CLOSE_DRAWER 7（LIMITED）/ OPERATE_SOCKET 2 / OPEN_SINK_COVER 4。**只修统计，未改 Human Truth。**

---

## PRE-STEP 1：3 条 Human QA 二次裁决 ✅（STAGE3_ACTION_QA_ADJUDICATION.json）

**Q3. 3 条冲突是否解决？** → 规则判定全部 **conflict=True**（group 与 sequence 无合法交集）：
- `2cf01ef8`：STATIC vs [PERSON_SPEAKING, OPEN_CABINET, CLOSE_CABINET, OPEN_THEN_CLOSE_DRAWER]
- `bc6189b6`：SPEAKING vs [OPEN_SINK_COVER]
- `d81be396`：STATIC vs [PERSON_SPEAKING, OPEN_SINK_COVER]

已生成 3 条二次裁决任务并接入 Review Center（`STAGE3_ACTION_QA_ADJUDICATION`，只修 action_group/action_sequence/comment/status，不显示 AI，走 revision 不覆盖 Human Lock）。**待用户裁决这 3 条**（不必重审 60）。

---

## TRACK A：模型开发

### A1+A2 PeoplePresenceAnalyzerV2（Q4/Q5）

**实现**：`people_analyzer_v2.py`（YOLOv8n person primary + SigLIP fallback，输出 YES/NO/UNKNOWN + max_person_conf/frame_hit_count/frames_sampled；禁输出身份属性）。

**A2 threshold DEV tuning**（POST-REVIEW DEV TUNING DATA，重新对 387 有效段跑 YOLO）：

| conf | TP/FP/TN/FN | P | R | Sp | F1 | acc | bacc |
|---|---|---|---|---|---|---|---|
| 0.40 | 273/36/77/1 | 88.3 | 99.6 | 68.1 | 93.7 | 90.4 | 83.9 |
| 0.50 | 273/34/79/1 | 88.9 | 99.6 | 69.9 | 94.0 | 91.0 | 84.8 |
| **0.70（冻结）** | **270/29/84/4** | **90.3** | **98.5** | **74.3** | **94.2** | **91.5** | **86.4** |

**Q5 最终 threshold = 0.70**（F1 最高且 FP 最少；比旧 0.55 少 4 FP）。分集合：CAL333 F1 94.6 / STAGE3 F1 92.1。
**Q4 People V2 最终 DEV 表现**：合并 F1 **94.2** / bacc 86.4 → **READY_CANDIDATE**。

### A3+A4+A5 SemanticActionAnalyzerV1（Q6/Q7）

**实现**：`semantic_action_v1.py`（规则基 state-change + ASR/OCR 精确短语 + component hints + 光流仅作 motion evidence；禁 Farneback→label；禁"收纳"作 RETRACT 强证据）。

**DEV（390 段，atomic 级，不 group 冒充）：**

| action | support | P | R | F1 |
|---|---|---|---|---|
| OPEN_DRAWER | 11 | 100 | 18.2 | **30.8** |
| PULL_OUT | 52 | 53.3 | 15.4 | 23.9 |
| OPERATE_SOCKET | 2 | 2.1 | 50.0 | 4.1 |
| OTHER | 67 | 19.9 | 97.0 | 33.1 |
| RETRACT / CLOSE_DRAWER / OPEN_CABINET / CLOSE_CABINET / PERSON_SPEAKING / STATIC_DISPLAY / OPEN_SINK_COVER | — | — | — | **0（ASR 短语未命中；规则基视觉证据缺失）** |

**Q6 真正建立能力**：仅 OPEN_DRAWER（P100）、PULL_OUT（弱）、OTHER（兜底）→ **Semantic Action 整体 EXPERIMENTAL**，V1 规则基证明 ASR 覆盖不足，需补视觉状态变化证据（B2）。
**Q7 仍不足**：RETRACT / CLOSE_DRAWER / OPEN_CABINET / CLOSE_CABINET / OPEN_SINK_COVER / PERSON_SPEAKING / STATIC_DISPLAY（F1 0 或 INSUFFICIENT）。

### A6 Component/Function V2（Q8）

| 字段 | n | pred_avg | human_avg | microF1 | macroF1 | exact |
|---|---|---|---|---|---|---|
| component V2 | 305 | 2.66 | 1.43 | **35.9** | 53.2 | 1.6 |
| function V2 | 382 | 2.73 | 1.51 | **33.2** | 52.6 | 0.5 |

**Q8 继续成立**：V2 压缩 pred≈2.7 vs human≈1.4-1.5，macroF1 53/52.6 → **READY_CANDIDATE**（合并 DEV）。

### A7 Material（Q10）

V1 F1 22.2（MIXED/弱）→ **确认 FALLBACK/EXPERIMENTAL**，不因 Stage3 强行升级。

### A8 ShotRole V3（Q9）

V1：pred_avg 7.0 / F1 36.9（过预测）。V3 网格（top3/4/5 × gap）：F1 32.1-34.2（降 2.7-4.8pt）→ **未达"F1 不降 >2pt"门槛 → 保留 V1 标 EXPERIMENTAL**。Q9：**无法在不明显降 F1 时显著减 label**。

### A9 Product Family（Q11）

Cal333 52.7% / Stage3 72.7% vs Holdout 51.7% 锚点 → **无退化，保持 READY_CANDIDATE**。

---

## TRACK B：数据缺口发现（STAGE3_DATA_GAP_DISCOVERY_V2.json）

**Q12 实际发现（改进发现器，禁"收纳"/"家"子串）：**

| 缺口 | 候选 | 唯一 asset | 状态 |
|---|---|---|---|
| OPERATE_SOCKET | **1940** | **908** | CANDIDATES_FOUND（插座素材其实丰富！） |
| CUSTOMER_HOME | **2367** | **819** | CANDIDATES_FOUND |
| SOLID_WOOD（实木） | **801** | **335** | CANDIDATES_FOUND |
| OPEN_SINK_COVER | 5 | 2 | WEAK（不足） |
| SHOWROOM | 6 | 2 | WEAK（不足） |
| CLOSE_DRAWER | **0** | 0 | **LIBRARY_DATA_GAP** |

**关键反转**：OPERATE_SOCKET / CUSTOMER_HOME / SOLID_WOOD 素材充足（旧发现器漏掉），**值得小批验证 precision**；CLOSE_DRAWER 素材库确实没有。

---

## STAGE3 CANDIDATE EVALUATION（VISION_STAGE3_CANDIDATE_V2.md）

| 状态 | 字段 |
|---|---|
| **READY_CANDIDATE** | people_presence(V2) · component(V2) · function(V2) · product_family |
| **EXPERIMENTAL** | action_sequence(V1) · material(V1) · shot_role(V1) |
| **LIMITED** | scene_family · product_variant（长尾素材缺失） |
| **LIBRARY_GAP** | FLOATING/FLOOR · 奢石/大理石/不锈钢/玻璃 · INSTALLATION_SITE · CLOSE_DRAWER |

---

## 16 问答复

1. **FACTORY352/岩板356 来源？** → canonical360 全表误用（27 段早期批次）；正确 Cal333 = FACTORY 327 / 岩板 331
2. **修正后真实 support？** → 见 PRE-STEP 0 表（Cal333 严格 333 段；Action 门槛微调）
3. **3 条 QA 冲突？** → 全部 conflict=True，已生成 3 条裁决任务接入 Review Center，待用户裁决
4. **People V2 最终 DEV？** → 合并 387 段 F1 94.2 / bacc 86.4（CAL333 94.6 / STAGE3 92.1）
5. **最终 People threshold？** → **0.70**（Stage3 DEV 冻结）
6. **Semantic Action 真正建立能力？** → OPEN_DRAWER（P100）、PULL_OUT（弱）、OTHER（兜底）；整体 EXPERIMENTAL
7. **仍不足的 Atomic？** → RETRACT/CLOSE_DRAWER/OPEN_CABINET/CLOSE_CABINET/OPEN_SINK_COVER/PERSON_SPEAKING/STATIC_DISPLAY
8. **Component/Function V2 成立？** → 是（macroF1 53.2/52.6，READY_CANDIDATE）
9. **ShotRole 减少撒网？** → 否（V3 网格 F1 降>2pt，保留 V1 EXPERIMENTAL）
10. **Material 仍 Fallback？** → 是（V1 F1 22.2，EXPERIMENTAL/FALLBACK）
11. **Product Family 保持？** → 是（52.7/72.7 vs 51.7 锚点，无退化）
12. **缺口数据高质量候选？** → OPERATE_SOCKET 1940 / CUSTOMER_HOME 2367 / SOLID_WOOD 801（唯一 asset 908/819/335）；OPEN_SINK_COVER 5 / SHOWROOM 6 / CLOSE_DRAWER 0
13. **是否还需用户审核？** → **需要极小批**（非默认 25-30）
14. **最小 Batch 多少？** → **约 15-20 条**：从 OPERATE_SOCKET/CUSTOMER_HOME/SOLID_WOOD 的高质量唯一候选抽样验证 precision（B6 触发条件满足：总候选 >>15 且 ≥2 类）
15. **如果不需要，为什么？** → 不适用；但纯 LIBRARY_GAP 类（CLOSE_DRAWER/FLOATING/FLOOR/奢石等）**不再靠审核**，标 LIBRARY_DATA_GAP
16. **是否具备冻结 Bundle V2 条件？** → **尚不具备**：Semantic Action 仍 EXPERIMENTAL（需补视觉状态证据）、3 条 QA 未裁决、Material/ShotRole 为 EXPERIMENTAL。**冻结条件**：Semantic Action 达到至少 3 类 F1≥30、QA 裁决完、小批验证完 → 才建 VISION_MODEL_BUNDLE_V2 → FRESH_HOLDOUT_V2

---

## 产物清单

- `SUPPORT_COUNT_INTEGRITY_AUDIT.json`（PRE-STEP 0）
- `STAGE3_ACTION_QA_ADJUDICATION.json`（PRE-STEP 1，3 条裁决任务）
- `PEOPLE_ANALYZER_V2_DEV_EVAL.json`（A1/A2）
- `SEMANTIC_ACTION_ANALYZER_V1_DEV_EVAL.json`（A3/A4/A5）
- `MULTILABEL_STAGE3_DEV_EVAL.json`（A6-A9）
- `STAGE3_DATA_GAP_DISCOVERY_V2.json`（TRACK B）
- `VISION_STAGE3_CANDIDATE_V2.md`
- `src/treecut/services/people_analyzer_v2.py`（PeoplePresenceAnalyzerV2）
- `src/treecut/services/semantic_action_v1.py`（SemanticActionAnalyzerV1）
- `STAGE3_POST_REVIEW_LABEL_SUPPORT.json`（口径已修正）

## 纪律确认

- 未建 Bundle V2 / Fresh Holdout V2 / Phase4 / 全量 41814
- Fresh Holdout V1 仅 KNOWN BENCHMARK 参考（51.7%），未训练/未调参
- 未覆盖任何 Human Truth Lock；未生成新人工真值（TRACK B 只做候选发现）
