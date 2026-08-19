"""Truthful hardware and model capability detection."""
from __future__ import annotations

import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import RuntimePaths


@dataclass(frozen=True)
class Capabilities:
    computer: str
    cpu_threads: int
    ram_gb: float
    cuda_available: bool
    cuda_vram_gb: float
    model_root: str
    florence_ready: bool
    qwen_vl_ready: bool
    sensevoice_ready: bool
    whisper_ready: bool
    yolo_ready: bool
    chinese_clip_ready: bool = False
    bge_m3_ready: bool = False
    local_tts_ready: bool = False
    model_checks: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _ram_gb() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().total / 2**30, 1)
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes

            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatus()
            status.dwLength = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return round(status.ullTotalPhys / 2**30, 1)
        except Exception:
            pass
    return 0.0


def _cuda() -> tuple[bool, float]:
    try:
        import torch
        if not torch.cuda.is_available():
            return False, 0.0
        props = torch.cuda.get_device_properties(0)
        return True, round(props.total_memory / 2**30, 1)
    except Exception:
        return False, 0.0


def detect_capabilities(paths: RuntimePaths | None = None) -> Capabilities:
    paths = paths or RuntimePaths.discover()
    cuda_available, cuda_vram_gb = _cuda()
    models = paths.models
    try:
        import torch
        cuda_runtime = bool(torch.version.cuda)
    except Exception:
        cuda_runtime = False
    whisper_dir = Path(os.environ.get("TREECUT_WHISPER_MODEL", models / "Whisper-small"))
    yolo_file = Path(os.environ.get("TREECUT_YOLO_MODEL", models / "yolov8n.pt"))
    clip_dir = Path(os.environ.get("TREECUT_CLIP_MODEL", models / "Chinese-CLIP-ViT-B-16"))
    bge_dir = Path(os.environ.get("TREECUT_BGE_MODEL", models / "BGE-M3"))
    tts_dir = Path(os.environ.get("TREECUT_TTS_MODEL", models / "LocalTTS"))
    from treecut.models.validation import inspect_model_contracts
    checks = inspect_model_contracts(
        models, cuda_available=cuda_available, cuda_runtime=cuda_runtime,
        locations={"whisper": whisper_dir, "yolo": yolo_file,
                   "chinese_clip": clip_dir, "bge_m3": bge_dir,
                   "local_tts": tts_dir},
        verification_receipt=paths.data_root / "model_verification.json",
    )
    return Capabilities(
        computer=platform.node(),
        cpu_threads=os.cpu_count() or 1,
        ram_gb=_ram_gb(),
        cuda_available=cuda_available,
        cuda_vram_gb=cuda_vram_gb,
        model_root=str(models),
        florence_ready=checks["florence"].ready,
        qwen_vl_ready=checks["qwen_vl"].ready,
        sensevoice_ready=checks["sensevoice"].ready,
        whisper_ready=checks["whisper"].ready,
        yolo_ready=checks["yolo"].ready,
        chinese_clip_ready=checks["chinese_clip"].ready,
        bge_m3_ready=checks["bge_m3"].ready,
        local_tts_ready=checks["local_tts"].ready,
        model_checks={name: check.to_dict() for name, check in checks.items()},
    )
