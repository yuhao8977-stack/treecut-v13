"""XHS Work Browser V0.1.1 — 极简控制台（§12/14/26/31）。

三区块面板：
  Creator / Spotlight / Frontend —— 各自 Session + Account + Binding
  TreeCut Local / Current Task / Last Checkpoint
日志面板（用户日志可见，§28 修复）+ 安全退出。

非阻塞（§28 修复）：所有浏览器/任务操作在线程中执行，经 queue 回投状态，
Tk 主循环只做事件驱动刷新（§31），绝不阻塞 UI。

按钮：同步数据 / 恢复训练媒体 / 继续任务 / 查看异常 / 检查状态 / 安全退出
（同步数据、恢复训练媒体 = V0.1.1 占位 NOT_IMPLEMENTED）
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from treecut.browser.workspace_manager import WorkspaceManager

ROLE_LABELS = {"CREATOR": "Creator", "SPOTLIGHT": "Spotlight", "FRONTEND": "XHS Frontend"}


class _QueueLogHandler(logging.Handler):
    """把日志写入 dashboard 事件队列（UI 可见）。"""

    def __init__(self, events: queue.Queue):
        super().__init__()
        self.events = events

    def emit(self, record: logging.LogRecord) -> None:  # noqa: A003
        try:
            self.events.put({"__log__": self.format(record)})
        except Exception:  # pragma: no cover
            pass


class MinimalDashboard:
    """回调（可注入假实现供测试）：
    on_sync_data / on_recover_media / on_resume_task / on_view_errors / on_check_status / on_safe_exit
    回调会在工作线程执行（非阻塞 UI）。"""

    def __init__(self, workspace: WorkspaceManager,
                 callbacks: dict | None = None,
                 log_level: int = logging.INFO):
        self.workspace = workspace
        self.callbacks = callbacks or {}
        self.events: queue.Queue = queue.Queue()
        self._values = {
            "creator_session": "UNKNOWN", "creator_account": "—", "creator_binding": "—",
            "spotlight_session": "UNKNOWN", "spotlight_account": "—", "spotlight_binding": "—",
            "frontend_session": "UNKNOWN", "frontend_account": "—", "frontend_binding": "—",
            "treecut_local": "UNKNOWN", "current_task": "IDLE", "last_checkpoint": "—",
        }
        self._labels: dict[str, tk.StringVar] = {}
        self._log_var = None
        self.root: tk.Tk | None = None
        self._busy = False

        handler = _QueueLogHandler(self.events)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger("treecut.browser").addHandler(handler)

    # ---- 事件驱动更新（任意线程可调） ----
    def post_status(self, **status: object) -> None:
        self.events.put(dict(status))

    def _drain(self) -> None:
        logs: list[str] = []
        try:
            while True:
                event = self.events.get_nowait()
                if "__log__" in event:
                    logs.append(event["__log__"])
                    continue
                for key, value in event.items():
                    if key in self._values and value is not None:
                        self._values[key] = str(value)
        except queue.Empty:
            pass
        if logs:
            for line in logs:
                self._log_var.insert(tk.END, line + "\n")
            self._log_var.see(tk.END)
        for key, var in self._labels.items():
            var.set(self._values.get(key, ""))

    # ---- UI ----
    def build(self) -> tk.Tk:
        root = tk.Tk()
        self.root = root
        root.title("TreeCut XHS Work Browser — Workspace " + self.workspace.config.workspace_id)
        root.geometry("560x520")
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="TreeCut XHS Work Browser",
                  font=("", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Workspace: " + self.workspace.config.workspace_id
                  ).grid(row=0, column=1, sticky="e")

        row = 1
        for role in ("CREATOR", "SPOTLIGHT", "FRONTEND"):
            label = ROLE_LABELS[role]
            ttk.Label(frame, text=f"── {label} ──", font=("", 9, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
            row += 1
            for field, key in (("Session", f"{role.lower()}_session"),
                               ("Account", f"{role.lower()}_account"),
                               ("Binding", f"{role.lower()}_binding")):
                var = tk.StringVar(value="")
                self._labels[key] = var
                ttk.Label(frame, text=f"{field}:").grid(row=row, column=0, sticky="w")
                ttk.Label(frame, textvariable=var, width=44, anchor="w").grid(
                    row=row, column=1, sticky="w")
                row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=6)
        row += 1
        for field, key in (("TreeCut Local", "treecut_local"),
                           ("Current Task", "current_task"),
                           ("Last Checkpoint", "last_checkpoint")):
            var = tk.StringVar(value="")
            self._labels[key] = var
            ttk.Label(frame, text=f"{field}:").grid(row=row, column=0, sticky="w")
            ttk.Label(frame, textvariable=var, width=44, anchor="w").grid(
                row=row, column=1, sticky="w")
            row += 1

        # 日志面板（用户日志可见）
        ttk.Label(frame, text="Log:").grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1
        self._log_var = scrolledtext.ScrolledText(frame, height=6, width=70,
                                                  state=tk.NORMAL, font=("Consolas", 8))
        self._log_var.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 6))
        self._log_var.configure(state=tk.DISABLED)
        row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky="ew")
        specs = [
            ("同步数据", "on_sync_data"),
            ("恢复训练媒体", "on_recover_media"),
            ("继续任务", "on_resume_task"),
            ("查看异常", "on_view_errors"),
            ("检查状态", "on_check_status"),
            ("安全退出", "on_safe_exit"),
        ]
        for i, (text, key) in enumerate(specs):
            cb = self.callbacks.get(key)
            btn = ttk.Button(buttons, text=text, width=13,
                             command=lambda k=key, fn=cb: self._invoke(k, fn))
            btn.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            buttons.columnconfigure(i % 3, weight=1)
        self._drain()
        return root

    def _log(self, text: str) -> None:
        self.events.put({"__log__": text})

    def _invoke(self, key: str, fn) -> None:
        """回调在工作线程执行 → UI 不阻塞（§28 修复）。"""
        if fn is None:
            self._log(f"[panel] {key}: 未注册")
            return
        if self._busy:
            self._log("[panel] 上一操作仍在执行")
            return

        def worker() -> None:
            self._busy = True
            try:
                fn()
            except Exception as error:
                self.post_status(current_task=f"FAILED: {type(error).__name__}")
                self._log(f"[panel] {key} 失败: {error}")
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True).start()

    # ---- 运行 ----
    def run(self) -> None:
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
        safe_exit = self.callbacks.get("on_safe_exit")
        if safe_exit is not None:
            try:
                safe_exit()
            except Exception:  # pragma: no cover
                pass
        if self.root is not None:
            self.root.destroy()
            self.root = None

    # ---- §14 查看异常 ----
    def view_errors_text(self, unfinished: list) -> str:
        lines = []
        for cp in unfinished[-5:]:
            lines.append(f"[{cp.updated_at}] {cp.task_type}/{cp.task_id} {cp.state} "
                         f"@{cp.step} tab={cp.required_tab}: {cp.last_error or '—'}")
        return "\n".join(lines) or "无错误记录"
