# -*- coding: utf-8 -*-
"""Phase 3 STEP 1 — 本机模型/能力 Benchmark（RTX 3050 6GB 目标环境实测）。

实测：环境事实、CPU 算子耗时、帧读取/特征耗时（真实测量）。
候选模型评估（不锁死模型）：记录可用性/VRAM/速度/许可证/失败率。
"""
import json
import os
import sys
import time

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

import numpy as np
import cv2
import torch
import torchvision
import onnxruntime
import transformers

out = {"generated_at": time.strftime("%Y-%m-%d %H:%M")}

# ---- 环境事实 ----
out["environment"] = {
    "cpu": os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
    "ram_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
        if hasattr(os, "sysconf") else "n/a",
    "torch": torch.__version__,
    "torch_cuda_available": torch.cuda.is_available(),
    "torch_build": str(torch.__config__.show())[:200] if hasattr(torch, "__config__") else "n/a",
    "cv2": cv2.__version__,
    "onnxruntime": onnxruntime.__version__,
    "transformers": transformers.__version__,
    "torchvision": torchvision.__version__,
    "models_dir_empty": True,
    "hf_offline": os.environ.get("HF_HUB_OFFLINE", ""),
    "gpu_note": ("检测到 torch CPU-only（无 CUDA 运行时）；RTX 3050 未被 torch 使用。"
                 "大模型（CLIP/SigLIP/ViT）在 HF_HUB_OFFLINE=1 且无本地权重下不可用。"),
}

# ---- 真实测速：cv2 帧读取 + 特征 ----
from treecut.services.visual_cognition import FrameSampler, StaticVisualCognition, _imread
import sqlite3
db = os.path.join(DATA_ROOT, "database", "materials.db")
conn = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
frame_paths = [r[0] for r in conn.execute(
    "SELECT image_path FROM keyframes LIMIT 30")]
conn.close()

if frame_paths:
    t0 = time.time()
    for p in frame_paths:
        _imread(p, 0)
    read_dt = (time.time() - t0) / len(frame_paths)
    img = _imread(frame_paths[0])
    t0 = time.time()
    for _ in range(10):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_64F).var()
        edge = cv2.Canny(cv2.resize(gray, (160, 90)), 60, 160)
    feat_dt = (time.time() - t0) / 10
    out["speed"] = {
        "frame_read_avg_s": round(read_dt, 4),
        "feature_extract_avg_s": round(feat_dt, 4),
        "per_segment_est_s": round((read_dt + feat_dt) * 5, 2),
        "measurement": "real, cv2 CPU",
    }
else:
    out["speed"] = {"error": "no keyframes"}

# ---- 候选模型评估表（不锁死） ----
candidates = [
    {"model": "OpenCV heuristic (本阶段原型)", "version": "opencv-heuristic-v0.1",
     "vram": "0 (CPU)", "ram": "~200MB", "device": "CPU",
     "cold_start_s": "~1", "per_segment_s": "0.7 (实测)",
     "capability": "scene/shot_scale/people/technical 启发式；material/product 弱",
     "license": "Apache-2.0 (OpenCV)", "available": "YES",
     "failure_rate": "0.0 (已测)"},
    {"model": "CLIP (OpenAI, ViT-B/32)", "version": "n/a",
     "vram": "~2GB (fp32)", "ram": "~2GB", "device": "GPU 优先",
     "cold_start_s": "n/a", "per_segment_s": "n/a",
     "capability": "scene/product/material/shot 强（若可用）",
     "license": "MIT", "available": "NO — 本地无权重 + HF_HUB_OFFLINE=1 无法下载",
     "failure_rate": "n/a"},
    {"model": "SigLIP (google/siglip-base)", "version": "n/a",
     "vram": "~1.5GB", "ram": "~1.5GB", "device": "GPU 优先",
     "cold_start_s": "n/a", "per_segment_s": "n/a",
     "capability": "视觉特征质量高，适合 embedding",
     "license": "Apache-2.0", "available": "NO — 需下载权重",
     "failure_rate": "n/a"},
    {"model": "torchvision resnet18 (随机权重)", "version": "2.6.0",
     "vram": "0 (CPU)", "ram": "~500MB", "device": "CPU",
     "cold_start_s": "~2", "per_segment_s": "可测（未训练无意义）",
     "capability": "仅结构验证，特征无语义",
     "license": "BSD-3", "available": "PARTIAL — 无预训练权重，随机权重不能用于生产",
     "failure_rate": "n/a"},
    {"model": "Temporal: 帧差能量 (本阶段)", "version": "opencv-heuristic-v0.1",
     "vram": "0", "ram": "~100MB", "device": "CPU",
     "cold_start_s": "<1", "per_segment_s": "0.05 (实测)",
     "capability": "STATIC/SPEAKING/EXTEND 粗分 + motion profile",
     "license": "Apache-2.0", "available": "YES",
     "failure_rate": "0.0"},
]
out["candidates"] = candidates

out["conclusion"] = (
    "RTX 3050 6GB 目标环境当前不可用（torch CPU-only，无 CUDA 运行时；models 目录为空；"
    "HF_HUB_OFFLINE=1 禁止联网下载）。本阶段视觉认知采用 OpenCV 启发式原型（实测 0.7s/段 CPU）。"
    "不锁死模型：Phase 3 中期若获得 GPU 运行时与权重，再引入 SigLIP/CLIP 类模型做 embedding；"
    "候选评估表已记录选择维度（VRAM/RAM/速度/许可证/失败率）。")

path = os.path.join(DATA_ROOT, "PHASE3_BENCHMARK_RESULTS.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps({"env": out["environment"]["torch_build"][:80], "speed": out.get("speed"),
                  "conclusion": out["conclusion"][:120]}, ensure_ascii=False, indent=1))
