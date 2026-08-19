"""Self-contained MP4 preview player used by the desktop interface."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


class VideoPlayerWindow(tk.Toplevel):
    """Play a local MP4 with play/pause, seek and folder-open controls."""

    def __init__(self, master: tk.Misc, video_path: str | Path):
        super().__init__(master)
        self.video_path = Path(video_path)
        self.title(f"成片预览 - {self.video_path.name}")
        self.geometry("560x820")
        self.transient(master)
        self._after_id: str | None = None
        self._playing = False

        import cv2
        self.capture = cv2.VideoCapture(str(self.video_path))
        if not self.capture.isOpened():
            self.destroy()
            messagebox.showerror("预览失败", f"无法打开视频文件：\n{self.video_path}", parent=master)
            return
        self.fps = float(self.capture.get(cv2.CAP_PROP_FPS) or 25.0)
        self.frame_count = float(self.capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        self.duration = self.frame_count / self.fps if self.fps else 0.0

        self._build()
        self._render_frame()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=8)
        frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(frame, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(8, 0))
        self.play_button = ttk.Button(controls, text="暂停", command=self._toggle)
        self.play_button.pack(side="left")
        ttk.Button(controls, text="停止", command=self._stop).pack(side="left", padx=6)
        ttk.Button(controls, text="用系统播放器打开（含声音）", command=self._open_external).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="打开所在文件夹", command=self._open_folder).pack(side="left")

        seek_frame = ttk.Frame(frame)
        seek_frame.pack(fill="x", pady=(8, 0))
        self.seek = ttk.Scale(seek_frame, from_=0, to=self.duration or 1,
                              command=self._seek, value=0)
        self.seek.pack(side="left", fill="x", expand=True)
        self.time_label = ttk.Label(seek_frame, text="0.0 / 0.0 秒", width=16)
        self.time_label.pack(side="left", padx=8)

    def _show_frame(self, frame) -> None:
        from PIL import Image, ImageTk
        height, width = frame.shape[:2]
        scale = min(1.0, 460.0 / width, 720.0 / height)
        image = Image.fromarray(frame[:, :, ::-1])
        if scale < 1.0:
            image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))))
        photo = ImageTk.PhotoImage(image)
        self._frame_photo = photo
        self.canvas.delete("all")
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        x = max(0, (canvas_width - image.width) // 2) if canvas_width > 1 else 0
        y = max(0, (canvas_height - image.height) // 2) if canvas_height > 1 else 10
        self.canvas.create_image(
            x, y, image=photo, anchor="nw",
        )

    def _render_frame(self) -> bool:
        import cv2
        import numpy as np
        ok, frame = self.capture.read()
        if not ok or frame is None:
            return False
        self._show_frame(np.asarray(frame))
        return True

    def _tick(self) -> None:
        if not self._playing:
            return
        rendered = self._render_frame()
        position = self.capture.get(0)
        self.seek.set(position / 1000.0 if self.fps else 0.0)
        self._update_time()
        if not rendered or (self.duration > 0 and position >= self.duration * 1000.0 - 50):
            self._pause()
            return
        self._after_id = self.after(max(20, int(1000.0 / max(self.fps, 1.0))), self._tick)

    def _toggle(self) -> None:
        if self._playing:
            self._pause()
        else:
            self._playing = True
            self.play_button.config(text="暂停")
            self._tick()

    def _pause(self) -> None:
        self._playing = False
        self.play_button.config(text="播放")
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None

    def _stop(self) -> None:
        self._pause()
        self.capture.set(0, 0)
        self.seek.set(0)
        self._render_frame()
        self._update_time()

    def _seek(self, value: str) -> None:
        try:
            self.capture.set(0, float(value) * 1000.0)
            self._render_frame()
            self._update_time()
        except (TypeError, ValueError):
            pass

    def _update_time(self) -> None:
        position = self.capture.get(0) / 1000.0
        self.time_label.config(text=f"{position:.1f} / {self.duration:.1f} 秒")

    def _open_folder(self) -> None:
        import os
        os.startfile(str(self.video_path.parent))

    def _open_external(self) -> None:
        import os
        self._pause()
        try:
            os.startfile(str(self.video_path))
        except OSError as error:
            from tkinter import messagebox
            messagebox.showerror("打开失败", f"无法用系统播放器打开：\n{error}", parent=self)

    def _close(self) -> None:
        self._pause()
        self.capture.release()
        self.destroy()
