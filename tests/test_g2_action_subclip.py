# -*- coding: utf-8 -*-
"""G2 逻辑测试(纯逻辑, 不依赖qwen): 窗口推导/语义边界分离/硬负例/长度指导。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.action_subclip import (build_windows, fit_duration, parse_qwen_state,
                                             ActionSubclipService)


def _ev(states_with_t):
    return [{"t_s": t, "state": s} for t, s in states_with_t]


def test_extend_window_detected():
    # 前OBJECT → START → IN_PROGRESS → END → 后OBJECT
    ev = _ev([(0.5, "OBJECT_PRESENT"), (2.0, "ACTION_START"), (3.0, "ACTION_IN_PROGRESS"),
              (4.0, "ACTION_END"), (5.5, "OBJECT_PRESENT")])
    wins = build_windows(ev, duration_s=6.0, action="EXTEND", media_id=1)
    assert len(wins) == 1
    w = wins[0]
    assert w.semantic_correct is True
    assert w.action_start_s == 2.0 and w.action_end_s == 4.0
    assert w.subclip_start_s <= 2.0 and w.subclip_end_s >= 4.0
    assert w.boundary_usable is True  # 前后有上下文


def test_no_action_returns_empty():
    ev = _ev([(0.5, "OBJECT_PRESENT"), (2.0, "OBJECT_PRESENT"), (3.0, "OBJECT_PRESENT")])
    assert build_windows(ev, 6.0, "EXTEND", media_id=2) == []


def test_socket_closeup_is_not_extend():
    # 文件名带"伸缩"的插座素材: 全程 NOT_PRESENT(对 EXTEND) → 无 EXTEND 窗口(硬负例核心)
    ev = _ev([(0.5, "NOT_PRESENT"), (2.0, "NOT_PRESENT"), (3.0, "NOT_PRESENT"),
              (4.0, "NOT_PRESENT"), (5.0, "NOT_PRESENT")])
    assert build_windows(ev, 6.0, "EXTEND", media_id=3) == []


def test_boundary_usable_false_when_action_at_edge():
    ev = _ev([(0.0, "ACTION_START"), (1.0, "ACTION_IN_PROGRESS"), (2.0, "ACTION_END"),
              (3.0, "OBJECT_PRESENT")])
    wins = build_windows(ev, duration_s=4.0, action="DRAWER_OPEN", media_id=4)
    assert len(wins) == 1
    assert wins[0].semantic_correct is True
    assert wins[0].boundary_usable is False  # 起始顶到 0s, 无前语境


def test_semantic_vs_boundary_separated():
    # 动作识别对(语义对)但首段缺失(边界差)
    ev = _ev([(0.0, "ACTION_IN_PROGRESS"), (1.0, "ACTION_IN_PROGRESS"), (2.0, "ACTION_END"),
              (3.5, "OBJECT_PRESENT")])
    w = build_windows(ev, 5.0, "SOCKET_INSERT", media_id=5)[0]
    assert w.semantic_correct is True and w.boundary_usable is False


def test_fit_duration_respects_guidance():
    ev = _ev([(1.0, "OBJECT_PRESENT"), (2.0, "ACTION_START"), (3.0, "ACTION_IN_PROGRESS"),
              (4.0, "ACTION_END"), (5.0, "OBJECT_PRESENT")])
    w = build_windows(ev, 6.0, "EXTEND", media_id=6)[0]
    fw = fit_duration(w, duration_target_s=3.0, shot_role="action")
    d = fw.subclip_end_s - fw.subclip_start_s
    assert 2.5 <= d <= 4.5
    assert fw.action_start_s >= fw.subclip_start_s  # 动作起点未被切掉


def test_parse_state_robust():
    assert parse_qwen_state("state=ACTION_IN_PROGRESS 桌面正在移动") == "ACTION_IN_PROGRESS"
    assert parse_qwen_state("没有伸缩动作") == "NOT_PRESENT"  # 保守
    assert parse_qwen_state("") == "NOT_PRESENT"


def test_service_topk_ordering_prefers_boundary():
    svc = ActionSubclipService(eligible_check=lambda mid, kind="media_file": (True, {}))
    svc._default_loader = lambda a: [
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 0.1, "state": "ACTION_START"},
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 1.0, "state": "ACTION_IN_PROGRESS"},
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 2.0, "state": "ACTION_END"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 3.0, "state": "OBJECT_PRESENT"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 4.0, "state": "ACTION_IN_PROGRESS"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 5.0, "state": "ACTION_END"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 6.5, "state": "OBJECT_PRESENT"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 4.0,
         "qwen_l2_raw": "direction=EXTEND", "direction_probe": True},
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 1.0,
         "qwen_l2_raw": "direction=EXTEND", "direction_probe": True},
    ]
    svc._loader = svc._default_loader
    res = svc.find_action_subclips("fixture", "EXTEND", top_k=3)
    assert len(res) >= 1
    assert res[0]["media_id"] == 11  # boundary_usable 优先


def test_subclip_within_segment_bounds():
    ev = _ev([(1.0, "OBJECT_PRESENT"), (2.5, "ACTION_START"), (3.5, "ACTION_IN_PROGRESS"),
              (4.5, "ACTION_END"), (6.0, "OBJECT_PRESENT")])
    w = build_windows(ev, 7.0, "CABINET_OPEN", media_id=12)[0]
    assert 0.0 <= w.subclip_start_s < w.subclip_end_s <= 7.0


def test_service_without_gate_fails_closed():
    # Source Audit R1 P1: 未注入 G1 资格门 → fail-closed（抛错，不静默全放行）
    svc = ActionSubclipService()
    try:
        svc.find_action_subclips("fixture", "EXTEND")
    except RuntimeError as e:
        assert "NO_ELIGIBILITY_GATE" in str(e)
    else:
        raise AssertionError("bare ActionSubclipService must fail closed")


def test_service_gate_excludes_ineligible_media():
    # Source Audit R1 P1: G1 门真实生效 —— 不合格 media 不进窗口
    svc = ActionSubclipService(eligible_check=lambda mid, kind="media_file": (True, {}) if mid == 10 else (False, {"reason": "REJECTED"}))
    svc._loader = lambda a: [
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 0.1, "state": "ACTION_START"},
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 1.0, "state": "ACTION_IN_PROGRESS"},
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 2.0, "state": "ACTION_END"},
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 3.0, "state": "OBJECT_PRESENT"},
        {"media_id": 10, "duration_s": 8.0, "full_path": "p1", "t_s": 1.0,
         "qwen_l2_raw": "direction=EXTEND", "direction_probe": True},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 3.0, "state": "ACTION_START"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 4.0, "state": "ACTION_IN_PROGRESS"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 5.0, "state": "ACTION_END"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 6.0, "state": "OBJECT_PRESENT"},
        {"media_id": 11, "duration_s": 8.0, "full_path": "p2", "t_s": 4.0,
         "qwen_l2_raw": "direction=EXTEND", "direction_probe": True},
    ]
    res = svc.find_action_subclips("fixture", "EXTEND", top_k=3)
    assert all(r["media_id"] == 10 for r in res)  # mid=11 被 G1 门拦截
    assert len(res) >= 1
