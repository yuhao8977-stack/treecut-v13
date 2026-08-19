"""Build a deterministic, diversity-aware edit decision list."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .matching import MatchResult


@dataclass(frozen=True)
class EditSegment:
    order: int
    media_id: int
    path: str
    category: str
    source_start: float
    source_end: float
    timeline_start: float
    timeline_end: float
    match_score: float
    matched_terms: tuple[str, ...]
    content_fingerprint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EditPlan:
    requested_duration: float
    planned_duration: float
    complete: bool
    warnings: tuple[str, ...]
    segments: tuple[EditSegment, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _fill_plan(matches: list[MatchResult], target_duration: float,
               clip_seconds: float) -> tuple[list[EditSegment], float]:
    selected = []
    used = set()
    used_fingerprints = set()
    timeline = 0.0
    # First pass favors different business categories; second pass fills the target.
    for pass_index in (0, 1):
        seen_categories = {item.category for item in selected}
        for match in matches:
            if (match.media_id in used
                    or (match.content_fingerprint and match.content_fingerprint in used_fingerprints)
                    or (pass_index == 0 and match.category in seen_categories)):
                continue
            remaining = target_duration - timeline
            if remaining <= 0.01:
                break
            length = min(clip_seconds, match.duration, remaining)
            if length < 1:
                continue
            source_start = max(0.0, min(match.duration - length, match.suggested_start))
            selected.append(EditSegment(
                len(selected) + 1, match.media_id, match.path, match.category,
                round(source_start, 3), round(source_start + length, 3),
                round(timeline, 3), round(timeline + length, 3),
                match.score, match.matched_terms, match.content_fingerprint,
            ))
            used.add(match.media_id)
            if match.content_fingerprint:
                used_fingerprints.add(match.content_fingerprint)
            seen_categories.add(match.category)
            timeline += length
        if timeline >= target_duration - 0.01:
            break
    return selected, timeline


def _clip_candidates(requested: float) -> list[float]:
    """Try the requested clip first, then gradually longer clips so a
    23-45s video can still be built from a smaller material library."""
    candidates = [requested]
    for multiplier in (1.5, 2.0, 3.0, 4.0):
        candidates.append(round(requested * multiplier, 3))
    candidates.append(15.0)
    seen = set()
    result = []
    for value in candidates:
        value = min(value, 15.0)
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return sorted(result)


def build_edit_plan(matches: list[MatchResult], target_duration: float = 30,
                    clip_seconds: float = 4) -> EditPlan:
    if target_duration <= 0 or clip_seconds <= 0:
        raise ValueError("成片时长和单片段时长必须大于 0")
    best: tuple[list[EditSegment], float] | None = None
    for clip in _clip_candidates(clip_seconds):
        segments, timeline = _fill_plan(matches, target_duration, clip)
        if best is None or timeline > best[1]:
            best = (segments, timeline)
        if timeline >= target_duration - 0.01:
            break
    segments, timeline = best or ([], 0.0)
    complete = timeline >= target_duration - 0.01
    warnings = () if complete else (f"合格素材不足：计划 {timeline:.1f} 秒，目标 {target_duration:.1f} 秒",)
    return EditPlan(target_duration, round(timeline, 3), complete, warnings, tuple(segments))
