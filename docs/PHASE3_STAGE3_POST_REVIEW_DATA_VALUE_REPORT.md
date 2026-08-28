# PHASE3 STAGE3 — POST-REVIEW TRUTH & DATA VALUE REPORT

> 状态：**60 条人工审核已完成并冻结；本轮为 Truth 冻结 + 数据价值审计（不训练、不调参、不改 Policy）**
> 日期：2026-08-28
> 批次：`TARGETED_REVIEW_STAGE3_V3_1`（60 条）· manifest_sha256 `f905d16bf61d03f20cca83cac3a7a355f41f3738a2f2e8dca6215d4d20c8ed02`
> 纪律：Fresh Holdout V1 仍 READ-ONLY / DO_NOT_TRAIN / DO_NOT_CALIBRATE；Stage3 60 为 DEV expansion（可做 threshold/routing/model selection，最终独立考试用 FRESH_HOLDOUT_V2）

---

## STEP 1-2：冻结校验 + Human Truth Lock ✅

**JOIN（严格按 segment_id，非 UI 顺序/index）**：

| 检查 | 结果 |
|---|---|
| manifest 60 unique | ✅ |
| human review 60 unique | ✅ |
| missing | **0** |
| extra | **0** |
| duplicate | **0** |

**分布**：status REVIEWED 53 / GOLD 6 / EXCLUDED 1 · confidence MEDIUM 54 / HIGH 6 · dictionary ANNOTATION_DICTIONARY_V2_1 全 60 · DB needs_review=**0**（与 Review Center 一致）
EXCLUDED 1 条：`a678c4b5…`（人工标"废弃视频，不可用"）

**Human Lock 已冻结**：`TARGETED_REVIEW_STAGE3_V3_1_HUMAN_LOCK.json`
**human_truth_sha256 = `a6cc7f3078cafd303e0460dc78079c9af17c71b21950ed773e8b4db06588733d`**
守卫：DO_NOT_OVERWRITE；修订必须走 revision/adjudication。

---

## STEP 3：这 60 条到底补了什么（真实 Human Truth，非采样目标）

| 字段 | Calibration333 | Stage3 60 | 说明 |
|---|---|---|---|
| people_presence | YES 237 / NO 93 | **YES 38 / NO 20 / UNK 2** | 60 里 NO 占 1/3，含大量难例 |
| product_variant | EXTENDABLE 199 / STANDARD 10 | EXTENDABLE 46 / STANDARD 6 / UNK 8 | **无 FLOATING/FLOOR** |
| scene_family | FACTORY 352 / 其他 3 | FACTORY 54 / **CUSTOMER_HOME 1** / UNK 5 | 长尾几乎没补出 |
| material | 岩板 356 / 实木 1 | 岩板 54 / UNK 6 | **无实木/奢石/大理石/不锈钢/玻璃** |
| action_group | SPEAKING 174 / EXTEND 77 / STATIC 25 / DRAWER 11 | SPEAKING 31 / STATIC 19 / DRAWER 1 | |
| shot_role | — | PERSON_TALKING 35 / PRODUCT_SHOWCASE 39 / FUNCTION_DEMO 21 / DETAIL 17 / CRAFT 12 | 丰富 |

⚠ 60 条是 TARGETED DEV（非随机），禁止当全库分布。

---

## STEP 4：Semantic Action 真实增量（action_sequence 原子）

| 原子动作 | before(333) | new(60) | combined | 门槛 |
|---|---|---|---|---|
| PERSON_SPEAKING | 192 | 33 | 225 | READY_FOR_DEV |
| PULL_OUT | 52 | 2 | 54 | READY_FOR_DEV |
| RETRACT | 35 | 1 | 36 | READY_FOR_DEV |
| OPEN_DRAWER | 9 | 3 | 12 | READY_FOR_DEV |
| OPEN_CABINET | 5 | 7 | 12 | READY_FOR_DEV |
| **CLOSE_CABINET** | 4 | 6 | **10** | **READY_FOR_DEV（原 GAP_UNCOVERED→COVERED！）** |
| CLOSE_DRAWER | 3 | 4 | 7 | LIMITED |
| OPEN_SINK_COVER | 1 | 3 | 4 | INSUFFICIENT_SAMPLE |
| OPERATE_SOCKET | 2 | 0 | 2 | INSUFFICIENT_SAMPLE |
| STATIC_DISPLAY | 34 | 17 | 51 | READY_FOR_DEV |
| OTHER | 70 | 1 | 71 | READY_FOR_DEV |

