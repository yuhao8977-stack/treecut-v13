# PHASE3 STAGE3 — FINAL PRE-REVIEW BATCH GATE（16 步收口报告）

> 状态：**GATE PASS（四项硬性要求全部落地，未开启人工审核）**
> 日期：2025-08（FINAL PRE-REVIEW BATCH）
> 范围：Calibration333 DEV ONLY；**未使用/未触碰 Fresh Holdout V1（30 条考试卷）**
> 产物：本报告 + 6 个数据产物 + Review Center 接入 `TARGETED_REVIEW_STAGE3_V3`

---

## 0. 本次解决的四项硬性要求（对照用户非接受点）

| # | 用户不接受的点 | 本次处理 | 结论 |
|---|---|---|---|
| 1 | Material Policy 不能退化 | 用**真实 per-label scores** 重放 V1/V2/10 变体于同一 333 | material V2 F1 10.1 vs V1 22.0 → **POLICY_V2_REJECTED_FOR_MATERIAL**（保留旧路由）；component/function 接受 V2；shot_role 拒绝 |
| 2 | People Detector 要先真实跑 | **真实下载并推理 YOLOv8n**（COCO person）于 333 keyframes | **P 91.5 / R 100.0 / F1 95.6**（conf=0.55）vs SigLIP 裸 F1 15.6 → 真实检测落地 |
| 3 | Action 候选要落实到原子动作 | 60 条逐条 action_reason + existing_support + potential_post_review_support | 8 个原子动作全部核算；CLOSE_CABINET / OPERATE_SOCKET = **GAP_UNCOVERED（全库 0 候选，如实报告）** |
| 4 | 60 条必须完成视觉去重 | **两信号判定**（SigLIP 余弦 + pHash DCT8x8），先做 333 背景校准 | 60 条：UNIQUE 49 / INTERNAL 8（去 4 留 4）/ CALIBRATION 2 / **LEAK_RISK_HOLDOUT 1（已替换）** → V3 内零近邻、零 Holdout 泄漏 |

---

## 1. STEP 1-3：Multi-label Policy 最终裁定（真实 per-label scores 重放）

方法：`stage3_final_feature_dump.py` 一次性推理 333+30+60=423 段，存**每标签真实 scores**；`stage3_policy_final_eval.py` 在**同一 333**上重放 V1（阈值 0.06 全标签）与 V2（Top-K+gap+min）及 material 调参网格。**禁止 Holdout，本次只用 333 DEV。**

### 裁定结果（MULTILABEL_POLICY_V2_FINAL_EVAL.json）

| 字段 | 人工 avg 标签 | V1 标签数 | V2 标签数 | V1 P/R/F1 | V2 P/R/F1 | 裁定 | 采用 |
|---|---|---|---|---|---|---|---|
| material | 1.0 | 4.86 | 1.98 | 13.3/64.6/22.0 | 7.6/15.0/10.1 | **REJECTED_FOR_MATERIAL** | V1 旧路由 |
| component | 1.38 | 5.34 | 2.66 | 20.3/78.8/32.3 | 25.0/48.2/32.9 | **ACCEPTED** | V2 |
| function | 1.46 | 8.17 | 2.75 | 17.2/96.1/29.1 | 23.7/44.7/31.0 | **ACCEPTED** | V2 |
| shot_role | 1.75 | 7.06 | 2.72 | 21.6/87.3/34.6 | 22.4/35.0/27.4 | **REJECTED** | V1 旧路由 |

**Material 调参网格（全部变体，无任何变体同时改善 P 与 F1）：**
top1_plain F1 4.8 · top1_min05 5.1 · top2_gap10 10.1 · top3_gap10 **13.9** · top3_gap15_min05 12.7 —— 均远低于 V1 22.0。
→ 结论：**material 的 SigLIP 语义本身弱，任何 Top-K 压缩策略都更差；裁定保留 V1 阈值路由，等人工审核后重估。**

### 生产接入
`static_vision_v2.py` `MULTI_POLICY` 增加 `policy_mode`：material/shot_role = `v1`（阈值 0.06 全标签），component/function = `v2`（Top-3+gap0.10+min0.02）。回归测试 `test_policy_mode_routing_final` 锁定。

---

## 2. STEP 4-5：People Detector 真实基准（333 DEV）

方法：**Ultralytics YOLOv8n（COCO person=0）**，真实 GPU 推理 333 段 keyframes（≤5 帧/段），段级 max-conf；conf 网格在 333 上选优。SigLIP 同真值对比。

