"""Remote management dialog: monitor clients, push updates, and control devices."""
from __future__ import annotations

import json
import socket
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
from tkinter import messagebox, simpledialog, ttk

from treecut.platform.paths import RuntimePaths
from treecut.remote.roles import load_or_create_master_key
from treecut.remote.security import load_or_create_token
from treecut.remote.update_pack import make_update_package


def _hub_url() -> str:
    return "http://127.0.0.1:8766"


class RemoteManagerDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, paths: RuntimePaths):
        super().__init__(master)
        self.paths = paths
        self.token = load_or_create_token(paths.data_root / "config" / "api_token.txt")
        self.master_key = load_or_create_master_key(paths)
        self.title("远程管理")
        self.geometry("880x560")
        self.transient(master)
        self._ensure_hub()
        self._build()
        self.refresh()

    def _ensure_hub(self) -> None:
        """Start the hub in the background when it is not already running."""
        probe = socket.socket()
        try:
            probe.connect(("127.0.0.1", 8766))
            probe.close()
            return
        except OSError:
            pass
        import uvicorn
        from treecut.remote.hub import create_hub_app
        app = create_hub_app(self.paths)
        config = uvicorn.Config(app, host="0.0.0.0", port=8766, log_level="warning")
        server = uvicorn.Server(config)
        threading.Thread(target=server.run, daemon=True).start()
        for _ in range(50):
            try:
                urllib.request.urlopen(_hub_url() + "/health", timeout=1)
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("远程管理服务启动失败，请检查端口 8766 是否被占用")

    def _build(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        from treecut.remote.hub_main import lan_ip
        address = f"http://{lan_ip()}:8766"
        ttk.Label(
            root,
            text=f"另一台电脑填写：\n地址：{address}\n口令：{self.token}",
            wraplength=840,
        ).pack(anchor="w")

        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(8, 0))
        ttk.Button(controls, text="刷新", command=self.refresh).pack(side="left")
        ttk.Button(controls, text="生成并推送更新…", command=self._push_update).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="设置最低版本…", command=self._set_min_version).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="操作记录…", command=self._audit).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="更新包库…", command=self._open_packages).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="IP 黑名单…", command=self._open_blacklist).pack(side="left", padx=(8, 0))
        ttk.Label(controls, text="分组：").pack(side="left", padx=(12, 2))
        self.group_var = tk.StringVar(value="全部")
        self.group_box = ttk.Combobox(controls, textvariable=self.group_var,
                                      state="readonly", width=12)
        self.group_box.pack(side="left")
        self.group_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="禁用", command=lambda: self._command("disable")).pack(side="left")
        ttk.Button(actions, text="启用", command=lambda: self._command("enable")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="拉黑", command=lambda: self._command("blacklist", confirm=True)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="解除拉黑", command=lambda: self._command("unblacklist")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="设置分组…", command=self._set_group).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="清空数据…", command=self._wipe).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="卸载…", command=self._uninstall).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="全部禁用", command=lambda: self._all("disable")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="全部启用", command=lambda: self._all("enable")).pack(side="left", padx=(8, 0))

        ops = ttk.Frame(root)
        ops.pack(fill="x", pady=(8, 0))
        ttk.Label(ops, text="远程操作：").pack(side="left")
        ttk.Button(ops, text="允许远程命令（先开这个）",
                   command=lambda: self._set_exec_policy(True)).pack(side="left", padx=(6, 0))
        ttk.Button(ops, text="禁止远程命令",
                   command=lambda: self._set_exec_policy(False)).pack(side="left", padx=(6, 0))
        ttk.Button(ops, text="远程命令…", command=self._remote_command).pack(side="left", padx=(6, 0))
        ttk.Button(ops, text="远程启动软件", command=lambda: self._app_action("start_app", "启动软件")).pack(side="left", padx=(6, 0))
        ttk.Button(ops, text="远程关闭软件", command=lambda: self._app_action("stop_app", "关闭软件")).pack(side="left", padx=(6, 0))
        ttk.Button(ops, text="软件状态", command=lambda: self._app_action("app_status", "软件状态")).pack(side="left", padx=(6, 0))

        columns = ("client", "ip", "version", "last_seen", "state", "assign", "database", "job", "group")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=14)
        headers = {"client": "客户端", "ip": "IP", "version": "版本", "last_seen": "最后上报",
                   "state": "状态", "assign": "指定版本", "database": "数据库",
                   "job": "最近任务", "group": "分组"}
        widths = {"client": 150, "ip": 110, "version": 62, "last_seen": 120, "state": 62,
                  "assign": 80, "database": 80, "job": 90, "group": 80}
        for column in columns:
            self.tree.heading(column, text=headers[column])
            self.tree.column(column, width=widths[column])
        self.tree.pack(fill="both", expand=True, pady=(8, 0))
        self.status_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.status_var, wraplength=840).pack(anchor="w", pady=(8, 0))

    def _request(self, path: str, payload: dict | None = None, method: str = "GET"):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(_hub_url() + path, data=data, method=method)
        request.add_header("Content-Type", "application/json; charset=utf-8")
        request.add_header("X-TreeCut-Token", self.token)
        request.add_header("X-TreeCut-Master", self.master_key)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def _selected_client_id(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("未选择", "请先在列表里选中一台电脑。", parent=self)
            return None
        return self.tree.item(selection[0], "values")[0]

    def refresh(self) -> None:
        try:
            clients = self._request("/api/v1/clients").get("clients", [])
            update_map = {
                item["update_id"]: item["version"]
                for item in self._request("/api/v1/updates").get("updates", [])
            }
        except Exception as error:
            messagebox.showerror("无法连接管理服务", str(error), parent=self)
            return
        groups = sorted({client.get("group_name") or "" for client in clients})
        self.group_box["values"] = ["全部", "未分组"] + [g for g in groups if g]
        chosen = self.group_var.get()
        for item in self.tree.get_children():
            self.tree.delete(item)
        shown = 0
        for client in clients:
            group = client.get("group_name") or ""
            if chosen == "未分组" and group:
                continue
            if chosen not in ("全部", "未分组") and group != chosen:
                continue
            status = client.get("status") or {}
            health = status.get("database_health") or {}
            bad = [name for name, state in health.items() if state != "ok"]
            database = "正常" if not bad else "异常：" + "、".join(bad)
            jobs = status.get("recent_jobs") or []
            job_state = jobs[0].get("state", "—") if jobs else "—"
            if client.get("blacklisted"):
                state = "已拉黑"
            elif client.get("disabled"):
                state = "已禁用"
            else:
                state = "正常"
            last_seen = time.strftime("%m-%d %H:%M:%S", time.localtime(client["last_seen"]))
            assigned = update_map.get(client.get("assigned_update_id") or "", "—")
            self.tree.insert("", "end", values=(
                client["client_id"], client.get("last_ip") or "—", client["version"],
                last_seen, state, assigned, database, job_state, group or "—",
            ))
            shown += 1
        self.status_var.set(f"显示 {shown} 台（共 {len(clients)} 台客户端）")

    def _command(self, action: str, confirm: bool = False) -> None:
        client_id = self._selected_client_id()
        if client_id is None:
            return
        labels = {"disable": "禁用", "enable": "启用", "blacklist": "拉黑", "unblacklist": "解除拉黑"}
        if confirm and not messagebox.askyesno(
                f"确认{labels[action]}？",
                f"确定对 {client_id} 执行「{labels[action]}」吗？",
                parent=self,
        ):
            return
        try:
            self._request(f"/api/v1/clients/{client_id}/commands",
                          {"action": action, "note": f"来自远程管理窗口：{labels[action]}"},
                          method="POST")
        except Exception as error:
            messagebox.showerror("下发失败", str(error), parent=self)
            return
        self.refresh()

    def _all(self, action: str) -> None:
        label = "禁用" if action == "disable" else "启用"
        if not messagebox.askyesno(f"全部{label}？",
                                   f"确定对列表里所有客户端执行「{label}」吗？", parent=self):
            return
        try:
            clients = self._request("/api/v1/clients").get("clients", [])
        except Exception as error:
            messagebox.showerror("查询失败", str(error), parent=self)
            return
        for client in clients:
            try:
                self._request(f"/api/v1/clients/{client['client_id']}/commands",
                              {"action": action, "note": f"批量{label}"}, method="POST")
            except Exception as error:
                messagebox.showerror("下发失败", f"{client['client_id']}：{error}", parent=self)
                return
        self.refresh()

    def _wipe(self) -> None:
        client_id = self._selected_client_id()
        if client_id is None:
            return
        if not messagebox.askyesno(
                "清空数据（第一步确认）",
                f"将清空 {client_id} 的数据库、素材记录、成品和历史日志。\n此操作不可撤销！\n确定继续吗？",
                parent=self,
        ):
            return
        if not messagebox.askyesno(
                "清空数据（第二步确认）",
                "再次确认：真的要清空这台电脑的全部用户数据吗？",
                parent=self,
        ):
            return
        try:
            self._request(f"/api/v1/clients/{client_id}/commands",
                          {"action": "wipe", "note": "远程清空用户数据（双重确认）"}, method="POST")
        except Exception as error:
            messagebox.showerror("下发失败", str(error), parent=self)
            return
        messagebox.showinfo("已下发", "清空指令已下发，客户端下次上报时自动执行。", parent=self)
        self.refresh()

    def _uninstall(self) -> None:
        client_id = self._selected_client_id()
        if client_id is None:
            return
        if not messagebox.askyesno(
                "卸载（第一步确认）",
                f"将清空 {client_id} 的全部用户数据，并删除整个软件文件夹。\n"
                "这是不可逆操作！确定继续吗？",
                parent=self,
        ):
            return
        if not messagebox.askyesno(
                "卸载（第二步确认）",
                "再次确认：真的要卸载这台电脑上的树剪吗？卸载后无法远程恢复。",
                parent=self,
        ):
            return
        try:
            self._request(f"/api/v1/clients/{client_id}/commands",
                          {"action": "uninstall", "note": "远程卸载（双重确认）"}, method="POST")
        except Exception as error:
            messagebox.showerror("下发失败", str(error), parent=self)
            return
        messagebox.showinfo("已下发", "卸载指令已下发，客户端下次上报时自动执行。", parent=self)
        self.refresh()

    def _set_group(self) -> None:
        client_id = self._selected_client_id()
        if client_id is None:
            return
        group = simpledialog.askstring("设置分组", "输入分组名称（留空清除）：", parent=self) or ""
        try:
            self._request(f"/api/v1/clients/{client_id}/group",
                          {"group_name": group.strip()}, method="POST")
        except Exception as error:
            messagebox.showerror("设置失败", str(error), parent=self)
            return
        self.refresh()

    def _set_min_version(self) -> None:
        current = ""
        try:
            current = self._request("/api/v1/config").get("min_version") or ""
        except Exception:
            pass
        value = simpledialog.askstring("设置最低版本", "低于此版本的客户端将被拦截并强制更新（例如 13.1.2，留空清除）：",
                                       initialvalue=current, parent=self)
        if value is None:
            return
        try:
            self._request("/api/v1/config", {"min_version": value.strip()}, method="POST")
        except Exception as error:
            messagebox.showerror("设置失败", str(error), parent=self)
            return
        self.refresh()

    def _audit(self) -> None:
        try:
            records = self._request("/api/v1/audit").get("commands", [])
        except Exception as error:
            messagebox.showerror("查询失败", str(error), parent=self)
            return
        window = tk.Toplevel(self)
        window.title("操作记录")
        window.geometry("760x400")
        text = tk.Text(window, state="disabled", wrap="word")
        text.pack(fill="both", expand=True, padx=8, pady=8)
        lines = []
        for record in records:
            created = time.strftime("%m-%d %H:%M:%S", time.localtime(record["created_at"]))
            status = {"pending": "待执行", "delivered": "已送达", "done": "已完成",
                      "failed": "失败"}.get(record["status"], record["status"])
            lines.append(f"[{created}] {record['client_id']} 动作：{record['action']} "
                         f"状态：{status} 备注：{record['note'] or '—'} 结果：{record['result'] or '—'}")
        text.config(state="normal")
        text.insert("1.0", "\n".join(lines) or "暂无操作记录")
        text.config(state="disabled")

    def _push_update(self) -> None:
        version = simpledialog.askstring("推送更新", "更新版本号（例如 13.1.1）：",
                                         initialvalue="13.1.1", parent=self)
        if not version:
            return
        notes = simpledialog.askstring("推送更新", "更新说明（例如：修复了…）：",
                                       parent=self) or ""
        force = messagebox.askyesno(
            "强制更新？",
            "是否标记为强制更新？\n强制更新时，客户端会先装完更新才允许继续使用。",
            parent=self,
        )
        package = self.paths.temp / f"treecut_update_{version}.zip"
        try:
            make_update_package(self.paths.install_root, version, notes, package, force=force)
            data = package.read_bytes()
            query = (f"/api/v1/updates?version={urllib.parse.quote(version)}"
                     f"&notes={urllib.parse.quote(notes)}&force={1 if force else 0}")
            request = urllib.request.Request(_hub_url() + query, data=data, method="POST")
            request.add_header("X-TreeCut-Token", self.token)
            request.add_header("X-TreeCut-Master", self.master_key)
            request.add_header("Content-Type", "application/zip")
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            messagebox.showerror("推送失败", str(error), parent=self)
            return
        finally:
            try:
                package.unlink(missing_ok=True)
            except OSError:
                pass
        messagebox.showinfo(
            "更新已推送",
            f"更新包 {result.get('version')} 已上传到管理端"
            + ("（强制更新）" if result.get("force") else "") + "。\n"
            "客户端下次上报时会自动接收、校验并安装。",
            parent=self,
        )
        self.refresh()

    def _set_exec_policy(self, allow: bool) -> None:
        client_id = self._selected_client_id()
        if client_id is None:
            return
        try:
            self._request(f"/api/v1/clients/{client_id}/exec-policy",
                          {"allow": allow}, method="POST")
        except Exception as error:
            messagebox.showerror("设置失败", str(error), parent=self)
            return
        messagebox.showinfo("已设置", "已" + ("允许" if allow else "禁止") + "该电脑的远程命令权限。",
                            parent=self)
        self.refresh()

    def _remote_command(self) -> None:
        client_id = self._selected_client_id()
        if client_id is None:
            return
        command = simpledialog.askstring(
            "远程命令",
            "输入要在这台电脑上执行的命令（在它的用户权限下运行）：\n"
            "例如：whoami   或   dir C:\\   或   systeminfo",
            parent=self,
        )
        if not command:
            return
        try:
            result = self._request(f"/api/v1/clients/{client_id}/commands",
                                   {"action": "exec", "note": command}, method="POST")
        except Exception as error:
            messagebox.showerror("下发失败", str(error), parent=self)
            return
        command_id = result["command_id"]
        messagebox.showinfo("已下发", "命令已下发，等待执行结果…", parent=self)
        for _ in range(20):
            time.sleep(1)
            try:
                audit = self._request("/api/v1/audit").get("commands", [])
                record = next((item for item in audit
                               if item.get("command_id") == command_id), None)
                if record and record.get("status") in ("done", "failed"):
                    label = "执行成功" if record["status"] == "done" else "执行失败"
                    messagebox.showinfo(
                        label,
                        f"命令：{command}\n\n返回：\n{record.get('result') or '（无输出）'}",
                        parent=self,
                    )
                    return
            except Exception:
                break
        messagebox.showinfo("执行中", "命令已下发，结果可在「操作记录」中查看。", parent=self)

    def _app_action(self, action: str, label: str) -> None:
        """远程启动/关闭/查看子机树剪程序，并回读执行结果。"""
        client_id = self._selected_client_id()
        if client_id is None:
            return
        try:
            result = self._request(f"/api/v1/clients/{client_id}/commands",
                                   {"action": action, "note": f"来自远程管理窗口：{label}"},
                                   method="POST")
        except Exception as error:
            messagebox.showerror("下发失败", str(error), parent=self)
            return
        command_id = result["command_id"]
        self.status_var.set(f"已下发「{label}」，等待子机执行…")
        for _ in range(25):
            time.sleep(1)
            try:
                audit = self._request("/api/v1/audit").get("commands", [])
                record = next((item for item in audit
                               if item.get("command_id") == command_id), None)
                if record and record.get("status") in ("done", "failed"):
                    self.status_var.set("")
                    label_ok = "执行成功" if record["status"] == "done" else "执行失败"
                    messagebox.showinfo(
                        label_ok,
                        f"子机返回：\n{record.get('result') or '（无输出）'}",
                        parent=self,
                    )
                    return
            except Exception:
                break
        self.status_var.set("")
        messagebox.showinfo("执行中", "已下发，结果可在「操作记录」中查看。", parent=self)

    def _open_packages(self) -> None:
        from treecut.ui.update_packages_dialog import UpdatePackagesDialog
        try:
            UpdatePackagesDialog(self, self.paths, self.token, self.master_key)
        except Exception as error:
            messagebox.showerror("无法打开更新包库", str(error), parent=self)

    def _open_blacklist(self) -> None:
        from treecut.ui.ip_blacklist_dialog import IpBlacklistDialog
        try:
            IpBlacklistDialog(self, self.token, self.master_key)
        except Exception as error:
            messagebox.showerror("无法打开 IP 黑名单", str(error), parent=self)
