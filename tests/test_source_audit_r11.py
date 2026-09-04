# -*- coding: utf-8 -*-
"""SOURCE AUDIT CORRECTION WAVE R1.1 — 确定性收口回归（Deterministic Closure）。

覆盖: G1 媒体契约/集成 / Pilot Source QA 事实分离与 entity_kind 隔离 /
R2 canonical 相机委托(静态守卫+行为) / affine inlier ratio / Enforcement 无 env 后门 /
Workbench replace 契约 + 动作保留 trim + local_reqa CAPTION_SIZE 诚实 / (本地规则不冒充完整 QA)。
"""
import json
import sqlite3
import sys
import threading
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from treecut.services.production_source import ProductionSourceService, CONTAM_FIELDS
from treecut.services.action_subclip import ActionSubclipService
from treecut.services.claim_visual import AtomicClaim, Candidate, ClaimVisualMatcher
from treecut.services.mmvl_master_v1 import (CameraMotionEstimator, ShadowGate, MMVVMode,
                                             compensate_pair)

R2_SCRIPT = REPO / "scripts" / "sprintv2_mmv_r2.py"


# ---------------------------------------------------------------
# helpers
# ---------------------------------------------------------------
def _mk_db(tmp_path, rows):
    """rows: list of dict(entity_kind, entity_id, source_role, review_status, cont fields...)."""
    db = tmp_path / "g1.db"
    c = sqlite3.connect(db)
    c.execute("""CREATE TABLE b007_source_role_v1 (
        entity_kind TEXT, entity_id TEXT, source_id INTEGER, source_role TEXT,
        burned_subtitle_present TEXT, platform_watermark_present TEXT,
        old_title_overlay_present TEXT, brand_overlay_present TEXT,
        unrelated_overlay_present TEXT, review_status TEXT)""")
    for r in rows:
        c.execute("INSERT INTO b007_source_role_v1(entity_kind, entity_id, source_id, source_role, "
                  "burned_subtitle_present, platform_watermark_present, old_title_overlay_present, "
                  "brand_overlay_present, unrelated_overlay_present, review_status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (r.get("entity_kind", "media_file"), str(r["entity_id"]), 1,
                   r.get("source_role", "PRODUCTION_CLEAN_RAW"),
                   r.get("burned_subtitle_present", "ABSENT"),
                   r.get("platform_watermark_present", "ABSENT"),
                   r.get("old_title_overlay_present", "ABSENT"),
                   r.get("brand_overlay_present", "ABSENT"),
                   r.get("unrelated_overlay_present", "ABSENT"),
                   r.get("review_status", "APPROVED")))
    c.commit()
    c.close()
    return str(db)


def _frames_for(mid, kind="action"):
    if kind == "action":
        return [{"media_id": mid, "duration_s": 8.0, "full_path": "p", "t_s": 0.1, "state": "ACTION_START"},
                {"media_id": mid, "duration_s": 8.0, "full_path": "p", "t_s": 1.0, "state": "ACTION_IN_PROGRESS"},
                {"media_id": mid, "duration_s": 8.0, "full_path": "p", "t_s": 2.0, "state": "ACTION_END"},
                {"media_id": mid, "duration_s": 8.0, "full_path": "p", "t_s": 3.0, "state": "OBJECT_PRESENT"},
                {"media_id": mid, "duration_s": 8.0, "full_path": "p", "t_s": 1.0,
                 "qwen_l2_raw": "direction=EXTEND", "direction_probe": True}]
    return [{"media_id": mid, "duration_s": 8.0, "full_path": "p", "t_s": 3.0, "state": "OBJECT_PRESENT"}]


# ---------------------------------------------------------------
# 1. 真 ProductionSourceService 媒体契约 + 集成
# ---------------------------------------------------------------
def test_real_media_gate_contract(tmp_path):
    db = _mk_db(tmp_path, [
        {"entity_id": 10, "source_role": "PRODUCTION_CLEAN_RAW", "review_status": "APPROVED"},
        {"entity_id": 11, "source_role": "PRODUCTION_CLEAN_RAW", "review_status": "PENDING",
         "platform_watermark_present": "PRESENT"},
        {"entity_id": 12, "source_role": "PRODUCTION_CLEAN_RAW", "review_status": "PENDING",
         "platform_watermark_present": "UNCERTAIN"},
        {"entity_id": 13, "source_role": "PUBLISHED_REFERENCE", "review_status": "APPROVED"},
    ])
    svc = ProductionSourceService(db)
    ok10, info10 = svc.is_media_production_eligible(10)
    assert ok10 is True and info10["eligible"] is True
    ok11, _ = svc.is_media_production_eligible(11)
    assert ok11 is False  # watermark PRESENT 排除
    ok12, _ = svc.is_media_production_eligible(12)
    assert ok12 is False  # strict: UNCERTAIN 阻断
    ok13, _ = svc.is_media_production_eligible(13)
    assert ok13 is False  # 角色不 CLEAN
    # 无记录
    okX, infoX = svc.is_media_production_eligible(999)
    assert okX is False and infoX.get("reason") == "NO_ROLE_ROW"


