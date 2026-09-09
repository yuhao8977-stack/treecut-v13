"""Unified model selection and adapters."""

from .speech_whisper import WhisperTranscriber
from .vision_qwen import QwenVision

__all__ = ["QwenVision", "WhisperTranscriber"]
