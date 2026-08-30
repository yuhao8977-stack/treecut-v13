"""XHS Work Browser V0.1 — 极简控制台（§13/14/31）。

两个主要区域：A. TreeCut Control Panel（本窗口） B. Single Work Tab（浏览器窗口）。
V0.1 无复杂 Dashboard / 动画 / 图表；状态更新事件驱动（queue + after），不做高频轮询。

按钮：打开 Creator / 打开聚光 / 检查账号 / 重新检查登录 / 继续任务 / 查看错误
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from treecut.browser.checkpoint_store import CheckpointStore
from treecut.browser.workspace_manager import WorkspaceManager

FIELD_KEYS = ("workspace_id", "creator", "spotlight", "account",
              "treecut_local", "current_task", "last_checkpoint")


class MinimalDashboard:
    """回调注入：on_open_creator / on_open_spotlight / on_check_account /
    on_recheck_login / on_resume_task / on_view_errors（测试可注入假回调）。"""

    def __init__(self, workspace: WorkspaceManager, checkpoint_store: CheckpointStore,
                 callbacks: dict | None = None):
        self.workspace = workspace
        self.checkpoint_store = checkpoint_store
        self.callbacks = callbacks or {}
        self.events: queue.Queue = queue.Queue()
        self._values = {
            "workspace_id": workspace.config.workspace_id,
            "creator": "UNKNOWN", "spotlight": "UNKNOWN", "account": "UNKNOWN",
            "treecut_local": "UNKNOWN", "current_task": "IDLE", "last_checkpoint": "—",
        }
        self._labels: dict[str, tk.StringVar] = {}
        self.root: tk.Tk | None = None
        self._thread: threading.Thread | None = None

    # ---- 事件驱动更新（可从任意线程调用） ----
    def post_status(self, **status: object) -> None:
        self.events.put(dict(status))

    def _drain(self) -> None:
        try:
            while True:
                status = self.events.get_nowait()
                for key, value in status.items():
                    if key in self._values and value is not None:
                        self._values[key] = str(value)
                    elif key == "last_checkpoint" and value:
                        self._values["last_checkpoint"] = str(value)
        except queue.Empty:
            pass
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        for key, var in self._labels.items():
            var.set(f"{key}: {self._values.get(key, '')}")

    # ---- UI 构建 ----
    def build(self) -> tk.Tk:
        root = tk.Tk()
        self.root = root
        root.title("TreeCut XHS Work Browser")
        root.geometry("420x300")
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="TreeCut XHS Work Browser", font=("", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Workspace: " + self.workspace.config.workspace_id).pack(anchor="w", pady=(2, 6))

        for key in FIELD_KEYS:
            if key == "workspace_id":
                continue
            var = tk.StringVar(value="")
            self._labels[key] = var
            row = ttk.Frame(frame)
            row.pack(anchor="w", fill="x")
            ttk.Label(row, textvariable=var, width=38, anchor="w").pack(side="left")
        self._refresh_labels()

        ttk.Separator(frame).pack(fill="x", pady=8)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        specs = [
            ("打开 Creator", "on_open_creator"),
            ("打开聚光", "on_open_spotlight"),
            ("检查账号", "on_check_account"),
            ("重新检查登录", "on_recheck_login"),
            ("继续任务", "on_resume_task"),
            ("查看错误", "on_view_errors"),
        ]
        for i, (text, key) in enumerate(specs):
            cb = self.callbacks.get(key)
            btn = ttk.Button(buttons, text=text, width=13,
                             command=lambda k=key, fn=cb: self._invoke(k, fn))
            btn.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            buttons.columnconfigure(i % 3, weight=1)
        return root

    def _invoke(self, key: str, fn) -> None:
        if fn is None:
            return
        try:
            fn()
        except Exception as error:  # 面板回调异常不得打断 UI
            self.post_status(current_task=f"FAILED: {type(error).__name__}")

    def run(self) -> None:
        """阻塞运行控制台事件循环（close 由窗口关闭触发）。"""
        if self.root is None:
            self.build()
        root = self.root
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        def tick() -> None:
            self._drain()
            if root.winfo_exists():
                root.after(250, tick)

        root.after(250, tick)
        root.mainloop()

    def _on_close(self) -> None:
        if self.root is not None:
            self.root.destroy()
            self.root = None

    # ---- §14 查看错误 ----
    def view_errors(self) -> str:
        """返回最近 checkpoint 的 last_error（无敏感信息）。"""
        lines = []
        for cp in self.checkpoint_store.unfinished(self.workspace.config.workspace_id)[-5:]:
            lines.append(f"[{cp.updated_at}] {cp.task_type}/{cp.task_id} {cp.state} @{cp.step}: {cp.last_error or '—'}")
        return "\n".join(lines) or "无错误记录"
