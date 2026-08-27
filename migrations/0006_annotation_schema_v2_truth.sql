-- Migration 0006: annotation_schema_v2_truth
-- Phase 2.5.1: Canonical Human Truth & Schema V2 Freeze（0006）
-- 1) 冻结字典表（ANNOTATION_DICTIONARY_V2）
CREATE TABLE IF NOT EXISTS annotation_dictionary (
    dictionary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version       TEXT NOT NULL UNIQUE,
    schema_json   TEXT NOT NULL DEFAULT '{}',
    frozen_at     REAL NOT NULL,
    git_commit    TEXT NOT NULL DEFAULT '',
    notes         TEXT NOT NULL DEFAULT ''
);

-- 2) 唯一 Canonical Human Truth（每 segment_id 恰好一行）
--    segment 是生产单位；v1/v2 是证据，不产生独立训练样本。
CREATE TABLE IF NOT EXISTS canonical_human_truth (
    segment_id        TEXT PRIMARY KEY,
    scene_family      TEXT NOT NULL DEFAULT 'UNKNOWN',
    scene_subtype     TEXT NOT NULL DEFAULT 'UNKNOWN',
    product_family    TEXT NOT NULL DEFAULT 'UNKNOWN',
    product_variant   TEXT NOT NULL DEFAULT 'UNKNOWN',
    material          TEXT NOT NULL DEFAULT 'UNKNOWN',
    component         TEXT NOT NULL DEFAULT 'UNKNOWN',
    function          TEXT NOT NULL DEFAULT 'UNKNOWN',
    action_group      TEXT NOT NULL DEFAULT 'UNKNOWN',
    atomic_action     TEXT NOT NULL DEFAULT 'UNKNOWN',
    shot_scale        TEXT NOT NULL DEFAULT 'UNKNOWN',
    shot_role         TEXT NOT NULL DEFAULT 'UNKNOWN',
    people_presence   TEXT NOT NULL DEFAULT 'UNKNOWN',
    product_visibility TEXT NOT NULL DEFAULT 'UNKNOWN',
    quality           REAL,
    -- 真值来源与证据
    truth_source      TEXT NOT NULL DEFAULT 'SINGLE_REVIEW',  -- SINGLE_REVIEW|DOUBLE_REVIEW_AGREED|DOUBLE_REVIEW_HIERARCHICAL|NEEDS_ADJUDICATION|EXCLUDED
    agreement_level   TEXT NOT NULL DEFAULT 'single',         -- single|exact|hierarchical|conflict|none
    human_evidence_count INTEGER NOT NULL DEFAULT 0,
    human_confidence  TEXT NOT NULL DEFAULT 'MEDIUM',
    review_status     TEXT NOT NULL DEFAULT 'REVIEWED',
    dictionary_version TEXT NOT NULL DEFAULT 'ANNOTATION_DICTIONARY_V2',
    v1_record_id      INTEGER,
    v2_record_id      INTEGER,
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cht_source ON canonical_human_truth(truth_source);
CREATE INDEX IF NOT EXISTS idx_cht_family ON canonical_human_truth(product_family);
CREATE INDEX IF NOT EXISTS idx_cht_material ON canonical_human_truth(material);