**GAP 检查**：CLOSE_CABINET 之前 GAP_UNCOVERED → 人工审核后 **combined=10（COVERED）** ✅；OPERATE_SOCKET 仍 combined=2（PARTIAL）—— **禁推断模型会此动作**。

---

## STEP 5：Action 候选发现器命中质量（审核前保存的 reason vs 人工真值）

| 候选动作 | candidate | truth_hit | precision |
|---|---|---|---|
| OPEN_DRAWER | 1 | 1 | **100%** |
| OPEN_SINK_COVER | 8 | 3 | 37.5% |
| PULL_OUT | 4 | 1 | 25.0% |
| RETRACT | 20 | 0 | **0%**（关键词"收纳"全误命中） |

→ 当前 ASR/OCR 关键词发现器**只有 OPEN_DRAWER 可靠**；RETRACT 发现器无价值。未来 Active Learning 候选发现器需重设计（不能靠"收纳"这类词）。可对照段仅 V2∩V3_1 的 49 条。

---

## STEP 6-7：People Detector 难例诊断（仅审核前已保存输出，无 post-hoc）

覆盖如实标注：YOLO 预存输出仅 10/60（people top12 中仍在 V3_1 者）；SigLIP 49/60（features）；其余替换段无审核前输出，**不补推理**。

| 子集 | 模型 | n | TP/FP/TN/FN | P | R | Sp | F1 | acc | bacc |
|---|---|---|---|---|---|---|---|---|---|
| A. 全部60 | SigLIP | 58 | 2/0/20/36 | 100 | 5.3 | 100 | 10.0 | 37.9 | 52.6 |
| A. 全部60 | YOLO | 10 | 7/3/0/0 | 70.0 | 100 | 0 | **82.4** | 70.0 | 50.0 |
| B. PEOPLE子集22 | SigLIP | 22 | 0/0/14/8 | 0 | 0 | 100 | **0** | 63.6 | 50.0 |
| B. PEOPLE子集22 | YOLO | 10 | 7/3/0/0 | 70.0 | 100 | 0 | **82.4** | 70.0 | 50.0 |
| C. 分歧子集10 | YOLO | 10 | 7/3/0/0 | 70.0 | 100 | 0 | **82.4** | 70.0 | 50.0 |
| C. 分歧子集10 | SigLIP | 10 | 0/0/3/7 | 0 | 0 | 100 | **0** | 30.0 | 50.0 |

**关键**：YOLO 在 7 条真 YES 上全中（R=100）；3 条人工 NO 但 YOLO YES（`dfee31c6`/`5a4cb04f`/`b4ea6c6a`）—— 正是 threshold 可调的难例（当前 conf=0.55 偏激进）。SigLIP 在这些难例上 R=0（8/8 全漏）。
**上述是 Targeted Hard-case Diagnostic Performance，非泛化 accuracy。**

**STEP 7 判定**：**PeoplePresenceAnalyzerV2 值得成为 Bundle V2 primary candidate**（审核前输出证据：难例 F1 82.4 vs SigLIP 0；333 上 F1 94.4 vs 15.6）。若调 threshold 须另开 DEV tuning，禁 post-hoc。

---

## STEP 8-10：Variant / Scene / Material 真实增量

**Variant**：EXTENDABLE +46、STANDARD +6；**FLOATING_ISLAND / FLOOR_ISLAND combined=0 → LIBRARY_GAP**（素材库没有，不假设模型能学）。

**Scene**：4 条 Scene 候选 → **0 条真 longtail**（发现精度 0%；"客户/安装/家"全关键词误命中）。60 条仅 1 条 CUSTOMER_HOME。SHOWROOM 1 / INSTALLATION_SITE 0 → **问题不是模型，是长尾素材发现困难 + 素材库缺失**。

