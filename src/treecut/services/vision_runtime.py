# -*- coding: utf-8 -*-
"""TreeCut Stage 2 — VisionRuntimeProvider（视觉运行时抽象）。

业务代码禁止直接写 .cuda()/.to("cuda")；统一经本 Provider 获取 backend/设备。
backend 由 benchmark 决定，运行时可探测并回退：
  PYTORCH_CUDA → ONNX_* → PYTORCH_CPU
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RuntimeInfo:
    backend: str = "PYTORCH_CPU"
    device: str = "cpu"
    precision: str = "fp32"
    available_vram_mb: int = 0
    torch_cuda: bool = False
    onnx_providers: list = field(default_factory=list)
    # 模型目录必须为纯 ASCII 路径（sentencepiece/onnx 等 C++ 后端不支持中文路径）
    models_dir: Path = Path(r"C:\Users\admin\dsh_models")


class VisionRuntimeProvider:
    """探测并选择可用视觉运行时；统一 device/backend 出口。"""

    def __init__(self, models_dir: str | Path | None = None):
        if models_dir:
            self.models_dir = Path(models_dir)
        else:
            self.models_dir = Path(r"C:\Users\admin\dsh_models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.info = self._probe()

    def _probe(self) -> RuntimeInfo:
        info = RuntimeInfo()
        # torch CUDA
        try:
            import torch
            if torch.cuda.is_available():
                info.backend = "PYTORCH_CUDA"
                info.device = "cuda:0"
                info.precision = "fp16"
                info.torch_cuda = True
                info.available_vram_mb = int(torch.cuda.get_device_properties(0).total_memory / 1e6)
        except Exception:
            pass
        # onnx providers
        try:
            import onnxruntime as ort
            info.onnx_providers = ort.get_available_providers()
        except Exception:
            info.onnx_providers = []
        if info.backend == "PYTORCH_CPU" and not info.onnx_providers:
            info.backend = "PYTORCH_CPU"
        return info

    # ------------------------------------------------------------------

    @property
    def device(self) -> str:
        return self.info.device

    @property
    def backend(self) -> str:
        return self.info.backend

    def summary(self) -> dict:
        return {
            "backend": self.info.backend,
            "device": self.info.device,
            "precision": self.info.precision,
            "available_vram_mb": self.info.available_vram_mb,
            "torch_cuda": self.info.torch_cuda,
            "onnx_providers": self.info.onnx_providers,
            "models_dir": str(self.models_dir),
        }

    # ------------------------------------------------------------------
    # 模型加载/卸载（按需，业务统一调用）
    # ------------------------------------------------------------------

    _models: dict = {}

    def load_model(self, key: str, loader, *args, **kwargs):
        """加载模型并缓存（key 唯一）；重复加载返回缓存实例。"""
        if key in self._models:
            return self._models[key]
        model = loader(*args, **kwargs)
        self._models[key] = model
        return model

    def unload_model(self, key: str) -> None:
        if key in self._models:
            del self._models[key]
            import gc
            gc.collect()
            if self.info.torch_cuda:
                import torch
                torch.cuda.empty_cache()

    def unload_all(self) -> None:
        for k in list(self._models):
            self.unload_model(k)

    # ------------------------------------------------------------------
    # 推理计时辅助
    # ------------------------------------------------------------------

    @staticmethod
    def timed(fn, *a, **kw):
        t0 = time.time()
        out = fn(*a, **kw)
        return out, (time.time() - t0) * 1000.0

    # ------------------------------------------------------------------
    # 真实 GPU 冒烟（STEP 3 验证：tensor → GPU → 运算 → 输出）
    # ------------------------------------------------------------------

    def gpu_smoke(self) -> dict:
        """真实 GPU 推理冒烟：随机 tensor 在 device 上做 matmul，测延迟/VRAM。"""
        res = {"backend": self.info.backend, "device": self.info.device}
        if self.info.torch_cuda:
            import torch
            dev = torch.device("cuda:0")
            a = torch.randn(512, 512, device=dev)
            b = torch.randn(512, 512, device=dev)
            torch.cuda.synchronize()
            t0 = time.time()
            for _ in range(20):
                c = a @ b
            torch.cuda.synchronize()
            dt = (time.time() - t0) / 20 * 1000
            res["matmul_512x512_ms"] = round(dt, 3)
            res["output_shape"] = list(c.shape)
            res["vram_allocated_mb"] = round(torch.cuda.memory_allocated() / 1e6, 1)
            res["vram_reserved_mb"] = round(torch.cuda.memory_reserved() / 1e6, 1)
        else:
            res["note"] = "no CUDA runtime; GPU smoke skipped (CPU path active)"
        return res
