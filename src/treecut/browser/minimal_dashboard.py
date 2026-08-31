"""TreeCut XHS Work Browser V0.1.2 — 极简控制台（简体中文）。

三区块：创作服务平台 / 聚光后台 / 小红书前台 + TreeCut（本地服务/当前任务/上次进度）+ 运行日志。
- 非阻塞：回调线程化，queue 回投，Tk 主循环仅事件驱动刷新。
- 日志：logging handler → queue → 面板（修复 V0.1.1 日志空白：insert 前临时置 NORMAL）。
- 绑定 UX：检测到未绑定时显示 [绑定当前Creator为B007] / [绑定为B007聚光账户]。
- 占位按钮（同步数据/恢复训练视频）disabled 并标注"下一阶段启用"。
- Frontend 绑定为可选，不作 B007 硬性要求（媒体身份以 note_id 为 Gate）。

状态翻译（开发枚举 → 中文显示）：
SESSION_VALID→已登录 / SESSION_EXPIRED→登录已过期 / LOGIN_REQUIRED→需要登录 /
SESSION_UNKNOWN→状态未知 / ACCOUNT_IDENTITY_VALID→已确认 / MISMATCH→账号不匹配 /
UNKNOWN→未检测到 / CONNECTED→已连接 / DISCONNECTED→未连接 / IDLE→空闲 / 无→暂无
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from treecut.browser.workspace_manager import WorkspaceManager

SESSION_ZH = {
    "SESSION_VALID": "已登录 ✅",
    "SESSION_EXPIRED": "登录已过期",
    "LOGIN_REQUIRED": "需要登录",
    "SESSION_UNKNOWN": "状态未知",
}
IDENTITY_ZH = {
    "ACCOUNT_IDENTITY_VALID": "已确认 ✅",
    "ACCOUNT_IDENTITY_MISMATCH": "账号不匹配（已阻断）",
    "ACCOUNT_IDENTITY_UNKNOWN": "未检测到",
    "FRONTEND_IDENTITY_UNCONFIRMED": "可选（未确认）",
}
LOCAL_ZH = {"CONNECTED": "已连接 ✅", "DISCONNECTED": "未连接", "UNKNOWN": "未知"}
TASK_ZH = {"IDLE": "空闲", "RUNNING": "运行中", "PAUSED": "已暂停", "SUCCESS": "成功",
           "FAILED": "失败", "NEEDS_HUMAN": "需人工处理"}


def _zh(value, table, fallback="未知") -> str:
    return table.get(str(value or ""), fallback if value else "暂无")


class _QueueLogHandler(logging.Handler):
    def __init__(self, events: queue.Queue):
        super().__init__()
        self.events = events

    def emit(self, record: logging.LogRecord) -> None:  # noqa: A003
        try:
            self.events.put({"__log__": self.format(record)})
        except Exception:  # pragma: no cover
            pass


class MinimalDashboard:
    """回调（测试可注入假实现）：
    on_sync_data / on_recover_media / on_resume_task / on_view_errors /
    on_check_status / on_bind_creator / on_bind_spotlight / on_safe_exit
    全部在工作线程执行（UI 不阻塞）。"""

    def __init__(self, workspace: WorkspaceManager,
                 callbacks: dict | None = None,
                 log_level: int = logging.INFO):
        self.workspace = workspace
        self.callbacks = callbacks or {}
        self.events: queue.Queue = queue.Queue()
        self._values = {
            "creator_session": "", "creator_account": "", "creator_xhs_id": "",
            "creator_binding": "NONE",
            "spotlight_session": "", "spotlight_account": "", "spotlight_ad_id": "",
            "spotlight_binding": "NONE",
            "frontend_session": "", "frontend_view": "", "frontend_binding": "OPTIONAL",
            "treecut_local": "", "current_task": "IDLE", "last_checkpoint": None,
        }
        self._labels: dict[str, tk.StringVar] = {}
        self._log_var: scrolledtext.ScrolledText | None = None
        self.root: tk.Tk | None = None
        self._inflight: set[str] = set()
        self._bind_creator_btn: ttk.Button | None = None
        self._bind_spotlight_btn: ttk.Button | None = None

        handler = _QueueLogHandler(self.events)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger("treecut.browser").addHandler(handler)

    # ---- 事件驱动更新 ----
    def post_status(self, **status: object) -> None:
        self.events.put(dict(status))

    def _log(self, text: str) -> None:
        self.events.put({"__log__": text})

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
                        self._values[key] = value
        except queue.Empty:
            pass
        if logs and self._log_var is not None:
            self._append_log("\n".join(logs))
        for key, var in self._labels.items():
            var.set(self._render(key))

    def _append_log(self, text: str) -> None:
        var = self._log_var
        var.configure(state=tk.NORMAL)  # insert 前临时置 NORMAL（修复空白）
        var.insert(tk.END, text + "\n")
        var.see(tk.END)
        var.configure(state=tk.DISABLED)

    def _render(self, key: str) -> str:
        v = self._values.get(key)
        if key == "creator_session":
            return "登录状态：" + _zh(v, SESSION_ZH)
        if key == "creator_account":
            return "账号：" + (str(v) if v else "—")
        if key == "creator_xhs_id":
            return "小红书号：" + (str(v) if v else "—")
        if key == "creator_binding":
            return "账号绑定：" + {"BOUND": "B007 ✅", "PENDING": "待绑定",
                                   "MISMATCH": "账号不匹配（阻断）"}.get(str(v), "—")
        if key == "spotlight_session":
            return "登录状态：" + _zh(v, SESSION_ZH)
        if key == "spotlight_account":
            return "广告账户：" + (str(v) if v else "—")
        if key == "spotlight_ad_id":
            return "广告账户ID：" + (str(v) if v else "—")
        if key == "spotlight_binding":
            return "账户绑定：" + {"BOUND": "B007 ✅", "PENDING": "待绑定",
                                   "MISMATCH": "账户不匹配（阻断）"}.get(str(v), "—")
        if key == "frontend_session":
            return "登录状态：" + _zh(v, SESSION_ZH)
        if key == "frontend_view":
            return "视频浏览状态：" + (str(v) if v else "—")
        if key == "frontend_binding":
            return "账号绑定：" + (str(v) if v else "可选（不作 B007 硬性要求）")
        if key == "treecut_local":
            return "本地服务：" + _zh(v, LOCAL_ZH)
        if key == "current_task":
            return "当前任务：" + _zh(v, TASK_ZH, fallback="未知")
        if key == "last_checkpoint":
            return "上次进度：" + (str(v) if v else "暂无")
        return ""

    # ---- UI ----
    def build(self) -> tk.Tk:
        root = tk.Tk()
        self.root = root
        root.title("TreeCut 小红书工作浏览器 — 工作账号 " + self.workspace.config.workspace_id)
        root.geometry("620x620")
        root.resizable(False, False)
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="TreeCut 小红书工作浏览器",
                  font=("", 13, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="工作账号：" + self.workspace.config.workspace_id
                  ).grid(row=0, column=1, sticky="e")

        row = 1
        sections = [
            ("── 创作服务平台 ──", ["creator_session", "creator_account", "creator_xhs_id",
                                   "creator_binding"]),
            ("── 聚光后台 ──", ["spotlight_session", "spotlight_account", "spotlight_ad_id",
                              "spotlight_binding"]),
            ("── 小红书前台 ──", ["frontend_session", "frontend_view", "frontend_binding"]),
        ]
        for title, keys in sections:
            ttk.Label(frame, text=title, font=("", 9, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
            row += 1
            for key in keys:
                var = tk.StringVar(value="")
                self._labels[key] = var
                ttk.Label(frame, textvariable=var, width=56, anchor="w").grid(
                    row=row, column=0, columnspan=2, sticky="w")
                row += 1

        ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky="ew", pady=6)
        row += 1
        for key in ("treecut_local", "current_task", "last_checkpoint"):
            var = tk.StringVar(value="")
            self._labels[key] = var
            ttk.Label(frame, textvariable=var, width=56, anchor="w").grid(
                row=row, column=0, columnspan=2, sticky="w")
            row += 1

        # 绑定按钮（动态启用）
        bind_row = ttk.Frame(frame)
        bind_row.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
        row += 1
        self._bind_creator_btn = ttk.Button(
            bind_row, text="绑定当前 Creator 为 B007", width=22,
            command=lambda: self._invoke("on_bind_creator", self.callbacks.get("on_bind_creator")))
        self._bind_creator_btn.grid(row=0, column=0, padx=2)
        self._bind_spotlight_btn = ttk.Button(
            bind_row, text="绑定为 B007 聚光账户", width=22,
            command=lambda: self._invoke("on_bind_spotlight", self.callbacks.get("on_bind_spotlight")))
        self._bind_spotlight_btn.grid(row=0, column=1, padx=2)

        # 运行日志
        ttk.Label(frame, text="── 运行日志 ──", font=("", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1
        self._log_var = scrolledtext.ScrolledText(frame, height=9, width=74,
                                                  state=tk.DISABLED, font=("Consolas", 8))
        self._log_var.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 6))
        row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=0, columnspan=2, sticky="ew")
        specs = [
            ("同步数据", "on_sync_data", False),
            ("恢复训练视频（下一阶段）", "on_recover_media", True),
            ("继续上次任务", "on_resume_task", False),
            ("查看异常", "on_view_errors", False),
            ("重新检测状态", "on_check_status", False),
            ("安全退出", "on_safe_exit", False),
        ]
        for i, (text, key, disabled) in enumerate(specs):
            cb = self.callbacks.get(key)
            btn = ttk.Button(buttons, text=text, width=15,
                             command=lambda k=key, fn=cb: self._invoke(k, fn))
            if disabled:
                btn.state(["disabled"])
            btn.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            buttons.columnconfigure(i % 3, weight=1)
        self._drain()
        return root

    def _refresh_bind_buttons(self) -> None:
        """绑定按钮启用条件：未绑定 或 未检测到（NONE/PENDING）——点击会重试检测并输出诊断；
        BOUND/MISMATCH 时禁用（已绑定或身份冲突，需人工处理）。"""
        if self._bind_creator_btn is None or self._bind_spotlight_btn is None:
            return
        creator = str(self._values.get("creator_binding", "NONE"))
        spotlight = str(self._values.get("spotlight_binding", "NONE"))
        if creator in ("NONE", "PENDING"):
            self._bind_creator_btn.state(["!disabled"])
        else:
            self._bind_creator_btn.state(["disabled"])
        if spotlight in ("NONE", "PENDING"):
            self._bind_spotlight_btn.state(["!disabled"])
        else:
            self._bind_spotlight_btn.state(["disabled"])

    def _invoke(self, key: str, fn) -> None:
        """回调在工作线程执行 → UI 不阻塞；同一操作不重复堆积（其余排队由
        BrowserExecutor 单线程串行消化），绝不出现"假死"提示。"""
        if fn is None:
            self._log(f"[面板] {key} 未注册")
            return
        if key in self._inflight:
            self._log(f"[面板] {key} 正在执行，请稍候")
            return
        self._inflight.add(key)

        def worker() -> None:
            try:
                fn()
            except Exception as error:
                self.post_status(current_task="FAILED")
                self._log(f"[面板] {key} 失败: {error}")
            finally:
                self._inflight.discard(key)

        threading.Thread(target=worker, daemon=True).start()

    # ---- 运行 ----
    def run(self) -> None:
        if self.root is None:
            self.build()
        root = self.root
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        def tick() -> None:
            self._drain()
            self._refresh_bind_buttons()
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

    # ---- 查看异常 ----
    def view_errors_text(self, unfinished: list) -> str:
        lines = []
        for cp in unfinished[-5:]:
            lines.append(f"[{cp.updated_at}] {cp.task_type}/{cp.task_id} {cp.state} "
                         f"@{cp.step} tab={cp.required_tab}: {cp.last_error or '—'}")
        return "\n".join(lines) or "无异常记录"
