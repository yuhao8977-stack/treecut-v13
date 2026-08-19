"""Backup and output-cleanup dialog for the desktop interface."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from treecut.maintenance import (
    auto_backup, backup_data, cleanup_outputs, export_diagnostic_bundle,
    export_project, restore_data,
)
from treecut.platform.paths import RuntimePaths


class MaintenanceDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, paths: RuntimePaths):
        super().__init__(master)
        self.paths = paths
        self.title("数据备份与清理")
        self.geometry("480x300")
        self.transient(master)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="备份会复制数据库与设置；清理只会把旧项目移入回收站。",
                  wraplength=430).pack(anchor="w")
        ttk.Button(frame, text="备份数据…", command=self._backup).pack(anchor="w", pady=(16, 0))
        ttk.Button(frame, text="清理旧输出（保留最近 20 个）", command=self._cleanup).pack(anchor="w", pady=(8, 0))
        ttk.Button(frame, text="立即自动备份（自动保留最近 7 份）", command=self._auto_backup).pack(anchor="w", pady=(8, 0))
        ttk.Button(frame, text="恢复备份…（会先备份当前数据）", command=self._restore).pack(anchor="w", pady=(8, 0))
        ttk.Button(frame, text="导出项目…（把某个项目整包拷出）", command=self._export).pack(anchor="w", pady=(8, 0))
        ttk.Button(frame, text="导出诊断包…（把本机状态打包，便于带回来分析）",
                   command=self._export_diagnostic).pack(anchor="w", pady=(8, 0))

    def _backup(self) -> None:
        destination = filedialog.askdirectory(title="选择备份保存位置")
        if not destination:
            return
        try:
            from pathlib import Path
            target = backup_data(self.paths, Path(destination))
            messagebox.showinfo("备份完成", f"已备份到：\n{target}", parent=self)
        except Exception as error:
            messagebox.showerror("备份失败", str(error), parent=self)

    def _cleanup(self) -> None:
        try:
            removed = cleanup_outputs(self.paths, keep=20)
            if removed:
                messagebox.showinfo("清理完成", f"已将 {len(removed)} 个旧项目移入回收站。", parent=self)
            else:
                messagebox.showinfo("清理完成", "没有需要清理的旧项目。", parent=self)
        except Exception as error:
            messagebox.showerror("清理失败", str(error), parent=self)

    def _auto_backup(self) -> None:
        try:
            target = auto_backup(self.paths)
            messagebox.showinfo("自动备份完成", f"已备份到：\n{target}", parent=self)
        except Exception as error:
            messagebox.showerror("自动备份失败", str(error), parent=self)

    def _restore(self) -> None:
        selected = filedialog.askdirectory(title="选择备份文件夹（含 .db 文件）")
        if not selected:
            return
        if not messagebox.askyesno(
                "恢复备份", "恢复会覆盖当前数据库（当前数据会先备份）。确定继续吗？", parent=self):
            return
        try:
            from pathlib import Path as PathType
            restored = restore_data(self.paths, PathType(selected))
            messagebox.showinfo("恢复完成", "已恢复：" + "、".join(restored), parent=self)
        except Exception as error:
            messagebox.showerror("恢复失败", str(error), parent=self)

    def _export(self) -> None:
        project = filedialog.askdirectory(title="选择要导出的项目文件夹")
        if not project:
            return
        destination = filedialog.askdirectory(title="选择导出到哪个文件夹")
        if not destination:
            return
        try:
            from pathlib import Path as PathType
            target = export_project(PathType(project), PathType(destination))
            messagebox.showinfo("导出完成", f"已导出到：\n{target}", parent=self)
        except Exception as error:
            messagebox.showerror("导出失败", str(error), parent=self)

    def _export_diagnostic(self) -> None:
        destination = filedialog.askdirectory(title="选择诊断包保存位置（例如 U 盘或桌面）")
        if not destination:
            return
        try:
            from pathlib import Path
            bundle = export_diagnostic_bundle(self.paths, Path(destination))
            messagebox.showinfo(
                "诊断包已生成",
                f"已生成：\n{bundle}\n\n把该 zip 文件带回开发电脑，交给 Codex 即可分析这台机器的状态。",
                parent=self,
            )
        except Exception as error:
            messagebox.showerror("导出失败", str(error), parent=self)
