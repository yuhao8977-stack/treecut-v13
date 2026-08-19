"""Explicit, auditable user feedback that can affect later material matching."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3


ACTIONS = {"keep", "replace", "block"}


def _terms(text: str) -> set[str]:
    chunks = re.findall(r"[A-Za-z0-9]+|[\u3400-\u9fff]+", text.lower())
    terms: set[str] = set()
    for chunk in chunks:
        if re.fullmatch(r"[\u3400-\u9fff]+", chunk):
            terms.update(chunk[index:index + 2] for index in range(max(0, len(chunk) - 1)))
        elif len(chunk) >= 2:
            terms.add(chunk)
    return terms


@dataclass(frozen=True)
class FeedbackAdjustment:
    media_id: int
    blocked: bool
    score_adjustment: float
    evidence: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class FeedbackStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS material_feedback ("
                "id INTEGER PRIMARY KEY, media_id INTEGER NOT NULL, query TEXT NOT NULL, "
                "action TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_media ON material_feedback(media_id)"
            )
            connection.commit()

    def record(self, media_id: int, query: str, action: str, reason: str = "") -> int:
        if media_id <= 0:
            raise ValueError("素材编号必须大于 0")
        if action not in ACTIONS:
            raise ValueError("反馈动作必须是 keep、replace 或 block")
        if not query.strip() and action != "block":
            raise ValueError("保留或替换反馈必须包含当时的卖点需求")
        with closing(sqlite3.connect(self.path)) as connection:
            cursor = connection.execute(
                "INSERT INTO material_feedback(media_id,query,action,reason,created_at) VALUES(?,?,?,?,?)",
                (media_id, query.strip(), action, reason.strip(),
                 datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def adjustments(self, query: str) -> dict[int, FeedbackAdjustment]:
        query_terms = _terms(query)
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT id,media_id,query,action,reason FROM material_feedback ORDER BY id"
            ).fetchall()
        grouped: dict[int, dict] = {}
        for feedback_id, media_id, old_query, action, reason in rows:
            item = grouped.setdefault(int(media_id), {"blocked": False, "score": 0.0, "evidence": []})
            if action == "block":
                item["blocked"] = True
                item["evidence"].append(f"feedback:{feedback_id}:block:{reason or '用户禁用'}")
                continue
            old_terms = _terms(str(old_query))
            overlap = len(query_terms & old_terms) / max(1, len(query_terms | old_terms))
            if overlap < 0.15:
                continue
            delta = (0.12 if action == "keep" else -0.12) * max(0.5, overlap)
            item["score"] += delta
            item["evidence"].append(
                f"feedback:{feedback_id}:{action}:overlap={overlap:.3f}:{reason or '用户反馈'}"
            )
        return {
            media_id: FeedbackAdjustment(
                media_id, bool(item["blocked"]),
                round(max(-0.25, min(0.25, item["score"])), 4),
                tuple(item["evidence"]),
            )
            for media_id, item in grouped.items()
        }

    def list_records(self, limit: int = 100) -> list[dict]:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT id,media_id,query,action,reason,created_at "
                "FROM material_feedback ORDER BY id DESC LIMIT ?", (max(0, limit),),
            ).fetchall()
        return [dict(row) for row in rows]
