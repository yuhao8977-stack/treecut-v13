# VISION_MODEL_BUNDLE_V1 — Stage 2 模型冻结

- **冻结日期**：2026-08-28 16:59 ｜ git `0d5fd98` ｜ 冻结后**禁止再用 Fresh Holdout 调参**
- **Runtime**：PYTORCH_CUDA（torch 2.6.0+cu124，RTX 3050 6GB，fp16，device cuda:0）

## 冻结成员

| 组件 | 模型/实现 | 版本 | backend | 职责 |
|---|---|---|---|---|
| Static | SigLIP base-patch16-224 | siglip-base-patch16-224-v1 | PYTORCH_CUDA fp16 | scene/product/material/component/shot_scale/shot_role/people/visibility |
| Temporal | Optical-Flow (Farneback) | temporal-flow-v1 | CPU | action_group + action_sequence[]（多帧光流） |
| Technical | OpenCV 8 子分 | opencv-heuristic-v0.1 | CPU | sharpness/brightness/contrast/motion/stability/black/exposure |
| Fusion | SegmentMultimodalEvidence（per-field 权重） | v1 | — | 视觉 + ASR + OCR 按字段融合 |
| Evidence Gate | SUFFICIENT/PARTIAL/WEAK/CONFLICT/MISSING | v1 | — | per-field 证据判定 |
| Dictionary | ANNOTATION_DICTIONARY_V2_1 | V2.1 | — | 全字段枚举 |

## 选择依据（Benchmark）

- SigLIP vs CLIP（scene, dev-set）：**SigLIP 19.7% vs CLIP 5.0%**（20 段 CLIP 小验证；SigLIP 全 333 段）
- SigLIP 6GB 显存：峰值 ~450MB（含 fp16），余量充足
- 速度：0.4s/段（333 段 120s 全量 GPU）
- license：SigLIP Apache-2.0；CLIP MIT（均本地离线可用）

## 冻结纪律

1. VISION_MODEL_BUNDLE_V1 一旦冻结，**不得用 FRESH_HOLDOUT_V1 调其任何参数**（模型/prompt/融合权重/门控阈值）
2. Fresh Holdout 只能用于评估（AI 预测先落库锁定 → 人工盲审 → 泛化验证）
3. 后续升级必须新建 BUNDLE_V2 版本并记录 git commit
