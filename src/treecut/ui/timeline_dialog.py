"""Reorder and retime edit-plan segments before re-rendering."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from treecut.workflow import EditPlan
from treecut.workflow.planning import EditSegment


class TimelineDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, plan: EditPlan,
                 on_apply) -> None:
        super().__init__(master)
        self.plan = plan
        self.on_apply = on_apply
        self.title("调整镜头（顺序与时长）")
        self.geometry("760x460")
        self.transient(master)
        self._segments = [dict(
            order=index + 1, media_id=item.media_id, path=item.path,
            duration=round(item.timeline_end - item.timeline_start, 2),
            segment=item,
        ) for index, item in enumerate(plan.segments)]
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text="选中一行后可用 上移/下移 调整顺序，修改时长后点击“应用并重新渲染”。",
            wraplength=720,
        ).pack(anchor="w")
        self.tree = ttk.Treeview(frame, columns=("order", "duration", "path"),
                                 show="headings", height=10)
        for name, title, width in (("order", "顺序", 60), ("duration", "时长(秒)", 90),
                                   ("path", "素材文件", 520)):
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, stretch=name == "path")
        self.tree.pack(fill="both", expand=True, pady=(8, 6))
        for item in self._segments:
            self.tree.insert("", "end", iid=str(item["order"]), values=(
                item["order"], item["duration"], item["path"],
            ))

        controls = ttk.Frame(frame)
        controls.pack(fill="x")
        ttk.Button(controls, text="上移", command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(controls, text="下移", command=lambda: self._move(1)).pack(side="left", padx=6)
        ttk.Label(controls, text="时长(秒)").pack(side="left", padx=(16, 4))
        self.duration_var = tk.DoubleVar(value=4)
        ttk.Spinbox(controls, from_=1, to=15, textvariable=self.duration_var,
                    width=6).pack(side="left")
        ttk.Button(controls, text="应用时长", command=self._apply_duration).pack(side="left", padx=6)

        ttk.Button(frame, text="应用并重新渲染", command=self._apply).pack(anchor="e", pady=(8, 0))

    def _selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("请选择镜头", "请先点击列表中的一行。", parent=self)
            return None
        return int(selection[0]) - 1

    def _move(self, delta: int) -> None:
        index = self._selected_index()
        if index is None:
            return
        target = index + delta
        if not 0 <= target < len(self._segments):
            return
        self._segments[index], self._segments[target] = self._segments[target], self._segments[index]
        self._refresh()

    def _apply_duration(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        try:
            value = max(1.0, min(15.0, float(self.duration_var.get())))
        except (TypeError, ValueError):
            messagebox.showerror("时长无效", "时长必须是 1–15 之间的数字。", parent=self)
            return
        self._segments[index]["duration"] = round(value, 2)
        self._refresh()

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for order, item in enumerate(self._segments, 1):
            item["order"] = order
            self.tree.insert("", "end", iid=str(order), values=(
                order, item["duration"], item["path"],
            ))

    def _apply(self) -> None:
        requested = self.plan.requested_duration
        total = sum(item["duration"] for item in self._segments)
        if self._segments:
            last = self._segments[-1]
            last["duration"] = round(max(1.0, min(15.0, last["duration"] + requested - total)), 2)
        rebuilt = []
        cursor = 0.0
        for item in self._segments:
            original = item["segment"]
            length = item["duration"]
            source_start = min(original.source_start,
                               max(0.0, original.source_end - original.source_start))
            rebuilt.append(EditSegment(
                len(rebuilt) + 1, original.media_id, original.path, original.category,
                round(source_start, 3), round(source_start + length, 3),
                round(cursor, 3), round(cursor + length, 3),
                original.match_score, original.matched_terms, original.content_fingerprint,
            ))
            cursor += length
        new_plan = EditPlan(requested, round(cursor, 3), round(cursor, 3) >= requested - 0.01,
                            (), tuple(rebuilt))
        self.destroy()
        self.on_apply(new_plan)