| 模型 | conf | P | R | F1 | acc | 备注 |
|---|---|---|---|---|---|---|
| **YOLOv8n** | 0.55（最优） | **91.5** | **100.0** | **95.6** | 91.5 | 330 有效（3 UNKNOWN） |
| YOLOv8n | 0.15 | 86.4 | 100.0 | 92.7 | 86.4 | 阈值扫描单调 |
| SigLIP raw | — | 100.0 | 8.5 | 15.6 | 8.5 | 裸分类严重漏检 |

（修正了上一轮 fp/fn 双计 bug——P==R 恒等是双计特征；本轮为单计混淆矩阵。）

**People 复核 12 条排序（60 候选池，YOLO × SigLIP 分歧优先）：**
全部 12 条均为 `DETECTOR_SIGLIP_DISAGREE`（YOLO 高置信检测到人、SigLIP 判 NO）——正是盲审价值最高的难例；balance 12/12 NO（SigLIP 侧），每条附 yolo_max_conf（0.72–0.93）。写入 `PEOPLE_DETECTOR_BENCHMARK_V1.json.people_review_order_top12`。

---

## 3. STEP 6-8：Action 原子动作候选支持审计（STAGE3_ACTION_CANDIDATE_SUPPORT.json）

**333 库原子动作支持量（canonical_human_truth is_current=1）：**

```
PERSON_SPEAKING 175 · PULL_OUT 47 · RETRACT 29 · OTHER 67 · STATIC_DISPLAY 28
OPEN_DRAWER 3 · CLOSE_DRAWER 1 · OPEN_CABINET 1 · OPEN_SINK_COVER 1
OPEN_THEN_CLOSE_DRAWER 2 · PULL_OUT_THEN_RETRACT 1 · UNKNOWN 5
```

**候选池命中（60 条逐条，关键词→原子映射）：** RETRACT 25 · OPEN_SINK_COVER 9 · PULL_OUT 6 · OPEN_DRAWER 2

**LIBRARY_CANDIDATE_GAP（库支持=0 的原子动作）：**

| 原子动作 | 库支持 | 候选池 | 状态 |
|---|---|---|---|
| CLOSE_CABINET | 0 | 0 | **GAP_UNCOVERED**（全语料无样本 → 无法采样，如实报告） |
| OPERATE_SOCKET | 0 | 0 | **GAP_UNCOVERED**（同上） |

**V3 Action 重平衡**：稀缺原子优先（OPEN_DRAWER/OPEN_SINK_COVER/PULL_OUT），RETRACT 封顶（库已 29，候选 25 过剩）。每个候选条目带 `action_reason`（原子列表）+ `existing_support` + `potential_post_review_support`（= 支持量+1）。

**Variant 回流**：EXTENDABLE 199 / STANDARD 10（333）已充足；悬浮/落地/固定发现=0 → **不伪造配额**，空额回流 Action/People。

---

## 4. STEP 9：Scene/Material 候选质量审计（关键词误命中）

- **Scene 6 条**：全部为关键词误命中——"家"是子串命中（家具/厂家/大家），"客户/安装"是服务语境非场景标签，3/6 的 hits 以动作词"伸缩/拉出"为主。质量门剔除 2 条纯"家"误命中（`59c460a5`、`a4c37c92`），保留 4 条（含"客户/安装"语境的），**不再回流**。
- **Material 4 条**：含真实"不锈钢"关键词（但混有"水槽/家"噪声），保留 4 条如实标注。

---

## 5. STEP 10-11：Visual Near-Duplicate 最终审计（STAGE3_NEAR_DUP_FINAL_AUDIT.json）

**方法（两信号 + 背景校准）**：
1. **背景校准**：333 随机对余弦 p50 0.797 / p90 0.871 / p95 0.888 / p99 0.914 / max 0.975（19933 对）→ 单一余弦阈值 0.92 会误抓 1% 无关对（上一轮 31 条 INTERNAL 是阈值过松的假象）。
2. **判定规则**：NEAR_DUP = cos≥0.99（近恒等）**或**（cos≥0.95 且 pHash 首帧汉明≤10）；Holdout 泄漏 = cos≥0.95 或 pHash≤8（保守高召回）。

