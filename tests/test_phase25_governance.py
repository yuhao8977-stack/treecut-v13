"""Phase 2.5 测试：Metric 口径 / people 标准化 / human confidence / 二次复核不可变 / queue / coverage。

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
    root = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\p25_tests")
    root.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".db", prefix="p25_", dir=str(root))
    import os
    os.close(fd)
    db = Path(path)
    conn = sqlite3.connect(db, timeout=10)
    conn.executescript("""
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
        CREATE TABLE human_annotation_v2 (
            v2_id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id TEXT NOT NULL, v1_annotation_id INTEGER NOT NULL,
            scene TEXT DEFAULT '', product TEXT DEFAULT '', material TEXT DEFAULT '',
            function TEXT DEFAULT '', action TEXT DEFAULT '', shot_type TEXT DEFAULT '',
            people_presence TEXT DEFAULT '', human_confidence TEXT DEFAULT 'MEDIUM',
            review_status TEXT DEFAULT 'REVIEWED', comment TEXT DEFAULT '',
            operator TEXT DEFAULT '', created_at REAL,
            UNIQUE(segment_id, v1_annotation_id));
        CREATE TABLE review_queue (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id TEXT NOT NULL, reason TEXT DEFAULT 'RANDOM_AUDIT',
            priority INTEGER DEFAULT 50, source TEXT DEFAULT 'system',
            status TEXT DEFAULT 'pending', created_at REAL, reviewed_at REAL);
        CREATE TABLE annotation_coverage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dim1 TEXT NOT NULL, dim1_value TEXT NOT NULL,
            dim2 TEXT DEFAULT '', dim2_value TEXT DEFAULT '',
            sample_count INTEGER DEFAULT 0, high_conf_count INTEGER DEFAULT 0,
            coverage_state TEXT DEFAULT 'EMPTY', updated_at REAL,
            UNIQUE(dim1, dim1_value, dim2, dim2_value));
    """)
    # 测试数据：5 条
    test_rows = [
        # (ai_func, human_func, ai_people, human_people, conf)
        ("收纳", "抽屉", "yes", "yes", 0.85),   # 错
        ("伸缩", "伸缩", "no", "no", 0.85),     # 对
        ("UNKNOWN", "抽屉", "unknown", "yes", 0.45),  # unknown 可判
        ("收纳", "收纳", "yes", "no", 0.85),    # 对(fn) 错(people)
        ("抽屉", "抽屉", "no", "no", 0.85),     # 对
    ]
    for i, (af, hf, ap, hp, conf) in enumerate(test_rows):
        conn.execute(
            "INSERT INTO semantic_annotations(target_type,target_id,function,people_presence,confidence,status) "
            "VALUES('segment',?,?,?,?,'candidate')",
            (f"S{i}", af, ap, conf))
        aid = conn.execute("SELECT annotation_id FROM semantic_annotations WHERE target_id=?",
                           (f"S{i}",)).fetchone()[0]
        conn.execute(
            "INSERT INTO human_annotations(annotation_id,target_type,target_id,function,people_presence) "
            "VALUES(?, 'segment', ?, ?, ?)",
            (aid, f"S{i}", hf, hp))
    conn.commit()
    conn.close()
    return db


# ----------------------------------------------------------------------
# Metric 口径（effective_correct_rate / conditional_accuracy）
# ----------------------------------------------------------------------

def test_metric_denominator_correct():
    """5 条样本：function conditional=3/4=75%，effective=3/5=60%。"""
    from treecut.services.segment_validation_report import SegmentValidationReport
    db = _make_db()
    rep = SegmentValidationReport(db)
    data = rep.generate()
    fm = data["field_metrics"]["function"]
    assert fm["human_valid_n"] == 5
    assert fm["ai_answered_n"] == 4      # 1 条 UNKNOWN
    assert fm["correct_n"] == 3
    assert fm["wrong_n"] == 1
    assert fm["conditional_accuracy"] == 75.0
    assert fm["effective_correct_rate"] == 60.0
    assert fm["ai_unknown_n"] == 1
    assert "UNKNOWN" in fm["confusion_matrix"]  # UNKNOWN 行保留


def test_people_normalization():
    """people 字段：yes/no 标准化后准确率正确（不再 0%）。"""
    from treecut.services.segment_validation_report import SegmentValidationReport
    db = _make_db()
    rep = SegmentValidationReport(db)
    data = rep.generate()
    pm = data["field_metrics"]["people_presence"]
    # 5 条中：yes/yes 对, no/no 对, unknown/yes(判对), yes/no 错, no/no 对
    # answered = 4 (yes/no), unknown=1; correct=3
    assert pm["human_valid_n"] == 5
    assert pm["ai_answered_n"] == 4
    assert pm["correct_n"] == 3
    assert pm["conditional_accuracy"] == 75.0
    assert pm["effective_correct_rate"] == 60.0


def test_confidence_reliability_table():
    from treecut.services.segment_validation_report import SegmentValidationReport
    db = _make_db()
    rep = SegmentValidationReport(db)
    data = rep.generate()
    cr = data["confidence_reliability"]
    assert "NOT_CALIBRATED_SCORE" in cr["note"]
    assert "0.80-0.89" in cr["buckets"]
    b = cr["buckets"]["0.80-0.89"]
    # 4 条 0.85，其中 function 错 1 条 → wrong=1
    assert b["n"] == 4
    assert b["wrong_n"] >= 1


# ----------------------------------------------------------------------
# Human Confidence / eligibility
# ----------------------------------------------------------------------

def test_calibration_eligibility():
    from treecut.services.annotation_governance import AnnotationService
    db = _make_db()
    svc = AnnotationService(db)
    assert svc.calibration_eligible("HIGH", "GOLD") is True
    assert svc.calibration_eligible("MEDIUM", "REVIEWED") is True
    assert svc.calibration_eligible("LOW", "REVIEWED") is False
    assert svc.calibration_eligible("HIGH", "EXCLUDED") is False
    assert svc.calibration_eligible("MEDIUM", "NEEDS_SECOND_REVIEW") is False


def test_second_review_immutability():
    """二次复核写入 v2 表，不覆盖 v1。"""
    from treecut.services.annotation_governance import AnnotationService
    db = _make_db()
    svc = AnnotationService(db)
    conn = sqlite3.connect(db, timeout=10)
    aid = conn.execute("SELECT annotation_id FROM human_annotations WHERE target_id='S0'").fetchone()[0]
    conn.close()
    svc.save_v2("S0", aid, {"function": "轨道插座", "scene": "客户住宅"},
                human_confidence="HIGH", review_status="GOLD")
    conn = sqlite3.connect(db, timeout=10)
    # v1 未变（function=抽屉）
    v1 = conn.execute("SELECT function FROM human_annotations WHERE target_id='S0'").fetchone()[0]
    v2 = conn.execute("SELECT function, human_confidence, review_status FROM human_annotation_v2 WHERE segment_id='S0'").fetchone()
    conn.close()
    assert v1 == "抽屉"
    assert v2[0] == "轨道插座"
    assert v2[1] == "HIGH" and v2[2] == "GOLD"


def test_review_queue_flow():
    from treecut.services.annotation_governance import ReviewQueueService
    db = _make_db()
    svc = ReviewQueueService(db)
    qid = svc.enqueue("S0", "LOW_CONFIDENCE", 90)
    qid2 = svc.enqueue("S1", "RANDOM_AUDIT", 10)
    pending = svc.next_pending(5)
    assert len(pending) == 2
    assert pending[0]["priority"] == 90  # 高优先级在前
    svc.mark_reviewed(qid)
    stats = svc.stats()
    assert stats["by_status"]["reviewed"] == 1
    assert stats["by_reason"]["LOW_CONFIDENCE"] == 1


def test_coverage_matrix():
    from treecut.services.annotation_governance import CoverageService
    db = _make_db()
    svc = CoverageService(db)
    n = svc.persist()
    assert n >= 3  # 抽屉/收纳/伸缩 3 个唯一 function 值
    combos = svc.compute("function")
    by = {c["dim1_value"]: c["sample_count"] for c in combos}
    # 人工 function 分布：S0=抽屉, S1=伸缩, S2=抽屉, S3=收纳, S4=抽屉
    assert by.get("抽屉") == 3
    assert by.get("伸缩") == 1
    assert by.get("收纳") == 1
