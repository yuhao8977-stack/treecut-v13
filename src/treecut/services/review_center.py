# -*- coding: utf-8 -*-
"""TreeCut Phase 3 — Review Center（人工审核中心，接入主程序）。

架构：
  TreeCutDesktop（主程序，tk.Tk）
    → 顶部【人工审核中心】按钮
    → ReviewCenterWindow(tk.Toplevel)【由 Main 管理，单实例】
        → 任务列表（动态注册，非硬编码）
        → 点任务 → ReviewTaskWindow(tk.Toplevel)
            → 未完成：审核模式（复用 _V21Form 表单 + 保存）
            → 已完成：只读结果模式（Treeview）

返回导航：
  ReviewTaskWindow ← 返回审核中心（destroy 自身）
  ReviewCenterWindow ← 返回主界面（destroy 自身）
X 关闭：只关闭审核窗口，主程序继续运行。
单实例：Main 持有唯一引用；重复点击 focus 已有窗口。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from treecut.services.phase3_review_ui import (
    FFMPEG, FIELD_CN, GROUPS, PlaybackController, _V21Form, cn, en, validate_v21,
)
from treecut.services.schema_v2 import DICTIONARY_VERSION_V2_1

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")

# 任务注册表（可扩展：SECOND_REVIEW/FRESH_HOLDOUT/ACTIVE_LEARNING 等后续追加）
TASKS = [
    {"id": "THIRD_ADJUDICATION_V1", "name": "第三次独立裁决（V3）", "type": "ADJUDICATION",
     "manifest": os.path.join(DATA_ROOT, "THIRD_ADJUDICATION_V1.json"),
     "table": "human_annotation_v3"},
    {"id": "TARGETED_REVIEW_BATCH_V1", "name": "主动学习新样本标注", "type": "TARGETED",
     "manifest": os.path.join(DATA_ROOT, "TARGETED_REVIEW_BATCH_V1.json"),
     "table": "targeted_human_review_v1"},
    {"id": "FRESH_HOLDOUT_V1", "name": "未见样本盲审（考试卷 30 条）", "type": "HOLDOUT",
     "manifest": os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"),
     "table": "fresh_holdout_human_review_v1",
     "blind": True,  # 盲审：隐藏一切 AI 信息（manifest 仅含题目，无预测）
     "hint": ("盲审说明：这是 AI 从未见过的考试卷。系统已隐藏 AI 预测/分数/证据，请只看视频独立作答。\n"
              "· 置信度解释：高=几乎确定；中=大体确定但有一定判断空间；低=自己拿不准\n"
              "· 材质/组件/功能/镜头角色：点击即多选，再点取消；动作按发生顺序添加\n"
              "· 看不清就选 未知 + 低 + 需复核，不硬猜")},
    {"id": "TARGETED_REVIEW_STAGE3_V3_1", "name": "Stage3 定向审核（60 条·最终批次 V3_1）", "type": "TARGETED",
     "manifest": os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"),
     "table": "targeted_human_review_v1",
     "blind": True,  # 只显示采样目标类别，隐藏一切 AI 预测/关键词/证据
     "show_sampling_target": True,
     "hint": ("定向审核（Stage3 最终批次 V3_1，DEV/校准扩展，非考试卷）。\n"
              "系统只显示采样目标（动作/人物/变体/场景/材质），不显示任何 AI 猜测，请只看视频独立作答。\n"
              "· 置信度解释：高=几乎确定；中=大体确定但有一定判断空间；低=自己拿不准\n"
              "· 材质/组件/功能/镜头角色：点击即多选，再点取消；动作按发生顺序添加\n"
              "· 看不清就选 未知 + 低 + 需复核，不硬猜")},
    {"id": "STAGE3_ACTION_QA_ADJUDICATION", "name": "Stage3 动作 QA 二次裁决（仅 3 条）", "type": "ADJUDICATION",
     "manifest": os.path.join(DATA_ROOT, "STAGE3_ACTION_QA_ADJUDICATION.json"),
     "table": "targeted_human_review_v1",
     "blind": True,  # 不显示 AI prediction；只显示现有 Human annotation
     "show_sampling_target": True,
     "show_current_annotation": True,
     "hint": ("QA 二次裁决（仅 3 条 action_group↔action_sequence 冲突）。\n"
              "请只看视频，修正 action_group 与 action_sequence 使其一致。\n"
              "· action_group 是主类别（如 静态展示/讲解/抽屉/柜门）\n"
              "· action_sequence 是按发生顺序的完整动作流\n"
              "· 系统不显示任何 AI 猜测；看不清就选 未知 + 低 + 需复核")},
]


def task_stats(task: dict) -> dict:
    """任务进度统计（只读 DB + manifest）。按 manifest 成员 segment_id 计数，避免跨任务表共享污染。"""
    total = 0
    seg_ids = []
    if os.path.exists(task["manifest"]):
        try:
            d = json.load(open(task["manifest"], encoding="utf-8"))
            seg_ids = [s["segment_id"] for s in d.get("segments", d.get("strata", []))]
            total = len(seg_ids)
        except Exception:
            total = 0
    done, needs = 0, 0
    if os.path.exists(DB) and seg_ids:
        try:
            conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
            ph = ",".join("?" * len(seg_ids))
            done = conn.execute(
                f"SELECT COUNT(*) FROM {task['table']} WHERE segment_id IN ({ph})",
                seg_ids).fetchone()[0]
            needs = conn.execute(
                f"SELECT COUNT(*) FROM {task['table']} WHERE review_status='NEEDS_SECOND_REVIEW'"
                f" AND segment_id IN ({ph})", seg_ids).fetchone()[0]
            conn.close()
        except Exception:
            done = 0
    pct = round(done / total * 100, 1) if total else 0.0
    status = "完成" if done >= total and total > 0 else "进行中"
    return {"total": total, "done": done, "remaining": max(0, total - done),
            "needs_review": needs, "pct": pct, "status": status}


class ReviewTaskWindow(tk.Toplevel):
    """单个审核任务窗口（Toplevel，由 Main 管理；返回按钮回审核中心）。"""

    def __init__(self, master, task: dict, on_back):
        super().__init__(master)
        self.task = task
        self.on_back = on_back
        self._ui_built = False
        self.db_path = Path(DB)
        self.title(f"人工审核 - {task['name']}")
        self.geometry("1280x820")
        self.minsize(980, 640)
        self.configure(bg="#f0f0f0")
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)
        st = task_stats(task)
        if st["remaining"] > 0:
            self._build_review()
        else:
            self._build_result(st)
        self.protocol("WM_DELETE_WINDOW", self.destroy)  # X 只关本窗口

    # ---------------- 结果模式（已完成） ----------------
    def _build_result(self, st):
        top = ttk.Frame(self, padding=(8, 6))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="← 返回审核中心", command=self.destroy).pack(side=tk.LEFT)
        ttk.Label(top, text=f"{self.task['name']}  已完成 {st['done']}/{st['total']}",
                  font=("Microsoft YaHei", 11, "bold")).pack(side=tk.LEFT, padx=16)
        ttk.Label(top, text=f"词典 {DICTIONARY_VERSION_V2_1}").pack(side=tk.RIGHT)
        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        cols = ("segment", "confidence", "status", "time")
        tree = ttk.Treeview(body, columns=cols, show="headings")
        for c, t in zip(cols, ("片段编号", "置信度", "状态", "时间")):
            tree.heading(c, text=t)
            tree.column(c, width=200 if c == "segment" else 90)
        sb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        for r in conn.execute(
                f"SELECT segment_id, human_confidence, review_status, created_at FROM {self.task['table']}"
                " ORDER BY created_at"):
            ts = time.strftime("%m-%d %H:%M", time.localtime(r["created_at"])) if r["created_at"] else ""
            tree.insert("", tk.END, values=(r["segment_id"][:20], r["human_confidence"],
                                            r["review_status"], ts))
        conn.close()

    # ---------------- 审核模式（未完成） ----------------
    def _build_review(self):
        if self._ui_built:
            raise RuntimeError("Review UI must only be built once")
        self._ui_built = True
        # 工具栏两行：第一行 返回/序号/进度；第二行 必选(置信度/状态/保存/提示) 固定可见
        self.top1 = ttk.Frame(self, padding=(8, 6))
        self.top1.grid(row=0, column=0, sticky="ew")
        self.top2 = ttk.Frame(self, padding=(8, 2))
        self.top2.grid(row=1, column=0, sticky="ew")
        ttk.Button(self.top1, text="← 返回审核中心", command=self.destroy).pack(side=tk.LEFT)
        self.pos = ttk.Label(self.top1, text="", font=("Microsoft YaHei", 12, "bold"))
        self.pos.pack(side=tk.LEFT, padx=12)
        self.progress = ttk.Label(self.top1, text="")
        self.progress.pack(side=tk.LEFT, padx=8)
        self.save_btn = ttk.Button(self.top2, text="✓ 保存并下一题", command=self._save, state="disabled")
        self.save_btn.pack(side=tk.RIGHT, padx=8)
        self.mandatory_hint = ttk.Label(self.top2, text="⚠ 请完成必选项", foreground="#b00020",
                                        font=("Microsoft YaHei", 9, "bold"))
        self.mandatory_hint.pack(side=tk.RIGHT)
        self.conf_var = tk.StringVar()
        self.status_var = tk.StringVar()
        ttk.Label(self.top2, text="置信度*").pack(side=tk.RIGHT, padx=(10, 2))
        ttk.Combobox(self.top2, textvariable=self.conf_var, values=("高", "中", "低"),
                     width=6, state="readonly").pack(side=tk.RIGHT)
        ttk.Label(self.top2, text="状态*").pack(side=tk.RIGHT, padx=(10, 2))
        ttk.Combobox(self.top2, textvariable=self.status_var,
                     values=("已审核", "需复核", "金标准", "排除"),
                     width=9, state="readonly").pack(side=tk.RIGHT)
        self.conf_var.trace_add("write", self._on_mandatory)
        self.status_var.trace_add("write", self._on_mandatory)
        self._on_mandatory()

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        left = ttk.Frame(paned, width=420)
        paned.add(left, weight=4)
        self.info = tk.Text(left, wrap=tk.WORD, font=("Microsoft YaHei", 9), height=8,
                            bg="#ffffff", relief="solid", borderwidth=1)
        self.info.pack(fill=tk.X)
        self.pb = PlaybackController(on_launch=lambda m, p: None)
        btn = ttk.Frame(left)
        btn.pack(fill=tk.X, pady=4)
        self._btn_ctx = ttk.Button(btn, text="▶ 播放本段（±3秒）", command=self._play_context)
        self._btn_ctx.pack(fill=tk.X, pady=1)
        self._btn_full = ttk.Button(btn, text="▶ 播放完整视频", command=self._play_full)
        self._btn_full.pack(fill=tk.X, pady=1)
        ttk.Label(left, text=self.task.get("hint", "审核提示：隐藏 AI/历史答案；多选点击即选；看不清选 未知+低+需复核"),
                  wraplength=400, foreground="#666").pack(anchor="w", pady=4)
        right = ttk.Frame(paned, width=600)
        paned.add(right, weight=6)  # 注意：ttk.Panedwindow 不支持 minsize 选项（曾致 _build_review 崩溃）
        self.form = _V21Form(right, self._save,
                             conf_var=self.conf_var, status_var=self.status_var)
        self.form.pack(fill=tk.BOTH, expand=True)

        # 载入待审队列
        self.items = self._load_items()
        self.done = self._done_set()
        self.queue = [it for it in self.items if it["segment_id"] not in self.done]
        self.idx = 0
        self.current = None
        if self.queue:
            self._load(0)
        else:
            self.pos.config(text="全部完成")
        self._freeze_widget_baseline()

    def _load_items(self):
        p = Path(self.task["manifest"])
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        # 兼容两种结构：{"segments":[...]} 与 {"strata":[{segment_id,asset_id,stratum}]}
        if "segments" in data:
            return data["segments"]
        if "strata" in data:
            items = []
            for s in data["strata"]:
                items.append({"segment_id": s["segment_id"], "asset_id": s.get("asset_id", ""),
                              "selection_reason": s.get("stratum", "")})
            return items
        return []

    def _done_set(self):
        """已完成集 = 本任务 manifest 成员 ∩ 表中已审 segment_id（避免共享表跨任务污染）。"""
        try:
            segs = self.items if hasattr(self, "items") and self.items else []
            if not segs:
                p = Path(self.task["manifest"])
                data = json.loads(p.read_text(encoding="utf-8"))
                segs = data.get("segments", data.get("strata", []))
            ids = {s["segment_id"] for s in segs}
            if not ids:
                return set()
            conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
            ph = ",".join("?" * len(ids))
            rows = conn.execute(f"SELECT segment_id FROM {self.task['table']} WHERE segment_id IN ({ph})",
                                list(ids)).fetchall()
            conn.close()
            return {r[0] for r in rows}
        except Exception:
            return set()

    def _seg_info(self, sid):
        try:
            conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
            r = conn.execute("SELECT asset_id, start_ms, end_ms FROM segments WHERE segment_id=?",
                             (sid,)).fetchone()
            conn.close()
            return (r[0], r[1], r[2]) if r else ("", 0, 0)
        except Exception:
            return "", 0, 0

    def _resolve_asset(self, asset_id):
        try:
            from treecut.services.identity import AssetRepository
            p = AssetRepository(self.db_path).resolve_path(asset_id)
            return p if p and os.path.exists(p) else ""
        except Exception:
            return ""

    def _load(self, idx):
        if not self.queue:
            self.pos.config(text="全部完成")
            return
        self.idx = idx % len(self.queue)
        it = self.queue[self.idx]
        self.current = it
        sid = it["segment_id"]
        self.pos.config(text=f"{self.idx + 1} / {len(self.queue)}")
        asset, start, end = self._seg_info(sid)
        self.current_start, self.current_end = start, end
        info = [f"片段编号：{sid[:20]}…", f"素材：{asset[:20]}…",
                f"时间范围：{start} - {end} ms（{(end - start) // 1000} 秒）"]
        if self.task.get("show_sampling_target"):
            tgt = it.get("sampling_target_cn") or it.get("sampling_target") or ""
            reason = it.get("selection_reason", "")
            info.append(f"采样目标：{tgt}" + (f"（{reason}）" if reason else ""))
        else:
            info.append(f"采样原因：{it.get('selection_reason', '')}")
        if self.task.get("show_current_annotation"):
            cur = it.get("current_annotation") or {}
            if cur:
                info.append("当前人工标注（待裁决）：")
                info.append(f"  action_group: {cur.get('action_group', '')}")
                info.append(f"  action_sequence: {','.join(cur.get('action_sequence', []))}")
                if cur.get("people_presence"):
                    info.append(f"  people: {cur.get('people_presence')}")
                if cur.get("comment"):
                    info.append(f"  原comment: {cur.get('comment')}")
        if it.get("conflict_fields"):
            info.append(f"冲突字段：{', '.join(d['field'] for d in it['conflict_fields'][:8])}")
        self.info.delete("1.0", tk.END)
        self.info.insert(tk.END, "\n".join(info))
        self.form.reset()
        self.progress.config(text=f"已完成 {len(self.done)} / {len(self.items)}")
        self.after_idle(self._assert_widget_stable)

    # ---------------- 防呆 / 保存 / 播放 ----------------
    def _on_mandatory(self, *_a):
        ok = bool((self.conf_var.get() or "").strip()) and bool((self.status_var.get() or "").strip())
        self.save_btn.config(state="normal" if ok else "disabled")
        self.mandatory_hint.config(text="" if ok else "⚠ 请完成必选项")

    def _persist(self, values, status):
        """Stage 2 STEP 0：统一走 AnnotationService（不直接写 SQL）。"""
        it = self.current
        from treecut.services.annotation_governance import AnnotationService
        svc = AnnotationService(self.db_path)
        if self.task["table"] == "targeted_human_review_v1":
            svc.save_targeted_review(it["segment_id"], values,
                                     values["human_confidence"], status,
                                     selection_reason=it.get("selection_reason", ""),
                                     operator=os.environ.get("USERNAME", ""))
        elif self.task["table"] == "fresh_holdout_human_review_v1":
            # 盲审保存：统一走 AnnotationService（只存人工结果 + stratum，无 AI 信息）
            svc.save_holdout_review(it["segment_id"], values,
                                    it.get("selection_reason", ""),
                                    values["human_confidence"], status,
                                    operator=os.environ.get("USERNAME", ""))
        else:
            svc.save_v3(it["segment_id"], values,
                        values["human_confidence"], status,
                        operator=os.environ.get("USERNAME", ""))

    def _save(self):
        if not getattr(self, "current", None):
            return
        values = self.form.collect()
        ok, msg, status = validate_v21(values, values["human_confidence"],
                                       values["review_status"], values["comment"])
        if not ok:
            messagebox.showerror("无法保存", msg)
            return
        if msg:
            messagebox.showwarning("状态已调整", msg)
        self._persist(values, status)
        self.done.add(self.current["segment_id"])
        self.queue = [it for it in self.items if it["segment_id"] not in self.done]
        self.progress.config(text=f"已完成 {len(self.done)} / {len(self.items)}")
        if len(self.done) >= len(self.items):
            messagebox.showinfo("批次完成", f"{self.task['name']} {len(self.done)}/{len(self.items)} 完成。"
                                            "请进行人工数据结算。")
            self.destroy()  # 完成后返回审核中心
            return
        if self.queue:
            self._load(0)
        else:
            self.pos.config(text="全部完成")

    def _play_full(self):
        if not getattr(self, "current", None):
            return
        path = self._resolve_asset(self._seg_info(self.current["segment_id"])[0])
        if not path:
            messagebox.showwarning("无法播放", "素材视频不可达")
            return
        if self.pb.play_full(path):
            self._debounce_btn(self._btn_full)

    def _play_context(self):
        if not getattr(self, "current", None):
            return
        asset = self._seg_info(self.current["segment_id"])[0]
        path = self._resolve_asset(asset)
        if not path:
            messagebox.showwarning("无法播放", "素材视频不可达")
            return
        if not self.pb.play_context(path, self.current_start, self.current_end):
            return
        self._debounce_btn(self._btn_ctx)
        out = os.path.join(__import__("tempfile").gettempdir(),
                           f"treecut_preview_{self.current['segment_id'][:12]}.mp4")
        deadline = time.time() + 15
        while time.time() < deadline:
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                break
            time.sleep(0.4)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            os.startfile(out)  # type: ignore[attr-defined]
        else:
            os.startfile(path)  # type: ignore[attr-defined]

    def _debounce_btn(self, btn):
        try:
            btn.config(state="disabled")
            self.after(PlaybackController.DEBOUNCE_MS + 150,
                       lambda: btn.config(state="normal"))
        except Exception:
            pass

    # ---------------- Widget leak guard ----------------
    def _count_widgets(self, w=None):
        w = w or self
        n = 1
        for c in w.winfo_children():
            n += self._count_widgets(c)
        return n

    def _freeze_widget_baseline(self):
        self.update_idletasks()
        self._widget_baseline = self._count_widgets()

    def _assert_widget_stable(self):
        if getattr(self, "_widget_baseline", None) is None:
            return
        cur = self._count_widgets()
        if cur != self._widget_baseline:
            import logging
            logging.getLogger("review_center").error(
                "UI_WIDGET_LEAK baseline=%s current=%s", self._widget_baseline, cur)


class ReviewCenterWindow(tk.Toplevel):
    """人工审核中心（任务列表，单实例由 Main 管理）。"""

    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("人工审核中心")
        self.geometry("860x480")
        self.minsize(760, 420)
        self.configure(bg="#f0f0f0")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self):
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill=tk.X)
        ttk.Button(top, text="← 返回主界面", command=self.destroy).pack(side=tk.LEFT)
        ttk.Label(top, text="人工审核中心", font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT, padx=16)
        ttk.Label(top, text=f"词典 {DICTIONARY_VERSION_V2_1}").pack(side=tk.RIGHT)

        body = ttk.Frame(self, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        cols = ("name", "type", "total", "done", "remaining", "needs", "pct", "status", "act")
        tree = ttk.Treeview(body, columns=cols, show="headings", height=8)
        heads = ("任务名称", "类型", "总数", "已审核", "剩余", "需复核", "完成率", "状态", "操作")
        widths = (220, 90, 60, 60, 60, 60, 70, 70, 90)
        for c, h, w in zip(cols, heads, widths):
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")
        tree.column("name", anchor="w")
        sb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for task in TASKS:
            st = task_stats(task)
            act = "查看结果" if st["status"] == "完成" else "继续审核"
            tree.insert("", tk.END, values=(task["name"], task["type"], st["total"],
                                            st["done"], st["remaining"], st["needs_review"],
                                            f"{st['pct']}%", st["status"], act),
                        tags=(task["id"],))
        tree.tag_configure("row", font=("Microsoft YaHei", 10))

        def on_open(_e=None):
            sel = tree.selection()
            if not sel:
                return
            tid = tree.item(sel[0], "tags")[0]
            task = next(t for t in TASKS if t["id"] == tid)
            self._open_task(task)

        ttk.Button(body, text="打开选中任务", command=on_open).pack(pady=6)
        tree.bind("<Double-1>", on_open)

    def _open_task(self, task):
        if getattr(self, "_task_win", None) is not None and self._task_win.winfo_exists():
            self._task_win.lift()
            self._task_win.focus_force()
            return
        self._task_win = ReviewTaskWindow(self, task, on_back=lambda: None)
        self._task_win.transient(self)
