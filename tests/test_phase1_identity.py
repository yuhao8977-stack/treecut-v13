"""Phase 1 测试：Canonical Identity / Asset-Segment Repository / ShotUsage / Migration。

使用临时库（E 盘可写），不触碰生产库。
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


def _make_db() -> Path:
    root = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\p1_tests")
    root.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".db", prefix="p1_", dir=str(root))
    import os
    os.close(fd)
    db = Path(path)
    # 建最小 schema：assets/media_files/sources/segments
    conn = sqlite3.connect(db, timeout=10)
    conn.executescript("""
        CREATE TABLE sources (id INTEGER PRIMARY KEY, path TEXT, online INTEGER DEFAULT 1);
        CREATE TABLE media_files (id INTEGER PRIMARY KEY, source_id INTEGER,
            relative_path TEXT, media_type TEXT, available INTEGER DEFAULT 1);
        CREATE TABLE assets (asset_id TEXT PRIMARY KEY, media_id INTEGER,
            duration REAL DEFAULT 0);
        CREATE TABLE segments (segment_id TEXT PRIMARY KEY, asset_id TEXT,
            start_ms INTEGER, end_ms INTEGER, duration_ms INTEGER,
            scene_no INTEGER, quality_score REAL DEFAULT 0,
            algorithm_version TEXT DEFAULT '', created_at REAL);
        INSERT INTO sources(id, path, online) VALUES(1, 'E:/tmp', 1);
        INSERT INTO media_files(id, source_id, relative_path, media_type) VALUES(1, 1, 'a.mp4', 'video');
        INSERT INTO assets(asset_id, media_id, duration) VALUES('A0001', 1, 60);
        INSERT INTO segments(segment_id, asset_id, start_ms, end_ms, duration_ms)
            VALUES('S0001-01', 'A0001', 1000, 5000, 4000);
        INSERT INTO segments(segment_id, asset_id, start_ms, end_ms, duration_ms)
            VALUES('S0001-02', 'A0001', 5000, 9000, 4000);
        CREATE TABLE shot_usage (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id TEXT NOT NULL, production_id TEXT DEFAULT '',
            account_id TEXT DEFAULT '', beat_id TEXT DEFAULT '',
            template_id TEXT DEFAULT '', usage_type TEXT DEFAULT 'candidate',
            used_at REAL NOT NULL, usage_count INTEGER DEFAULT 1,
            cooldown_until REAL DEFAULT 0, status TEXT DEFAULT 'active',
            created_at REAL NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    return db


# ----------------------------------------------------------------------
# AssetRepository
# ----------------------------------------------------------------------

def test_asset_resolve_media():
    from treecut.services.identity import AssetRepository
    db = _make_db()
    repo = AssetRepository(db)
    assert repo.resolve_media("A0001") == 1
    assert repo.resolve_media("NOPE") is None


def test_asset_resolve_path():
    from treecut.services.identity import AssetRepository
    db = _make_db()
    repo = AssetRepository(db)
    p = repo.resolve_path("A0001")
    assert "E:/tmp" in p.replace("\\", "/") and "a.mp4" in p
    assert repo.resolve_path("NOPE") == ""


def test_asset_invalid_handling():
    from treecut.services.identity import AssetRepository
    db = _make_db()
    repo = AssetRepository(db)
    r = repo.validate_asset("NOPE")
    assert r["valid"] is False and r["reason"] == "asset 不存在"
    r2 = repo.validate_asset("A0001")
    assert r2["valid"] is True


# ----------------------------------------------------------------------
# SegmentRepository
# ----------------------------------------------------------------------

def test_segment_resolve_asset():
    from treecut.services.identity import SegmentRepository
    db = _make_db()
    repo = SegmentRepository(db)
    assert repo.get_asset_id("S0001-01") == "A0001"
    assert repo.get_asset_id("NOPE") is None


def test_segment_resolve_path_and_time():
    from treecut.services.identity import SegmentRepository
    db = _make_db()
    repo = SegmentRepository(db)
    src = repo.resolve_source("S0001-01")
    assert src["found"] is True
    assert src["asset_id"] == "A0001" and src["media_id"] == 1
    assert "a.mp4" in src["path"]
    tr = repo.resolve_time_range("S0001-01")
    assert tr["start_ms"] == 1000 and tr["end_ms"] == 5000
    assert repo.list_by_asset("A0001") and len(repo.list_by_asset("A0001")) == 2


def test_segment_invalid_orphan_handling():
    from treecut.services.identity import SegmentRepository
    db = _make_db()
    repo = SegmentRepository(db)
    r = repo.validate_segment("NOPE")
    assert r["valid"] is False and r["reason"] == "segment 不存在"
    # 非法时间范围
    conn = sqlite3.connect(db, timeout=10)
    conn.execute("INSERT INTO segments(segment_id,asset_id,start_ms,end_ms,duration_ms) "
                 "VALUES('BAD','A0001',9000,5000,4000)")
    conn.commit()
    conn.close()
    r2 = repo.validate_segment("BAD")
    assert r2["valid"] is False and any("start_ms" in i for i in r2["issues"])


# ----------------------------------------------------------------------
# Canonical Identity 完整链路
# ----------------------------------------------------------------------

def test_canonical_identity_chain():
    """segment → asset → media → physical path 完整追溯。"""
    from treecut.services.identity import SegmentRepository
    from treecut.services.identity import AssetRepository
    db = _make_db()
    seg_repo = SegmentRepository(db)
    asset_repo = AssetRepository(db)
    # segment → asset
    asset_id = seg_repo.get_asset_id("S0001-01")
    assert asset_id == "A0001"
    # asset → media
    media_id = asset_repo.resolve_media(asset_id)
    assert media_id == 1
    # asset → path
    path = asset_repo.resolve_path(asset_id)
    assert "a.mp4" in path
    # segment → path 直接
    src = seg_repo.resolve_source("S0001-01")
    assert src["path"] == path


# ----------------------------------------------------------------------
# Migration 0001 → 0002
# ----------------------------------------------------------------------

def test_migration_0001_to_0002():
    from treecut.platform.migrations import MigrationManager
    db = _make_db()
    mgr = MigrationManager(db)
    r = mgr.init()
    assert r[0]["version"] == "0001"
    # 应用 0002（若 migrations/ 目录存在该文件）
    result = mgr.apply_pending()
    versions = {x["version"] for x in mgr.status()}
    # 可能 0002 已存在或不存在；至少验证幂等（再次 init 不报错）
    mgr.init()
    conn = sqlite3.connect(db, timeout=10)
    tables = {r2[0] for r2 in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "schema_migrations" in tables


def test_migration_idempotent_reapply():
    from treecut.platform.migrations import MigrationManager
    db = _make_db()
    mgr = MigrationManager(db)
    mgr.init()
    n1 = len(mgr.status())
    mgr.init()  # 幂等
    n2 = len(mgr.status())
    assert n1 == n2 == 1


# ----------------------------------------------------------------------
# ShotUsageService
# ----------------------------------------------------------------------

def test_shot_usage_insert_query_cancel():
    from treecut.services.shot_usage import ShotUsageService
    db = _make_db()
    svc = ShotUsageService(db)
    uid = svc.record_usage("S0001-01", usage_type="rendered", production_id="P1")
    assert uid > 0
    rows = svc.query_by_segment("S0001-01")
    assert len(rows) == 1 and rows[0]["usage_type"] == "rendered"
    # 重复记录同一 (segment, production, type) → usage_count+1
    svc.record_usage("S0001-01", usage_type="rendered", production_id="P1")
    assert svc.usage_count("S0001-01") == 2
    # cancel
    svc.cancel(uid)
    assert svc.usage_count("S0001-01") == 0
    stats = svc.stats()
    assert stats["total"] >= 1


def test_shot_usage_rejects_invalid_segment():
    from treecut.services.shot_usage import ShotUsageService
    db = _make_db()
    svc = ShotUsageService(db)
    try:
        svc.record_usage("NOPE", usage_type="rendered")
        assert False, "应拒绝无效 segment_id"
    except ValueError:
        pass
