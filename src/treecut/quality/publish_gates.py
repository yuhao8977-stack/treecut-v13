"""B1R1 — publish gates (pure logic): script completeness, audible-end
alignment. Terminal punctuation is mandatory; scripts may only be edited by
whole sentences/beats, never by character slicing."""
from __future__ import annotations

from dataclasses import dataclass

TERMINAL = set("。！？!?")
CLAUSE = set("，、；：,;")

SCRIPT_TRUNCATED = "SCRIPT_TRUNCATED"
SCRIPT_NO_TERMINAL_PUNCTUATION = "SCRIPT_NO_TERMINAL_PUNCTUATION"
AUDIO_GAIN_PUMPING = "AUDIO_GAIN_PUMPING"
AUDIO_TRUE_PEAK_EXCEEDED = "AUDIO_TRUE_PEAK_EXCEEDED"
AUDIBLE_END_TOO_CLOSE = "AUDIBLE_END_TOO_CLOSE"
LAST_SUBTITLE_INCOMPLETE = "LAST_SUBTITLE_INCOMPLETE"

TAIL_MIN = 0.25
TAIL_MAX = 0.8


def last_sentence(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return ""
    # split on terminal punctuation, keep last segment including its punct
    import re
    parts = [p for p in re.split(r"(?<=[。！？!?])", stripped) if p.strip()]
    return parts[-1].strip() if parts else stripped


@dataclass(frozen=True)
class GateResult:
    passed: bool
    code: str | None
    fields: dict
    reason: str = ""

    def to_dict(self) -> dict:
        return {"passed": self.passed, "code": self.code, "fields": self.fields,
                "reason": self.reason}


def check_script_completeness(text: str) -> GateResult:
    """Script must end with a COMPLETE sentence and terminal punctuation.
    SCRIPT_TRUNCATED: cut mid-flow after earlier punctuation (e.g. '…可以按户');
    SCRIPT_NO_TERMINAL_PUNCTUATION: text has no terminal punctuation at all."""
    stripped = text.rstrip()
    if not stripped:
        return GateResult(False, SCRIPT_NO_TERMINAL_PUNCTUATION,
                          {"char_count": 0}, "空文案")
    tail = stripped[-1]
    if tail in TERMINAL:
        return GateResult(True, None,
                          {"char_count": len(stripped),
                           "last_sentence": last_sentence(stripped),
                           "last_char": tail},
                          "脚本完整")
    has_any_terminal = any(ch in TERMINAL for ch in stripped)
    code = SCRIPT_TRUNCATED if has_any_terminal else SCRIPT_NO_TERMINAL_PUNCTUATION
    return GateResult(False, code,
                      {"char_count": len(stripped),
                       "last_sentence": last_sentence(stripped),
                       "last_char": tail},
                      f"脚本必须以完整句子与结束标点结尾（当前尾字符: {tail}）")


def check_audible_end(last_voice_s: float, video_duration_s: float,
                      narration_duration_s: float,
                      intentional_outro: bool = False) -> GateResult:
    """Real last-voice moment must keep a natural 0.25-0.8s tail before the
    video ends (non-outro); AUDIBLE_END_TOO_CLOSE when cut too tight."""
    if last_voice_s <= 0 or video_duration_s <= 0:
        return GateResult(False, AUDIBLE_END_TOO_CLOSE,
                          {"last_voice_s": last_voice_s,
                           "video_duration_s": video_duration_s},
                          "无法确定真实最后发声时间")
    tail = round(video_duration_s - last_voice_s, 3)
    fields = {"last_voice_s": round(last_voice_s, 3),
              "narration_duration_s": round(narration_duration_s, 3),
              "video_duration_s": round(video_duration_s, 3),
              "audible_tail_gap": tail,
              "intentional_outro": bool(intentional_outro)}
    if intentional_outro:
        return GateResult(True, None, fields, "声明片尾，跳过可闻尾距检查")
    if not TAIL_MIN <= tail <= TAIL_MAX:
        return GateResult(False, AUDIBLE_END_TOO_CLOSE, fields,
                          f"最后发声距画面结束 {tail:.3f}s，需在 "
                          f"{TAIL_MIN}-{TAIL_MAX}s")
    return GateResult(True, None, fields, "可闻结尾对齐通过")
