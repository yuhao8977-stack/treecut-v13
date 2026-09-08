# -*- coding: utf-8 -*-
"""A0 R1 tests — verify against REAL evidence files (baseline/db/artifacts),
NOT against RESULT self-strings. Reads machine-generated JSONs."""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_real_baseline_clean():
    b = load("TREECUT_A0R1_REAL_BASELINE.json")
    # START state was clean (git empty at bdc7506 BEFORE any A0R1 file existed)
    s = b["start_state_before_a0r1"]
    assert s["tracked_clean"] is True
    assert s["untracked_count"] == 0
    # GENERATION-time: no tracked modifications; untracked = A0R1 audit outputs only
    assert b["tracked_files_clean"] is True
    assert b["tracked_diff_name_status"] == []
    assert b["untracked_count"] >= 13  # A0R1 outputs/scripts, never pre-existing files
    assert b["untracked_all_are_a0r1_outputs"] is True
    assert b["untracked_entries_kinds"] == ["??"]
    assert b["head"] == b["origin_main"]
    assert b["branch"] == "main"


def test_db_evidence_real_counts():
    d = load("TREECUT_A0R1_RAW_DB_EVIDENCE.json")
    assert d["cam_join"]["segments"] == 41834
    assert d["cam_join"]["segments_without_asset"] == 0
    # A0 wrong \X1 mapping corrected in path file
    p = load("TREECUT_A0R1_PATH_VALIDITY_CORRECTED.json")
    assert p["total"] == 15378
    assert p["path_valid"] > 15000  # real majority valid (not the wrong-0 from A0)


def test_historical_two_success_same_input():
    h = load("TREECUT_A0R1_HISTORICAL_ARTIFACT_MANIFEST.json")
    succ = [k for k, v in h.items() if v.get("status") == "success"]
    assert len(succ) == 2
    nar = set()
    for k in succ:
        rep = h[k].get("report") or {}
        nar.add(str(rep.get("request_narration"))[:40])
    assert len(nar) == 1  # same input rerun, not 2 independent E2E


def test_current_reproduction_render_only():
    r = load("TREECUT_A0R1_CURRENT_REPRODUCTION.json")
    assert r["mp4"]["exists"] is True  # render stage output real
    assert r["status"] == "failed"
    assert "date.fst" in r.get("error", "")  # TTS blocker evidence


def test_three_e2e_target_blocker_not_none():
    t = load("TREECUT_A0R1_THREE_E2E_TRACE.json")
    assert t["C_TARGET_PRODUCT_CHAIN"]["first_blocker"] == "SCRIPT_TO_BEAT_CLAIM_NOT_FOUND"
    assert t["FIRST_REAL_TARGET_BLOCKER"] != "NONE"


def test_gap_counts_all_match():
    g = load("TREECUT_A0R1_GAP_MAP.json")
    res = load("TREECUT_A0R1_RESULT.json")
    assert len(g["P0_PRODUCT_BLOCKERS"]) == res["gap_counts"]["P0"]
    assert len(g["P1_PRODUCT"]) == res["gap_counts"]["P1"]
    assert len(g["P2_PRODUCT"]) == res["gap_counts"]["P2"] == 2  # fixed (was 3 wrong)
    assert len(g["RESEARCH_NOT_BLOCKING_MVP"]) == res["gap_counts"]["RESEARCH"]


def test_capability_regrade_downgrades():
    m = load("TREECUT_A0R1_CAPABILITY_MATRIX.json")
    items = {i["capability_id"]: i for i in m["items"]}
    # historical-only chain outputs must NOT claim current E2E_PROVEN
    assert items["H1_mp4_final"]["current_level"] == "NOT_REACHED_CURRENT"
    assert items["H1_mp4_final"]["historical_level"] == "HISTORICALLY_E2E_PROVEN"
    assert items["C3_feedback"]["current_level"] == "CODE_PATH_CONNECTED"  # no counterfactual
    assert items["D2_script_beat"]["current_level"] == "NOT_FOUND"
    # USER_USABLE not claimed live without session
    assert items["H3_desktop_ui"]["current_level"] == "USER_USABLE_NOT_PROVEN_LIVE"


def test_n0_state_from_real_file():
    n0 = load("TREECUT_CAM01_EH02N0_ARCHITECT_DECISION_STATUS.json")
    assert n0["N1_APPROVED"] is False
    assert n0["PRESENT"] == "YES"
    assert n0["ESTABLISHED"] == "NO"
    assert n0["GEOM_ALLOWED"] == "NO"


def test_evidence_index_all_exist():
    idx = load("TREECUT_A0R1_EVIDENCE_INDEX.json")
    assert idx["count"] == len(idx["entries"])
    for e in idx["entries"]:
        p = OUT / e["path"]
        assert p.exists(), e["path"]
        assert e["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
