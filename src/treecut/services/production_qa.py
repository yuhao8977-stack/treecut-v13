"""STAGE8 G5 — ProductionQAService：分层 QA + P0 门禁 + 规则注册表。

§50-§56。分层: TECHNICAL/SOURCE/SEMANTIC/PRODUCTION/HUMAN；不塌缩成单一分数。
任何 P0 FAIL → 禁止 READY_FOR_HUMAN_REVIEW。历史机器结果与人工结果分开持久化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

P0_KEYS = ("DIRTY_SOURCE", "UNSUPPORTED_CORE_CLAIM", "WRONG_ACTION", "WRONG_FUNCTION_VISUAL",
           "AV_DURATION_MISMATCH", "VIDEO_END_BEFORE_AUDIO", "NEW_CAPTION_MISSING", "MAJOR_DUPLICATE")


@dataclass
class QAResult:
    gate: str
    key: str
    status: str   # PASS | WARNING | FAIL
    detail: str = ""
    layer: str = ""

    def to_dict(self):
        return {"gate": self.gate, "key": self.key, "status": self.status,
                "detail": self.detail, "layer": self.layer}


# ---- 原子检查(显式输入, 可单测) ----
def check_av_sync(vdur_s, adur_s, tol=0.10) -> QAResult:
    ok = vdur_s and adur_s and abs(vdur_s - adur_s) <= tol
    return QAResult("TECHNICAL", "AV_SYNC", "PASS" if ok else "FAIL",
                    f"|video-audio|={abs((vdur_s or 0) - (adur_s or 0)):.3f}s tol={tol}s", "TECHNICAL")


def check_video_tail(vdur_s, adur_s) -> QAResult:
    ok = bool(vdur_s) and vdur_s >= (adur_s or 0) - 0.05
    return QAResult("TECHNICAL", "VIDEO_TAIL_VALID", "PASS" if ok else "FAIL",
                    f"video {vdur_s}s vs audio {adur_s}s", "TECHNICAL")


def check_caption_rendered(rendered: bool) -> QAResult:
    return QAResult("TECHNICAL", "CAPTION_RENDERED", "PASS" if rendered else "FAIL",
                    "new caption burned into final?", "TECHNICAL")


def check_caption_size(fontsize: int, allowed=(62, 68)) -> QAResult:
    if allowed[0] <= fontsize <= allowed[1]:
        return QAResult("TECHNICAL", "CAPTION_READABLE", "PASS", f"FontSize {fontsize}", "TECHNICAL")
    return QAResult("TECHNICAL", "CAPTION_READABLE", "WARNING",
                    f"FontSize {fontsize} 超出 {allowed}(V2 债务: 55 太小)", "TECHNICAL")


def check_voice_provider(provider: str, production_ready: bool) -> QAResult:
    ok = provider != "SAPI" or production_ready
    return QAResult("TECHNICAL", "VOICE_PROVIDER_VALID", "PASS" if ok else "WARNING",
                    f"provider={provider} (SAPI=FALLBACK, 非主声)", "TECHNICAL")


def check_bgm(bgm_present: bool, required: bool = True) -> QAResult:
    if required and not bgm_present:
        return QAResult("PRODUCTION", "BGM_PRESENT_IF_REQUIRED", "WARNING", "BGM missing(限制)", "PRODUCTION")
    return QAResult("PRODUCTION", "BGM_PRESENT_IF_REQUIRED", "PASS", "bgm ok/未要求", "PRODUCTION")


def check_loudness(lufs: float, tp_dbtp: float) -> QAResult:
    ok = (-16.5 <= lufs <= -13.5) and tp_dbtp <= -1.0
    return QAResult("TECHNICAL", "AUDIO_LOUDNESS_VALID", "PASS" if ok else "WARNING",
                    f"I={lufs} LUFS TP={tp_dbtp} dBTP", "TECHNICAL")


def check_source_eligibility(eligible: bool, role: str) -> QAResult:
    return QAResult("SOURCE", "SOURCE_PRODUCTION_ELIGIBLE", "PASS" if eligible else "FAIL",
                    f"role={role} eligible={eligible}", "SOURCE")


def check_no_old_subtitle(burned: str) -> QAResult:
    return QAResult("SOURCE", "NO_OLD_SUBTITLE", "PASS" if burned != "PRESENT" else "FAIL",
                    f"burned={burned}", "SOURCE")


def check_no_watermark(wm: str) -> QAResult:
    return QAResult("SOURCE", "NO_PLATFORM_WATERMARK", "PASS" if wm != "PRESENT" else "FAIL",
                    f"wm={wm}", "SOURCE")


def check_claim_supported(supported: bool, claim_id: str) -> QAResult:
    return QAResult("SEMANTIC", "CLAIM_SUPPORTED", "PASS" if supported else "FAIL",
                    f"claim {claim_id} unsupported → UNSUPPORTED_CORE_CLAIM(P0)", "SEMANTIC")


def check_action_demonstrated(level: str, required: str) -> QAResult:
    ok = level in ("ACTION_DEMONSTRATION_COMPLETE", "ACTION_IN_PROGRESS", "ACTION_END") or \
         (required is None)
    return QAResult("SEMANTIC", "ACTION_DEMONSTRATED", "PASS" if ok else "FAIL",
                    f"require {required} level={level} → WRONG_ACTION(P0)", "SEMANTIC")


def check_beat_visual_alignment(match: bool) -> QAResult:
    return QAResult("SEMANTIC", "BEAT_VISUAL_ALIGNMENT", "PASS" if match else "FAIL",
                    "口播与画面语义不匹配 → WRONG_FUNCTION_VISUAL(P0)", "SEMANTIC")


def check_story_consistent(consistent: bool) -> QAResult:
    return QAResult("SEMANTIC", "STORY_ENTITY_CONSISTENT", "PASS" if consistent else "WARNING",
                    "story mode 一致性", "SEMANTIC")


def check_dedup(hits: list) -> QAResult:
    high = [h for h in hits if h.get("strength") == "HIGH"]
    if high:
        return QAResult("PRODUCTION", "NEAR_DUPLICATE_FREE", "FAIL",
                        f"{len(high)} HIGH dedup hits → MAJOR_DUPLICATE(P0)", "PRODUCTION")
    if hits:
        return QAResult("PRODUCTION", "NEAR_DUPLICATE_FREE", "WARNING",
                        f"{len(hits)} warning-level dedup", "PRODUCTION")
    return QAResult("PRODUCTION", "NEAR_DUPLICATE_FREE", "PASS", "", "PRODUCTION")


P0_MAP = {
    "AV_SYNC": "AV_DURATION_MISMATCH", "VIDEO_TAIL_VALID": "VIDEO_END_BEFORE_AUDIO",
    "CAPTION_RENDERED": "NEW_CAPTION_MISSING", "CLAIM_SUPPORTED": "UNSUPPORTED_CORE_CLAIM",
    "ACTION_DEMONSTRATED": "WRONG_ACTION", "BEAT_VISUAL_ALIGNMENT": "WRONG_FUNCTION_VISUAL",
    "NEAR_DUPLICATE_FREE": "MAJOR_DUPLICATE", "SOURCE_PRODUCTION_ELIGIBLE": "DIRTY_SOURCE",
    "NO_OLD_SUBTITLE": "DIRTY_SOURCE", "NO_PLATFORM_WATERMARK": "DIRTY_SOURCE",
}


def verdict(results: list[QAResult]) -> dict:
    fails = [r for r in results if r.status == "FAIL"]
    warnings = [r for r in results if r.status == "WARNING"]
    p0 = []
    for r in fails:
        k = P0_MAP.get(r.key, r.key)
        if k in P0_KEYS:
            p0.append(k)
    ready = not p0
    return {"READY_FOR_HUMAN_REVIEW": ready,
            "P0_BLOCKERS": sorted(set(p0)),
            "fail_count": len(fails), "warning_count": len(warnings),
            "not_ready_reason": ("; ".join(sorted(set(p0)))) if p0 else ""}


class ProductionQAService:
    """分层运行 + 持久化(机器结果; 人工结果追加, 不覆盖)。"""

    def __init__(self, checks: list[Callable] | None = None):
        self.checks = checks or []

    def run(self, checks_input: list[QAResult]) -> dict:
        results = checks_input
        layers = {}
        for r in results:
            layers.setdefault(r.layer, []).append(r.to_dict())
        v = verdict(results)
        return {"layers": layers, "verdict": v,
                "results": [r.to_dict() for r in results]}
