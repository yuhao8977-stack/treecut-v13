"""Production result window: playback, feedback and timeline tweak."""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path


class ResultDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, result, feedback, get_query, on_edit_timeline,
                 auto_preview: bool = True):
        super().__init__(master)
        self.result = result
        self.feedback = feedback
        self.get_query = get_query
        self.on_edit_timeline = on_edit_timeline
        self.title("制作完成与镜头反馈")
        self.geometry("900x520")
        self.transient(master)
        self._build()
        if auto_preview and self.result.final_mp4:
            self.after(400, lambda: self._play(self.result.final_mp4))

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="制作完成", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"保存位置：{self.result.project_dir}", wraplength=850).pack(
            anchor="w", pady=(3, 8),
        )
        ttk.Button(frame, text="打开结果文件夹",
                   command=lambda: os.startfile(self.result.project_dir)).pack(anchor="w")
        if self.result.final_mp4:
            ttk.Button(frame, text="播放成片",
                       command=lambda: self._play(self.result.final_mp4)).pack(anchor="w", pady=(4, 0))
        ttk.Button(frame, text="调整镜头并重新渲染",
                   command=lambda: self.on_edit_timeline(self.result)).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            frame,
            text="下面是本次使用的镜头。选择一行后反馈，树剪只会依据您的明确选择学习。",
            wraplength=850,
        ).pack(anchor="w", pady=(12, 4))
        self.tree = ttk.Treeview(frame, columns=("order", "media", "score", "path"),
                                 show="headings", height=11)
        for name, title, width in (
            ("order", "顺序", 55), ("media", "素材编号", 75),
            ("score", "匹配分", 70), ("path", "素材文件", 620),
        ):
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, stretch=name == "path")
        self.tree.pack(fill="both", expand=True)

        try:
            report = json.loads(Path(self.result.report_json).read_text(encoding="utf-8"))
            segments = report.get("plan", {}).get("segments", [])
        except Exception:
            segments = []
        for segment in segments:
            self.tree.insert("", "end", iid=str(segment["order"]), values=(
                segment["order"], segment["media_id"], segment["match_score"], segment["path"],
            ))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="这个镜头很好，保留",
                   command=lambda: self._record("keep", "用户在成片结果中保留")).pack(side="left")
        ttk.Button(buttons, text="不合适，下次替换",
                   command=lambda: self._record("replace", "用户要求下次替换")).pack(side="left", padx=8)
        ttk.Button(buttons, text="含隐私，完全不可用，永久禁用",
                   command=lambda: self._record("block", "用户永久禁用")).pack(side="left")

    def _record(self, action: str, reason: str) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("请选择镜头", "请先点击上方的一行镜头。", parent=self)
            return
        values = self.tree.item(selected[0], "values")
        media_id = int(values[1])
        query = self.get_query()
        try:
            self.feedback.record(media_id, query, action, reason)
        except Exception as error:
            messagebox.showerror("反馈保存失败", str(error), parent=self)
            return
        labels = {"keep": "已保留", "replace": "下次降低使用概率", "block": "已永久禁用"}
        messagebox.showinfo("反馈已保存", f"素材 {media_id}：{labels[action]}。", parent=self)

    def _play(self, video_path: str) -> None:
        from treecut.ui.player import VideoPlayerWindow
        VideoPlayerWindow(self, video_path)