def test_g2_real_eligibility_adapter(tmp_path):
    db = _mk_db(tmp_path, [
        {"entity_id": 10, "review_status": "APPROVED"},
        {"entity_id": 11, "review_status": "PENDING", "platform_watermark_present": "PRESENT"},
    ])
    svc = ProductionSourceService(db)
    s = ActionSubclipService(eligible_check=svc.is_media_production_eligible)
    s._loader = lambda a: _frames_for(10) + _frames_for(11)
    res = s.find_action_subclips("fixture", "EXTEND", top_k=5)
    assert res and all(r["media_id"] == 10 for r in res)  # mid=11 被真 G1 门拦截


def test_g3_real_eligibility_adapter(tmp_path):
    db = _mk_db(tmp_path, [
        {"entity_id": 10, "review_status": "APPROVED"},
        {"entity_id": 11, "review_status": "PENDING", "platform_watermark_present": "PRESENT"},
    ])
    svc = ProductionSourceService(db)
    claim = AtomicClaim(claim_id="C1", beat_id="B1", text="拉开以后变宽", claim_type="ACTION",
                        required_action="EXTEND")
    good = Candidate(media_id=10, object_="TABLETOP", actions=["EXTEND"])
    bad = Candidate(media_id=11, object_="TABLETOP", actions=["EXTEND"])
    m = ClaimVisualMatcher(eligible_check=svc.is_media_production_eligible)
    r_good = m.rank(claim, "INFORMATION_MONTAGE", [good])
    r_bad = m.rank(claim, "INFORMATION_MONTAGE", [bad])
    assert r_good[0]["status"] == "PASS"
    assert r_bad[0]["status"] == "REJECT"
    assert any("SOURCE_NOT_ELIGIBLE" in x for x in r_bad[0]["reasons"])


# ---------------------------------------------------------------
# 2. Pilot Source QA 独立事实 + entity_kind 隔离
# ---------------------------------------------------------------
def test_source_qa_entity_kind_isolation(tmp_path):
    # 同 entity_id 出现在非 media_file kind 不得影响媒体判定
    db = _mk_db(tmp_path, [
        {"entity_id": 42, "review_status": "APPROVED"},
    ])
    c = sqlite3.connect(db)
    c.execute("INSERT INTO b007_source_role_v1(entity_kind, entity_id, source_role, review_status, "
              "platform_watermark_present) VALUES (?,?,?,?,?)",
              ("b007_asset", "42", "PRODUCTION_CLEAN_RAW", "REJECTED", "PRESENT"))
    c.commit()
    c.close()
    svc = ProductionSourceService(db)
    ok, _ = svc.is_media_production_eligible(42)
    assert ok is True  # media_file 行 APPROVED/ABSENT 决定；asset 行 REJECTED 不干扰
    f = svc.media_source_facts(42)
    assert f["exists"] is True and f["eligible"] is True
    assert f["contamination"]["platform_watermark_present"] == "ABSENT"


def test_source_qa_independent_contamination_facts(tmp_path):
    # brand UNCERTAIN → 资格 False；但单字段事实独立：burned=ABSENT 仍 True 表达
    db = _mk_db(tmp_path, [
        {"entity_id": 7, "review_status": "PENDING", "brand_overlay_present": "UNCERTAIN"},
    ])
    svc = ProductionSourceService(db)
    f = svc.media_source_facts(7)
    assert f["eligible"] is False  # strict: brand UNCERTAIN 阻断资格
    assert f["contamination"]["burned_subtitle_present"] == "ABSENT"
    assert f["contamination"]["brand_overlay_present"] == "UNCERTAIN"
    # 字段值独立可报告（Pilot 映射: burned→OLD_SUBTITLE_ABSENT=True, 但资格仍 NOT_VERIFIED）


# ---------------------------------------------------------------
# 4/5/6. R2 canonical 相机委托 + affine inlier
# ---------------------------------------------------------------
def test_r2_script_delegates_to_canonical_camera():
    txt = R2_SCRIPT.read_text(encoding="utf-8")
    assert "compensate_pair" in txt, "R2 runner 必须调用 canonical compensate_pair"
    assert "camera_stage" not in txt, "R2 runner 不得再含独立 camera_stage 重复算法"
    assert "estimateAffinePartial2D" not in txt, "R2 runner 不得含独立 affine 实现"
    assert "phaseCorrelate" not in txt, "R2 runner 不得含独立 translation 实现"


def test_compensate_pair_behavior():
    rng = np.random.default_rng(3)
    img = np.full((120, 160), 40, dtype=np.uint8)
    for _ in range(30):
        x1 = int(rng.integers(0, 140)); y1 = int(rng.integers(0, 100))
        cv2.rectangle(img, (x1, y1), (x1 + 15, y1 + 15), int(rng.integers(90, 255)), -1)
    a = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    b = cv2.warpAffine(a, np.float32([[1, 0, 5.0], [0, 1, 3.0]]), (160, 120))
    wb, m = compensate_pair(a, b)
    assert m.translation_px >= 3.0
    raw = float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())
    comp = float(np.abs(a.astype(np.float32) - wb.astype(np.float32)).mean())
    assert comp < 0.5 * raw


