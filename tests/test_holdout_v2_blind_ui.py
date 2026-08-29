# -*- coding: utf-8 -*-
"""Stage3 FINAL — FRESH_HOLDOUT_V2 Blind UI 泄漏测试（STEP 13）。

用临时 manifest 构造"进行中"盲审任务（真实任务已 30/30 完成 → 结果页）。
检查审核表单页文本：
  - 不得出现 AI 术语（provider/score/routing/evidence/prediction/model/yolo/siglip/asr/ocr）
  - 表单自带合法标签（YES/NO/ISLAND/FACTORY 等是 V2.1 选项，属表单非 AI 泄漏）不判泄漏；
    仅检查 prediction 中的"AI 特有组合值"（如同时含多个标签的长串）不出现。
"""
import json
import os
import shutil
import sys
import tempfile
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


def _open_pending_v2(root):
    """构造临时"进行中"盲审任务（manifest 前 3 条 + 目标表指向空表 → remaining>0）。"""
    base = [t for t in TASKS if t["id"] == "FRESH_HOLDOUT_V2"][0]
    tmpdir = tempfile.mkdtemp(prefix="hv2_blind_")
    data = json.load(open(base["manifest"], encoding="utf-8"))
    data["strata"] = data["strata"][:3]
    data["manifest_version"] = "FRESH_HOLDOUT_V2_BLIND_TEST"
    dst = os.path.join(tmpdir, "FRESH_HOLDOUT_V2_BLIND_TEST.json")
    json.dump(data, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
    task = dict(base)
    task["manifest"] = dst
    task["table"] = "blind_ui_test_nonexistent_table"
    cen = ReviewCenterWindow(root)
    root.update_idletasks()
    cen._open_task(task)
    root.update_idletasks()
    tw = getattr(cen, "_task_win", None)
    return cen, tw, tmpdir


def test_holdout_v2_blind_ui_no_ai_leak():
    """FRESH_HOLDOUT_V2 盲审审核页不得含 AI 术语/预测特有值。"""
    root = tk.Tk()
    root.withdraw()
    cen, tw, tmpdir = _open_pending_v2(root)
    try:
        assert tw is not None, "应打开审核表单页（remaining>0）"
        dump = _dump_texts(tw).lower()
        # 1) AI 术语
        for t in ("yolo", "siglip", "provider", "model_score", "raw_score", "routing",
                  "evidence", "prediction", "semantic_action", "asr", "ocr"):
            assert t not in dump, f"AI 术语泄漏: {t}"
        # 2) 表单含合法标签（证明表单正常显示）
        for label in ("场景类别", "产品类别", "材质", "组件", "功能", "动作类别",
                      "景别", "镜头角色", "人物", "质量分"):
            assert label in dump, f"表单缺字段: {label}"
        # 3) AI prediction 文件的"多标签组合值"不得出现在 UI（单个合法标签排除）
        pp = os.path.join(DATA_ROOT, "HOLDOUT_V2_AI_PREDICTIONS_V1.json")
        if os.path.exists(pp):
            pred = json.load(open(pp, encoding="utf-8"))
            combo_values = set()
            for r in pred["results"]:
                for f, v in r["final_routed_prediction"].items():
                    if isinstance(v, list) and len(v) >= 2:
                        combo_values.add(",".join(sorted(v)).lower())
            leaked = [c for c in combo_values if c and c in dump]
            assert not leaked, f"UI 泄漏 AI 组合值: {leaked[:3]}"
    finally:
        try:
            tw.destroy()
        except Exception:
            pass
        cen.destroy()
        root.destroy()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_holdout_v2_task_registered():
    ids = [t["id"] for t in TASKS]
    assert "FRESH_HOLDOUT_V2" in ids
    task = [t for t in TASKS if t["id"] == "FRESH_HOLDOUT_V2"][0]
    assert task["table"] == "fresh_holdout_human_review_v1"
    assert task["blind"] is True