**Material**：岩板 +54；**实木 1 / 奢石 0 / 大理石 0 / 不锈钢 0 / 玻璃 0**。4 条"不锈钢"候选人工全部未确认不锈钢（发现器误命中）。→ 素材库无这些材质，LIBRARY_GAP。

---

## STEP 11-13：Multi-label Policy Post-review（新60 DEV，仅诊断不修改）

| 字段 | 冻结策略 | n | pred_avg | human_avg | P | R | F1 | macroF1 | exact | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|
| material | V1 | 49 | 4.67 | 1.02 | 14.4 | 66.0 | 23.7 | 33.7 | 0 | **MIXED** |
| component | V2 | 49 | 2.69 | 1.67 | 40.9 | 65.9 | **50.5** | 55.0 | 6.1 | **SUPPORTED** |
| function | V2 | 49 | 2.59 | 1.88 | 40.9 | 56.5 | **47.5** | 54.7 | 2.0 | **SUPPORTED** |
| shot_role | V1 | 49 | 6.9 | 2.29 | 28.4 | 85.7 | 42.7 | 47.0 | 0 | SUPPORTED（但过预测明显） |

**product_family 保护**：新60 DEV acc=**72.7%**（n=44）> V1_1 Holdout 锚点 51.7% → **无退化信号**。

→ component/function 的 V2 压缩在新真值上成立（F1 50.5/47.5，pred 2.6-2.7 vs human 1.7-1.9）；material V1 仍弱（MIXED）；shot_role V1 R 高但 pred 6.9 是撒网。**本轮不修改任何 Policy**。

---

## STEP 14：Human QA（只 FLAG 不修改）

**3 条** action_group 与 action_sequence 不一致（`2cf01ef8` STATIC vs [PERSON_SPEAKING,OPEN_CABINET,CLOSE_CABINET,OPEN_THEN_CLOSE_DRAWER]；`bc6189b6` SPEAKING vs [OPEN_SINK_COVER]；`d81be396` STATIC vs [PERSON_SPEAKING,OPEN_SINK_COVER]）。
无全 UNKNOWN、无多标签过选。→ 少数可二次裁决，无需全量重审。

---

## STEP 15-17：开发门槛与下一步

**Action（combined=333+60）**：
- **READY_FOR_DEV（8 类）**：PERSON_SPEAKING 225 · OTHER 71 · PULL_OUT 54 · RETRACT 36 · STATIC_DISPLAY 51 · OPEN_DRAWER 12 · OPEN_CABINET 12 · **CLOSE_CABINET 10**
- **LIMITED**：CLOSE_DRAWER 7
- **INSUFFICIENT_SAMPLE**：OPEN_SINK_COVER 4 · OPERATE_SOCKET 2
- **ZERO/LIBRARY_GAP**：FLOATING/FLOOR 变体 · INSTALLATION_SITE · 奢石/大理石/不锈钢/玻璃

**STEP 16 判定**：**需补最小 Targeted Batch**（仅真实存在少量缺口的类别）：OPEN_SINK_COVER(4→目标≥10)、OPERATE_SOCKET(2)、CLOSE_DRAWER(7→10)、CUSTOMER_HOME(2)、SHOWROOM(1)、实木(1)。**不默认再 60/100 条。**

**STEP 17 推荐**：**OPTION B（先补最小批）+ OPTION A 并行可行** ——
- 已 READY 的 Action 8 类 + People V2 + component/function V2 可**直接进入开发**（不影响人工批次）
- 同时补 1 个 20-30 条小批（仅以上少量缺口，若素材可发现）

---

## 20 问答复