def test_affine_inlier_ratio_is_float():
    # estimateAffinePartial2D 第二返回值是 inlier mask；实现必须转 mean() 浮点，不得 float(mask)
    rng = np.random.default_rng(4)
    img = np.full((120, 160), 40, dtype=np.uint8)
    for _ in range(30):
        x1 = int(rng.integers(0, 140)); y1 = int(rng.integers(0, 100))
        cv2.rectangle(img, (x1, y1), (x1 + 15, y1 + 15), int(rng.integers(90, 255)), -1)
    a = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    Mrot = cv2.getRotationMatrix2D((80, 60), 2.0, 1.0)
    b = cv2.warpAffine(a, Mrot, (160, 120))
    m = CameraMotionEstimator().estimate(a, b)
    assert isinstance(m.inlier_ratio, float)
    assert 0.0 <= m.inlier_ratio <= 1.0
    assert isinstance(m.residual, float)


# ---------------------------------------------------------------
# 7. Enforcement 无 env 后门
# ---------------------------------------------------------------
def test_enforcement_never_bypassable_by_env(monkeypatch):
    monkeypatch.setenv("TREECUT_MMVV_ENFORCEMENT_ALLOW", "1")
    with pytest.raises(ValueError, match="MMVV_ENFORCEMENT_BLOCKED"):
        ShadowGate(MMVVMode.ENFORCEMENT)


# ---------------------------------------------------------------
# 8/9/10. Workbench: replace 契约 / 动作保留 trim / local_reqa 诚实
# ---------------------------------------------------------------
def _start_server(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "tools" / "production_workbench"))
    import http.client
    import importlib
    wb = importlib.import_module("server")
    proj = {"project_id": "P1", "beats": [{
        "id": "B1",
        "claim": {"required_action": "EXTEND"},
        "candidates": [{"media_id": 10, "object_": "TABLETOP", "actions": ["EXTEND"],
                        "path": "C:/x.mp4", "subclip": {"start_s": 1.0, "end_s": 4.0},
                        "action_start_s": 2.0, "action_end_s": 3.5}],
        "selected": None}]}
    pf = tmp_path / "proj.json"
    pf.write_text(json.dumps(proj, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wb, "PROJECT_FILE", pf)
    monkeypatch.setattr(wb, "_probe_duration", lambda p: 10.0)
    srv = wb.ThreadingHTTPServer(("127.0.0.1", 0), wb.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return wb, srv, http.client.HTTPConnection("127.0.0.1", srv.server_address[1])


def _post(conn, path, payload):
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    return r.status, json.loads(r.read().decode("utf-8"))


def test_workbench_replace_invalid_candidate_400(tmp_path, monkeypatch):
    import cv2  # noqa: F401  (server import 依赖)
    wb, srv, conn = _start_server(tmp_path, monkeypatch)
    try:
        st, j = _post(conn, "/api/replace",
                      {"beat_id": "B1", "selection": {"media_id": 999, "subclip": {"start_s": 1.0, "end_s": 2.0}}})
        assert st == 400 and "INVALID_CANDIDATE" in j.get("error", "")
    finally:
        srv.shutdown(); conn.close()


def test_workbench_trim_preserves_action_window(tmp_path, monkeypatch):
    import cv2  # noqa: F401
    wb, srv, conn = _start_server(tmp_path, monkeypatch)
    try:
        # 先合法 replace 选中候选（action 窗 [2.0,3.5]）
        st, j = _post(conn, "/api/replace",
                      {"beat_id": "B1", "selection": {"media_id": 10, "subclip": {"start_s": 1.0, "end_s": 4.0}}})
        assert st == 200, j
        # 裁掉动作窗 → 400 ACTION_EVIDENCE_TRIMMED_OUT
        st, j = _post(conn, "/api/trim", {"beat_id": "B1", "start_s": 0.0, "end_s": 1.9})
        assert st == 400 and "ACTION_EVIDENCE_TRIMMED_OUT" in j.get("error", "")
        # 保留动作窗 → 200
        st, j = _post(conn, "/api/trim", {"beat_id": "B1", "start_s": 1.5, "end_s": 3.8})
        assert st == 200, j
    finally:
        srv.shutdown(); conn.close()


def test_workbench_local_qa_caption_size_honest(tmp_path, monkeypatch):
    wb, srv, conn = _start_server(tmp_path, monkeypatch)
    try:
        st, j = _post(conn, "/api/replace",
                      {"beat_id": "B1", "selection": {"media_id": 10, "subclip": {"start_s": 1.0, "end_s": 4.0}}})
        assert st == 200
        proj = json.loads(wb.PROJECT_FILE.read_text(encoding="utf-8"))
        beat = proj["beats"][0]
        qa = wb.local_reqa(proj, beat)
        cap = next((q for q in qa if q["key"] == "CAPTION_SIZE"), None)
        assert cap is not None and cap["status"] != "PASS"
        assert "CONFIG_EXPECTED" in cap["detail"]
    finally:
        srv.shutdown(); conn.close()
