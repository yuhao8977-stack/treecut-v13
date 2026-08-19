"""Truthful success contract for one persisted material-analysis result."""
from __future__ import annotations


class AnalysisContractError(RuntimeError):
    """Raised when required analysis evidence is missing or failed."""


def evaluate_analysis_contract(result: dict) -> dict:
    media = result.get("media") or {}
    frames = result.get("frames") or []
    vision = result.get("vision") or {}
    speech = result.get("speech") or {}
    objects = result.get("objects") or {}
    evidence = result.get("evidence") or {}
    required_failures: list[str] = []
    optional_warnings: list[str] = []
    if not bool(evidence.get("media_probed")):
        required_failures.append("媒体参数没有完成真实探测")
    if len(frames) < 1 or int(evidence.get("frames_extracted") or 0) < 1:
        required_failures.append("没有抽取到有效视频帧")
    if not bool(evidence.get("vision_completed")):
        required_failures.append("画面模型没有完成推理")
    if vision.get("error"):
        required_failures.append(f"画面模型失败：{vision['error']}")
    if not (vision.get("captions") or []):
        required_failures.append("画面模型没有返回有效描述")
    if bool(media.get("has_audio")):
        if not bool(evidence.get("speech_attempted")):
            required_failures.append("视频有音轨，但语音模型没有运行")
        if not bool(evidence.get("speech_completed")):
            required_failures.append("视频有音轨，但语音分析没有完成")
        if speech.get("error"):
            required_failures.append(f"语音模型失败：{speech['error']}")
    if evidence.get("object_detection_expected") and not evidence.get("object_detection_completed"):
        detail = objects.get("error") or "物体检测没有完成"
        optional_warnings.append(f"YOLO降级：{detail}")
    status = "failed" if required_failures else ("degraded" if optional_warnings else "complete")
    return {"status": status, "required_passed": not required_failures,
            "required_failures": required_failures, "optional_warnings": optional_warnings}


def require_complete_analysis(result: dict) -> dict:
    completion = evaluate_analysis_contract(result)
    result["completion"] = completion
    if not completion["required_passed"]:
        raise AnalysisContractError("；".join(completion["required_failures"]))
    return completion
