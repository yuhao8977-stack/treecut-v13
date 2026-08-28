-- Migration 0009: fresh_holdout_human_review
-- Stage 2 FRESH_HOLDOUT_V1 盲审表（AI 预测已锁定；本表只存人工盲审结果，不存任何 AI 信息）

CREATE TABLE IF NOT EXISTS fresh_holdout_human_review_v1 (
    review_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id        TEXT NOT NULL UNIQUE,
    stratum           TEXT NOT NULL DEFAULT '',      -- RANDOM|HARD|GAP
    scene_family      TEXT NOT NULL DEFAULT '',
    scene_subtype     TEXT NOT NULL DEFAULT '',
    product_family    TEXT NOT NULL DEFAULT '',
    product_variant   TEXT NOT NULL DEFAULT '',
    material_multi    TEXT NOT NULL DEFAULT '[]',
    component_multi   TEXT NOT NULL DEFAULT '[]',
    function_multi    TEXT NOT NULL DEFAULT '[]',
    action_group      TEXT NOT NULL DEFAULT '',
    action_sequence   TEXT NOT NULL DEFAULT '[]',
    shot_scale        TEXT NOT NULL DEFAULT '',
    shot_role_multi   TEXT NOT NULL DEFAULT '[]',
    people_presence   TEXT NOT NULL DEFAULT '',
    product_visibility TEXT NOT NULL DEFAULT '',
    quality           REAL,
    human_confidence  TEXT NOT NULL DEFAULT '',       -- HIGH|MEDIUM|LOW（中文解释见 UI，无默认）
    review_status     TEXT NOT NULL DEFAULT '',       -- REVIEWED|NEEDS_SECOND_REVIEW|GOLD|EXCLUDED（无默认）
    comment           TEXT NOT NULL DEFAULT '',
    operator          TEXT NOT NULL DEFAULT '',
    dictionary_version TEXT NOT NULL DEFAULT 'ANNOTATION_DICTIONARY_V2_1',
    created_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fhhr_seg ON fresh_holdout_human_review_v1(segment_id);
