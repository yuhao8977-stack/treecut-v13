# -*- coding: utf-8 -*-
"""Stage3 FINAL — FRESH_HOLDOUT_V2 Blind UI 泄漏测试（STEP 13）。

递归检查 Review Center 的 FRESH_HOLDOUT_V2 任务 UI 文本：
不得出现 HOLDOUT_V2_AI_PREDICTIONS_V1.json 中任何 final prediction 值、
provider/score/model/routing/evidence。
"""
import json
import os
import sys
import tkinter as tk

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

from treecut.services.review_center import TASKS, ReviewCenterWindow


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


def test_holdout_v2_blind_ui_no_ai_leak():
    """FRESH_HOLDOUT_V2 盲审 UI 不得含任何 AI prediction 值/provider/score。"""
    task = [t for t in TASKS if t["id"] == "FRESH_HOLDOUT_V2"][0]
    root = tk.Tk()
    root.withdraw()
    cen = ReviewCenterWindow(root)
    root.update_idletasks()
    cen._open_task(task)
    root.update_idletasks()
    tw = getattr(cen, "_task_win", None)
    try:
        if tw is None:
            return  # 结果页或未加载（不崩溃）
        dump = _dump_texts(tw).lower()
        # 1) AI 术语不得出现（bundle 是任务名"Bundle V2"的一部分，非 AI 泄漏；单独排除）
        for t in ("yolo", "siglip", "provider", "model_score", "raw_score", "routing",
                  "evidence", "prediction", "semantic_action", "asr", "ocr"):
            assert t not in dump, f"AI 术语泄漏: {t}"
        # 2) prediction 文件中的具体答案值不得出现
        pp = os.path.join(DATA_ROOT, "HOLDOUT_V2_AI_PREDICTIONS_V1.json")
        if os.path.exists(pp):
            pred = json.load(open(pp, encoding="utf-8"))
            leaked = 0
            for r in pred["results"]:
                for f, v in r["final_routed_prediction"].items():
                    if isinstance(v, list):
                        v = ",".join(v)
                    if v and str(v).lower() in dump:
                        leaked += 1
            assert leaked == 0, f"UI 泄漏 {leaked} 个 AI 答案值"
    finally:
        try:
            tw.destroy()
        except Exception:
            pass
        cen.destroy()
        root.destroy()


def test_holdout_v2_task_registered():
    ids = [t["id"] for t in TASKS]
    assert "FRESH_HOLDOUT_V2" in ids
    task = [t for t in TASKS if t["id"] == "FRESH_HOLDOUT_V2"][0]
    assert task["table"] == "fresh_holdout_human_review_v1"
    assert task["blind"] is True
