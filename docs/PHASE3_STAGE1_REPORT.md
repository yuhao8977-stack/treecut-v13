# Phase 3 Stage 1 — Adaptive Multimodal Visual Cognition 报告

- **日期**：2026-08-28 10:39 ｜ 仓库 `22ed1b4` ｜ 迁移 0007 已应用（备份 `pre_0007_20260828_102940.db`）
- **状态**：**Stage 1 第一停点完成**。等待人工审核 **34（THIRD_ADJUDICATION_V1）+ 60（TARGETED_REVIEW_BATCH_V1）= 94 条**
- **禁止项确认**：未全量跑 41814 / 未导入行业知识库 / 未启动 Knowledge Brain V2 / 未改 VALIDATION_SNAPSHOT_V1 / 未将 Calibration 成绩当 generalization accuracy / 未自动生产 / 未改模板 / 未 Fine-tune / 未 LoRA / 未联网学习 / 未将人工反馈变 ACTIVE RULE / HEURISTIC_CONFIDENCE 未当概率

## 1. STEP 0 — 数据模型补强（0007）

- **Canonical Truth Versioning**：`canonical_human_truth_history`（300 行 v1 链）+ 主表 `truth_version/status/is_current/supersedes_version`；`CanonicalTruthService.new_version()` 支持 V3 裁决升级且旧真值永远可追溯；可回答"V1 怎么判 / V2 怎么判 / V3 怎么裁决 / current truth"
- **Annotation Dictionary V2.1**（兼容升级，不推翻 V2）：`ANNOTATION_DICTIONARY_V2_1` 已入 `annotation_dictionary`
  - 单值：scene_family/subtype、product_family/variant、shot_scale、people_presence、quality
  - **多标签**：material[]/component[]/function[]/shot_role[]（JSON array 列）
  - **action**：action_group + **action_sequence[]**（如 `["PULL_OUT","RETRACT"]`），旧 atomic_action 兼容读取
  - 现有 298 段已初始化 multi 列（单元素集合）

## 2. STEP 1 — 模型 Benchmark（详见 PHASE3_MODEL_BENCHMARK.md）

- 本机事实：**torch CPU-only（无 CUDA 运行时，RTX 3050 未被使用）**、models 目录空、HF_HUB_OFFLINE=1
- 实测：帧读取 0.035s、特征提取 0.047s、**全管线 0.97s/段（CPU，240 段实测 232s）**
- 候选：OpenCV 启发式原型（可用，本阶段采用）；CLIP/SigLIP（本地无权重，暂不可用，**不锁死**）；resnet18（随机权重无语义）
- 结论：不因"模型更大"而选；待 GPU 运行时 + 权重就绪再引入 SigLIP/CLIP embedding

## 3. STEP 2-5 — 视觉认知管线（原型）

- **FrameSampler**：start/25/50/75/end + 运动自适应（motion>0.06 加帧、<0.01 减帧）
- **StaticVisualCognition**：OpenCV 启发式（颜色/纹理/边缘/人脸）→ scene_family/shot_scale/people/material/product；**每字段输出 prediction/model_score/visual_evidence/frame_refs/model_version**
- **TemporalActionAnalyzer**：帧差运动能量 → action_group + action_sequence（纯画面，不依赖字幕）
- **TechnicalQualityV2**：sharpness/brightness/contrast/motion/stability/black_frame_ratio/over_exposure/under_exposure 八子分，保留解释性，**无单一总分**
- 诚实声明：`opencv-heuristic-v0.1` 为原型，无法可靠判定的字段输出 UNKNOWN + 低分

## 4. STEP 6-8 — 融合与门控

- **SegmentMultimodalEvidence**：per-field 融合（material 视觉0.8/ASR0.2；function 0.5/0.5；action temporal0.7/ASR0.3；scene 视觉0.85；product 0.6/0.4；shot_scale 视觉1.0；shot_role 视觉0.5/OCR0.5；component 0.3/0.7）——**禁止一个总 confidence 控制所有字段**
- **EvidenceGate**：per-field SUFFICIENT/PARTIAL/WEAK/CONFLICT/MISSING
- **ConfidenceGate**：路由（SUFFICIENT→CHEAP_END；PARTIAL→ADD_FRAMES；WEAK→STRONG_VISION；CONFLICT→STRONG_VISION_WITH_EXPLANATION；MISSING→UNKNOWN）；**model_score/evidence_sufficiency/fusion_score 分离，不称概率**；HEURISTIC_CONFIDENCE_V1 仅历史保留

