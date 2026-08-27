-- Migration 0005: annotation_governance
-- git_commit: c794444
-- checksum: cbd46d6a70aed3c9


-- Phase 2.5: Annotation Governance（0005）
-- 1) 二次复核（不覆盖首次答案）
CREATE TABLE IF NOT EXISTS human_annotation_v2 (
    v2_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id     TEXT NOT NULL,
    v1_annotation_id INTEGER NOT NULL,
    scene          TEXT NOT NULL DEFAULT '',
    product        TEXT NOT NULL DEFAULT '',
    material       TEXT NOT NULL DEFAULT '',
    function       TEXT NOT NULL DEFAULT '',
    action         TEXT NOT NULL DEFAULT '',
    shot_type      TEXT NOT NULL DEFAULT '',
    people_presence TEXT NOT NULL DEFAULT '',
    human_confidence TEXT NOT NULL DEFAULT 'MEDIUM',  -- HIGH|MEDIUM|LOW
    review_status  TEXT NOT NULL DEFAULT 'REVIEWED',  -- REVIEWED|NEEDS_SECOND_REVIEW|GOLD|EXCLUDED
    comment        TEXT NOT NULL DEFAULT '',
    operator       TEXT NOT NULL DEFAULT '',
    created_at     REAL NOT NULL,
    UNIQUE(segment_id, v1_annotation_id)
);
CREATE INDEX IF NOT EXISTS idx_hann_v2_seg ON human_annotation_v2(segment_id);

-- 2) 主动学习审核队列
CREATE TABLE IF NOT EXISTS review_queue (
    queue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id  TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT 'RANDOM_AUDIT',
    priority    INTEGER NOT NULL DEFAULT 50,
    source      TEXT NOT NULL DEFAULT 'system',
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending|reviewed|skipped
    created_at  REAL NOT NULL,
    reviewed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_rq_seg ON review_queue(segment_id);
CREATE INDEX IF NOT EXISTS idx_rq_status ON review_queue(status);

-- 3) 标注覆盖矩阵
CREATE TABLE IF NOT EXISTS annotation_coverage (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dim1           TEXT NOT NULL,
    dim1_value     TEXT NOT NULL,
    dim2           TEXT NOT NULL DEFAULT '',
    dim2_value     TEXT NOT NULL DEFAULT '',
    sample_count   INTEGER NOT NULL DEFAULT 0,
    high_conf_count INTEGER NOT NULL DEFAULT 0,
    coverage_state TEXT NOT NULL DEFAULT 'EMPTY',  -- EMPTY|LOW|MEDIUM|GOOD
    updated_at     REAL NOT NULL,
    UNIQUE(dim1, dim1_value, dim2, dim2_value)
);

-- 4) 快照注册表
CREATE TABLE IF NOT EXISTS validation_snapshots (
    snapshot_id   TEXT PRIMARY KEY,
    git_commit    TEXT NOT NULL DEFAULT '',
    model_name    TEXT NOT NULL DEFAULT '',
    model_version TEXT NOT NULL DEFAULT '',
    algorithm_version TEXT NOT NULL DEFAULT '',
    sample_count  INTEGER NOT NULL DEFAULT 0,
    created_at    REAL NOT NULL,
    notes         TEXT NOT NULL DEFAULT ''
);
