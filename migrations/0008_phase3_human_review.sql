-- Migration 0008: phase3_human_review
-- Phase 3 人工审核阶段：34 条 V3 裁决 + 60 条 Targeted 新审核（Schema V2.1）
-- 不覆盖 V1/V2；人工审核期间系统冻结，本迁移仅建表。

CREATE TABLE IF NOT EXISTS human_annotation_v3 (
    v3_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id        TEXT NOT NULL UNIQUE,
    scene_family      TEXT NOT NULL DEFAULT '',
    scene_subtype     TEXT NOT NULL DEFAULT '',
    product_family    TEXT NOT NULL DEFAULT '',
    product_variant   TEXT NOT NULL DEFAULT '',
    material_multi    TEXT NOT NULL DEFAULT '[]',   -- JSON array
    component_multi   TEXT NOT NULL DEFAULT '[]',
    function_multi    TEXT NOT NULL DEFAULT '[]',
    action_group      TEXT NOT NULL DEFAULT '',
    action_sequence   TEXT NOT NULL DEFAULT '[]',   -- JSON array（有序）
    shot_scale        TEXT NOT NULL DEFAULT '',
    shot_role_multi   TEXT NOT NULL DEFAULT '[]',
    people_presence   TEXT NOT NULL DEFAULT '',
    product_visibility TEXT NOT NULL DEFAULT '',
    quality           REAL,
    human_confidence  TEXT NOT NULL DEFAULT '',      -- 必选，无默认
    review_status     TEXT NOT NULL DEFAULT '',      -- 必选，无默认
    comment           TEXT NOT NULL DEFAULT '',
    operator          TEXT NOT NULL DEFAULT '',
    dictionary_version TEXT NOT NULL DEFAULT 'ANNOTATION_DICTIONARY_V2_1',
    created_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hav3_seg ON human_annotation_v3(segment_id);

CREATE TABLE IF NOT EXISTS targeted_human_review_v1 (
    review_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id        TEXT NOT NULL UNIQUE,
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
    human_confidence  TEXT NOT NULL DEFAULT '',
    review_status     TEXT NOT NULL DEFAULT '',
    comment           TEXT NOT NULL DEFAULT '',
    operator          TEXT NOT NULL DEFAULT '',
    dictionary_version TEXT NOT NULL DEFAULT 'ANNOTATION_DICTIONARY_V2_1',
    selection_reason  TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_thr1_seg ON targeted_human_review_v1(segment_id);
