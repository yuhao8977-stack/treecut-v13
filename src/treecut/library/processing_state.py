"""P1.1: Asset processing lifecycle — stage-level state machine, idempotency,
dependency graph and incremental analysis control.

设计要点（第二阶段 P1.1 总指令）:
- 唯一 Canonical Asset Registry = `assets`（内容身份，asset_id 稳定）
- Stage 级状态，而非 analyzed=true/false：
  probe / fingerprint / duplicate / scene / keyframe / asr / ocr / vision /
  labels / embedding，每阶段状态机:
  NEW → PENDING → PROCESSING → DONE | PARTIAL | FAILED | SKIPPED | STALE | REVIEW
- 幂等: should_process() 依据 fingerprint + pipeline/algorithm/model 版本判定，
  DONE 且版本一致 → SKIP_ALREADY_DONE（绝不允许重复昂贵分析）
- 版本变化只局部 STALE（依赖图），不无理由全量重跑
- processing_history 记录每次状态转移原因（能回答“为什么又重跑 ASR”）
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.assets import AssetsManager

# ---------------------------------------------------------------------------
# 常量定义
# ---------------------------------------------------------------------------

PROCESSING_SCHEMA_VERSION = 1

# 处理阶段（P1.1 §二）
STAGES = [
    "probe",          # ffprobe 元数据
    "fingerprint",    # 指纹（quick/full hash）
    "duplicate",      # 重复识别
    "scene",          # 场景切分
    "keyframe",       # 关键帧
    "asr",            # 语音转写
    "ocr",            # 字幕/文字识别
    "vision",         # 视觉理解
    "labels",         # 运营标签
    "embedding",      # 向量嵌入
]

# 阶段状态（P1.1 §四）
STATUS_NEW = "NEW"
STATUS_PENDING = "PENDING"
STATUS_PROCESSING = "PROCESSING"
STATUS_DONE = "DONE"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
STATUS_STALE = "STALE"
STATUS_REVIEW = "REVIEW"
ALL_STATUSES = {
    STATUS_NEW, STATUS_PENDING, STATUS_PROCESSING, STATUS_DONE, STATUS_PARTIAL,
    STATUS_FAILED, STATUS_SKIPPED, STATUS_STALE, STATUS_REVIEW,
}

# Stage 依赖图（P1.1 §五）
# key 阶段依赖哪些上游阶段完成才可处理；invalidation: 某阶段变化会波及哪些下游
STAGE_DEPENDENCIES = {
    "probe": [],
    "fingerprint": ["probe"],
    "duplicate": ["fingerprint"],
    "scene": ["probe", "fingerprint"],
    "keyframe": ["probe", "scene"],
    "asr": ["probe", "fingerprint"],
    "ocr": ["keyframe"],
    "vision": ["keyframe"],
    "labels": ["asr", "ocr", "vision"],
    "embedding": ["keyframe", "labels"],
}

# 反向：某阶段升级/失效时，需要一起 STALE 的下游（含自身）
def _build_downstream() -> dict[str, set[str]]:
    downstream: dict[str, set[str]] = {s: set() for s in STAGES}
    for stage, deps in STAGE_DEPENDENCIES.items():
        for dep in deps:
            downstream[dep].add(stage)
    # 传递闭包
    changed = True
    while changed:
        changed = False
        for stage in STAGES:
            for child in list(downstream[stage]):
                for grand in downstream.get(child, set()):
                    if grand not in downstream[stage]:
                        downstream[stage].add(grand)
                        changed = True
    return downstream


DOWNSTREAM = _build_downstream()


def invalidated_by(stage: str) -> set[str]:
    """Stages that must be marked STALE when `stage` is reprocessed."""
    return DOWNSTREAM.get(stage, {stage}) | {stage}


PROCESSING_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS asset_processing_state (
    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NEW',
    pipeline_version TEXT NOT NULL DEFAULT '',
    algorithm_version TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT '',
    model_version TEXT NOT NULL DEFAULT '',
    input_fingerprint TEXT NOT NULL DEFAULT '',
    started_at REAL,
    completed_at REAL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT '',
    result_count INTEGER NOT NULL DEFAULT 0,
    reviewed INTEGER NOT NULL DEFAULT 0,
    reviewed_at REAL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (asset_id, stage)
);
CREATE INDEX IF NOT EXISTS idx_state_status ON asset_processing_state(status);
CREATE INDEX IF NOT EXISTS idx_state_stage ON asset_processing_state(stage);

CREATE TABLE IF NOT EXISTS processing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_asset ON processing_history(asset_id, stage);
CREATE INDEX IF NOT EXISTS idx_history_time ON processing_history(created_at);

CREATE TABLE IF NOT EXISTS asset_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    media_id INTEGER NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    current INTEGER NOT NULL DEFAULT 1,
    UNIQUE(source_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_locations_asset ON asset_locations(asset_id);
"""


