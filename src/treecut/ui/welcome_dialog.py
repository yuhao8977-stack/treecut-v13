"""First-run welcome dialog that walks a new user through the first production."""
from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import ttk


_MARKER = "welcomed.txt"


def is_first_run(data_root: Path) -> bool:
    return not (data_root / "config" / _MARKER).is_file()


def mark_welcomed(data_root: Path) -> None:
    marker = data_root / "config" / _MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("1", encoding="ascii")


class WelcomeDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, data_root: Path, docs_dir: Path):
        super().__init__(master)
        self.data_root = data_root
        self.docs_dir = docs_dir
        self.title("欢迎使用树剪 v13")
        self.geometry("620x340")
        self.transient(master)
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="欢迎使用树剪 v13", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text="三步开始制作第一条视频：", wraplength=560).pack(anchor="w", pady=(14, 6))
        ttk.Label(frame, text="① 第一步：选择素材文件夹（放你拍摄/下载的视频）", wraplength=560).pack(anchor="w", pady=2)
        ttk.Label(frame, text="② 第二步：点击“扫描素材”，程序会自动分析画面、语音和物体", wraplength=560).pack(anchor="w", pady=2)
        ttk.Label(frame, text="③ 第三步：填写卖点和配音文案，点击“开始自动制作”", wraplength=560).pack(anchor="w", pady=2)
        ttk.Label(frame, text="制作完成后会自动播放成片，并可一键导出剪映草稿。", wraplength=560).pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(anchor="e", pady=(20, 0))
        ttk.Button(buttons, text="查看使用说明", command=self._open_docs).pack(side="left", padx=8)
        ttk.Button(buttons, text="开始使用", command=self.destroy).pack(side="left")

    def _open_docs(self) -> None:
        if self.docs_dir.is_dir():
            os.startfile(str(self.docs_dir))
        else:
            tk.messagebox.showinfo("使用说明", "软件目录下没有 docs 文件夹。", parent=self)
