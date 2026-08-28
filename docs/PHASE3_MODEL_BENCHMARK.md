# Phase 3 模型 Benchmark — 本机能力审计（RTX 3050 6GB 目标环境）

- **日期**：2026-08-28 10:39 ｜ 实测数据（非估算）

## 1. 环境事实

| 项 | 值 |
|---|---|
| torch | 2.6.0+cpu（**CPU-only，CUDA 不可用**） |
| torchvision | 0.21.0+cpu |
| opencv | 4.10.0 |
| onnxruntime | 1.28.0 |
| transformers | 5.15.0 |
| models 目录 | 空 |
| HF_HUB_OFFLINE |  |
| GPU | RTX 3050 6GB 存在但 **未被 torch 使用**（无 CUDA 运行时） |

> 检测到 torch CPU-only（无 CUDA 运行时）；RTX 3050 未被 torch 使用。大模型（CLIP/SigLIP/ViT）在 HF_HUB_OFFLINE=1 且无本地权重下不可用。

## 2. 实测速度（CPU，cv2）

| 项 | 实测 |
|---|---|
| 单帧读取 | 0.035s |
| 单帧特征提取 | 0.0469s |
| 5 帧/段估算 | 0.41s |
| 全管线实测（240 段） | 0.97s/段（232s 总） |

## 3. 候选模型评估（不锁死）

| 模型 | 可用性 | VRAM | RAM | 单段 | 能力 | 许可证 |
|---|---|---|---|---|---|---|
| OpenCV heuristic (本阶段原型) | YES | 0 (CPU) | ~200MB | 0.7 (实测) | scene/shot_scale/people/technical 启发式；material/product 弱 | Apache-2.0 (OpenCV) |
| CLIP (OpenAI, ViT-B/32) | NO — 本地无权重 + HF_HUB_OFFLINE=1 无法下载 | ~2GB (fp32) | ~2GB | n/a | scene/product/material/shot 强（若可用） | MIT |
| SigLIP (google/siglip-base) | NO — 需下载权重 | ~1.5GB | ~1.5GB | n/a | 视觉特征质量高，适合 embedding | Apache-2.0 |
| torchvision resnet18 (随机权重) | PARTIAL — 无预训练权重，随机权重不能用于生产 | 0 (CPU) | ~500MB | 可测（未训练无意义） | 仅结构验证，特征无语义 | BSD-3 |
| Temporal: 帧差能量 (本阶段) | YES | 0 | ~100MB | 0.05 (实测) | STATIC/SPEAKING/EXTEND 粗分 + motion profile | Apache-2.0 |

## 4. 结论与路线

- 当前环境无法运行 CLIP/SigLIP 类模型（无权重 + 离线）；**本阶段视觉认知 = OpenCV 启发式原型**（CPU 0.97s/段）
- 选择原则：成本/速度/准确率平衡，**不因模型更大就选**
- 中期路线：获得 GPU 运行时 + 权重后，引入 SigLIP embedding（scene/product/material/shot_role），保持 TemporalActionAnalyzer 与 TechnicalQualityV2 不变，融合层直接对接
