"""Select one portable model plan from truthful capabilities."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from treecut.platform.capabilities import Capabilities


@dataclass(frozen=True)
class ModelPlan:
    profile: str
    vision: str
    speech: str
    object_detection: str
    image_text_matching: str
    text_embedding: str
    tts: str

    def to_dict(self) -> dict:
        return asdict(self)


def select_model_plan(c: Capabilities, requested_mode: str = "auto",
                      vision_preference: str = "auto") -> ModelPlan:
    if requested_mode not in {"auto", "cpu", "nvidia"}:
        raise ValueError(f"不支持的模型模式: {requested_mode}")
    if vision_preference not in {"auto", "florence", "qwen"}:
        raise ValueError(f"不支持的视觉模型选择: {vision_preference}")
    if requested_mode == "nvidia" and not (
        c.cuda_available and c.cuda_vram_gb >= 10 and c.qwen_vl_ready
    ):
        raise RuntimeError("已指定 NVIDIA 模式，但没有检测到可用的 10GB 以上显存、CUDA 运行时和完整 Qwen 模型")
    if vision_preference == "qwen":
        if not (c.cuda_available and c.cuda_vram_gb >= 10 and c.qwen_vl_ready):
            raise RuntimeError("已指定本地 Qwen 视觉模型，但未检测到可用的 10GB 以上显存、CUDA 运行时和完整 Qwen 模型")
        profile = "nvidia"
        vision = "qwen3-vl-4b"
    elif vision_preference == "florence":
        profile = "cpu" if c.florence_ready else "minimal"
        vision = "florence-2-base" if c.florence_ready else "unavailable"
    elif requested_mode != "cpu" and c.cuda_available and c.cuda_vram_gb >= 10 and c.qwen_vl_ready:
        profile = "nvidia"
        vision = "qwen3-vl-4b"
    elif c.florence_ready:
        profile = "cpu"
        vision = "florence-2-base"
    else:
        profile = "minimal"
        vision = "unavailable"

    speech = "whisper" if c.whisper_ready else "unavailable"
    return ModelPlan(
        profile=profile,
        vision=vision,
        speech=speech,
        object_detection="florence-2-base-od" if c.florence_ready else "unavailable",
        image_text_matching="chinese-clip-vit-base-patch16" if c.chinese_clip_ready else "unavailable",
        text_embedding="bge-m3" if c.bge_m3_ready else "unavailable",
        tts="sherpa-onnx-vits-zh-en" if c.local_tts_ready else "unavailable",
    )
