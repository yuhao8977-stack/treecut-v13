-- Migration 0003: segment_cognition
-- git_commit: f827a47
-- checksum: ab9ea6636bdfc886


-- Phase 2: Segment 认知层（宪法 3：L1/L2/L3 严格分层）

-- L2 AI 语义解释（versioned，不可覆盖）
CREATE TABLE IF NOT EXISTS semantic_annotations (
    annotation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type       TEXT NOT NULL,              -- segment|asset
    target_id         TEXT NOT NULL,
    scene             TEXT NOT NULL DEFAULT '',
    product           TEXT NOT NULL DEFAULT '',
    material          TEXT NOT NULL DEFAULT '',
    function          TEXT NOT NULL DEFAULT '',
    action            TEXT NOT NULL DEFAULT '',
    shot_type         TEXT NOT NULL DEFAULT '',
    people_presence   TEXT NOT NULL DEFAULT '',   -- yes|no|unknown
    product_visibility REAL NOT NULL DEFAULT -1,  -- 0-100, -1=unknown
    product_completeness TEXT NOT NULL DEFAULT '',
    quality_score     REAL NOT NULL DEFAULT -1,   -- 0-100, -1=unknown
    content_role      TEXT NOT NULL DEFAULT '',
    business_value    REAL NOT NULL DEFAULT -1,   -- 0-100, -1=unknown
    confidence        REAL NOT NULL DEFAULT 0,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    model_name        TEXT NOT NULL DEFAULT '',
    model_version     TEXT NOT NULL DEFAULT '',
    prompt_version    TEXT NOT NULL DEFAULT 'NONE',
    knowledge_version TEXT NOT NULL DEFAULT '',
    algorithm_version TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'candidate',  -- candidate|validated|superseded
    created_at        REAL NOT NULL,
    superseded_by     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sem_annot_target ON semantic_annotations(target_type, target_id);

-- L3 人工裁决（单独保存，不覆盖 L2）
CREATE TABLE IF NOT EXISTS human_annotations (
    adjudication_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    annotation_id     INTEGER NOT NULL,           -- 指向被裁决的 L2
    target_type       TEXT NOT NULL,
    target_id         TEXT NOT NULL,
    scene             TEXT NOT NULL DEFAULT '',
    product           TEXT NOT NULL DEFAULT '',
    material          TEXT NOT NULL DEFAULT '',
    function          TEXT NOT NULL DEFAULT '',
    action            TEXT NOT NULL DEFAULT '',
    shot_type         TEXT NOT NULL DEFAULT '',
    people_presence   TEXT NOT NULL DEFAULT '',
    product_visibility REAL NOT NULL DEFAULT -1,
    quality_score     REAL NOT NULL DEFAULT -1,
    comment           TEXT NOT NULL DEFAULT '',
    operator          TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_human_annot_target ON human_annotations(target_id);
