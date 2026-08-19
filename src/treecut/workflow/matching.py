"""Explainable local material matching used until optional embeddings are ready."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sqlite3


CLIP_SEMANTIC_THRESHOLD = 0.18
CLIP_SEMANTIC_LIMIT = 5


@dataclass(frozen=True)
class MaterialCandidate:
    media_id: int
    path: str
    category: str
    duration: float
    transcript: str
    caption: str
    eligible: bool
    speech_segments: tuple[dict, ...] = ()
    object_terms: tuple[str, ...] = ()
    representative_frame: str = ""
    content_fingerprint: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchResult:
    media_id: int
    path: str
    category: str
    duration: float
    score: float
    matched_terms: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    suggested_start: float = 0.0
    temporal_evidence: str = "midpoint_fallback"
    method: str = "local_explainable_text_v1"
    base_score: float = 0.0
    learning_adjustment: float = 0.0
    feedback_evidence: tuple[str, ...] = ()
    bge_similarity: float | None = None
    clip_similarity: float | None = None
    content_fingerprint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_candidates(db_path: Path, include_test: bool = True) -> list[MaterialCandidate]:
    # Formal jobs must never silently consume test materials. Any source that
    # was registered with an explicit test kind is excluded unless the caller
    # opts in (development mode).
    test_kinds = "'test_folder','test_materials','deployment_test','isolated_validation'"
    where_test = "" if include_test else f"AND s.kind NOT IN ({test_kinds})"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT m.id,s.path source_path,m.relative_path,m.category,m.fingerprint,j.result_json,"
            "(SELECT GROUP_CONCAT(tag, ',') FROM "
            "(SELECT tag FROM media_tags t WHERE t.media_id=m.id ORDER BY t.rowid)) tags "
            "FROM media_files m JOIN sources s ON s.id=m.source_id "
            "JOIN analysis_jobs j ON j.media_id=m.id "
            "WHERE m.available=1 AND s.online=1 AND j.status='success' " + where_test
        ).fetchall()
    candidates = []
    for row in rows:
        payload = json.loads(row["result_json"] or "{}")
        media = payload.get("media", {})
        speech = payload.get("speech", {})
        vision = payload.get("vision", {})
        selection = payload.get("selection", {})
        caption_evidence = vision.get("caption_evidence") or []
        representative_frame = ""
        if caption_evidence:
            representative_frame = str(caption_evidence[len(caption_evidence) // 2].get("frame_path") or "")
        elif payload.get("frames"):
            frames = payload["frames"]
            representative_frame = str(frames[len(frames) // 2].get("path") or "")
        absolute_path = Path(row["source_path"]) / row["relative_path"]
        try:
            if not absolute_path.is_file():
                continue
            with absolute_path.open("rb") as stream:
                stream.read(1)
        except OSError:
            continue
        candidates.append(MaterialCandidate(
            media_id=int(row["id"]),
            path=str(absolute_path),
            category=str(row["category"] or "unclassified"),
            duration=float(media.get("duration") or 0),
            transcript=str(speech.get("transcript") or ""),
            caption=str(vision.get("representative_caption") or ""),
            eligible=bool(selection.get("eligible_for_auto_edit", True)),
            speech_segments=tuple(speech.get("segments") or ()),
            object_terms=tuple((payload.get("objects") or {}).get("business_terms") or ()),
            representative_frame=representative_frame,
            content_fingerprint=str(row["fingerprint"] or ""),
            tags=tuple((row["tags"] or "").split(",")) if row["tags"] else (),
        ))
    return candidates


def _terms(text: str) -> tuple[str, ...]:
    chunks = re.findall(r"[A-Za-z0-9]+|[\u3400-\u9fff]+", text.lower())
    terms = []
    for chunk in chunks:
        if re.fullmatch(r"[\u3400-\u9fff]+", chunk):
            terms.extend(chunk[index:index + size] for size in (2, 3, 4)
                         for index in range(max(0, len(chunk) - size + 1)))
        elif len(chunk) >= 2:
            terms.append(chunk)
    return tuple(dict.fromkeys(terms))


def match_materials(query: str, candidates: list[MaterialCandidate], limit: int = 12,
                    feedback_adjustments: dict | None = None,
                    bge_scores: dict[int, float] | None = None,
                    clip_scores: dict[int, float] | None = None,
                    domain_terms: tuple[str, ...] | None = None) -> list[MatchResult]:
    base_query_terms = set(_terms(query))
    if not base_query_terms:
        raise ValueError("卖点或文案不能为空")
    query_terms = set(base_query_terms)
    # Domain vocabulary (v12-era selling-point library) expands the query with
    # terms the user implied, so materials named after industry terms still match.
    for term in domain_terms or ():
        candidate_term = str(term).strip().lower()
        if candidate_term and (candidate_term in query.lower()
                               or any(token in base_query_terms for token in _terms(candidate_term))):
            query_terms.add(candidate_term)
    results = []
    feedback_adjustments = feedback_adjustments or {}
    bge_scores = bge_scores or {}
    clip_scores = clip_scores or {}
    semantic_candidates: list[tuple[float, MaterialCandidate]] = []
    for item in candidates:
        if not item.eligible or item.duration <= 0:
            continue
        feedback = feedback_adjustments.get(item.media_id)
        if feedback is not None and bool(getattr(feedback, "blocked", False)):
            continue
        fields = {"speech": item.transcript.lower(), "vision": item.caption.lower(),
                  "objects": " ".join(item.object_terms).lower(),
                  "filename": Path(item.path).stem.lower(), "category": item.category.lower(),
                  "tags": " ".join(item.tags).lower()}
        matched = sorted(term for term in query_terms if any(term in value for value in fields.values()))
        if not matched:
            if (clip_scores and item.media_id in clip_scores
                    and clip_scores[item.media_id] >= CLIP_SEMANTIC_THRESHOLD):
                semantic_candidates.append((clip_scores[item.media_id], item))
            continue
        matched_base = [term for term in matched if term in base_query_terms]
        coverage = len(matched_base) / len(base_query_terms) if base_query_terms else 0.0
        sources = tuple(name for name, value in fields.items() if any(term in value for term in matched))
        source_weight = sum({"speech": 1.0, "vision": 0.75, "objects": 0.55,
                             "filename": 0.6, "category": 0.35, "tags": 0.7}[name]
                            for name in sources)
        base_score = min(1.0, 0.65 * coverage + 0.12 * source_weight + 0.02 * min(len(matched), 5))
        bge_score = bge_scores.get(item.media_id)
        clip_score = clip_scores.get(item.media_id)
        # Semantic models rerank only candidates backed by readable evidence.  This
        # prevents a weak CPU-model score from inventing an otherwise unsupported match.
        semantic_adjustment = 0.0
        if bge_score is not None:
            semantic_adjustment += max(-0.04, min(0.12, (bge_score - 0.90) * 1.2))
            sources = tuple(dict.fromkeys((*sources, "bge_m3")))
        if clip_score is not None:
            semantic_adjustment += max(-0.03, min(0.08, (clip_score - 0.15) * 0.35))
            sources = tuple(dict.fromkeys((*sources, "chinese_clip")))
        learning_adjustment = float(getattr(feedback, "score_adjustment", 0.0)) if feedback else 0.0
        score = max(0.0, min(1.0, base_score + semantic_adjustment + learning_adjustment))
        suggested_start = max(0.0, item.duration * 0.45)
        temporal_evidence = "midpoint_fallback"
        best_segment = None
        best_segment_hits = 0
        for segment in item.speech_segments:
            segment_text = str(segment.get("text") or "").lower()
            hits = sum(1 for term in matched if term in segment_text)
            if hits > best_segment_hits:
                best_segment, best_segment_hits = segment, hits
        if best_segment is not None:
            suggested_start = float(best_segment.get("start") or 0)
            temporal_evidence = "matched_speech_chunk"
        evidence = tuple(getattr(feedback, "evidence", ())) if feedback else ()
        results.append(MatchResult(
            item.media_id, item.path, item.category, item.duration,
            round(score, 4), tuple(matched), sources,
            round(suggested_start, 3), temporal_evidence,
            "local_hybrid_semantic_v2+explicit_feedback" if evidence else "local_hybrid_semantic_v2",
            round(base_score, 4), round(learning_adjustment, 4), evidence,
            bge_score, clip_score,
            item.content_fingerprint,
        ))
    semantic_candidates.sort(key=lambda pair: pair[0], reverse=True)
    for clip_score, item in semantic_candidates[:CLIP_SEMANTIC_LIMIT]:
        feedback = feedback_adjustments.get(item.media_id)
        learning_adjustment = float(getattr(feedback, "score_adjustment", 0.0)) if feedback else 0.0
        base_score = min(0.45, 0.20 + max(0.0, clip_score - 0.15) * 1.5)
        score = max(0.0, min(1.0, base_score + learning_adjustment))
        results.append(MatchResult(
            item.media_id, item.path, item.category, item.duration,
            round(score, 4), ("画面内容",), ("chinese_clip",),
            round(item.duration * 0.45, 3), "midpoint_fallback",
            "chinese_clip_semantic_v1", round(base_score, 4), round(learning_adjustment, 4),
            tuple(getattr(feedback, "evidence", ())) if feedback else (),
            None, clip_score, item.content_fingerprint,
        ))
    return sorted(results, key=lambda item: (-item.score, item.media_id))[:max(0, limit)]
