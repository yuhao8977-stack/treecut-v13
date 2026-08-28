-- Migration 0007: phase3_cognition_foundation
-- Phase 3 Step 0: Canonical Truth Versioning + Annotation Dictionary V2.1（兼容升级）

-- 1) canonical_human_truth 版本化与 V2.1 多值扩展（兼容升级：单值列保留）
ALTER TABLE canonical_human_truth ADD COLUMN truth_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE canonical_human_truth ADD COLUMN status TEXT NOT NULL DEFAULT 'CURRENT';  -- CURRENT|SUPERSEDED
ALTER TABLE canonical_human_truth ADD COLUMN is_current INTEGER NOT NULL DEFAULT 1;   -- 1|0
ALTER TABLE canonical_human_truth ADD COLUMN supersedes_version INTEGER;
ALTER TABLE canonical_human_truth ADD COLUMN material_multi TEXT;    -- JSON array
ALTER TABLE canonical_human_truth ADD COLUMN component_multi TEXT;   -- JSON array
ALTER TABLE canonical_human_truth ADD COLUMN function_multi TEXT;    -- JSON array
ALTER TABLE canonical_human_truth ADD COLUMN shot_role_multi TEXT;   -- JSON array
ALTER TABLE canonical_human_truth ADD COLUMN action_sequence TEXT;   -- JSON array of atomic actions

-- 2) 历史表：旧真值永远可追溯（V1/V2/V3 裁决链）
CREATE TABLE IF NOT EXISTS canonical_human_truth_history (
    history_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id        TEXT NOT NULL,
    truth_version     INTEGER NOT NULL,
    status            TEXT NOT NULL,          -- CURRENT|SUPERSEDED
    is_current        INTEGER NOT NULL,       -- 1|0
    supersedes_version INTEGER,
    snapshot_json     TEXT NOT NULL,          -- 完整真值快照（含 multi 列）
    truth_source      TEXT NOT NULL,
    agreement_level   TEXT NOT NULL,
    human_evidence_count INTEGER NOT NULL DEFAULT 0,
    human_confidence  TEXT NOT NULL DEFAULT 'MEDIUM',
    review_status     TEXT NOT NULL DEFAULT 'REVIEWED',
    dictionary_version TEXT NOT NULL,
    created_at        REAL NOT NULL,
    UNIQUE(segment_id, truth_version)
);
CREATE INDEX IF NOT EXISTS idx_chth_seg ON canonical_human_truth_history(segment_id, truth_version);
