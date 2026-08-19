"""Materials library management window."""
from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from treecut.analysis.worker import AnalysisWorker
from treecut.maintenance import export_tags_csv, import_tags_csv


class LibraryDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, catalog, paths, run_background, on_message):
        super().__init__(master)
        self.catalog = catalog
        self.paths = paths
        self.run_background = run_background
        self.on_message = on_message
        self.title("素材库管理")
        self.geometry("1080x650")
        self.transient(master)
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="素材来源与分析状态",
                  font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="这里显示硬盘是否在线、分析失败原因。可选一行视频重新分析，或人工修正业务分类、设置标签。",
            wraplength=1040,
        ).pack(anchor="w", pady=(2, 8))

        self.source_tree = ttk.Treeview(
            frame, columns=("online", "files", "failed", "path"), show="headings", height=5,
        )
        for name, title, width in (
            ("online", "状态", 70), ("files", "可用文件", 80),
            ("failed", "失败任务", 80), ("path", "素材来源", 790),
        ):
            self.source_tree.heading(name, text=title)
            self.source_tree.column(name, width=width, stretch=name == "path")
        self.source_tree.pack(fill="x")

        self.media_tree = ttk.Treeview(
            frame, columns=("id", "status", "category", "tags", "attempts", "error", "path"),
            show="headings", height=14,
        )
        for name, title, width in (
            ("id", "编号", 55), ("status", "分析状态", 80), ("category", "分类", 120),
            ("tags", "标签", 130), ("attempts", "尝试", 50),
            ("error", "失败原因", 210), ("path", "文件", 360),
        ):
            self.media_tree.heading(name, text=title)
            self.media_tree.column(name, width=width, stretch=name in {"error", "path"})
        self.media_tree.pack(fill="both", expand=True, pady=(10, 6))

        search = ttk.Frame(frame)
        search.pack(fill="x", pady=(0, 4))
        ttk.Label(search, text="搜索（文件名/分类/标签）").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(search, textvariable=self.search_var, width=42).pack(side="left", padx=6)
        self.search_var.trace_add("write", lambda *_: self.refresh())

        controls = ttk.Frame(frame)
        controls.pack(fill="x")
        ttk.Button(controls, text="刷新状态", command=self.refresh).pack(side="left")
        self.category_var = tk.StringVar(value="product_display")
        ttk.Combobox(
            controls, textvariable=self.category_var, state="readonly", width=22,
            values=("product_display", "factory_production", "installation", "talking_head",
                    "customer_case", "interior_space", "unclassified"),
        ).pack(side="left", padx=(12, 4))
        ttk.Button(controls, text="应用人工分类", command=self._apply_category).pack(side="left")
        ttk.Button(controls, text="重新分析选中视频", command=self._retry_analysis).pack(side="left", padx=8)
        ttk.Button(controls, text="设置标签", command=self._edit_tags).pack(side="left")
        ttk.Button(controls, text="预览选中视频", command=self._preview).pack(side="left", padx=8)
        ttk.Button(controls, text="导出标签CSV", command=self._export_tags).pack(side="left")
        ttk.Button(controls, text="导入标签CSV", command=self._import_tags).pack(side="left", padx=6)
        self.refresh()

    def refresh(self) -> None:
        self.catalog.relink_sources()
        self.source_tree.delete(*self.source_tree.get_children())
        for source in self.catalog.list_sources():
            self.source_tree.insert("", "end", values=(
                "在线" if source["online"] else "离线", source["available_files"],
                source["failed_jobs"], source["path"],
            ))
        self.media_tree.delete(*self.media_tree.get_children())
        keyword = self.search_var.get().strip().lower()
        for item in self.catalog.list_media(limit=1000):
            if keyword:
                haystack = " ".join([
                    str(item["absolute_path"]).lower(),
                    str(item["category"]).lower(),
                    " ".join(item.get("tags") or ()).lower(),
                ])
                if keyword not in haystack:
                    continue
            self.media_tree.insert("", "end", iid=str(item["media_id"]), values=(
                item["media_id"], item.get("status") or "无任务", item["category"],
                "、".join(item.get("tags") or ()),
                item.get("attempts") or 0, item.get("error") or item.get("stale_reason") or "",
                item["absolute_path"],
            ))

    def _selected_media_id(self) -> int | None:
        selected = self.media_tree.selection()
        if not selected:
            messagebox.showwarning("请选择素材", "请先点击下方一行素材。", parent=self)
            return None
        return int(selected[0])

    def _apply_category(self) -> None:
        media_id = self._selected_media_id()
        if media_id is None:
            return
        try:
            self.catalog.set_category(media_id, self.category_var.get())
            self.refresh()
        except Exception as error:
            messagebox.showerror("分类修改失败", str(error), parent=self)

    def _retry_analysis(self) -> None:
        media_id = self._selected_media_id()
        if media_id is None:
            return
        try:
            self.catalog.retry_analysis(media_id)
        except Exception as error:
            messagebox.showerror("不能重新分析", str(error), parent=self)
            return

        def task():
            run = AnalysisWorker(catalog=self.catalog, paths=self.paths).run(
                limit=1, media_id=media_id,
                progress=lambda text: self.on_message("progress", text),
            )
            summary = f"重新分析完成：成功 {run.succeeded}，待重试 {run.retried}，失败 {run.failed}"
            self.on_message("done", summary)

        self.run_background(task)

    def _edit_tags(self) -> None:
        media_id = self._selected_media_id()
        if media_id is None:
            return
        matching = [
            item for item in self.catalog.list_media(limit=1000)
            if item["media_id"] == media_id
        ]
        current = "、".join(matching[0].get("tags") or ()) if matching else ""
        value = simpledialog.askstring(
            "设置标签", "用顿号或逗号分隔（最多 20 个，每个 ≤20 字）：\n当前：" + current,
            initialvalue=current, parent=self,
        )
        if value is None:
            return
        tags = [tag.strip() for tag in re.split(r"[、,，]", value) if tag.strip()]
        try:
            self.catalog.set_tags(media_id, tags)
            self.refresh()
        except Exception as error:
            messagebox.showerror("标签保存失败", str(error), parent=self)

    def _preview(self) -> None:
        media_id = self._selected_media_id()
        if media_id is None:
            return
        matching = [
            item for item in self.catalog.list_media(limit=1000)
            if item["media_id"] == media_id
        ]
        if not matching:
            return
        path = matching[0]["absolute_path"]
        if not Path(path).is_file():
            messagebox.showwarning("无法预览", "素材文件当前不可用（可能已离线）。", parent=self)
            return
        from treecut.ui.player import VideoPlayerWindow
        VideoPlayerWindow(self, path)

    def _export_tags(self) -> None:
        destination = filedialog.asksaveasfilename(
            title="保存标签清单", defaultextension=".csv", initialfile="treecut_tags.csv",
            filetypes=[("CSV", "*.csv")], parent=self,
        )
        if not destination:
            return
        try:
            from pathlib import Path as PathType
            target = export_tags_csv(self.paths, PathType(destination))
            messagebox.showinfo("导出完成", f"已导出：\n{target}", parent=self)
        except Exception as error:
            messagebox.showerror("导出失败", str(error), parent=self)

    def _import_tags(self) -> None:
        source = filedialog.askopenfilename(
            title="选择标签 CSV", filetypes=[("CSV", "*.csv"), ("所有文件", "*.*")], parent=self,
        )
        if not source:
            return
        try:
            from pathlib import Path as PathType
            imported = import_tags_csv(self.paths, PathType(source))
            messagebox.showinfo("导入完成", f"已更新 {imported} 条标签。", parent=self)
            self.refresh()
        except Exception as error:
            messagebox.showerror("导入失败", str(error), parent=self)
