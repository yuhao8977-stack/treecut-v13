-- Migration 0002: shot_usage_visual_clusters
-- git_commit: a21446d
-- checksum: 7460bd95b8120c6c


-- Phase 1: 镜头使用 Ledger（宪法8：素材使用必须有记忆）
CREATE TABLE IF NOT EXISTS shot_usage (
    usage_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id     TEXT NOT NULL,
    production_id  TEXT NOT NULL DEFAULT '',
    account_id     TEXT NOT NULL DEFAULT '',
    beat_id        TEXT NOT NULL DEFAULT '',
    template_id    TEXT NOT NULL DEFAULT '',
    usage_type     TEXT NOT NULL DEFAULT 'candidate',  -- candidate|preview|rendered|published
    used_at        REAL NOT NULL,
    usage_count    INTEGER NOT NULL DEFAULT 1,
    cooldown_until REAL NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'active',     -- active|cancelled
    created_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shot_usage_segment ON shot_usage(segment_id);
CREATE INDEX IF NOT EXISTS idx_shot_usage_prod ON shot_usage(production_id);

-- Phase 1: Visual Cluster 占位（Phase 6 启用聚类，本 Phase 不运行）
CREATE TABLE IF NOT EXISTS visual_clusters (
    cluster_id     TEXT PRIMARY KEY,
    method         TEXT NOT NULL DEFAULT '',  -- phash|clip_embedding|future
    created_at     REAL NOT NULL,
    status         TEXT NOT NULL DEFAULT 'empty'  -- empty|populated
);
CREATE TABLE IF NOT EXISTS visual_cluster_members (
    cluster_id     TEXT NOT NULL,
    segment_id     TEXT NOT NULL,
    distance       REAL NOT NULL DEFAULT 0,
    added_at       REAL NOT NULL,
    PRIMARY KEY (cluster_id, segment_id)
);
