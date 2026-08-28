# VISION_MODEL_BUNDLE_V1_1 — Pre-Holdout 最终冻结（基于 Gate 修正）

- **冻结日期**：2026-08-28 17:11 ｜ git `ed9907c` ｜ 前置：V1（CANDIDATE SNAPSHOT）保留
- 变更记录：SigLIP prompt 中→英（已重跑 333）；字段路由 FIELD_ROUTING_V1；temporal 职责降级为 motion evidence
- 模型参数：SigLIP base（未变）｜ Runtime：PYTORCH_CUDA fp16

| 组件 | 模型 | 路由状态 |
|---|---|---|
| Static | SigLIP base（EN prompt） | product READY；scene/material/component/function/shot_scale/shot_role EXPERIMENTAL；people/product_variant FALLBACK |
| Temporal | Farneback 光流（motion evidence） | EXPERIMENTAL（非语义分类器） |
| Technical | OpenCV 8 子分 | READY |
| Fusion | 字段级 best-known-route（Fusion V2 加权待下轮） | — |
| Dictionary | ANNOTATION_DICTIONARY_V2_1 | 冻结 |

**冻结纪律**：不得再用 FRESH_HOLDOUT 调 Bundle V1_1；Holdout 预测先落库锁定（hash）→ 人工盲审。
