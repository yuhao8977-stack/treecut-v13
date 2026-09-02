# -*- coding: utf-8 -*-
"""STAGE8 G1 测试（§30）。只读主库；写路径(adjudicate)用临时库副本。"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.production_source import ProductionSourceService

DB = os.environ.get("TREECUT_DB", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db")
svc = ProductionSourceService(DB)


def _first_by(sql: str, value) -> tuple:
    with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
        return c.execute(f"SELECT entity_id, source_role FROM b007_source_role_v1 "
                         f"WHERE entity_kind='media_file' AND {sql} LIMIT 1",
                         (value,)).fetchone()


def _first_clean_by_role(role: str):
    with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
        return c.execute("""SELECT entity_id FROM b007_source_role_v1
                            WHERE entity_kind='media_file' AND source_role=?
                            AND burned_subtitle_present='ABSENT'
                            AND platform_watermark_present='ABSENT'
                            AND unrelated_overlay_present='ABSENT'
                            AND old_title_overlay_present='ABSENT'
                            AND review_status!='REJECTED' LIMIT 1""", (role,)).fetchone()


def test_published_reference_not_production_eligible():
    r = _first_by("source_role=?", "PUBLISHED_REFERENCE")
    ok, info = svc.is_production_eligible("media_file", r[0])
    assert ok is False
    assert any("ROLE_NOT_ELIGIBLE" in x for x in info["reasons"])


def test_s3_not_production_source():
    r = _first_by("source_role=?", "NOT_PRODUCTION_SOURCE")
    ok, info = svc.is_production_eligible("media_file", r[0])
    assert ok is False


def test_unknown_not_silently_eligible():
    # 无 OCR 覆盖 → burned=UNCERTAIN 的资产，strict 下不得入池
    with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
        r = c.execute("""SELECT entity_id FROM b007_source_role_v1
                         WHERE entity_kind='media_file' AND burned_subtitle_present='UNCERTAIN'
                         AND contamination_confidence<0.4 LIMIT 1""").fetchone()
    assert r is not None
    ok_s, _ = svc.is_production_eligible("media_file", r[0], strict=True)
    ok_l, _ = svc.is_production_eligible("media_file", r[0], strict=False)
    assert ok_s is False
    assert ok_l is True  # 非 strict 仅显式放行，不代表默认


def test_clean_raw_can_enter_production():
    r = _first_clean_by_role("PRODUCTION_CLEAN_RAW")
    assert r is not None
    ok, info = svc.is_production_eligible("media_file", r[0])
    assert ok is True, info


def test_clean_semi_can_enter_production():
    r = _first_clean_by_role("PRODUCTION_CLEAN_SEMI")
    assert r is not None
    ok, info = svc.is_production_eligible("media_file", r[0])
    assert ok is True, info


def test_burned_subtitle_blocks_candidate():
    with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
        r = c.execute("""SELECT entity_id FROM b007_source_role_v1
                         WHERE entity_kind='media_file'
                         AND burned_subtitle_present='PRESENT' LIMIT 1""").fetchone()
    ok, info = svc.is_production_eligible("media_file", r[0])
    assert ok is False
    assert any("burned_subtitle_present=PRESENT" in x for x in info["reasons"])


def test_platform_watermark_blocks_candidate():
    with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
        r = c.execute("""SELECT entity_id FROM b007_source_role_v1
                         WHERE entity_kind='media_file'
                         AND platform_watermark_present='PRESENT' LIMIT 1""").fetchone()
    ok, info = svc.is_production_eligible("media_file", r[0])
    assert ok is False
    assert any("platform_watermark_present=PRESENT" in x for x in info["reasons"])


def test_path_hint_does_not_define_clean_role():
    # 服务接口不接受 path 当角色证据；角色只来自表
    assert not hasattr(svc, "role_from_path")
    row = svc.role_row("media_file", 1)
    assert row is None or "source_role" in row  # 空行也走表查询而非路径规则


def test_human_adjudication_overrides_candidate_without_overwriting_history():
    tmp = Path(tempfile.gettempdir()) / f"g1_test_{os.getpid()}.db"
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    con.execute("""CREATE TABLE b007_source_role_v1 (
        entity_kind TEXT, entity_id TEXT, source_id INTEGER, initial_prior TEXT,
        source_role TEXT, role_basis TEXT, role_confidence REAL, asset_type TEXT,
        burned_subtitle_present TEXT, platform_watermark_present TEXT,
        old_title_overlay_present TEXT, brand_overlay_present TEXT,
        unrelated_overlay_present TEXT, contamination_confidence REAL,
        contamination_evidence TEXT, environment_text_present TEXT,
        review_status TEXT, role_version INTEGER, created_at REAL, updated_at REAL,
        PRIMARY KEY (entity_kind, entity_id))""")
    con.execute("""INSERT INTO b007_source_role_v1 VALUES
        ('media_file','t1',1,'PRODUCTION_CLEAN_SEMI','PRODUCTION_CLEAN_SEMI','PRIOR',0.5,NULL,
         'PRESENT','ABSENT','ABSENT','ABSENT','ABSENT',0.9,
         '[{"reason_code":"SUBTITLE_FLAG","frames":3}]','ABSENT','REVIEW_REQUIRED',1,0,0)""")
    con.commit()
    tsvc = ProductionSourceService(str(tmp))
    tsvc.adjudicate("media_file", "t1", "rejected", "人工复核：确为旧字幕，排除")
    with sqlite3.connect(str(tmp)) as c:
        row = c.execute("SELECT contamination_evidence, review_status, role_version "
                        "FROM b007_source_role_v1 WHERE entity_id='t1'").fetchone()
    ev = json.loads(row[0])
    assert row[1] == "REJECTED"
    assert row[2] == 2
    assert any("human_adjudication" in e for e in ev)          # 追加
    assert any("SUBTITLE_FLAG" in e.get("reason_code", "") for e in ev)  # 原机器证据保留
    ok, _ = tsvc.is_production_eligible("media_file", "t1")
    assert ok is False
    for _ in range(5):
        try:
            tmp.unlink()
            break
        except PermissionError:
            import time as _t
            _t.sleep(0.3)


def test_production_consumer_uses_source_role_service():
    cands = svc.select_clean_candidates(["薄抽"], limit=5, strict=True)
    assert len(cands) > 0
    for cd in cands:
        ok, info = svc.is_production_eligible("media_file", cd["media_id"], strict=True)
        assert ok, info
        assert cd["source_role"] in ("PRODUCTION_CLEAN_RAW", "PRODUCTION_CLEAN_SEMI")
