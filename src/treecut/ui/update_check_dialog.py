"""Check-update dialog backed by the remote hub."""
from __future__ import annotations

import json
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import messagebox, ttk

from treecut.platform.paths import RuntimePaths
from treecut.remote.config import load_config


class UpdateCheckDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, paths: RuntimePaths):
        super().__init__(master)
        self.paths = paths
        self.title("检查更新")
        self.geometry("560x320")
        self.transient(master)
        self.config = load_config(paths.data_root / "config" / "remote.json")
        self._build()
        self._refresh()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        self.text = tk.Text(root, height=10, state="disabled", wrap="word")
        self.text.pack(fill="both", expand=True)
        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(10, 0))
        ttk.Button(controls, text="立即检查（通知远程助手）", command=self._wake).pack(side="left")
        ttk.Button(controls, text="重新查询", command=self._refresh).pack(side="left", padx=(8, 0))

    def _set_text(self, content: str) -> None:
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.config(state="disabled")

    def _hub_request(self):
        if not self.config.valid():
            return None, "未配置远程管理：请先在「远程管理」窗口填写地址与口令。"
        request = urllib.request.Request(self.config.hub_url.rstrip("/") + "/api/v1/config")
        request.add_header("X-TreeCut-Token", self.config.token)
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8")), None

    def _refresh(self) -> None:
        try:
            info, error = self._hub_request()
        except urllib.error.HTTPError as exc:
            error = f"管理端拒绝访问（{exc.code}）：请检查口令"
            info = None
        except Exception as exc:
            error = f"无法连接管理端：{exc}"
            info = None
        if error:
            self._set_text(error)
            return
        from treecut.maintenance import treecut_version
        current = treecut_version(self.paths)
        min_version = info.get("min_version") or "未设置"
        latest = info.get("latest_update")
        lines = [
            f"当前软件版本：{current}",
            f"管理端最低版本要求：{min_version}",
        ]
        if latest:
            lines.append(f"最新更新包：{latest['version']}"
                         + ("（强制更新）" if latest.get("force") else ""))
            lines.append(f"更新说明：{latest.get('notes') or '无'}")
        else:
            lines.append("最新更新包：无")
        self._set_text("\n".join(lines))

    def _wake(self) -> None:
        if not self.config.valid():
            messagebox.showwarning("未配置", "请先在「远程管理」窗口填写管理端地址与口令。", parent=self)
            return
        try:
            (self.paths.data_root / "config" / "remote_wake.flag").write_text("1", encoding="ascii")
        except OSError as error:
            messagebox.showerror("通知失败", str(error), parent=self)
            return
        messagebox.showinfo(
            "已通知",
            "已通知远程助手立即检查。\n若有更新会自动下载安装；强制更新安装完成后请重启软件生效。",
            parent=self,
        )
