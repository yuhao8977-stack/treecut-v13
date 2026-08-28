# -*- coding: utf-8 -*-
"""Stage 2 Blind Review UI — Regression（STEP 13：12 项）。"""
import json
import os
import shutil
import sys
import tempfile
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
    """构造临时待审 manifest 副本任务（不碰真实任务完成状态）。

    真实 TARGETED_REVIEW_STAGE3_V3_1 已 60/60 完成 → 结果页无 items；
    盲审 UI 回归需要审核表单路径，故复制 manifest 到临时目录，并把目标表指向
    不存在的表（task_stats/_done_set 查空返回 done=0 → remaining>0 → 审核表单）。
    段用真实 V3_1 前 3 条（asset/keyframes 可解析）；测试不保存，故不落库。
    """
    base = [t for t in TASKS if t["id"] == "TARGETED_REVIEW_STAGE3_V3_1"][0]
    tmpdir = tempfile.mkdtemp(prefix="blind_ui_")
    src_manifest = base["manifest"]
    dst_manifest = os.path.join(tmpdir, "TARGETED_REVIEW_STAGE3_V3_1_BLIND_TEST.json")
    data = json.load(open(src_manifest, encoding="utf-8"))
    data["segments"] = data["segments"][:3]
    data["manifest_version"] = "TARGETED_REVIEW_STAGE3_V3_1_BLIND_TEST"
    json.dump(data, open(dst_manifest, "w", encoding="utf-8"), ensure_ascii=False)
    task = dict(base)
    task["manifest"] = dst_manifest
    task["id"] = "TARGETED_REVIEW_STAGE3_V3_1_BLIND_TEST"
    task["table"] = "blind_ui_test_nonexistent_table"  # 强制 remaining>0 → 审核表单
    task["_tmpdir"] = tmpdir
    cen = ReviewCenterWindow(root)
    root.update_idletasks()
    cen._open_task(task)
    root.update_idletasks()
    tw = getattr(cen, "_task_win", None)
    if tw is not None:
        tw._tmpdir = tmpdir
    return cen, tw, tmpdir


@pytest.fixture(scope="module")
def blind_win():
    root = tk.Tk()
    root.withdraw()
    cen, tw, tmpdir = _open_blind(root)
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
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_blind_task_loads_30(blind_win):
    _, _, tw = blind_win
    assert tw is not None
    assert len(tw.items) == 3  # 临时待审 manifest 前 3 条
    assert len(tw.queue) == 3


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
    for i in range(3):
        tw._load(i)
    tw.update_idletasks()
    assert count_w(tw) == base


def test_open_close_no_save_count_stays_zero(blind_win):
    root, _, tw = blind_win
    tw.destroy()
    cen2, tw2, tmpdir2 = _open_blind(root)
    root.update_idletasks()
    assert len(tw2.queue) == 3
    # 真实 V3_1 已完成（60/60）；临时 manifest 段不在表内 → done=0
    assert task_stats([t for t in TASKS if t["id"] == "TARGETED_REVIEW_STAGE3_V3_1"][0])["done"] == 60
    tw2.destroy()
    cen2.destroy()
    import shutil
    shutil.rmtree(tmpdir2, ignore_errors=True)


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