**60 条分类**：UNIQUE 49 · NEAR_DUP_INTERNAL 8（保留 4 代表、**DUPLICATE_DROPPED 4**）· NEAR_DUP_CALIBRATION 2（novelty 0.6）· **LEAK_RISK_HOLDOUT 1（`8b0fd719…`，cos 0.959 命中 Holdout → 已从 V3 替换）**。

**冻结后复核（V3 60 条 × 全库）**：内部 cos≥0.99 = **NONE**；×Holdout30 cos≥0.95 = **NONE** → 零泄漏、零内部近邻。

---

## 6. STEP 12-14：TARGETED_REVIEW_STAGE3_V3 冻结

**配额（动态，优先级 Action > People > Variant > Scene > Material > PureVisual，共 60）：**

```
SEMANTIC_ACTION 24（稀缺原子重平衡）
PEOPLE 22（YOLO×SigLIP 分歧 top12 + 补足）
PRODUCT_VARIANT 6（诚实保留，EXTENDABLE 已足不补）
SCENE 4（质量门后）· MATERIAL 4（不锈钢真实）
multi-target 46/60（77%）
```

- 每条含：`sampling_target` / `sampling_target_cn`（动作/人物/变体/场景/材质）、`sampling_keywords`、`near_duplicate_status`、`novelty_score`（UNIQUE 1.0 · CALIBRATION 0.6 · 内部代表 0.0）。
- **盲审契约**：manifest **零 AI 字段**（已程序校验：无 prediction/model_score/siglip/yolo/evidence/provider/backend/probability）。
- 冻结指纹：`TARGETED_REVIEW_STAGE3_V3.json` sha256 = **`a4efda7fe3f101035912c1d1b63dc0ceeb04518c28473d4d2f8c71ef86224a9f`**（sidecar `.sha256`）。
- 守卫：`DEV_ONLY; NOT_HOLDOUT`；V2 已标记 `SUPERSEDED_PRE_REVIEW_BATCH`（保留未删）。

---

## 7. STEP 15：Review Center 接入

`review_center.py` TASKS 注册 `TARGETED_REVIEW_STAGE3_V3`（60 条，type=TARGETED，table=targeted_human_review_v1）：
- `blind: True` + `show_sampling_target: True` → UI 只显示「采样目标：动作/人物/…」，**不显示** sampling_keywords 与任何 AI 猜测。
- `task_stats` / `_done_set` 改为**按 manifest 成员 segment_id 计数**——修复共享表（targeted_human_review_v1 已有旧批次 60 行）导致的新任务虚报 60/60 完成问题。
- V3 与旧批次 60 条 segment 零重叠，启动时 done=0 ✓。

---

## 8. 测试与产物

- 全量 pytest：**116 passed**（新增 `test_policy_mode_routing_final`；修正 `test_task_stats_complete` 为 V3 语义）。
- 数据产物（DATA_ROOT）：`MULTILABEL_POLICY_V2_FINAL_EVAL.json` · `PEOPLE_DETECTOR_BENCHMARK_V1.json` · `STAGE3_ACTION_CANDIDATE_SUPPORT.json` · `STAGE3_NEAR_DUP_FINAL_AUDIT.json` · `TARGETED_REVIEW_STAGE3_V3.json(+.sha256)` · `STAGE3_FINAL_FEATURES.json` · `STAGE3_FINAL_SEGMENT_EMBEDDINGS.npz` · `STAGE3_ACTION_CANDIDATE_SUPPORT.json`。
- 脚本（scripts/）：`stage3_final_feature_dump.py` · `stage3_policy_final_eval.py` · `stage3_people_benchmark.py` · `stage3_people_reorder.py` · `stage3_action_support.py` · `stage3_near_dup_final.py` · `stage3_v3_manifest.py`。

---

## 9. 明确未做（按禁令）

- ❌ 未开启 60 条人工审核（等用户放行）
- ❌ 未用 Fresh Holdout V1 调参（30 条考试卷全程只产特征、零参与策略选择）
- ❌ 未跑全量 41814 / 未建 FRESH_HOLDOUT_V2 / 未进 Phase 4
- ❌ 未触碰 V1_1 历史 / 未自动生产

## 10. 下一步（等指令）

1. 用户放行后开启 `TARGETED_REVIEW_STAGE3_V3` 人工审核（60 条盲审）。
2. 审核结果回填后：重估 material 策略（新真值允许在 333 上重调）、重估 CLOSE_CABINET/OPERATE_SOCKET 缺口。
3. 之后才可规划 Bundle V2（新建 FRESH_HOLDOUT_V2）。
