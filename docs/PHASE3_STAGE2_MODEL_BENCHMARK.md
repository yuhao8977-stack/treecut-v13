# Phase 3 Stage 2 模型 Benchmark

- **日期**：2026-08-28 16:59 ｜ 环境：RTX 3050 6GB / 32GB RAM / torch 2.6.0+cu124（真实 GPU）
- **数据**：CALIBRATION_CORPUS_V2（333 unique，dev-set；**非 holdout，成绩为 dev-set performance**）

## 1. Runtime 启用结果（STEP 1-3）

| 项 | 值 |
|---|---|
| GPU | NVIDIA GeForce RTX 3050（6144 MiB，driver 591.86） |
| torch | 2.6.0+cu124（已从 CPU-only 升级；ASR faster-whisper/ctranslate2 环境未破坏） |
| backend | **PYTORCH_CUDA**（device cuda:0，fp16） |
| GPU smoke | 512×512 matmul 2.86ms；VRAM 分配 11.7MB（真实 tensor→GPU→output） |
| onnxruntime | 仅有 CPU/Azure provider（未采用；torch CUDA 已满足） |
| 模型目录 | `C:\Users\admin\dsh_models`（纯 ASCII 路径——sentencepiece 不支持中文路径） |

## 2. 候选模型（真实下载/加载/推理）

| 模型 | 版本 | backend | VRAM峰值 | 速度 | scene dev eff |
|---|---|---|---|---|---|
| **SigLIP base**（选用） | siglip-base-patch16-224 | cuda fp16 | ~450MB | 0.4s/段（333 段 120s） | **19.7%** |
| CLIP ViT-B/32 | openai/clip-vit-base-patch32 | cuda fp16 | ~500MB | 0.4s/段 | 5.0%（20 段小验证） |
| Stage1 opencv-heuristic | opencv-heuristic-v0.1 | CPU | 0 | 0.97s/段 | —（Stage1 报告） |

> 选择原则：成本/速度/准确率平衡；SigLIP 在 scene 上 4 倍优于 CLIP，且显存/速度相当 → 冻结为 Static 模型。

## 3. 333 段三路对比（baseline rules+clip-v1 vs Stage2 SigLIP）

| 字段 | baseline eff | **Stage2 eff** | Stage2 coverage | Stage2 UNKNOWN |
|---|---|---|---|---|
| scene | 3.9% | **19.7%** | 56.1% | 7.5% |
| product | 28.8% | 0.5% | 42.0% | 16.6% |
| shot_scale | 0% | **13.9%** | 39.9% | 34.2% |
| people | 19.6% | **25.1%** | 34.0% | 57.2% |

多标签（micro F1）：material **0→13.6%**、component **0→24.3%**、function **0→22.3%**、shot_role **0→16.9%**
action：本轮未含 Temporal（STEP 11 光流已实现，0.32s/段，另行评估）

## 4. 结论（诚实）

1. **视觉能力真实建立**：material/component/function/shot_role/people/scene 均有真实视觉信号（baseline 多为 0，Stage2 双位数）
2. **product 弱**（0.5%）：SigLIP 难以区分岛台/吧台/餐边柜（家居产品视觉相近）→ 后续依赖 variant 级提示或更强模型
3. **exact_set_match=0**：多标签预测为集合、真值为单值，评估口径需在 Stage2 后续对齐（先如实报告）
4. Calibration 偏科：material 331/333 岩板，**不能报告实木等类别准确率（INSUFFICIENT_SAMPLE）**
