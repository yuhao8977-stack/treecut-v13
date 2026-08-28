# -*- coding: utf-8 -*-
"""Phase 3 PART B/F — Review System Productization Regression Tests。

模块级共享 app 实例（避免多 Tk 根冲突）。
"""
import os
import sys
import time
import tkinter as tk

import pytest

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

import treecut.services.phase3_review_ui as prui
from treecut.services.phase3_review_ui import TargetedReviewV1App, PlaybackController
from treecut.services.review_center import ReviewCenterWindow, task_stats, TASKS


def count_w(w):
    n = 1
    for c in w.winfo_children():
        n += count_w(c)
    return n


@pytest.fixture(scope="module")
def app():
    """共享审核窗口实例（模块级，只创建一次 Tk 根）。

    BATCH_V1 已 60/60 完成 → queue 空；播放/加载测试注入假题目数据，
    独立于真实任务完成状态。
    """
    a = TargetedReviewV1App(os.path.join(DATA_ROOT, "database", "materials.db"))
    a.withdraw()
    a._resolve_asset = lambda asset_id: r"C:\fake.mp4"
    a.pb._on_launch = lambda m, p: None
    # 注入假题目（不影响真实库）：items/queue/current 覆盖为测试数据
    fake_items = [{"segment_id": f"blind_test_segment_{i:016d}",
                   "selection_reason": "test"} for i in range(120)]
    a.items = fake_items
    a.done = set()
    a.queue = list(fake_items)
    a.idx = 0
    a._load(0)
    yield a
    a.destroy()


# ---------------------------------------------------------------------------
# Playback: one click = one launch
# ---------------------------------------------------------------------------

def test_playback_one_click_one_launch(app):
    app.pb._last.clear()
    launches = {"n": 0}
    prui.os.startfile = lambda p: launches.__setitem__("n", launches["n"] + 1)
    launches["n"] = 0
    app._play_full()
    assert launches["n"] == 1


def test_playback_double_click_one_launch(app):
    app.pb._last.clear()
    launches = {"n": 0}
    prui.os.startfile = lambda p: launches.__setitem__("n", launches["n"] + 1)
    launches["n"] = 0
    app._play_full()
    app._play_full()
    assert launches["n"] == 1  # 600ms 内防抖
    time.sleep(0.8)
    app._play_full()
    assert launches["n"] == 2  # debounce 过后允许


def test_playback_after_load100_stable(app):
    app.pb._last.clear()
    launches = {"n": 0}
    prui.os.startfile = lambda p: launches.__setitem__("n", launches["n"] + 1)
    time.sleep(0.8)
    for i in range(100):
        app._load(i)
    launches["n"] = 0
    app._play_full()
    assert launches["n"] == 1


# ---------------------------------------------------------------------------
# Widget leak / 唯一性 / trace（核心验收）
# ---------------------------------------------------------------------------

def test_widget_leak_load100_stable(app):
    app.update_idletasks()
    base = count_w(app)
    for i in range(100):
        app._load(i)
    app.update_idletasks()
    assert count_w(app) == base
    acc = []

    def find(w, cls):
        if w.winfo_class() == cls:
            acc.append(w)
        for c in w.winfo_children():
            find(c, cls)

    acc.clear(); find(app, "TPanedwindow"); assert len(acc) == 1
    acc.clear(); find(app, "Canvas"); assert len(acc) == 1


def test_mandatory_trace_100_cycles_no_leak(app):
    app.update_idletasks()
    base = count_w(app)
    for _ in range(100):
        app.form.reset()
        app.conf_var.set("中")
        app.status_var.set("已审核")
        app.conf_var.set("")
        app.status_var.set("")
    app.update_idletasks()
    assert count_w(app) == base


# ---------------------------------------------------------------------------
# Review Center 生命周期（独立 Tk 根）
# ---------------------------------------------------------------------------

def test_review_center_lifecycle_20_cycles():
    root = tk.Tk()
    root.withdraw()
    try:
        for _ in range(20):
            cen = ReviewCenterWindow(root)
            root.update_idletasks()
            cen._open_task(TASKS[1])
            root.update_idletasks()
            tw = getattr(cen, "_task_win", None)
            assert tw is not None and tw.winfo_exists()
            n0 = len([x for x in root.winfo_children() if x.winfo_class() == "Toplevel"])
            cen._open_task(TASKS[1])
            root.update_idletasks()
            n1 = len([x for x in root.winfo_children() if x.winfo_class() == "Toplevel"])
            assert n0 == n1  # 单实例
            tw.destroy()
            cen.destroy()
            root.update_idletasks()
        assert root.winfo_exists()  # Main 不因 Review 关闭退出
    finally:
        root.destroy()


def test_task_stats_complete():
    for t in TASKS:
        st = task_stats(t)
        if t["id"] in ("THIRD_ADJUDICATION_V1", "TARGETED_REVIEW_BATCH_V1"):
            # 按 manifest 成员计数（旧批次 manifest 与库存在历史漂移，仅断言范围与状态机）
            assert st["total"] > 0
            assert 0 <= st["done"] <= st["total"]
            assert st["status"] in ("完成", "进行中")
        elif t["id"] == "FRESH_HOLDOUT_V1":
            assert st["total"] == 30
            assert st["done"] == 30  # 盲审已交卷（30 条人工锁存在）
            assert st["status"] == "完成"
        elif t["id"] == "TARGETED_REVIEW_STAGE3_V3_1":
            assert st["total"] == 60  # 最终批次冻结 60 条
            assert st["done"] == 60  # 人工审核已完成并冻结
            assert st["status"] == "完成"


def test_responsive_sizes(app):
    base = count_w(app)
    for w, h in ((1600, 900), (1280, 820), (1100, 700), (980, 640)):
        app.geometry(f"{w}x{h}")
        app.update_idletasks()
        assert count_w(app) == base
    app.form._relayout_quick()
    assert count_w(app) == base
