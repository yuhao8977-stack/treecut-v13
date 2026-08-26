-- Migration 0004: segment_validation_closure
-- git_commit: a08856f
-- checksum: 00f2317d34db90ba


-- Phase 2 Validation Closure: Segment 边界人工审核（0004）
CREATE TABLE IF NOT EXISTS segment_boundary_reviews (
    review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id       TEXT NOT NULL,
    annotation_id    INTEGER NOT NULL DEFAULT 0,
    boundary_start_ok   INTEGER NOT NULL DEFAULT -1,  -- 1=ok 0=bad -1=未审
    boundary_end_ok     INTEGER NOT NULL DEFAULT -1,
    action_complete     INTEGER NOT NULL DEFAULT -1,  -- 动作完整
    semantic_complete   INTEGER NOT NULL DEFAULT -1,  -- 语义完整
    cut_mid_action      INTEGER NOT NULL DEFAULT -1,  -- 动作被切断
    cut_mid_sentence    INTEGER NOT NULL DEFAULT -1,  -- 语句被切断
    usable_as_edit_unit INTEGER NOT NULL DEFAULT -1,  -- 可作为剪辑单位
    boundary_comment    TEXT NOT NULL DEFAULT '',
    operator            TEXT NOT NULL DEFAULT '',
    created_at          REAL NOT NULL,
    UNIQUE(segment_id, annotation_id)
);
CREATE INDEX IF NOT EXISTS idx_boundary_rev_seg ON segment_boundary_reviews(segment_id);

-- segments 来源标记（Phase 2 Closure：provenance 无法从历史证明，为未来记录）
ALTER TABLE segments ADD COLUMN generation_method TEXT NOT NULL DEFAULT 'UNKNOWN';
