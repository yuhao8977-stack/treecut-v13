# -*- coding: utf-8 -*-
"""V2 集成回归: 窗口级负例记忆/素材可跨动作复用/不同窗OPEN+CLOSE共存/Beat保留Claims/展开检索语义。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.action_subclip import build_windows, apply_action_gate
from treecut.services.claim_visual import AtomicClaim, Candidate, ClaimVisualMatcher
from treecut.services.visual_beat import group_visual_beats, suggest_script_fix
from treecut.services.claim_visual import parse_script_to_claims

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
E_OK = lambda mid, kind="media_file": (True, {})


def _mem():
    return json.loads((OUT / "TREECUT_REVIEW_EXAMPLE_MEMORY_V1.json").read_text(encoding="utf-8"))


def test_memory_is_window_scoped_not_asset_blacklist():
    m = _mem()
    for e in m["memory"]:
        assert e["review_scope"] == "SUBCLIP_WINDOW"
        assert e["reviewed_window_start"] is not None  # 有精确被审窗
    # 1985 负例存在
    ex = [e for e in m["memory"] if e["segment_id"] == "1985" and e["requested_action"] == "EXTEND"]
    assert ex, "1985/EXTEND 负例应存在"
    # supports map 保留 1985 其它语义
    sup = m.get("supports_by_segment", {})
    assert "1985" in sup
    assert any("SOCKET" in s for s in sup["1985"]["supports"]), "1985 应保留 TRACK_SOCKET 可用性"


def test_same_asset_other_semantics_still_usable():
    # EXTEND 对 1985 无效, 但 TRACK_SOCKET(对象主张) 应可 PASS(不是 BAD MATERIAL)
    claim = AtomicClaim(claim_id="C", beat_id="B", text="轨道插座", claim_type="OBJECT",
                        required_object="TRACK_SOCKET")
    cand = Candidate(media_id=1985, actions=[], object_="TRACK_SOCKET")
    m = ClaimVisualMatcher(eligible_check=E_OK)
    res = m.rank(claim, "INFORMATION_MONTAGE", [cand])
    # 无 required_action → 对象主张无需动作证据
    assert res[0]["status"] == "PASS"


def test_open_close_distinct_windows_coexist():
    # 同一素材 0-3s OPEN 与 8-11s CLOSE 不同窗, 各带逐窗方向证据 → 共存(仅同窗重叠才丢)
    ev = [{"t_s": 0.5, "state": "OBJECT_PRESENT", "media_id": 1},
          {"t_s": 1.5, "state": "ACTION_IN_PROGRESS", "media_id": 1},
          {"t_s": 2.5, "state": "ACTION_IN_PROGRESS", "media_id": 1},
          {"t_s": 3.5, "state": "OBJECT_PRESENT", "media_id": 1},
          {"t_s": 8.5, "state": "OBJECT_PRESENT", "media_id": 1},
          {"t_s": 9.5, "state": "ACTION_IN_PROGRESS", "media_id": 1},
          {"t_s": 10.5, "state": "ACTION_IN_PROGRESS", "media_id": 1},
          {"t_s": 11.5, "state": "OBJECT_PRESENT", "media_id": 1},
          {"t_s": 1.5, "qwen_l2_raw": "direction=DRAWER_OPEN", "direction_probe": True, "media_id": 1},
          {"t_s": 9.5, "qwen_l2_raw": "direction=DRAWER_CLOSE", "direction_probe": True, "media_id": 1}]
    wopen = build_windows(ev, 13.0, "DRAWER_OPEN", media_id=1)
    wclose = build_windows(ev, 13.0, "DRAWER_CLOSE", media_id=1)
    g = apply_action_gate(wopen + wclose, ev)
    assert len(g) == 2
    acts = sorted(x.action for x in g)
    assert "DRAWER_OPEN" in acts and "DRAWER_CLOSE" in acts  # 两窗按各自方向证据共存


def test_visual_beat_retains_atomic_claims():
    SCRIPT = ("岛台想好用，这三个细节最值得看。第一，上层薄抽，收纳小物不弯腰，打开就能拿到。"
              "第二，轨道插座，吃火锅煮茶都方便，插拔也顺手。"
              "第三，伸缩桌面，来客时一拉就变宽，平时收起来不占位。厨房好不好用，全在这些小细节里。")
    claims = parse_script_to_claims(SCRIPT)
    beats = group_visual_beats([c.__dict__ for c in claims])
    total = sum(len(b["claims"]) for b in beats)
    assert total == len(claims)  # 合并不丢 claim
    assert any(len(b["claims"]) >= 3 for b in beats)  # 功能段含多 claim


def test_no_source_note_triggers_expand_retrieval_semantics():
    q = json.loads((OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").read_text(encoding="utf-8"))["queries"]
    empty = [x for x in q if x["top3_n"] == 0]
    assert empty, "当前候选集耗尽应为 NO_VALID(触发 EXPAND_RETRIEVAL) 而非假候选"
    assert all("EXPAND_RETRIEVAL" in x["note"] or "NO_VALID" in x["note"] for x in empty)


def test_rewrite_does_not_invent_unsupported_claim():
    sug = suggest_script_fix("轨道插座插拔也顺手",
                             {"SOCKET_INSERT": {"status": "NO_SOURCE", "windows": 0, "hints": 0}})
    assert sug["production_blocked"] is True
    # 不改写不伪造: 仅产出改写指示(占位), 不产出"插拔已支持"的新文案
    assert "fixed_text_placeholder" in sug
    assert any("SOCKET_INSERT" in n for n in sug["notes"])