@dataclass(frozen=True)
class StageState:
    asset_id: str
    stage: str
    status: str
    pipeline_version: str = ""
    algorithm_version: str = ""
    model_name: str = ""
    model_version: str = ""
    input_fingerprint: str = ""
    started_at: float | None = None
    completed_at: float | None = None
    retry_count: int = 0
    error_code: str = ""
    error_message: str = ""
    result_count: int = 0
    reviewed: int = 0
    reviewed_at: float | None = None
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class ProcessingState:
    """Stage-level processing state machine over the canonical assets table."""

    def __init__(self, assets: AssetsManager | None = None):
        self.assets = assets or AssetsManager()
        self.db_path = self.assets.db_path
        with self._connect() as connection:
            connection.executescript(PROCESSING_SCHEMA)
            connection.execute(f"PRAGMA user_version={PROCESSING_SCHEMA_VERSION}")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # 状态读写
    # ------------------------------------------------------------------

    def ensure_asset_stages(self, asset_id: str, input_fingerprint: str = "") -> None:
        """Create NEW rows for all stages of an asset (idempotent)."""
        now = time.time()
        with self._connect() as connection:
            for stage in STAGES:
                connection.execute(
                    "INSERT OR IGNORE INTO asset_processing_state"
                    "(asset_id,stage,status,input_fingerprint,updated_at) VALUES(?,?,?,?,?)",
                    (asset_id, stage, STATUS_NEW, input_fingerprint, now),
                )

    def ensure_asset_stages_all(self) -> int:
        """Create NEW stage rows for every asset that lacks them (idempotent)."""
        now = time.time()
        with self._connect() as connection:
            assets = connection.execute(
                "SELECT asset_id, fingerprint_quick FROM assets"
            ).fetchall()
            created = 0
            for row in assets:
                for stage in STAGES:
                    cursor = connection.execute(
                        "INSERT OR IGNORE INTO asset_processing_state"
                        "(asset_id,stage,status,input_fingerprint,updated_at) VALUES(?,?,?,?,?)",
                        (row["asset_id"], stage, STATUS_NEW, row["fingerprint_quick"] or "", now),
                    )
                    created += cursor.rowcount
            return created

    def get_state(self, asset_id: str, stage: str) -> StageState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM asset_processing_state WHERE asset_id=? AND stage=?",
                (asset_id, stage),
            ).fetchone()
        return StageState(**dict(row)) if row else None

    def get_asset_states(self, asset_id: str) -> dict[str, StageState]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM asset_processing_state WHERE asset_id=? ORDER BY "
                "CASE stage WHEN 'probe' THEN 0 WHEN 'fingerprint' THEN 1 WHEN 'duplicate' THEN 2 "
                "WHEN 'scene' THEN 3 WHEN 'keyframe' THEN 4 WHEN 'asr' THEN 5 WHEN 'ocr' THEN 6 "
                "WHEN 'vision' THEN 7 WHEN 'labels' THEN 8 WHEN 'embedding' THEN 9 END",
                (asset_id,),
            ).fetchall()
        return {row["stage"]: StageState(**dict(row)) for row in rows}

    # ------------------------------------------------------------------
    # 状态转移（带历史记录）
    # ------------------------------------------------------------------

    def _transition(self, asset_id: str, stage: str, new_status: str, reason: str,
                    model: str = "", version: str = "", extra: dict | None = None) -> None:
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM asset_processing_state WHERE asset_id=? AND stage=?",
                (asset_id, stage),
            ).fetchone()
            old_status = row["status"] if row else STATUS_NEW
            values = dict(extra or {})
            values.setdefault("status", new_status)
            values.setdefault("updated_at", now)
            if new_status == STATUS_PROCESSING:
                values.setdefault("started_at", now)
            if new_status in (STATUS_DONE, STATUS_PARTIAL, STATUS_FAILED, STATUS_SKIPPED):
                values.setdefault("completed_at", now)
            if new_status == STATUS_PROCESSING:
                values["retry_count"] = (row["retry_count"] if row else 0) + 1
            if new_status == STATUS_DONE:
                values["error_code"] = ""
                values["error_message"] = ""
            if row is None:
                connection.execute(
                    "INSERT INTO asset_processing_state(asset_id,stage,status,pipeline_version,"
                    "algorithm_version,model_name,model_version,input_fingerprint,started_at,completed_at,"
                    "retry_count,error_code,error_message,result_count,reviewed,reviewed_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (asset_id, stage, values.get("status", new_status),
                     values.get("pipeline_version", ""), values.get("algorithm_version", ""),
                     values.get("model_name", ""), values.get("model_version", ""),
                     values.get("input_fingerprint", ""), values.get("started_at"),
                     values.get("completed_at"), values.get("retry_count", 0),
                     values.get("error_code", ""), values.get("error_message", ""),
                     values.get("result_count", 0), values.get("reviewed", 0),
                     values.get("reviewed_at"), now),
                )
            else:
                sets = []
                params = []
                for key, value in values.items():
                    sets.append(f"{key}=?")
                    params.append(value)
                params.append(asset_id)
                params.append(stage)
                connection.execute(
                    f"UPDATE asset_processing_state SET {','.join(sets)} WHERE asset_id=? AND stage=?",
                    params,
                )
            connection.execute(
                "INSERT INTO processing_history(asset_id,stage,old_status,new_status,reason,"
                "model,version,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (asset_id, stage, old_status, new_status, reason, model, version, now),
            )

    def set_status(self, asset_id: str, stage: str, status: str, reason: str = "",
                   model: str = "", version: str = "", **extra) -> None:
        if status not in ALL_STATUSES:
            raise ValueError(f"非法状态: {status}")
        if stage not in STAGES:
            raise ValueError(f"非法阶段: {stage}")
        self._transition(asset_id, stage, status, reason, model, version, extra)

    # 便捷方法
    def mark_pending(self, asset_id: str, stage: str, reason: str = "进入处理队列") -> None:
        self.set_status(asset_id, stage, STATUS_PENDING, reason)

    def mark_processing(self, asset_id: str, stage: str, reason: str = "worker 领取") -> None:
        self.set_status(asset_id, stage, STATUS_PROCESSING, reason)

    def mark_done(self, asset_id: str, stage: str, reason: str = "处理完成",
                  model: str = "", version: str = "", pipeline_version: str = "",
                  algorithm_version: str = "", input_fingerprint: str = "",
                  result_count: int = 0, **extra) -> None:
        self.set_status(asset_id, stage, STATUS_DONE, reason, model, version,
                        pipeline_version=pipeline_version,
                        algorithm_version=algorithm_version,
                        input_fingerprint=input_fingerprint,
                        result_count=result_count, **extra)

    def mark_failed(self, asset_id: str, stage: str, reason: str,
                    error_code: str = "", error_message: str = "") -> None:
        self.set_status(asset_id, stage, STATUS_FAILED, reason,
                        error_code=error_code, error_message=error_message)

    def mark_skipped(self, asset_id: str, stage: str, reason: str) -> None:
        self.set_status(asset_id, stage, STATUS_SKIPPED, reason)

    def mark_review(self, asset_id: str, stage: str, reason: str = "需要人工审核") -> None:
        self.set_status(asset_id, stage, STATUS_REVIEW, reason)

    def mark_stale(self, asset_id: str, stage: str, reason: str) -> None:
        """Mark a stage STALE and cascade to downstream stages (dependency graph)."""
        self._transition(asset_id, stage, STATUS_STALE, reason)
        for downstream in invalidated_by(stage):
            if downstream == stage:
                continue
            self._transition(asset_id, downstream, STATUS_STALE, f"上游 {stage} 失效: {reason}")

    # ------------------------------------------------------------------
    # 幂等判定（P1.1 §四）
    # ------------------------------------------------------------------

    def should_process(self, asset_id: str, stage: str,
                       pipeline_version: str = "", algorithm_version: str = "",
                       model_name: str = "", model_version: str = "",
                       input_fingerprint: str = "") -> str:
        """Decide whether this stage must (re)run.

        Returns one of:
          SKIP_ALREADY_DONE  — DONE 且版本/指纹一致，绝不再跑
          NEED_REPROCESS     — 版本/指纹变化或状态非 DONE
        """
        state = self.get_state(asset_id, stage)
        if state is None:
            return "NEED_REPROCESS"
        if state.status == STATUS_DONE:
            fingerprint_ok = (not input_fingerprint) or (state.input_fingerprint == input_fingerprint)
            pipeline_ok = (not pipeline_version) or (state.pipeline_version == pipeline_version)
            algorithm_ok = (not algorithm_version) or (state.algorithm_version == algorithm_version)
            model_ok = (not model_name) or (
                state.model_name == model_name and (not model_version or state.model_version == model_version)
            )
            if fingerprint_ok and pipeline_ok and algorithm_ok and model_ok:
                return "SKIP_ALREADY_DONE"
        return "NEED_REPROCESS"

    # ------------------------------------------------------------------
    # 统计与查询（Dashboard / UI）
    # ------------------------------------------------------------------

    def stage_stats(self) -> dict[str, dict[str, int]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT stage,status,COUNT(*) n FROM asset_processing_state GROUP BY stage,status"
            ).fetchall()
        stats: dict[str, dict[str, int]] = {s: {} for s in STAGES}
        for row in rows:
            stats.setdefault(row["stage"], {})[row["status"]] = row["n"]
        return stats

    def dashboard(self) -> dict:
        """Global dashboard counters (P1.1 §十)."""
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) n FROM assets").fetchone()["n"]
            stage_rows = connection.execute(
                "SELECT stage,status,COUNT(*) n FROM asset_processing_state GROUP BY stage,status"
            ).fetchall()
            failed = connection.execute(
                "SELECT COUNT(DISTINCT asset_id) n FROM asset_processing_state WHERE status='FAILED'"
            ).fetchone()["n"]
            stale = connection.execute(
                "SELECT COUNT(DISTINCT asset_id) n FROM asset_processing_state WHERE status='STALE'"
            ).fetchone()["n"]
            review = connection.execute(
                "SELECT COUNT(DISTINCT asset_id) n FROM asset_processing_state WHERE status='REVIEW'"
            ).fetchone()["n"]
            fully = connection.execute(
                "SELECT COUNT(DISTINCT asset_id) n FROM asset_processing_state "
                "WHERE stage IN ('probe','fingerprint','scene','keyframe','asr','ocr',"
                "'vision','labels','embedding') AND status='DONE'"
            ).fetchone()["n"]
            never = connection.execute(
                "SELECT COUNT(*) n FROM assets a WHERE NOT EXISTS "
                "(SELECT 1 FROM asset_processing_state s WHERE s.asset_id=a.asset_id)"
            ).fetchone()["n"]
        by_stage: dict[str, dict[str, int]] = {}
        for row in stage_rows:
            by_stage.setdefault(row["stage"], {})[row["status"]] = row["n"]
        return {
            "total_assets": total,
            "never_processed": never,
            "failed_assets": failed,
            "stale_assets": stale,
            "review_assets": review,
            "by_stage": by_stage,
        }

    def recent_history(self, limit: int = 50) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM processing_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def history_for(self, asset_id: str, stage: str | None = None, limit: int = 100) -> list[dict]:
        where = "asset_id=?"
        params: list = [asset_id]
        if stage:
            where += " AND stage=?"
            params.append(stage)
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM processing_history WHERE {where} ORDER BY id DESC LIMIT ?", params
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # 资产定位（移动/改名追踪）
    # ------------------------------------------------------------------

    def record_location(self, asset_id: str, media_id: int, source_id: int,
                        relative_path: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO asset_locations(asset_id,source_id,relative_path,media_id,"
                "first_seen,last_seen,current) VALUES(?,?,?,?,?,?,1) "
                "ON CONFLICT(source_id,relative_path) DO UPDATE SET asset_id=excluded.asset_id,"
                "media_id=excluded.media_id,last_seen=excluded.last_seen,current=1",
                (asset_id, source_id, relative_path, media_id, now, now),
            )
            connection.execute(
                "UPDATE asset_locations SET current=0 WHERE asset_id=? "
                "AND NOT (source_id=? AND relative_path=?)",
                (asset_id, source_id, relative_path),
            )

    def locations_for(self, asset_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT l.*,s.path source_path FROM asset_locations l "
                "JOIN sources s ON s.id=l.source_id WHERE l.asset_id=? ORDER BY l.current DESC,l.id",
                (asset_id,),
            ).fetchall()
        return [dict(row) for row in rows]
