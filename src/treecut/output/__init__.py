"""Draft and rendered-video output adapters."""

from .mp4 import RenderResult, render_video_plan
from .narration import (
    NarratedResult, build_srt, burn_subtitles, create_narrated_video,
    mix_background_music, validate_narration_fit,
)
from .jianying import DraftResult, build_jianying_draft

__all__ = ["RenderResult", "render_video_plan", "NarratedResult", "build_srt",
           "burn_subtitles", "create_narrated_video", "mix_background_music",
           "validate_narration_fit",
           "DraftResult", "build_jianying_draft"]
