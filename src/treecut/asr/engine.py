"""P2: ASR engine — faster-whisper small first, medium fallback.

保存 raw transcript + corrected 分离、时间戳、语言、置信度、model_version。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AsrResult:
    segments: tuple[dict, ...]       # [{start_ms,end_ms,text_raw,text_corrected,confidence}]
    full_text_raw: str = ""
    full_text_corrected: str = ""
    language: str = ""
    model_name: str = ""
    model_version: str = ""
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class WhisperEngine:
    """faster-whisper 封装。先 small；中文口播 Benchmark 不足可换 medium。

    device ∈ {auto, cpu, cuda}：
      - auto: 自动检测（GPU 可用且显存充足 → cuda/float16，否则 cpu/int8）
      - cpu:  强制 CPU (int8)
      - cuda: 强制 GPU (float16)，不可用则抛错
    """

    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "auto", language: str = "zh"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None
        self._device_decision = None

    @property
    def device_decision(self):
        """返回 DeviceDecision（在首次加载后可用）。"""
        return self._device_decision

    def _resolve_device(self):
        """把 auto/cpu/cuda 解析为 (device, compute_type)。"""
        from treecut.asr.device_manager import detect_device, apply_cuda_dll_path
        if self.device == "auto":
            apply_cuda_dll_path()  # 先注入 TREECUT_CUDA_DLL_DIR 目录（若有）
            decision = detect_device("auto")
        else:
            apply_cuda_dll_path()
            decision = detect_device(self.device)
        self._device_decision = decision
        if self.compute_type and self.compute_type != "auto":
            return decision.device, self.compute_type
        return decision.device, decision.compute_type

    def _lazy_load(self):
        if self._model is None:
            # 离线优先：模型已在本地 HF 缓存（避免在线下载/SSL 失败）
            import os as _os
            _os.environ.setdefault("HF_HUB_OFFLINE", "1")
            _os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            # v13 bootstrap 会把 HF_HOME 指向数据目录缓存；若那里没有模型，
            # 回退到用户级 HF 缓存（~/.cache/huggingface），否则离线找不到模型
            user_hf = str(Path.home() / ".cache" / "huggingface")
            current_hf = _os.environ.get("HF_HOME", "")
            model_dir_name = f"models--Systran--faster-whisper-{self.model_size}"
            if not (Path(current_hf) / "hub" / model_dir_name).exists() and \
               (Path(user_hf) / "hub" / model_dir_name).exists():
                _os.environ["HF_HOME"] = user_hf
            device, compute_type = self._resolve_device()
            import logging
            logging.getLogger("treecut.asr").info(
                "WhisperEngine 设备决策: device=%s compute_type=%s (%s)",
                device, compute_type,
                self._device_decision.reason if self._device_decision else "")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self.model_size, device=device,
                                       compute_type=compute_type)

    def transcribe(self, video_path: str | Path) -> AsrResult:
        started = time.perf_counter()
        self._lazy_load()
        segments_raw, info = self._model.transcribe(
            str(video_path), language=self.language, vad_filter=True)
        segments = []
        for seg in segments_raw:
            text = (seg.text or "").strip()
            if not text:
                continue
            start = int(seg.start * 1000)
            end = int(seg.end * 1000)
            segments.append({
                "start_ms": start,
                "end_ms": end,
                "text_raw": text,
                "text_corrected": text,   # 人工修正版初始=raw，P3 人工纠错覆盖
                "confidence": float(getattr(seg, "avg_logprob", 0) or 0),
            })
        return AsrResult(
            segments=tuple(segments),
            full_text_raw="".join(s["text_raw"] for s in segments),
            full_text_corrected="".join(s["text_corrected"] for s in segments),
            language=getattr(info, "language", "") or self.language,
            model_name=f"faster-whisper-{self.model_size}",
            model_version=self.model_size,
            seconds=round(time.perf_counter() - started, 3),
        )
