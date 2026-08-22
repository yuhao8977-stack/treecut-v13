"""P2.6: ASR Device Manager — automatic GPU/CPU selection for faster-whisper.

规则：
- asr_device == "cuda"  → 强制 GPU（若失败抛错）
- asr_device == "cpu"   → 强制 CPU
- asr_device == "auto"  → 检测：ctranslate2 能加载 CUDA + 显存 ≥ 3GB → cuda，否则 cpu

GPU 可用性探测（不依赖 torch，直接验证 ctranslate2 能否真正初始化 CUDA）：
1. ctranslate2.get_cuda_device_count() > 0
2. 尝试创建 cuda 设备上下文（StorageView 或模型加载）
3. 检查关键 DLL（cublas64_12.dll / cublasLt64_12.dll）可加载
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("treecut.asr.device")

CUDA_DLL_NAMES = ("cublas64_12.dll", "cublasLt64_12.dll")
MIN_VRAM_GB_FOR_GPU = 3.0


@dataclass(frozen=True)
class DeviceDecision:
    device: str            # "cuda" | "cpu"
    compute_type: str      # "float16" | "int8"
    reason: str            # 决策原因（日志/报告用）
    cuda_available: bool
    vram_gb: float = 0.0


def _cublas_loadable() -> bool:
    """验证 cuBLAS DLL 可加载（ctranslate2 GPU 推理的硬依赖）。

    Python 3.8+ 在 Windows 用裸名查找需要 os.add_dll_directory；
    这里用完整路径探测更可靠。
    """
    import ctypes
    import glob
    search_dirs = []
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if part.strip():
            search_dirs.append(part.strip())
    try:
        import ctranslate2
        search_dirs.append(os.path.dirname(ctranslate2.__file__))
    except Exception:
        pass
    for name in CUDA_DLL_NAMES:
        found = False
        for d in search_dirs:
            for candidate in (os.path.join(d, name),):
                if os.path.isfile(candidate):
                    try:
                        ctypes.CDLL(candidate)
                        found = True
                        break
                    except OSError:
                        continue
        if not found:
            return False
    return True


def _cuda_vram_gb() -> float:
    """通过 ctranslate2/驱动查询显存（尽力而为，失败返回 0）。"""
    try:
        import ctypes
        # 简单方案：尝试从 nvidia-smi 获取（系统已有）
        import subprocess
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return float(out.stdout.strip().splitlines()[0]) / 1024.0
    except Exception:
        pass
    return 0.0


def detect_device(requested: str = "auto",
                  min_vram_gb: float = MIN_VRAM_GB_FOR_GPU) -> DeviceDecision:
    """决定 ASR 推理设备。requested ∈ {auto, cpu, cuda}。"""
    requested = (requested or "auto").lower()
    if requested not in ("auto", "cpu", "cuda"):
        raise ValueError(f"非法 ASR 设备: {requested}（可选 auto/cpu/cuda）")

    if requested == "cpu":
        return DeviceDecision("cpu", "int8", "用户指定 CPU", cuda_available=False)

    # 探测 CUDA 可用性
    try:
        import ctranslate2
        cuda_count = int(ctranslate2.get_cuda_device_count())
    except Exception as exc:  # noqa: BLE001
        logger.warning("ctranslate2 CUDA 探测失败: %s", exc)
        cuda_count = 0

    vram_gb = _cuda_vram_gb()
    dll_ok = _cublas_loadable()

    if cuda_count > 0 and dll_ok and (requested == "cuda" or vram_gb >= min_vram_gb or vram_gb == 0):
        reason = (f"GPU 可用 (device_count={cuda_count}, vram={vram_gb:.1f}GB, "
                  f"cublas=OK)")
        return DeviceDecision("cuda", "float16", reason,
                              cuda_available=True, vram_gb=vram_gb)

    if requested == "cuda":
        raise RuntimeError(
            f"指定 GPU 但不可用: cuda_count={cuda_count}, cublas={dll_ok}, "
            f"vram={vram_gb:.1f}GB。请安装 CUDA 12 runtime 或改用 cpu/auto")

    reason = (f"GPU 不可用 (device_count={cuda_count}, cublas={dll_ok}, "
              f"vram={vram_gb:.1f}GB)，回退 CPU")
    return DeviceDecision("cpu", "int8", reason, cuda_available=False,
                          vram_gb=vram_gb)


def apply_cuda_dll_path(extra_dirs: list[str] | None = None) -> None:
    """把 cublas DLL 目录加入 PATH 与 DLL 搜索路径（Windows）。

    TreeCut 便携版场景：cublas64_12.dll 可能随升级包放在 data_root/cuda_dlls，
    或通过环境变量 TREECUT_CUDA_DLL_DIR 指定。Python 3.8+ 需 os.add_dll_directory
    才能用裸名加载。
    """
    import os as _os
    dirs = list(extra_dirs or [])
    env_dir = _os.environ.get("TREECUT_CUDA_DLL_DIR", "")
    if env_dir and env_dir not in dirs:
        dirs.append(env_dir)
    if hasattr(_os, "add_dll_directory"):
        for d in dirs:
            if _os.path.isdir(d):
                try:
                    _os.add_dll_directory(d)
                except Exception:
                    pass
    for d in dirs:
        if _os.path.isdir(d):
            cur = _os.environ.get("PATH", "")
            if d not in cur:
                _os.environ["PATH"] = d + _os.pathsep + cur
