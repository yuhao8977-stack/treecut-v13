"""One truthful inventory for every optional AI model used by TreeCut."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from treecut.platform.capabilities import Capabilities


@dataclass(frozen=True)
class ModelStatus:
    purpose: str
    selected_name: str
    ready: bool
    fallback: str
    explanation: str
    files_complete: bool = False
    runtime_compatible: bool = False
    load_verified: bool = False
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def build_model_registry(c: Capabilities) -> dict[str, ModelStatus]:
    """Return user-facing status; never equate a code stub with a usable model."""
    details = c.model_checks or {}

    def status(key: str, purpose: str, selected: str, fallback: str,
               explanation: str, declared_ready: bool) -> ModelStatus:
        detail = details.get(key) or {}
        files = bool(detail.get("files_complete", declared_ready))
        runtime = bool(detail.get("runtime_compatible", declared_ready))
        verified = bool(detail.get("load_verified", False))
        issues = tuple(detail.get("issues") or ())
        return ModelStatus(
            purpose, selected, files and runtime, fallback, explanation,
            files, runtime, verified, issues,
        )

    vision_key = "qwen_vl" if c.cuda_available and c.qwen_vl_ready else "florence"
    return {
        "vision": status(
            vision_key, "理解视频画面",
            "Qwen3-VL" if vision_key == "qwen_vl" else "Florence-2",
            "文件名低置信度分类", "NVIDIA 显存至少 10 GB 时尝试 Qwen，其他电脑使用 Florence；Qwen 失败自动回退。",
            c.qwen_vl_ready if vision_key == "qwen_vl" else c.florence_ready,
        ),
        "speech": status(
            "whisper", "识别人声并生成时间轴", "Faster-Whisper", "不生成语音时间轴",
            "安装版统一使用本地 Faster-Whisper，避免重复语音模型和运行库。", c.whisper_ready,
        ),
        "object_detection": status(
            "florence", "识别人、产品等物体", "Florence-2 Object Detection",
            "使用 Florence 画面描述", "与画面理解共用同一套本地模型，减少重复权重和授权风险。",
            c.florence_ready,
        ),
        "image_text_matching": status(
            "chinese_clip", "用中文文案匹配画面", "Chinese-CLIP",
            "使用画面描述、语音、标签和关键词匹配", "v13 核心版不依赖该可选模型；必须同时存在代码与本地权重才算可用。",
            c.chinese_clip_ready,
        ),
        "text_embedding": status(
            "bge_m3", "素材语义搜索", "BGE-M3",
            "使用字符、关键词与明确用户反馈", "v13 核心版不依赖该可选模型；以后可用于大规模多语言语义检索。",
            c.bge_m3_ready,
        ),
        "tts": status(
            "local_tts", "离线配音", "Sherpa-ONNX VITS 中英双语",
            "暂不配音", "完全离线运行，不依赖网络服务。",
            c.local_tts_ready,
        ),
    }


def missing_models(registry: dict[str, ModelStatus]) -> list[str]:
    return [name for name, status in registry.items() if not status.ready]
