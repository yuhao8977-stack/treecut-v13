"""Remote agent: reports status periodically and applies updates from the hub."""
from __future__ import annotations

import json
import base64
import ctypes
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from treecut.maintenance import collect_light_status
from treecut.remote.discovery import discover_hubs, fingerprint
from treecut.platform.paths import RuntimePaths
from treecut.remote.config import RemoteConfig
from treecut.remote.update_pack import apply_update, read_manifest


def standalone_agent_running(install_root: Path) -> bool:
    """True if a pythonw process with -m treecut.remote.agent_main is alive."""
    import subprocess
    try:
        probe = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
             "Where-Object { $_.CommandLine -match 'treecut.remote.agent_main' } | "
             "Measure-Object).Count"],
            capture_output=True, timeout=20,
        )
        return probe.stdout.decode("utf-8", errors="replace").strip() not in ("", "0")
    except Exception:
        return False


def launch_standalone_agent(install_root: Path) -> None:
    """Start the standalone background agent (hidden pythonw) if the launcher exists."""
    import subprocess
    root = Path(install_root).resolve()
    pythonw = root / "runtime" / "pythonw.exe"
    if not pythonw.is_file():
        return
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    subprocess.Popen(
        [str(pythonw), "-m", "treecut.remote.agent_main"],
        cwd=str(root), env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class RemoteAgent:
    def __init__(self, paths: RuntimePaths, config: RemoteConfig, logger=None):
        self.paths = paths
        self.config = config
        self._logger = logger
        self._state_path = paths.data_root / "config" / "remote_applied.json"
        self._lock_path = paths.data_root / "locks" / "remote_agent.lock"
        self._policy_path = paths.data_root / "config" / "remote_policy.json"
        self._wake_path = paths.data_root / "config" / "remote_wake.flag"
        self._caps: dict | None = None
        self._base_url = config.hub_url.rstrip("/")

    def _log(self, message: str) -> None:
        if self._logger:
            self._logger(message)

    def _url(self, path: str) -> str:
        return self._base_url + path

    def _candidate_urls(self) -> list[str]:
        urls: list[str] = []
        if self.config.hub_url:
            urls.append(self.config.hub_url.rstrip("/"))
        if self.config.auto_discover:
            try:
                expected = fingerprint(self.config.token)
                for ip, port in discover_hubs(timeout=2.0, expected_fp=expected):
                    candidate = f"http://{ip}:{port}"
                    if candidate not in urls:
                        urls.append(candidate)
            except Exception:
                pass
        return urls

    def _rotate_hub(self) -> None:
        candidates = self._candidate_urls()
        if not candidates:
            return
        current = self._base_url
        if current in candidates:
            index = candidates.index(current)
            self._base_url = candidates[(index + 1) % len(candidates)]
        else:
            self._base_url = candidates[0]

    def _acquire_lock(self) -> bool:
        """Only one agent may run per installation; reclaim stale locks."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            return True
        except FileExistsError:
            try:
                pid = int(self._lock_path.read_text(encoding="ascii").strip() or "0")
            except (OSError, ValueError):
                pid = 0
            alive = False
            if pid > 0:
                try:
                    import psutil
                    alive = psutil.pid_exists(pid)
                    if alive:
                        try:
                            process = psutil.Process(pid)
                            command = " ".join(process.cmdline() or [])
                            # PID 被其他程序复用不算占用：只有树剪代理进程才算。
                            alive = ("treecut" in command
                                     and "agent_main" in command)
                        except Exception:
                            alive = False
                except Exception:
                    alive = True
            if not alive:
                try:
                    self._lock_path.unlink()
                except OSError:
                    return False
                return self._acquire_lock()
            return False

    def _release_lock(self) -> None:
        try:
            self._lock_path.unlink()
        except OSError:
            pass

    def _prevent_sleep(self, active: bool) -> None:
        """Keep the machine awake while the remote assistant is running."""
        if os.name != "nt":
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                0x80000000 | (0x00000001 if active else 0)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            )
        except Exception:
            pass

    def _state(self) -> dict:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return {"applied": []}

    def _mark_applied(self, update_id: str) -> None:
        state = self._state()
        applied = list(state.get("applied", []))
        if update_id not in applied:
            applied.append(update_id)
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps({"applied": applied}, ensure_ascii=False), encoding="utf-8",
        )

    def _request_json(self, path: str, payload: dict | None = None,
                      method: str = "GET", timeout: float = 30) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self._url(path), data=data, method=method)
        request.add_header("Content-Type", "application/json; charset=utf-8")
        request.add_header("X-TreeCut-Token", self.config.token)
        # treecut_no_proxy_patch: never route LAN hub traffic through a proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _download(self, path: str, target: Path, timeout: float = 120) -> None:
        request = urllib.request.Request(self._url(path), method="GET")
        request.add_header("X-TreeCut-Token", self.config.token)
        # treecut_no_proxy_patch: downloads also go direct.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response, open(target, "wb") as out:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        parts = []
        for chunk in str(version).split("."):
            digits = "".join(char for char in chunk if char.isdigit())
            parts.append(int(digits) if digits else 0)
        return tuple(parts)

    def _read_policy(self) -> dict:
        try:
            return json.loads(self._policy_path.read_text(encoding="utf-8"))
        except Exception:
            return {"disabled": False, "blacklisted": False, "hub_reachable": False}

    def _policy_with(self, **updates) -> dict:
        policy = self._read_policy()
        policy.update(updates)
        return policy

    def _write_policy(self, policy: dict) -> None:
        self._policy_path.parent.mkdir(parents=True, exist_ok=True)
        self._policy_path.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")

    def _error_body(self, error) -> str:
        try:
            body = error.read().decode("utf-8", errors="replace")
            return json.loads(body).get("detail", body)[:300]
        except Exception:
            return str(error)[:300]

    def _capabilities_summary(self) -> dict:
        """Probe hardware once per process so the hub can see CPU/GPU/RAM.

        treecut_caps_timeout_patch: bounded to 15s so slow CPU machines
        (torch import / model inspection) can never hang the report loop.
        """
        if self._caps is None:
            import threading
            probe_result: dict = {}
            def _probe() -> None:
                try:
                    from treecut.platform.capabilities import detect_capabilities
                    probe_result.update(detect_capabilities(self.paths).to_dict())
                except Exception as error:
                    probe_result["error"] = f"{type(error).__name__}: {error}"
            thread = threading.Thread(target=_probe, daemon=True)
            thread.start()
            thread.join(timeout=15)
            if thread.is_alive():
                self._caps = {"error": "capabilities timeout",
                              "cpu_threads": (os.cpu_count() or 1)}
            else:
                self._caps = probe_result or {"error": "capabilities empty"}
        return self._caps

    def _execute_command(self, action: str, note: str = "") -> tuple[bool, str]:
        if action in ("disable", "enable"):
            self._write_policy(self._policy_with(disabled=(action == "disable")))
            return True, "已" + ("禁用" if action == "disable" else "启用")
        if action in ("blacklist", "unblacklist"):
            self._write_policy(self._policy_with(blacklisted=(action == "blacklist")))
            return True, "已" + ("拉黑" if action == "blacklist" else "解除拉黑")
        if action == "wipe":
            try:
                from treecut.maintenance import wipe_user_data
                removed = wipe_user_data(self.paths)
                return True, f"已清空用户数据（{len(removed)} 项）"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "uninstall":
            try:
                from treecut.maintenance import wipe_user_data
                wipe_user_data(self.paths)
                self._schedule_uninstall()
                return True, "已清空数据并安排卸载，软件即将退出"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "exec":
            if not note.strip():
                return False, "远程命令为空"
            process = None
            try:
                creation = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                            | getattr(subprocess, "CREATE_NO_WINDOW", 0))
                process = subprocess.Popen(
                    note, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=str(self.paths.install_root), creationflags=creation,
                )
                stdout, stderr = process.communicate(timeout=180)
                raw = (stdout or b"") + (stderr or b"")
                try:
                    output = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    output = raw.decode("gbk", errors="replace").strip()
                return process.returncode == 0, output[-19000:] or f"退出码 {process.returncode}"
            except subprocess.TimeoutExpired:
                if process is not None and process.poll() is None:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                            capture_output=True, timeout=15,
                        )
                    except Exception:
                        pass
                return False, "命令执行超时（180 秒），已强制终止整个进程树"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "list_dir":
            try:
                target = self.paths.install_root / (note.strip() or ".")
                entries = sorted(os.listdir(target))
                return True, "\n".join(entries[-300:])
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "produce":
            try:
                payload = json.loads(note or "{}")
                selling = str(payload.get("selling_points", "")).strip()
                narration = str(payload.get("narration", "")).strip()
                if not selling or not narration:
                    return False, "制作任务缺少卖点或文案"
                python = self.paths.install_root / "runtime" / "python.exe"
                creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                process = subprocess.Popen(
                    [str(python), "-c",
                     "import sys,json; from treecut.remote.remote_produce import run_remote_production; "
                     "print(json.dumps(run_remote_production(json.loads(sys.argv[1])), ensure_ascii=False))",
                     note],
                    cwd=str(self.paths.install_root),
                    creationflags=creation,
                )
                return True, f"制作任务已在后台启动（pid {process.pid}），子机页面会实时显示进度"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "restart":
            try:
                self._schedule_restart()
                return True, "重启指令已安排：软件将在数秒后自动重启并加载最新代码"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "ship_file":
            try:
                note_parts = note.split("|", 1)
                target = Path(note_parts[0].strip())
                offset = int(note_parts[1]) if len(note_parts) > 1 else 0
                if not target.is_file():
                    return False, f"文件不存在: {target}"
                chunk_size = 1_400_000
                with open(target, "rb") as stream:
                    stream.seek(offset)
                    chunk = stream.read(chunk_size)
                if not chunk:
                    return False, f"偏移越界: {offset}"
                data = base64.b64encode(chunk).decode("ascii")
                return True, f"BASE64:{data}|{offset + len(chunk)}"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "app_status":
            try:
                command = (
                    "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
                    "Where-Object { $_.CommandLine -match 'treecut' } | "
                    "ForEach-Object { Write-Output ($_.ProcessId.ToString() + '|' + $_.CommandLine) }"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    capture_output=True, timeout=30,
                )
                lines = [line for line in result.stdout.decode("utf-8", errors="replace").splitlines()
                         if line.strip()]
                desktop = any("-m treecut.desktop" in line for line in lines)
                watchdog = any("-m treecut.watchdog" in line for line in lines)
                agent = any("-m treecut.remote.agent_main" in line for line in lines)
                summary = (
                    f"桌面程序={'运行中' if desktop else '未运行'} | "
                    f"看门狗={'运行中' if watchdog else '未运行'} | "
                    f"独立代理={'运行中' if agent else '未运行'}"
                )
                return True, summary + ("\n" + "\n".join(lines[-8:]) if lines else "")
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "start_app":
            try:
                launcher = self.paths.install_root / "启动树剪v13.cmd"
                if not launcher.is_file():
                    return False, f"启动脚本不存在: {launcher}"
                subprocess.Popen(
                    ["cmd", "/c", "start", "", str(launcher)],
                    cwd=str(self.paths.install_root),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return True, "已启动树剪桌面程序"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "stop_app":
            try:
                command = (
                    "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
                    "Where-Object { $_.CommandLine -match 'treecut\\.(desktop|watchdog)' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    capture_output=True, timeout=30,
                )
                return True, "已关闭树剪桌面程序（独立代理保持运行）"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        if action == "send_file":
            try:
                target = Path(note.strip())
                if not target.is_file():
                    return False, f"文件不存在: {target}"
                if target.stat().st_size > 12000:
                    return False, "文件超过 12KB，请先压缩或截断后再发送"
                data = base64.b64encode(target.read_bytes()).decode("ascii")
                return True, f"BASE64:{data}"
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        return False, f"未知命令：{action}"

    def _schedule_restart(self) -> None:
        """Restart the watchdog+desktop chain via a detached helper, never inline."""
        import subprocess
        batch = self.paths.temp / "treecut_restart.bat"
        root = self.paths.install_root.resolve()
        pythonw = root / "runtime" / "pythonw.exe"
        script = (
            "@echo off\r\n"
            "timeout /t 3 /nobreak >nul\r\n"
            "powershell -NoProfile -Command \"Get-CimInstance Win32_Process -Filter "
            "'Name=pythonw.exe' | Where-Object { $_.CommandLine -match 'treecut' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }\" >nul 2>&1\r\n"
            f"cd /d \"{root}\"\r\n"
            "set PYTHONPATH=src\r\n"
            f"start \"\" \"{pythonw}\" -m treecut.watchdog\r\n"
        )
        try:
            batch.write_text(script, encoding="ascii")
        except UnicodeEncodeError:
            batch.write_text(script, encoding="gbk")
        subprocess.Popen(
            ["cmd", "/c", str(batch)],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0),
        )

    def _schedule_uninstall(self) -> None:
        """Delete the install folder a few seconds after this process exits."""
        import subprocess
        batch = self.paths.temp / "treecut_uninstall.bat"
        root = self.paths.install_root.resolve()
        batch.write_text(
            "@echo off\r\n"
            "cd /d \"%TEMP%\"\r\n"
            "timeout /t 3 /nobreak >nul\r\n"
            f"taskkill /F /PID {os.getpid()} >nul 2>&1\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f"rd /s /q \"{root}\" >nul 2>&1\r\n"
            "del /q \"%~f0\" >nul 2>&1\r\n",
            encoding="ascii",
        )
        subprocess.Popen(
            ["cmd", "/c", str(batch)],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _process_commands(self) -> list[dict]:
        try:
            response = self._request_json(
                f"/api/v1/clients/{self.config.client_id}/commands")
        except urllib.error.HTTPError as error:
            if error.code == 403:
                self._write_policy(self._policy_with(
                    blacklisted=True, disabled=True, hub_reachable=True))
            return [{"ok": False, "error": f"HTTP {error.code}: {self._error_body(error)}"}]
        except Exception as error:
            return [{"ok": False, "error": f"{type(error).__name__}: {error}"}]
        policy = response.get("policy") or {}
        if policy.get("blacklisted"):
            self._write_policy(self._policy_with(
                blacklisted=True, disabled=True, hub_reachable=True))
        results: list[dict] = []
        for command in response.get("commands", []):
            action = str(command.get("action", ""))
            command_id = str(command.get("command_id", ""))
            note = str(command.get("note", ""))
            if action in {"exec", "list_dir", "produce", "send_file"} and not policy.get("allow_exec"):
                ok, result = False, "未开启远程操作权限"
            else:
                ok, result = self._execute_command(action, note)
            results.append({"action": action, "command_id": command_id, "ok": ok, "result": result})
            try:
                self._request_json(
                    f"/api/v1/clients/{self.config.client_id}/commands/{command_id}/result",
                    {"ok": ok, "result": result}, method="POST",
                )
            except Exception as error:
                self._log(f"上报命令结果失败：{error}")
        return results

    def poll_once(self) -> dict:
        """One status-report and update-check cycle."""
        report = collect_light_status(self.paths)
        report["capabilities"] = self._capabilities_summary()
        try:
            response = self._request_json("/api/v1/status", {
                "client_id": self.config.client_id,
                "version": report.get("treecut_version", ""),
                "report": report,
            }, method="POST")
        except urllib.error.HTTPError as error:
            reason = self._error_body(error)
            if error.code == 403:
                self._write_policy(self._policy_with(
                    blacklisted=True, disabled=True, hub_reachable=True))
                return {"ok": False, "step": "policy", "error": f"被管理端拒绝：{reason}"}
            return {"ok": False, "step": "status", "error": f"HTTP {error.code}: {reason}"}
        except Exception as error:
            self._rotate_hub()
            self._write_policy(self._policy_with(hub_reachable=False))
            return {"ok": False, "step": "status", "error": f"{type(error).__name__}: {error}"}

        min_version = response.get("min_version", "")
        blocked_reason = response.get("blocked_reason", "")
        min_version_ok = not bool(min_version and blocked_reason)
        force = bool(response.get("force"))
        update_available = bool(response.get("update_available"))
        update_id = str(response["update_id"]) if update_available else ""
        self._write_policy(self._policy_with(
            min_version=min_version,
            min_version_ok=min_version_ok,
            force_update_pending=bool(update_id and (force or not min_version_ok)),
            update_state="idle",
            hub_reachable=True,
        ))

        # 先安装更新，再执行命令：避免“重启/关闭”类命令打断正在进行的更新安装。
        update_detail = None
        if update_available and update_id not in self._state().get("applied", []):
            package = self.paths.temp / f"treecut_update_{update_id}.zip"
            try:
                self._write_policy(self._policy_with(update_state="downloading"))
                self._download(f"/api/v1/updates/{update_id}/package", package, timeout=300)
                manifest = read_manifest(package)
                installed = self._version_key(report.get("treecut_version", ""))
                if installed and self._version_key(manifest.get("version", "")) < installed:
                    self._mark_applied(update_id)
                    self._write_policy(self._policy_with(
                        force_update_pending=False, update_state="idle"))
                    update_detail = {"ok": True, "skipped": "版本不高于当前，已跳过"}
                else:
                    self._write_policy(self._policy_with(update_state="applying"))
                    python = self.paths.install_root / "runtime" / "python.exe"
                    smoke = [
                        str(python), "-c",
                        "import treecut.main, treecut.desktop, treecut.api; print('ok')",
                    ]
                    env = dict(os.environ)
                    env["PYTHONPATH"] = str(self.paths.install_root / "src")
                    env["TREECUT_DATA_ROOT"] = str(self.paths.data_root)
                    env["TREECUT_MODEL_ROOT"] = str(self.paths.models)
                    result = apply_update(
                        self.paths.install_root, package, smoke_command=smoke, env=env,
                    )
                    if result.get("ok"):
                        self._mark_applied(update_id)
                        self._write_policy(self._policy_with(
                            force_update_pending=False, update_state="idle"))
                    else:
                        self._write_policy(self._policy_with(update_state="failed"))
                    update_detail = result
            except Exception as error:
                update_detail = {"ok": False, "error": f"{type(error).__name__}: {error}"}
            finally:
                try:
                    package.unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                self._request_json(
                    f"/api/v1/clients/{self.config.client_id}/update-result",
                    {
                        "update_id": update_id,
                        "ok": bool(update_detail.get("ok")),
                        "error": update_detail.get("error", ""),
                        "version": update_detail.get("version", ""),
                    },
                    method="POST",
                )
            except Exception as error:
                self._log(f"上报更新结果失败：{error}")

        command_results = self._process_commands()
        if any(item.get("action") == "uninstall" and item.get("ok") for item in command_results):
            self._write_policy(self._policy_with(update_state="uninstall_scheduled"))
            return {"ok": True, "step": "commands", "commands": command_results,
                    "uninstall_scheduled": True}
        if update_detail is not None:
            return {"ok": bool(update_detail.get("ok")), "step": "update",
                    "update": update_id, "detail": update_detail,
                    "commands": command_results}
        return {"ok": True, "step": "status", "update": None, "commands": command_results}

    def run(self, stop=None) -> None:
        """Report status and apply updates until the stop flag is set."""
        if not self._acquire_lock():
            self._log("另一个远程助手已在运行（桌面或命令行），本实例退出。")
            return
        self._log("远程助手已启动")
        self._prevent_sleep(True)
        try:
            while not (stop and stop.is_set()):
                try:
                    outcome = self.poll_once()
                except Exception as error:
                    self._log(f"轮询异常（已自动继续）: {type(error).__name__}: {error}")
                    outcome = {"ok": False, "step": "crash", "error": str(error)}
                if not outcome.get("ok"):
                    self._log(f"本轮未成功：{outcome.get('error')}")
                elif outcome.get("step") == "update":
                    self._log(f"更新处理完成：{outcome.get('detail')}")
                if outcome.get("uninstall_scheduled"):
                    self._log("已执行卸载安排，本机即将退出。")
                    return
                deadline = time.time() + max(15, self.config.interval_seconds)
                while time.time() < deadline:
                    if stop and stop.is_set():
                        return
                    if self._wake_path.exists():
                        try:
                            self._wake_path.unlink()
                        except OSError:
                            pass
                        break
                    time.sleep(1)
        finally:
            self._prevent_sleep(False)
            self._release_lock()

    def run_once(self) -> dict:
        """Report and check updates once; respects the single-instance lock."""
        if not self._acquire_lock():
            return {"ok": False, "step": "locked", "error": "另一个远程助手正在运行"}
        try:
            try:
                return self.poll_once()
            except Exception as error:
                return {"ok": False, "step": "crash",
                        "error": f"{type(error).__name__}: {error}"}
        finally:
            self._release_lock()
