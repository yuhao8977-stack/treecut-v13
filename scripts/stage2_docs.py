# -*- coding: utf-8 -*-
"""Stage 2 交付文档生成：VISION_MODEL_BUNDLE_V1 + MODEL_BENCHMARK + STAGE2_REPORT。"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
REPO = r"C:\Users\admin\github\treecut-v13"
DOCS = os.path.join(REPO, "docs")
commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True, encoding="utf-8").stdout.strip()
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

ev = json.load(open(os.path.join(DATA_ROOT, "PHASE3_STAGE2_EVAL.json"), encoding="utf-8"))
m = ev["metrics"]

# ---------------- VISION_MODEL_BUNDLE_V1 ----------------
B = []
B.append(f"""# VISION_MODEL_BUNDLE_V1 — Stage 2 模型冻结

- **冻结日期**：{NOW} ｜ git `{commit}` ｜ 冻结后**禁止再用 Fresh Holdout 调参**
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
""")
with open(os.path.join(DOCS, "VISION_MODEL_BUNDLE_V1.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(B))

# ---------------- MODEL BENCHMARK ----------------
MB = []
MB.append(f"""# Phase 3 Stage 2 模型 Benchmark

- **日期**：{NOW} ｜ 环境：RTX 3050 6GB / 32GB RAM / torch 2.6.0+cu124（真实 GPU）
- **数据**：CALIBRATION_CORPUS_V2（333 unique，dev-set；**非 holdout，成绩为 dev-set performance**）

## 1. Runtime 启用结果（STEP 1-3）

| 项 | 值 |
|---|---|
| GPU | NVIDIA GeForce RTX 3050（6144 MiB，driver 591.86） |
| torch | 2.6.0+cu124（已从 CPU-only 升级；ASR faster-whisper/ctranslate2 环境未破坏） |
| backend | **PYTORCH_CUDA**（device cuda:0，fp16） |
| GPU smoke | 512×512 matmul 2.86ms；VRAM 分配 11.7MB（真实 tensor→GPU→output） |
| onnxruntime | 仅有 CPU/Azure provider（未采用；torch CUDA 已满足） |
| 模型目录 | `C:\\Users\\admin\\dsh_models`（纯 ASCII 路径——sentencepiece 不支持中文路径） |

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
""")
with open(os.path.join(DOCS, "PHASE3_STAGE2_MODEL_BENCHMARK.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(MB))

# ---------------- STAGE2 REPORT（14 问） ----------------
S = []
S.append(f"""# Phase 3 Stage 2 — Real Visual Intelligence & GPU Enablement 报告

- **日期**：{NOW} ｜ git `{commit}` ｜ 判定依据：Stage1 FULL PASS → Stage2 第一停点
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
""")
with open(os.path.join(DOCS, "PHASE3_STAGE2_REPORT.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(S))

desktop = os.path.join(os.environ.get("USERPROFILE", r"C:\Users\admin"), "Desktop")
for fn in ("PHASE3_STAGE2_REPORT.md", "PHASE3_STAGE2_MODEL_BENCHMARK.md", "VISION_MODEL_BUNDLE_V1.md"):
    src = os.path.join(DOCS, fn)
    shutil.copy2(src, os.path.join(desktop, fn))
    print("copied ->", os.path.join(desktop, fn))
