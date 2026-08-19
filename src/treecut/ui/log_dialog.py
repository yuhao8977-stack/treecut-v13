"""Plain-language log viewer for the desktop interface."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk


class LogDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, log_path: Path):
        super().__init__(master)
        self.log_path = log_path
        self.title("运行日志")
        self.geometry("860x560")
        self.transient(master)
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="这里是程序运行记录，报错时把最后几行发给我即可。",
                  wraplength=820).pack(anchor="w", pady=(0, 6))
        self.text = tk.Text(frame, wrap="none", state="disabled")
        scroll = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(frame, text="刷新", command=self._refresh).pack(anchor="w", pady=(6, 0))
        self._refresh()

    def _refresh(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        try:
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-300:])
        except OSError:
            tail = "（暂无日志文件）"
        self.text.insert("1.0", tail)
        self.text.configure(state="disabled")
        self.text.see("end")
