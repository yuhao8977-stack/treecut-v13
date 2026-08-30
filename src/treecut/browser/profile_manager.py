"""XHS Work Browser V0.1.2 — Profile Manager（Persistent Profile + 无 --no-sandbox）。

V0.1.2 修订：Playwright launch_persistent_context 会向 Edge 注入 --no-sandbox
（真实验证：子进程命令行含该参数，Edge 顶部出现不受支持标志警告）。
改为：自启 Edge（user-data-dir 持久 Profile，参数完全可控，**不含 --no-sandbox**）
→ 读 DevToolsActivePort → playwright connect_over_cdp 接管。

Playwright 延迟导入：无 playwright 环境下（纯单元测试）不报错。
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from treecut.browser.config import XhsWorkBrowserConfig
from treecut.browser.errors import XhsWorkBrowserError
from treecut.browser.workspace_manager import WorkspaceManager


def _default_edge_paths() -> list[Path]:
    candidates = []
    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    for base in (pf86, pf):
        candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    return candidates


class ProfileManager:
    def __init__(self, config: XhsWorkBrowserConfig, workspace: WorkspaceManager):
        self.config = config
        self.workspace = workspace
        self._context = None
        self._playwright = None
        self._proc: subprocess.Popen | None = None
        self._edge_path: Path | None = None

    @property
    def user_data_dir(self) -> Path:
        return self.workspace.ensure_workspace()

    # ---- §33 健康检查 ----
    def check_health(self) -> dict:
        return self.workspace.profile_health()

    # ---- Edge 可执行文件定位 ----
    def resolve_edge(self) -> Path:
        if self._edge_path is not None:
            return self._edge_path
        candidates = _default_edge_paths()
        for path in candidates:
            if path.is_file():
                self._edge_path = path
                return path
        raise XhsWorkBrowserError(
            f"未找到 Edge（{candidates}），无法启动 Work Browser；"
            "可安装 Edge 或在配置指定 executable_path")

    # ---- 自启 Edge + CDP 接管（无 --no-sandbox） ----
    def launch_persistent_context(self, headless: bool | None = None):
        """启动持久 Profile Edge 并通过 CDP 连接。

        参数完全由本模块控制：--user-data-dir / --remote-debugging-port=0 /
        --no-first-run / --lang=zh-CN（+headless 时 --headless=new）。
        不传 --no-sandbox（V0.1.2 修复，Edge 顶部不再出现不受支持标志警告）。
        返回 (context, browser)；进程句柄内部保留，close() 时整树终止。
        """
        edge = self.resolve_edge()
        headless = self.config.headless if headless is None else headless
        self.workspace.ensure_workspace()
        profile = self.user_data_dir

        args = [str(edge), f"--user-data-dir={profile}",
                "--remote-debugging-port=0", "--no-first-run", "--lang=zh-CN"]
        if headless:
            args.append("--headless=new")

        stdout_log = profile / "edge_launch.stdout.log"
        stderr_log = profile / "edge_launch.stderr.log"
        port_file = profile / "DevToolsActivePort"
        # 清理上次运行残留（同 Profile 二次启动时旧端口文件会导致读到失效端口）
        try:
            port_file.unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass
        try:
            proc = subprocess.Popen(
                args,
                stdout=open(stdout_log, "w", encoding="utf-8", errors="replace"),
                stderr=open(stderr_log, "w", encoding="utf-8", errors="replace"),
            )
        except OSError as error:
            raise XhsWorkBrowserError(f"Edge 启动失败：{error}") from error
        self._proc = proc

        port = self._wait_devtools_port(profile, proc, stderr_log)
        if port is None:
            self._kill_proc()
            raise XhsWorkBrowserError(
                f"Edge DevTools 端口未就绪（rc={proc.poll()}），见 {stderr_log}")

        try:
            from playwright.sync_api import sync_playwright
            pw = sync_playwright().start()
            browser = self._connect_with_retry(pw, port)
        except Exception as error:
            self._kill_proc()
            raise XhsWorkBrowserError(f"CDP 连接 Edge 失败：{error}") from error

        self._playwright = pw
        self._context = browser.contexts[0] if browser.contexts else None
        if self._context is None:  # pragma: no cover
            self._kill_proc()
            raise XhsWorkBrowserError("CDP 默认 context 未就绪")
        return self._context, browser

    @staticmethod
    def _wait_devtools_port(profile: Path, proc, stderr_log: Path) -> int | None:
        port_file = profile / "DevToolsActivePort"
        deadline = time.time() + 30
        while time.time() < deadline:
            if proc.poll() is not None:
                return None
            try:
                text = port_file.read_text(encoding="utf-8", errors="replace").strip()
                port = int(text.splitlines()[0])
                return port
            except Exception:
                time.sleep(0.2)
        return None

    @staticmethod
    def _connect_with_retry(pw, port: int, tries: int = 10, delay: float = 0.3):
        """端口文件出现后监听可能尚未就绪 → 短暂重试连接。"""
        import socket
        last = None
        for _ in range(tries):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            except Exception as error:  # noqa: BLE001
                last = error
                time.sleep(delay)
        raise last  # type: ignore[misc]

    # ---- 关闭：先干净断开 CDP → 再整树终止进程 → 清理临时 debug 日志（§27） ----
    def close(self) -> None:
        # CDP 默认 context 关闭行为不可靠，且强杀进程会使 websocket 异常断开 →
        # 先 pw.stop() 干净断开，再 taskkill 整树，避免 playwright 后台任务残留（退出码 1）。
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # pragma: no cover
                pass
            self._playwright = None
        self._context = None
        self._kill_proc()
        self._cleanup_debug_logs()

    def _kill_proc(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self._proc.pid), "/T", "/F"],
                    capture_output=True, timeout=15)
            except Exception:  # pragma: no cover
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            # 等待进程树完全退出（否则同 Profile 立即重启会被 Edge SingletonLock 干扰）
            deadline = time.time() + 10
            while time.time() < deadline and self._proc.poll() is None:
                time.sleep(0.2)
        self._proc = None

    def _cleanup_debug_logs(self) -> None:
        profile = self.user_data_dir
        for name in ("edge_launch.stdout.log", "edge_launch.stderr.log"):
            try:
                (profile / name).unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                pass
