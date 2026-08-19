"""Scheduled-production dialog."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from treecut.scheduler import ScheduleStore


class ScheduleDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, store: ScheduleStore, request_factory):
        super().__init__(master)
        self.store = store
        self.request_factory = request_factory
        self.title("定时生产")
        self.geometry("680x420")
        self.transient(master)
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="设置时间后，到点会自动使用当前页面的卖点/配音/时长制作一条视频。",
                  wraplength=640).pack(anchor="w")
        add = ttk.Frame(frame)
        add.pack(fill="x", pady=(10, 6))
        ttk.Label(add, text="时间（格式 2026-08-05 09:30）").pack(side="left")
        self.time_var = tk.StringVar()
        ttk.Entry(add, textvariable=self.time_var, width=20).pack(side="left", padx=6)
        ttk.Button(add, text="添加定时任务", command=self._add).pack(side="left")

        self.tree = ttk.Treeview(frame, columns=("time", "state", "selling"), show="headings", height=10)
        for name, title, width in (("time", "执行时间", 150), ("state", "状态", 70),
                                   ("selling", "卖点", 420)):
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, stretch=name == "selling")
        self.tree.pack(fill="both", expand=True)
        ttk.Button(frame, text="删除选中任务", command=self._delete).pack(anchor="w", pady=(8, 0))
        self._refresh()

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for item in self.store.list():
            label = datetime.fromtimestamp(float(item["run_at_ts"])).strftime("%Y-%m-%d %H:%M")
            selling = (item.get("request") or {}).get("selling_points") or ""
            self.tree.insert("", "end", iid=item["id"], values=(label, item["state"], selling))

    def _add(self) -> None:
        try:
            run_at = datetime.strptime(self.time_var.get().strip(), "%Y-%m-%d %H:%M")
            run_at_ts = run_at.timestamp()
        except ValueError:
            messagebox.showerror("时间格式错误", "请按 2026-08-05 09:30 的格式填写。", parent=self)
            return
        try:
            request = self.request_factory()
        except Exception as error:
            messagebox.showerror("无法读取当前需求", str(error), parent=self)
            return
        self.store.add(run_at_ts, request)
        self._refresh()

    def _delete(self) -> None:
        selection = self.tree.selection()
        if selection:
            self.store.remove(selection[0])
            self._refresh()
