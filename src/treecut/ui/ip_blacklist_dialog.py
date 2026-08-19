"""IP blacklist management page (master program only)."""
from __future__ import annotations

import json
import tkinter as tk
import urllib.request
from tkinter import messagebox, simpledialog, ttk


HUB = "http://127.0.0.1:8766"


class IpBlacklistDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, token: str, master_key: str):
        super().__init__(master)
        self.token = token
        self.master_key = master_key
        self.title("IP 黑名单")
        self.geometry("520x400")
        self.transient(master)
        self._build()
        self.refresh()

    def _headers(self) -> dict:
        return {"X-TreeCut-Token": self.token, "X-TreeCut-Master": self.master_key}

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(HUB + path, data=data, method=method)
        for name, value in self._headers().items():
            request.add_header(name, value)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="被拉黑的 IP 将无法访问管理端任何接口（IP 黑名单管理本身除外）。").pack(anchor="w")
        self.listbox = tk.Listbox(root, height=12)
        self.listbox.pack(fill="both", expand=True, pady=8)
        controls = ttk.Frame(root)
        controls.pack(fill="x")
        ttk.Button(controls, text="拉黑 IP…", command=self._add).pack(side="left")
        ttk.Button(controls, text="解除所选", command=self._remove).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="刷新", command=self.refresh).pack(side="left", padx=(8, 0))

    def refresh(self) -> None:
        try:
            ips = self._request("GET", "/api/v1/blacklist").get("ips", [])
        except Exception as error:
            messagebox.showerror("查询失败", str(error), parent=self)
            return
        self.listbox.delete(0, "end")
        for ip in ips:
            self.listbox.insert("end", ip)

    def _add(self) -> None:
        ip = simpledialog.askstring("拉黑 IP", "输入要拉黑的 IP 地址：", parent=self)
        if not ip:
            return
        ip = ip.strip()
        if not messagebox.askyesno("确认拉黑",
                                   f"确定拉黑 {ip} 吗？该 IP 的所有客户端将无法上报。",
                                   parent=self):
            return
        try:
            self._request("POST", "/api/v1/blacklist", {"ip": ip})
        except Exception as error:
            messagebox.showerror("操作失败", str(error), parent=self)
            return
        self.refresh()

    def _remove(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("未选择", "请先选中要解除的 IP。", parent=self)
            return
        ip = self.listbox.get(selection[0])
        try:
            self._request("DELETE", f"/api/v1/blacklist/{ip}")
        except Exception as error:
            messagebox.showerror("操作失败", str(error), parent=self)
            return
        self.refresh()