1. **60 条 Human Review 完整且唯一？** → 是（missing/extra/duplicate=0）
2. **human_truth_sha256？** → `a6cc7f3078cafd303e0460dc78079c9af17c71b21950ed773e8b4db06588733d`
3. **confidence/status 分布？** → MEDIUM 54 / HIGH 6；REVIEWED 53 / GOLD 6 / EXCLUDED 1
4. **实际新增 Action？** → OPEN_CABINET +7、CLOSE_CABINET +6、CLOSE_DRAWER +4、OPEN_DRAWER +3、OPEN_SINK_COVER +3、PULL_OUT +2、RETRACT +1
5. **CLOSE_CABINET / OPERATE_SOCKET 仍 0？** → CLOSE_CABINET **10（不再 0）**；OPERATE_SOCKET 仍 **2**（不足）
6. **Action 候选发现器命中率？** → OPEN_DRAWER 100% / OPEN_SINK_COVER 37.5% / PULL_OUT 25% / **RETRACT 0%**（"收纳"误命中）
7. **YOLO 全部60？** → 仅 10 条有审核前输出：P 70 / R 100 / F1 82.4（其余 50 无预存输出，不补推理）
8. **YOLO 难例子集？** → 同 10 条：TP 7/FP 3/TN 0/FN 0，F1 82.4（Targeted Hard-case Diagnostic）
9. **People V2 值得继续？** → **是**（难例 F1 82.4 vs SigLIP 0；333 F1 94.4 vs 15.6）
10. **Variant 新增真实类别？** → EXTENDABLE +46 / STANDARD +6；**FLOATING/FLOOR 0（素材库没有）**
11. **Scene 真 longtail？** → 仅 CUSTOMER_HOME +1（SHOWROOM 1 已有）；Scene 候选发现精度 **0%**
12. **Material 真 longtail？** → 实木 +1；奢石/大理石/不锈钢/玻璃 **0（素材库没有）**
13. **component/function V2 新60 有价值？** → **是**（F1 50.5/47.5，SUPPORTED）
14. **material/shot_role 保留 V1 合理？** → material MIXED（仍弱但无更好）；shot_role SUPPORTED（但 R 靠撒网）
15. **Product Family 退化信号？** → **无**（新60 DEV 72.7% > 锚点 51.7%）
16. **READY_FOR_DEV 字段？** → People V2、Action 8 类（含 CLOSE_CABINET）、component/function V2
17. **INSUFFICIENT/ZERO？** → OPERATE_SOCKET 2、OPEN_SINK_COVER 4、CLOSE_DRAWER 7、CUSTOMER_HOME 2、SHOWROOM 1、实木 1；ZERO：FLOATING/FLOOR/INSTALLATION_SITE/奢石/大理石/不锈钢/玻璃
18. **还需人工审核？** → **需要少量**（非默认 60/100）
19. **最少多少条、为什么？** → **约 25-30 条**：OPEN_SINK_COVER 需 ~7、OPERATE_SOCKET ~8、CLOSE_DRAWER ~3、CUSTOMER_HOME ~8、SHOWROOM ~4、实木 ~4（达到各类 ≥10 门槛；若素材库无可发现则转 LIBRARY_GAP）
20. **下一步？** → **双轨**：① 已 READY 部分（People V2 / Action / component/function routing）直接进入 Stage3 模型开发；② 同时评估小批 25-30 条数据发现可行性（素材存在才审）

---

## 产物清单

- `TARGETED_REVIEW_STAGE3_V3_1_HUMAN_LOCK.json`（+ human_truth_sha256 `a6cc7f30…`）
- `STAGE3_POST_REVIEW_LABEL_SUPPORT.json`（全字段 support + step8-10 明细）
- `STAGE3_ACTION_TRUTH_AUDIT.json`（STEP 4-5）
- `STAGE3_PEOPLE_HARDCASE_EVAL.json`（STEP 6-7）
- `STAGE3_MULTILABEL_POST_REVIEW_EVAL.json`（STEP 11-13）
- `STAGE3_HUMAN_QA_FLAGS.json`（STEP 14-17）
- 脚本：`stage3_postreview_{lock,action,people,vsm,multilabel,qa}.py`

## 纪律声明

- Fresh Holdout V1：READ-ONLY / DO_NOT_TRAIN / DO_NOT_CALIBRATE（本轮仅引用 51.7% 锚点）
- Stage3 60：DEV expansion，可做 threshold/routing/model selection/error analysis
- 未训练 / 未调参 / 未改 Policy / 未建 Bundle V2 / 未建 FRESH_HOLDOUT_V2 / 未进 Phase 4
