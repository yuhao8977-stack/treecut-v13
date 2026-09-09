"""B1 — Narration duration contract (fail-closed).

The REAL measured narration duration is the only authority. BGM is never counted
as narration. Strategies:
  FIT_SCRIPT_TO_TARGET     expand/trim script to hit target (requires a script
                           generator; B1 raises NotImplementedError instead of
                           silently padding)
  FIT_VIDEO_TO_NARRATION   keep user script; video obeys real narration length
  STRICT_REJECT            default; narration/target mismatch fails the job
Hard gates: narration coverage >= 95%, ordinary tail <= 0.8s, no silent empty
clips, no extreme speed stretching (caller enforces speed only in natural range).
"""
from __future__ import annotations

from dataclasses import dataclass

ALLOWED_TAIL_S = 0.8
MIN_COVERAGE = 0.95

FIT_SCRIPT_TO_TARGET = "fit_script_to_target"
FIT_VIDEO_TO_NARRATION = "fit_video_to_narration"
STRICT_REJECT = "strict_reject"
STRATEGIES = (FIT_SCRIPT_TO_TARGET, FIT_VIDEO_TO_NARRATION, STRICT_REJECT)

NARRATION_TOO_SHORT = "NARRATION_TOO_SHORT"
NARRATION_TOO_LONG = "NARRATION_TOO_LONG"
VOICE_COVERAGE_LOW = "VOICE_COVERAGE_LOW"
VOICE_TAIL_TOO_LONG = "VOICE_TAIL_TOO_LONG"
BGM_ONLY_AUDIO = "BGM_ONLY_AUDIO"
DURATION_CONTRACT_NOT_RUN = "DURATION_CONTRACT_NOT_RUN"
FAIL_CODES = (NARRATION_TOO_SHORT, NARRATION_TOO_LONG, VOICE_COVERAGE_LOW,
              VOICE_TAIL_TOO_LONG, BGM_ONLY_AUDIO, DURATION_CONTRACT_NOT_RUN)


def resolve_plan_duration(strategy: str, target_duration: float,
                          narration_duration: float) -> float:
    """Video plan duration under the strategy (strict: fixed target; fit_video:
    real narration length; fit_script: needs a generator -> explicit error)."""
    if strategy == STRICT_REJECT:
        return float(target_duration)
    if strategy == FIT_VIDEO_TO_NARRATION:
        return float(narration_duration)
    raise NotImplementedError(
        "B1: FIT_SCRIPT_TO_TARGET needs a script generator (Beat/Claim layer is "
        "not in scope); use fit_video_to_narration or strict_reject - never "
        "silently pad empty footage")


@dataclass(frozen=True)
class DurationContract:
    passed: bool
    code: str | None
    fields: dict
    reason: str = ""

    def to_dict(self) -> dict:
        return {"passed": self.passed, "code": self.code, "fields": self.fields,
                "reason": self.reason}


def check_duration_contract(*, strategy: str, target_duration: float,
                            narration_duration: float, video_duration: float,
                            intentional_outro: bool = False) -> DurationContract:
    """Evaluate the contract against REAL measured durations. video_duration is
    the final (planned/measured) video length; for STRICT it equals target."""
    if narration_duration <= 0:
        return DurationContract(False, BGM_ONLY_AUDIO,
                                {"narration_duration": narration_duration}, "无旁白音频")
    if video_duration <= 0:
        return DurationContract(False, DURATION_CONTRACT_NOT_RUN,
                                {"video_duration": video_duration}, "无画面时长")
    tail = round(video_duration - narration_duration, 3)
    coverage = round(narration_duration / video_duration, 4) if video_duration else 0.0
    fields = {
        "narration_duration": round(narration_duration, 3),
        "video_duration": round(video_duration, 3),
        "narration_coverage": coverage,
        "narration_tail_gap": tail,
        "intentional_outro": bool(intentional_outro),
        "duration_contract_pass": None,
    }
    if strategy == STRICT_REJECT:
        # narration must fill the target within the allowed tail
        if narration_duration < target_duration - ALLOWED_TAIL_S:
            fields["duration_contract_pass"] = False
            return DurationContract(False, NARRATION_TOO_SHORT, fields,
                                    f"旁白 {narration_duration:.2f}s 短于目标 "
                                    f"{target_duration:.2f}s 超过 {ALLOWED_TAIL_S}s")
        if narration_duration > video_duration + 0.05:
            fields["duration_contract_pass"] = False
            return DurationContract(False, NARRATION_TOO_LONG, fields,
                                    f"旁白 {narration_duration:.2f}s 长于画面 "
                                    f"{video_duration:.2f}s")
    if coverage < MIN_COVERAGE:
        fields["duration_contract_pass"] = False
        return DurationContract(False, VOICE_COVERAGE_LOW, fields,
                                f"旁白覆盖率 {coverage:.1%} < {MIN_COVERAGE:.0%}")
    if tail > ALLOWED_TAIL_S and not intentional_outro:
        fields["duration_contract_pass"] = False
        return DurationContract(False, VOICE_TAIL_TOO_LONG, fields,
                                f"空尾 {tail:.2f}s > {ALLOWED_TAIL_S}s 且非声明片尾")
    fields["duration_contract_pass"] = True
    return DurationContract(True, None, fields, "时长契约通过")
