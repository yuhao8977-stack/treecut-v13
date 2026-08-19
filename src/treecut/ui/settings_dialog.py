"""Graphical settings editor for the desktop interface."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from treecut.config.settings import Settings, save_settings
from treecut.platform.paths import RuntimePaths


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, settings: Settings, paths: RuntimePaths):
        super().__init__(master)
        self.settings = settings
        self.paths = paths
        self.title("设置")
        self.geometry("560x520")
        self.transient(master)
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="默认时长（秒，建议 23–45）").grid(row=0, column=0, sticky="w")
        self.duration_var = tk.DoubleVar(value=self.settings.default_duration)
        ttk.Spinbox(frame, from_=5, to=300, textvariable=self.duration_var, width=8).grid(
            row=0, column=1, sticky="w", padx=10,
        )

        ttk.Label(frame, text="输出模式").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.output_labels = {"双输出（MP4 + 剪映）": "both", "仅 MP4": "mp4", "仅剪映草稿": "jianying"}
        default_output = next(label for label, key in self.output_labels.items()
                              if key == self.settings.output_mode)
        self.output_display = tk.StringVar(value=default_output)
        ttk.Combobox(frame, textvariable=self.output_display, state="readonly",
                     values=tuple(self.output_labels), width=24).grid(
            row=1, column=1, sticky="w", padx=10, pady=(12, 0),
        )

        ttk.Label(frame, text="模型模式").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.model_labels = {"自动": "auto", "纯 CPU": "cpu", "NVIDIA 显卡": "nvidia"}
        default_model = next(label for label, key in self.model_labels.items()
                             if key == self.settings.model_mode)
        self.model_display = tk.StringVar(value=default_model)
        ttk.Combobox(frame, textvariable=self.model_display, state="readonly",
                     values=tuple(self.model_labels), width=24).grid(
            row=2, column=1, sticky="w", padx=10, pady=(12, 0),
        )

        ttk.Label(frame, text="视觉模型").grid(row=3, column=0, sticky="w", pady=(12, 0))
        self.vision_labels = {
            "自动": "auto", "Florence（CPU 可用）": "florence", "本地 Qwen（需 NVIDIA）": "qwen",
        }
        default_vision = next(label for label, key in self.vision_labels.items()
                              if key == self.settings.vision_mode)
        self.vision_display = tk.StringVar(value=default_vision)
        ttk.Combobox(frame, textvariable=self.vision_display, state="readonly",
                     values=tuple(self.vision_labels), width=24).grid(
            row=3, column=1, sticky="w", padx=10, pady=(12, 0),
        )

        self.auto_preview_var = tk.BooleanVar(value=self.settings.auto_preview)
        ttk.Checkbutton(frame, text="制作完成后自动播放成片",
                        variable=self.auto_preview_var).grid(
            row=4, column=1, sticky="w", padx=10, pady=(12, 0),
        )

        ttk.Label(frame, text="分析并行数（按内存自动限制）").grid(row=5, column=0, sticky="w", pady=(12, 0))
        self.workers_var = tk.IntVar(value=self.settings.analysis_workers)
        ttk.Spinbox(frame, from_=1, to=4, textvariable=self.workers_var, width=8).grid(
            row=5, column=1, sticky="w", padx=10, pady=(12, 0),
        )

        ttk.Label(frame, text="素材来源").grid(row=6, column=0, sticky="nw", pady=(14, 0))
        self.source_list = tk.Listbox(frame, height=8)
        for source in self.settings.material_sources:
            self.source_list.insert("end", source)
        self.source_list.grid(row=6, column=1, sticky="we", padx=10, pady=(14, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=1, sticky="w", pady=8)
        ttk.Button(buttons, text="添加文件夹", command=self._add_source).pack(side="left")
        ttk.Button(buttons, text="移除选中", command=self._remove_source).pack(side="left", padx=6)

        ttk.Button(frame, text="保存", command=self._save).grid(row=8, column=1, sticky="e", pady=(10, 0))

    def _add_source(self) -> None:
        selected = filedialog.askdirectory(title="选择素材文件夹")
        if selected and selected not in self.source_list.get(0, "end"):
            self.source_list.insert("end", selected)

    def _remove_source(self) -> None:
        selection = self.source_list.curselection()
        if selection:
            self.source_list.delete(selection[0])

    def _save(self) -> None:
        try:
            self.settings.output_mode = self.output_labels[self.output_display.get()]
            self.settings.model_mode = self.model_labels[self.model_display.get()]
            self.settings.vision_mode = self.vision_labels[self.vision_display.get()]
            self.settings.auto_preview = bool(self.auto_preview_var.get())
            self.settings.analysis_workers = int(self.workers_var.get())
            self.settings.default_duration = float(self.duration_var.get())
            self.settings.material_sources = list(self.source_list.get(0, "end"))
            save_settings(self.settings, self.paths)
            messagebox.showinfo("设置", "设置已保存", parent=self)
            self.destroy()
        except Exception as error:
            messagebox.showerror("设置保存失败", str(error), parent=self)
