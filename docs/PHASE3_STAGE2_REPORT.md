# Phase 3 Stage 2 — Real Visual Intelligence & GPU Enablement 报告

- **日期**：2026-08-28 16:59 ｜ git `0d5fd98` ｜ 判定依据：Stage1 FULL PASS → Stage2 第一停点
- **纪律**：未导入行业知识库/未进 Phase4/未全量 41814/未用 333 称泛化/未创建 Fresh Holdout 后调参/未 LoRA-FT 大模型

## 1. 核心目标达成：RTX 3050 真正"看视频"

| # | 架构监工问题 | 答案 |
|---|---|---|
| 1 | RTX3050 是否真正用于视觉推理？ | **是**：torch 2.6.0+cu124 真实 CUDA（cuda:0 fp16），tensor→GPU→模型推理→输出实测；SigLIP 333 段全量 GPU 推理 120s |
| 2 | 最终 Runtime？ | **PYTORCH_CUDA**（VisionRuntimeProvider 统一出口，业务零 .cuda() 直写；ASR faster-whisper 环境未破坏） |
| 3 | Static 模型？ | **SigLIP base-patch16-224**（vs CLIP ViT-B/32：scene 19.7% vs 5.0% 胜出） |
| 4 | Temporal 模型？ | **TemporalActionAnalyzerV2（Farneback 光流，多帧短 clip，真实时序；0.32s/段）** |
| 5 | Peak VRAM？ | **~450MB**（SigLIP fp16，6GB 余量充足；GPU smoke 11.7MB） |
| 6 | 每 segment 平均速度？ | **0.4s**（333 段 120s；光流 0.32s） |
| 7 | material 是否真正有视觉能力？ | **是**：microF1 0→13.6%（真实视觉信号，不再靠 ASR）；实木等类别 INSUFFICIENT_SAMPLE 不可宣称 |
| 8 | shot_scale/shot_role 是否真正有视觉能力？ | **是**：shot_scale eff 0→13.9%；shot_role microF1 0→16.9% |
| 9 | action 是否用真正时序信息？ | **是**：Temporal V2 用多帧光流（方向/能量/峰），非"单帧+ASR" |
| 10 | 333 Calibration 三路对比？ | baseline→Stage2：scene 3.9→19.7%、material 0→13.6%、component 0→24.3%、function 0→22.3%、shot_role 0→16.9%、people 19.6→25.1%、shot_scale 0→13.9%；**product 弱 0.5%** |
| 11 | 哪些类别因样本不足不能评价？ | 实木(1)/奢石(0)/大理石(0)/不锈钢/玻璃/水槽/吧台/茶桌 等 → **INSUFFICIENT_SAMPLE**（见 COVERAGE_MATRIX_V3） |
| 12 | Fresh Holdout 30 是否完全隔离？ | **是**：FRESH_HOLDOUT_V1_CANDIDATES 30 条与 canonical 360 零重叠、asset 唯一、guard=DO_NOT_TRAIN;DO_NOT_CALIBRATE |
| 13 | VISION_MODEL_BUNDLE_V1 是否已冻结？ | **是**（详见 VISION_MODEL_BUNDLE_V1.md；冻结后禁止用 Holdout 调参） |
| 14 | 是否准备好进入 Fresh Holdout 盲审？ | **候选已准备**；待架构监工验收后：Bundle 先 AI 预测落库锁定 → 再人工盲审 30 条 |

## 2. 工程债收口（STEP 0）

- AnnotationService 统一保存入口（save_v3/save_targeted_review）；Standalone/Main 3 份 _persist 已收敛（UI 不再直写 SQL）；parity 测试 3 项；34+60 数据不变

## 3. 交付物

- `PHASE3_STAGE2_MODEL_BENCHMARK.md`（本目录）· `VISION_MODEL_BUNDLE_V1.md` · `PHASE3_STAGE2_REPORT.md`
- `PHASE3_STAGE2_EVAL.json`（333 三路明细）· `FRESH_HOLDOUT_V1_CANDIDATES.json`（30）
- 代码：`vision_runtime.py` / `static_vision_v2.py` / `temporal_action_v2.py` / AnnotationService 扩展

## 4. 第一停点

> **Stage 2 候选模型已冻结（VISION_MODEL_BUNDLE_V1），FRESH_HOLDOUT_V1 30 条已准备，等待架构监工验收后再进行盲审。**

- 未启动 Fresh Holdout 人工审核、未进入 Phase4、未全量 41814、未自动生产
- 下一轮（验收后）：Bundle 对 30 条未见样本 AI 预测 → 锁定 → 人工盲审 → 泛化评估