## 5. STEP 12 — Calibration 评估（240 段，Calibration 非 holdout）

**baseline rules+clip-v1 vs Phase3 candidate（opencv-heuristic-v0.1）**：

| 字段 | baseline effective% | candidate effective% | baseline coverage% | candidate coverage% | candidate 其他 |
|---|---|---|---|---|---|
| scene | 5.4 | **20.4** | 5.8 | **60.2** | cond 33.9% |
| product | 37.3 | 0.0 | 37.8 | 0.0 | UNKNOWN 100%（诚实） |
| shot_scale | 0.0 | **13.3** | 0.0 | **56.6** | |
| people | 23.8 | 16.8 | 25.4 | **58.4** | |

多标签（micro F1 / exact set match）：
- material：base 0.0% → cand 0.0%（exact 0.0%）—— 视觉原型无法识别材质
- component：base 0.0% → cand **20.5%**（ASR 关键词）
- function：base 0.0% → cand **23.8%**（ASR 关键词）
- shot_role：base 0% → cand 0.0%

action：candidate group accuracy **22.9%**、sequence exact **15.0%**、mean edit distance 0.85

**解读（诚实）**：
1. 原型把 scene/shot_scale 从"不敢答"（coverage 5.8%/0%）带到"敢答"（60.2%/56.6%），符合 Phase 3 目标"AI 最大问题是大面积 UNKNOWN"
2. component/function 靠 ASR 关键词获得初步召回（0→20.5%/23.8%），证明多模态融合方向有效
3. **product/material/shot_role 仍是 0 级**（视觉原型不足）→ 正是需要真实视觉模型 + 94 条人工数据的原因
4. **240 条为 CALIBRATION_CORPUS_V1，极偏 FACTORY×ISLAND×岩板（237/240），禁止以此宣称 TreeCut 整体准确率**（STEP 9 纪律）

## 6. STEP 11 — ActiveLearningSamplerV1 → TARGETED_REVIEW_BATCH_V1

- **60 条 unique Segment** = 40 coverage_gap + 10 low_evidence + 10 random_audit
- 素材库 discover（诚实）：实木仅 21 asset（**稀有，不伪造配额**）；轨道插座/插座类 1797；客户家/安装等非工厂 2358；无 ASR asset **6297**（纯视觉候选充足）
- dedup：与 300 已审段零重叠；同 asset ≤2 段且时间窗不重叠（near-duplicate 规避）
- 样本构成（gap hits）：轨道插座 40、家 33、办公 24、安装 6、抽屉 4、实木 1、插电 4…

## 7. STEP 10 — THIRD_ADJUDICATION_V1（34 段裁决队列）

- 34 段 NEEDS_ADJUDICATION，冲突构成：scene 34 / action 34 / shot_type 32 / function 24 / product 4
- 每段含 V1/V2 原始标签 + 冲突字段 + canonical 参考 + 裁决指引（V2.1 词典、隐藏三方答案、保存 Human V3）
- **不自动启动审核窗口**；等 Schema V2.1 UI 就绪后人工执行

## 8. 交付与测试

- 迁移：0007（versioning + V2.1 multi + history 300 行）；DB integrity ok
- 测试：Phase 3 新增 13 个（truth versioning / multi-label / action sequence / visual adapter / temporal / fusion / gate / UNKNOWN fallback / model version / dedup / near-dup / metrics）
- 交付物：`CALIBRATION_CORPUS_V1_MANIFEST_V2.json`（240）· `COVERAGE_MATRIX_V2.json` · `TARGETED_REVIEW_BATCH_V1.json`（60）· `THIRD_ADJUDICATION_V1.json`（34）· `PHASE3_EVAL_RESULTS.json` · `PHASE3_BENCHMARK_RESULTS.json`

## 9. 第一停点

> **Phase 3 Stage 1 已完成。请人工审核：34 条 THIRD_ADJUDICATION_V1 + 60 条 TARGETED_REVIEW_BATCH_V1（共 94 条）。**

- 禁止：启动 FRESH_HOLDOUT_V1、全量运行 41814、进入 Phase 4 / 自动生产
- 人工数据完成后：用 V3/新标签调整 Phase 3（融合权重/采样策略），再进入模型冻结 → FRESH_HOLDOUT_V1（30 条未见样本）
