# -*- coding: utf-8 -*-
"""Stage 2 Blind Review UI — Regression（STEP 13：12 项）。"""
import json
import os
import sys
import tkinter as tk

import pytest

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.review_center import TASKS, task_stats, ReviewCenterWindow
from treecut.services.phase3_review_ui import _V21Form


def count_w(w):
    n = 1
    for c in w.winfo_children():
        n += count_w(c)
    return n


def _open_blind(root):
    # 盲审 UI 回归：FRESH_HOLDOUT_V1 已交卷（30/30）→ 结果页无 items；
    # 改用待审的 TARGETED_REVIEW_STAGE3_V3（60 条，blind=True，同一 ReviewTaskWindow 路径）。
    hold = [t for t in TASKS if t["id"] == "TARGETED_REVIEW_STAGE3_V3"][0]
    cen = ReviewCenterWindow(root)
    root.update_idletasks()
    cen._open_task(hold)
    root.update_idletasks()
    tw = getattr(cen, "_task_win", None)
    return cen, tw


@pytest.fixture(scope="module")
def blind_win():
    root = tk.Tk()
    root.withdraw()
    cen, tw = _open_blind(root)
    yield root, cen, tw
    try:
        tw.destroy()
    except Exception:
        pass
    try:
        cen.destroy()
    except Exception:
        pass
    root.destroy()


def test_blind_task_loads_30(blind_win):
    _, _, tw = blind_win
    assert tw is not None
    assert len(tw.items) == 60  # V3 最终批次冻结 60 条
    assert len(tw.queue) == 60


def test_current_record_non_null(blind_win):
    _, _, tw = blind_win
    assert tw.current is not None
    assert tw.current["segment_id"]


def test_segment_metadata_populates(blind_win):
    _, _, tw = blind_win
    txt = tw.info.get("1.0", "end")
    assert "片段编号" in txt and "素材" in txt and "时间范围" in txt


def test_v21form_instance_one(blind_win):
    _, _, tw = blind_win
    forms = [x for x in tw.__dict__.values() if isinstance(x, _V21Form)]
    assert len(forms) == 1


def test_blind_form_has_human_fields(blind_win):
    _, _, tw = blind_win
    dump = _dump_texts(tw)
    for label in ("场景类别", "产品类别", "材质", "组件", "功能", "动作类别",
                  "景别", "镜头角色", "人物", "质量分"):
        assert label in dump, f"缺失字段 {label}"


def test_blind_form_zero_ai_fields(blind_win):
    _, _, tw = blind_win
    dump = _dump_texts(tw)
    ai_terms = ("SIGLIP", "provider", "model_score", "raw_score", "routing",
                "evidence_sufficiency", "bundle", "prediction")
    for t in ai_terms:
        assert t.lower() not in dump.lower(), f"AI 信息泄漏: {t}"


def test_blind_ui_text_dump_no_prediction_values(blind_win):
    """盲审 UI 文本不得包含 30 条 AI 预测文件中的任何 prediction 值。"""
    _, _, tw = blind_win
    dump = _dump_texts(tw).lower()
    pp = os.path.join(DATA_ROOT, "HOLDOUT_AI_PREDICTIONS_V1.json")
    if os.path.exists(pp):
        pred = json.load(open(pp, encoding="utf-8"))
        leaked = 0
        for seg in pred["segments"]:
            for f, v in seg["fields"].items():
                val = v.get("final") if isinstance(v, dict) else None
                if isinstance(val, list):
                    val = ",".join(val)
                if val and str(val).lower() in dump:
                    leaked += 1
        assert leaked == 0, f"UI 泄漏 {leaked} 个 AI prediction 值"


def test_load30_widget_count_stable(blind_win):
    _, _, tw = blind_win
    tw.update_idletasks()
    base = count_w(tw)
    for i in range(60):
        tw._load(i)
    tw.update_idletasks()
    assert count_w(tw) == base


def test_open_close_no_save_count_stays_zero(blind_win):
    root, _, tw = blind_win
    tw.destroy()
    cen2, tw2 = _open_blind(root)
    root.update_idletasks()
    assert len(tw2.queue) == 60
    assert task_stats([t for t in TASKS if t["id"] == "TARGETED_REVIEW_STAGE3_V3"][0])["done"] == 0
    tw2.destroy()
    cen2.destroy()


def test_prediction_hash_unchanged():
    lock = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_PREDICTION_LOCK.json"),
                          encoding="utf-8"))
    assert lock["prediction_sha256"] == "f5c7c5e70c0fa299"
    assert lock["state"]["DO_NOT_REPREDICT"] is True
    assert lock["state"]["PREDICTION_LOCKED"] is True


def test_human_review_started_false():
    lock = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_PREDICTION_LOCK.json"),
                          encoding="utf-8"))
    assert lock["state"]["HUMAN_REVIEW_STARTED"] is False


def _dump_texts(w):
    parts = []
    stack = [w]
    while stack:
        cur = stack.pop()
        cls = cur.winfo_class()
        try:
            if cls in ("Label", "TLabel"):
                parts.append(cur.cget("text") or "")
            elif cls == "Text":
                parts.append(cur.get("1.0", "end"))
            elif cls in ("Entry", "TEntry"):
                parts.append(cur.get())
        except Exception:
            pass
        for c in cur.winfo_children():
            stack.append(c)
    return "\n".join(parts)
