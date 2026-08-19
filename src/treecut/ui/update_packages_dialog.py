"""Update package library: keep multiple versions and assign one to a client."""
from __future__ import annotations

import json
import time
import tkinter as tk
import urllib.parse
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from treecut.platform.paths import RuntimePaths
from treecut.remote.update_pack import make_update_package


HUB = "http://127.0.0.1:8766"


class UpdatePackagesDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, paths: RuntimePaths, token: str, master_key: str):
        super().__init__(master)
        self.paths = paths
        self.token = token
        self.master_key = master_key
        self.updates: list[dict] = []
        self.title("更新包库（多版本）")
        self.geometry("780x480")
        self.transient(master)
        self._build()
        self.refresh()

    def _headers(self) -> dict:
        return {"X-TreeCut-Token": self.token, "X-TreeCut-Master": self.master_key}

    def _request(self, method: str, path: str, payload: dict | None = None,
                 raw: bytes | None = None) -> dict:
        data = raw if raw is not None else (
            json.dumps(payload).encode("utf-8") if payload is not None else None
        )
        request = urllib.request.Request(HUB + path, data=data, method=method)
        for name, value in self._headers().items():
            request.add_header(name, value)
        if raw is not None:
            request.add_header("Content-Type", "application/zip")
        elif data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="本机可存放多个版本的更新包；可指定某一版本发给某台电脑。").pack(anchor="w")
        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=6)
        ttk.Button(controls, text="从当前代码生成…", command=self._generate).pack(side="left")
        ttk.Button(controls, text="上传本地包…", command=self._upload).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="删除所选", command=self._delete).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="刷新", command=self.refresh).pack(side="left", padx=(8, 0))

        assign = ttk.Frame(root)
        assign.pack(fill="x")
        ttk.Label(assign, text="指定给：").pack(side="left")
        self.client_var = tk.StringVar()
        self.client_box = ttk.Combobox(assign, textvariable=self.client_var, width=24)
        self.client_box.pack(side="left", padx=(4, 8))
        ttk.Button(assign, text="把所选版本指定给这台电脑",
                   command=self._assign_one).pack(side="left")
        ttk.Button(assign, text="指定给全部电脑",
                   command=self._assign_all).pack(side="left", padx=(8, 0))
        ttk.Button(assign, text="清除指定", command=self._clear_assign).pack(side="left", padx=(8, 0))

        columns = ("version", "force", "notes", "time", "size")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=10)
        headers = {"version": "版本", "force": "强制", "notes": "说明", "time": "时间", "size": "大小"}
        widths = {"version": 90, "force": 60, "notes": 320, "time": 150, "size": 90}
        for column in columns:
            self.tree.heading(column, text=headers[column])
            self.tree.column(column, width=widths[column])
        self.tree.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

    def refresh(self) -> None:
        try:
            data = self._request("GET", "/api/v1/updates")
            clients = self._request("GET", "/api/v1/clients")
        except Exception as error:
            messagebox.showerror("查询失败", str(error), parent=self)
            return
        self.updates = data.get("updates", [])
        client_ids = [client["client_id"] for client in clients.get("clients", [])]
        self.client_box["values"] = client_ids
        if self.client_var.get() not in client_ids:
            self.client_var.set(client_ids[0] if client_ids else "")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for update in self.updates:
            created = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(update["created_at"]))
            path = Path(update["package_path"])
            size = path.stat().st_size if path.is_file() else 0
            self.tree.insert("", "end", iid=update["update_id"], values=(
                update["version"], "是" if update.get("force") else "否",
                update.get("notes") or "", created, f"{size / 1024:.0f} KB",
            ))
        self.status_var.set(f"共 {len(self.updates)} 个更新包")

    def _selected_update_id(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("未选择", "请先选中一个更新包。", parent=self)
            return None
        return selection[0]

    def _generate(self) -> None:
        version = simpledialog.askstring("生成更新包", "版本号（例如 13.1.3）：",
                                         initialvalue="13.1.3", parent=self)
        if not version:
            return
        notes = simpledialog.askstring("生成更新包", "说明：", parent=self) or ""
        force = messagebox.askyesno("生成更新包", "是否标记为强制更新？", parent=self)
        package = self.paths.temp / f"treecut_update_{version}.zip"
        try:
            make_update_package(self.paths.install_root, version, notes, package, force=force)
            data = package.read_bytes()
            query = (f"/api/v1/updates?version={urllib.parse.quote(version)}"
                     f"&notes={urllib.parse.quote(notes)}&force={1 if force else 0}")
            self._request("POST", query, raw=data)
        except Exception as error:
            messagebox.showerror("生成失败", str(error), parent=self)
            return
        finally:
            try:
                package.unlink(missing_ok=True)
            except OSError:
                pass
        self.refresh()

    def _upload(self) -> None:
        path = filedialog.askopenfilename(
            title="选择树剪更新包（zip）", filetypes=[("更新包", "*.zip")],
        )
        if not path:
            return
        version = simpledialog.askstring("上传更新包", "该包的版本号：", parent=self)
        if not version:
            return
        notes = simpledialog.askstring("上传更新包", "说明（可选）：", parent=self) or ""
        try:
            data = Path(path).read_bytes()
            query = (f"/api/v1/updates?version={urllib.parse.quote(version)}"
                     f"&notes={urllib.parse.quote(notes)}")
            self._request("POST", query, raw=data)
        except Exception as error:
            messagebox.showerror("上传失败", str(error), parent=self)
            return
        self.refresh()

    def _delete(self) -> None:
        update_id = self._selected_update_id()
        if update_id is None:
            return
        if not messagebox.askyesno("删除更新包", "确定从库中删除这个更新包吗？", parent=self):
            return
        try:
            self._request("DELETE", f"/api/v1/updates/{update_id}")
        except Exception as error:
            messagebox.showerror("删除失败", str(error), parent=self)
            return
        self.refresh()

    def _assign_one(self) -> None:
        update_id = self._selected_update_id()
        client_id = self.client_var.get().strip()
        if update_id is None or not client_id:
            messagebox.showwarning("信息不完整", "请先选中更新包并选择一台电脑。", parent=self)
            return
        try:
            self._request("POST", f"/api/v1/clients/{client_id}/assign",
                          {"update_id": update_id})
        except Exception as error:
            messagebox.showerror("指定失败", str(error), parent=self)
            return
        messagebox.showinfo("已指定", f"已把该版本指定给 {client_id}，下次上报自动安装。", parent=self)

    def _assign_all(self) -> None:
        update_id = self._selected_update_id()
        if update_id is None:
            return
        try:
            clients = self._request("GET", "/api/v1/clients").get("clients", [])
            for client in clients:
                self._request("POST", f"/api/v1/clients/{client['client_id']}/assign",
                              {"update_id": update_id})
        except Exception as error:
            messagebox.showerror("指定失败", str(error), parent=self)
            return
        messagebox.showinfo("已指定", f"已把该版本指定给全部 {len(clients)} 台电脑。", parent=self)

    def _clear_assign(self) -> None:
        client_id = self.client_var.get().strip()
        if not client_id:
            return
        try:
            self._request("POST", f"/api/v1/clients/{client_id}/assign", {"update_id": ""})
        except Exception as error:
            messagebox.showerror("清除失败", str(error), parent=self)
            return
        self.refresh()
