"""Phase 2 测试：SegmentEvidenceBuilder / SegmentCognitionService / TechnicalQuality / L3。

使用临时库（E 盘可写），不触碰生产库。
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))


def _make_db() -> Path:
    root = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\p2_tests")
    root.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".db", prefix="p2_", dir=str(root))
    import os
    os.close(fd)
    db = Path(path)
    conn = sqlite3.connect(db, timeout=10)
    conn.executescript("""
        CREATE TABLE sources (id INTEGER PRIMARY KEY, path TEXT, online INTEGER DEFAULT 1);
        CREATE TABLE media_files (id INTEGER PRIMARY KEY, source_id INTEGER,
            relative_path TEXT, media_type TEXT, available INTEGER DEFAULT 1);
        CREATE TABLE assets (asset_id TEXT PRIMARY KEY, media_id INTEGER,
            duration REAL DEFAULT 0, width INTEGER DEFAULT 0, height INTEGER DEFAULT 0,
            fps REAL DEFAULT 0);
        CREATE TABLE segments (segment_id TEXT PRIMARY KEY, asset_id TEXT,
            start_ms INTEGER, end_ms INTEGER, duration_ms INTEGER,
            scene_no INTEGER, quality_score REAL DEFAULT 0,
            algorithm_version TEXT DEFAULT '', created_at REAL);
        CREATE TABLE transcripts (id INTEGER PRIMARY KEY, asset_id TEXT,
            segment_id TEXT, start_ms INTEGER, end_ms INTEGER, text_raw TEXT,
            text_corrected TEXT, language TEXT, confidence REAL,
            model_name TEXT, model_version TEXT, created_at REAL);
        CREATE TABLE ocr_text (id INTEGER PRIMARY KEY, asset_id TEXT, frame_id TEXT,
            frame_timestamp_ms INTEGER, text TEXT, bbox TEXT, subtitle_flag INTEGER,
            coverage REAL, confidence REAL, ocr_model TEXT, ocr_model_version TEXT,
            created_at REAL);
        CREATE TABLE keyframes (frame_id TEXT PRIMARY KEY, segment_id TEXT,
            asset_id TEXT, timestamp_ms INTEGER, image_path TEXT,
            sharpness REAL DEFAULT 0, brightness REAL DEFAULT 0,
            selected INTEGER DEFAULT 0, created_at REAL);
        CREATE TABLE scene_semantics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL, segment_id TEXT,
            semantic TEXT NOT NULL, action TEXT DEFAULT '',
            lens_value INTEGER DEFAULT 0, confidence REAL DEFAULT 0,
            model_version TEXT DEFAULT '', created_time REAL);
        CREATE TABLE content_classification (
            asset_id TEXT PRIMARY KEY, content_type TEXT DEFAULT '',
            sub_type TEXT DEFAULT '', confidence REAL DEFAULT 0,
            reasons TEXT DEFAULT '', model_version TEXT DEFAULT '',
            content_elements TEXT DEFAULT '', reviewed INTEGER DEFAULT 0,
            created_time REAL);
        CREATE TABLE semantic_annotations (
            annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL, target_id TEXT NOT NULL,
            scene TEXT DEFAULT '', product TEXT DEFAULT '', material TEXT DEFAULT '',
            function TEXT DEFAULT '', action TEXT DEFAULT '', shot_type TEXT DEFAULT '',
            people_presence TEXT DEFAULT '', product_visibility REAL DEFAULT -1,
            product_completeness TEXT DEFAULT '', quality_score REAL DEFAULT -1,
            content_role TEXT DEFAULT '', business_value REAL DEFAULT -1,
            confidence REAL DEFAULT 0, evidence_refs_json TEXT DEFAULT '[]',
            model_name TEXT DEFAULT '', model_version TEXT DEFAULT '',
            prompt_version TEXT DEFAULT 'NONE', knowledge_version TEXT DEFAULT '',
            algorithm_version TEXT DEFAULT '', status TEXT DEFAULT 'candidate',
            created_at REAL, superseded_by INTEGER);
        CREATE TABLE human_annotations (
            adjudication_id INTEGER PRIMARY KEY AUTOINCREMENT,
            annotation_id INTEGER NOT NULL, target_type TEXT NOT NULL,
            target_id TEXT NOT NULL, scene TEXT DEFAULT '', product TEXT DEFAULT '',
            material TEXT DEFAULT '', function TEXT DEFAULT '', action TEXT DEFAULT '',
            shot_type TEXT DEFAULT '', people_presence TEXT DEFAULT '',
            product_visibility REAL DEFAULT -1, quality_score REAL DEFAULT -1,
            comment TEXT DEFAULT '', operator TEXT DEFAULT '', created_at REAL);
        INSERT INTO sources(id, path, online) VALUES(1, 'E:/tmp', 1);
        INSERT INTO media_files(id, source_id, relative_path, media_type) VALUES(1, 1, 'a.mp4', 'video');
        INSERT INTO assets(asset_id, media_id, duration, width, height, fps)
            VALUES('A0001', 1, 60, 1920, 1080, 30);
        INSERT INTO segments(segment_id, asset_id, start_ms, end_ms, duration_ms)
            VALUES('S1', 'A0001', 10000, 14000, 4000);
        INSERT INTO segments(segment_id, asset_id, start_ms, end_ms, duration_ms)
            VALUES('S2', 'A0001', 20000, 25000, 5000);
        -- ASR：S1 范围内（12-13s）一条，范围外（30-31s）一条
        INSERT INTO transcripts(asset_id, segment_id, start_ms, end_ms, text_raw)
            VALUES('A0001', 'S1', 12000, 13000, '这个可以伸缩60公分');
        INSERT INTO transcripts(asset_id, segment_id, start_ms, end_ms, text_raw)
            VALUES('A0001', NULL, 30000, 31000, '范围外的语音');
        -- OCR：S1 范围内（11.5s）一条，范围外（35s）一条
        INSERT INTO ocr_text(asset_id, frame_id, frame_timestamp_ms, text)
            VALUES('A0001', 'f1', 11500, '2.4m');
        INSERT INTO ocr_text(asset_id, frame_id, frame_timestamp_ms, text)
            VALUES('A0001', 'f2', 35000, '范围外');
        -- 关键帧：S1 范围内 3 个 + 范围外 1 个
        INSERT INTO keyframes(frame_id, asset_id, timestamp_ms, sharpness, brightness, selected)
            VALUES('k1', 'A0001', 11000, 40.0, 150.0, 1);
        INSERT INTO keyframes(frame_id, asset_id, timestamp_ms, sharpness, brightness, selected)
            VALUES('k2', 'A0001', 12500, 35.0, 120.0, 1);
        INSERT INTO keyframes(frame_id, asset_id, timestamp_ms, sharpness, brightness, selected)
            VALUES('k3', 'A0001', 13500, 45.0, 160.0, 1);
        INSERT INTO keyframes(frame_id, asset_id, timestamp_ms, sharpness, brightness, selected)
            VALUES('k4', 'A0001', 30000, 50.0, 180.0, 1);
    """)
    conn.commit()
    conn.close()
    return db


# ----------------------------------------------------------------------
# SegmentEvidenceBuilder
# ----------------------------------------------------------------------

def test_evidence_asr_time_filtered():
    from treecut.services.segment_cognition import SegmentEvidenceBuilder
    db = _make_db()
    b = SegmentEvidenceBuilder(db)
    ev = b.build("S1")
    assert ev is not None
    # 时间过滤：S1 是 10-14s，只有 12-13s 的 ASR 应命中
    assert "伸缩" in ev.asr_text
    assert "范围外" not in ev.asr_text
    assert len(ev.asr_hits) == 1


def test_evidence_ocr_time_filtered():
    from treecut.services.segment_cognition import SegmentEvidenceBuilder
    db = _make_db()
    b = SegmentEvidenceBuilder(db)
    ev = b.build("S1")
    assert "2.4m" in ev.ocr_text
    assert "范围外" not in ev.ocr_text


def test_evidence_keyframes_filtered():
    from treecut.services.segment_cognition import SegmentEvidenceBuilder
    db = _make_db()
    b = SegmentEvidenceBuilder(db)
    ev = b.build("S1")
    # 3 个在范围内，1 个在范围外（30s）
    assert len(ev.keyframes) == 3
    assert all(10000 <= k["timestamp_ms"] <= 14000 for k in ev.keyframes)


def test_evidence_no_asr_no_ocr():
    from treecut.services.segment_cognition import SegmentEvidenceBuilder
    db = _make_db()
    # S2 无 ASR/OCR/关键帧
    b = SegmentEvidenceBuilder(db)
    ev = b.build("S2")
    assert ev.asr_text == "" and ev.ocr_text == ""
    assert ev.keyframes == []


def test_evidence_invalid_segment():
    from treecut.services.segment_cognition import SegmentEvidenceBuilder
    db = _make_db()
    b = SegmentEvidenceBuilder(db)
    assert b.build("NOPE") is None


# ----------------------------------------------------------------------
# SegmentCognitionService（L2）
# ----------------------------------------------------------------------

def test_annotate_infers_from_evidence():
    from treecut.services.segment_cognition import SegmentCognitionService
    db = _make_db()
    svc = SegmentCognitionService(db)
    r = svc.annotate("S1")
    assert r is not None
    # ASR "伸缩60公分" → function=伸缩, product=伸缩岛台
    assert r["function"] == "伸缩"
    assert r["product"] in ("伸缩岛台", "岛台")
    assert r["confidence"] >= 0.8
    # evidence 保存
    assert "asr_text" in r["evidence"]
    # version 完整
    assert r["versions"]["model_version"] != ""
    assert r["versions"]["prompt_version"] == "NONE"
    assert r["versions"]["knowledge_version"] != ""


def test_annotate_unknown_for_no_evidence():
    from treecut.services.segment_cognition import SegmentCognitionService
    db = _make_db()
    svc = SegmentCognitionService(db)
    r = svc.annotate("S2")
    # 无证据 → UNKNOWN 合法
    assert r["function"] in ("UNKNOWN", "")
    assert r["confidence"] <= 0.55


def test_annotation_versioning_supersedes():
    from treecut.services.segment_cognition import SegmentCognitionService
    db = _make_db()
    svc = SegmentCognitionService(db)
    r1 = svc.annotate("S1")
    r2 = svc.annotate("S1")
    assert r2["annotation_id"] > r1["annotation_id"]
    # 旧 candidate 标记 superseded
    conn = sqlite3.connect(db, timeout=10)
    n = conn.execute("SELECT COUNT(*) FROM semantic_annotations "
                     "WHERE target_id='S1' AND status='superseded'").fetchone()[0]
    conn.close()
    assert n >= 1


def test_human_adjudication_does_not_overwrite():
    from treecut.services.segment_cognition import SegmentCognitionService
    db = _make_db()
    svc = SegmentCognitionService(db)
    r = svc.annotate("S1")
    # 人工裁决：修正 function
    svc.add_human_adjudication("S1", r["annotation_id"],
                               {"function": "收纳", "comment": "人工确认"})
    conn = sqlite3.connect(db, timeout=10)
    # L2 未变
    l2 = conn.execute("SELECT function FROM semantic_annotations WHERE annotation_id=?",
                      (r["annotation_id"],)).fetchone()
    # L3 单独保存
    l3 = conn.execute("SELECT function, comment FROM human_annotations WHERE target_id='S1'").fetchone()
    conn.close()
    assert l2[0] == "伸缩"  # L2 不被覆盖
    assert l3[0] == "收纳"  # L3 单独存
    assert l3[1] == "人工确认"


# ----------------------------------------------------------------------
# SegmentTechnicalQuality
# ----------------------------------------------------------------------

def test_technical_quality_computed():
    from treecut.services.segment_cognition import SegmentTechnicalQuality
    db = _make_db()
    tq = SegmentTechnicalQuality(db)
    r = tq.compute("S1")
    assert r["available"] is True
    assert r["frame_count"] == 3
    assert r["technical_quality_score"] > 0
    assert r["black_frame_ratio"] == 0.0


def test_technical_quality_no_frames_returns_minus1():
    from treecut.services.segment_cognition import SegmentTechnicalQuality
    db = _make_db()
    tq = SegmentTechnicalQuality(db)
    r = tq.compute("S2")
    assert r["available"] is True
    assert r["frame_count"] == 0
    assert r["technical_quality_score"] == -1.0  # 不伪造
