# -*- coding: utf-8 -*-
"""R1-R7 修复回归测试(吸收 2026-09-03 人工裁决负反馈)。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.claim_visual import (AtomicClaim, Candidate, ClaimVisualMatcher)
from treecut.services.action_subclip import (build_windows, apply_action_gate, parse_direction)
from treecut.services.visual_beat import group_visual_beats, audit_action_availability, suggest_script_fix
from treecut.services.production_dedup import Shot, detect_duplicates

E_OK = lambda mid, kind="media_file": (True, {})


def test_r1_opposite_direction_rejected_before_topk():
    # 人工裁决: EXTEND 查询曾返回 machine=RETRACT 候选(1985等) → 必须确定性拒绝
    claim = AtomicClaim(claim_id="C", beat_id="B", text="伸缩", claim_type="ACTION", required_action="EXTEND")
    cand = Candidate(media_id=1985, actions=["RETRACT"], object_="TABLETOP")
    m = ClaimVisualMatcher(eligible_check=E_OK)
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand])
    assert res[0]["status"] == "REJECT"
    assert any("OPPOSITE_DIRECTION" in r for r in res[0]["reasons"])


def test_r1_putin_vs_takeout_rejected():
    claim = AtomicClaim(claim_id="C", beat_id="B", text="放进去", claim_type="ACTION",
                        required_action="STORAGE_PUT_IN")
    cand = Candidate(media_id=3, actions=["STORAGE_TAKE_OUT"], object_="DRAWER")
    res = ClaimVisualMatcher(eligible_check=E_OK).rank(claim, "INFORMATION_MONTAGE", [cand])
    assert res[0]["status"] == "REJECT"
    assert any("OPPOSITE_DIRECTION" in r for r in res[0]["reasons"])


def _ev(states_with_t, media_id=1):
    return [{"t_s": t, "state": s, "media_id": media_id} for t, s in states_with_t]


def test_r2_direction_gate_drops_static_claim():
    # 2482 曾因单帧 ACTION+方向 STATIC 被当 EXTEND → 门必须丢弃
    ev = _ev([(1.0, "OBJECT_PRESENT"), (2.5, "ACTION_IN_PROGRESS"), (3.0, "OBJECT_PRESENT")]) + [
        {"media_id": 2482, "t_s": 2.5, "qwen_l2_raw": "direction=STATIC", "direction_probe": True}]
    wins = build_windows(ev, 6.0, "EXTEND", media_id=2482)
    gated = apply_action_gate(wins, ev)
    assert gated == []  # STATIC → 不证明 EXTEND


def test_r2_direction_gate_keeps_matching_direction_with_2frames():
    ev = _ev([(1.0, "OBJECT_PRESENT"), (2.0, "ACTION_IN_PROGRESS"), (3.0, "ACTION_IN_PROGRESS"),
              (4.0, "ACTION_END"), (5.0, "OBJECT_PRESENT")]) + [
        {"media_id": 1, "t_s": 2.0, "qwen_l2_raw": "direction=EXTEND", "direction_probe": True}]
    wins = build_windows(ev, 6.0, "EXTEND", media_id=1)
    gated = apply_action_gate(wins, ev)
    assert len(gated) == 1 and gated[0].action == "EXTEND"


def test_r2_open_close_ambiguity_dropped():
    # 同素材同刻 open+close 并存 → 歧义丢弃(不猜方向)
    ev = _ev([(0.5, "OBJECT_PRESENT"), (2.0, "ACTION_IN_PROGRESS"), (3.0, "ACTION_IN_PROGRESS"), (4.5, "OBJECT_PRESENT")])
    wins = build_windows(ev, 6.0, "DRAWER_OPEN", media_id=7) + build_windows(ev, 6.0, "DRAWER_CLOSE", media_id=7)
    gated = apply_action_gate(wins, ev)
    assert gated == []


def test_r4_group_16_claims_to_5_visual_beats():
    claims = []
    import json
    claims = json.loads(Path(r"C:\Users\admin\github\treecut-v13\reports\storage\TREECUT_G3_ATOMIC_CLAIMS_V1.json")
                        .read_text(encoding="utf-8"))["claims"]
    beats = group_visual_beats(claims)
    # 16 文本 claim → ≤6 视觉段; "第一/第二/第三" 不单独成段
    assert len(beats) <= 6
    joined = "".join(b["text"] for b in beats)
    assert "第一" in joined and "第二" in joined and "第三" in joined  # 结构词仍在, 但已并入
    assert all(not (b["text"].strip() in ("第一", "第二", "第三")) for b in beats)


def test_r5_unsupported_action_blocks_production():
    avail = audit_action_availability(["SOCKET_INSERT", "EXTEND"],
                                      {"EXTEND": [1]}, {"SOCKET_INSERT": [1590]})
    assert avail["SOCKET_INSERT"]["status"] == "OBJECT_ONLY_NO_ACTION_EVIDENCE"
    sug = suggest_script_fix("轨道插座插拔也顺手", avail)
    assert sug["production_blocked"] is True  # 插拔无动作素材 → 不许静默配画面
    assert any("SOCKET_INSERT" in n for n in sug["notes"])


def test_r7_narrative_requires_same_presenter_and_folder():
    # 人工裁决 PAIR01/03/04 = FALSE_POSITIVE(不同功能文件夹/人物) → 不得命中
    a = Shot(media_id=1, folder_hint="【01】上层薄抽", case_id="王小姐", shot_role="feature")
    b = Shot(media_id=1591, folder_hint="【05】公牛轨道插座", case_id="王小姐", shot_role="feature")
    assert detect_duplicates([a, b]) == []


def test_r7_pair02_still_detected_warning():
    # PAIR02 = TRUE_DUPLICATE: 同人+同功能文件夹(不同 role) → 至少 WARNING
    a = Shot(media_id=2, folder_hint="【01】上层薄抽", case_id="王小姐", shot_role="feature")
    b = Shot(media_id=99, folder_hint="【01】上层薄抽", case_id="王小姐", shot_role="cta")
    hits = detect_duplicates([a, b])
    assert hits and hits[0]["level"] == "NARRATIVE_NEAR_DUPLICATE"
    assert hits[0]["strength"] in ("WARNING", "HIGH")
    assert "same_presenter" in hits[0]["reason"] and "same_function_folder" in hits[0]["reason"]


def test_parse_direction():
    assert parse_direction("direction=STATIC") == "STATIC"
    assert parse_direction("direction=EXTEND 桌面在动") == "EXTEND"
    assert parse_direction("no token") == "UNCERTAIN"
