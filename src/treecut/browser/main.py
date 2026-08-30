"""XHS Work Browser V0.1 — 启动流（§6/7/8/9/13/46）。

用法：
  python -m treecut.browser.main --workspace B007                     # 图形控制台 + 固定工作浏览器
  python -m treecut.browser.main --workspace B007 --headless          # 无窗口（供脚本/CI）
  python -m treecut.browser.main --workspace B007 --smoke             # 无 UI 自检：persistent profile 持久化 + 单 Tab
  python -m treecut.browser.main --workspace B007 --bind-account 昵称 # 首次登录后人工确认绑定（§9）

启动流：加载 Profile（存在复用/不存在创建）→ Profile Lock（§33/34）→
TreeCut Local health（§46）→ Persistent Browser Context → Single Work Tab → 控制台。
"""
from __future__ import annotations

import argparse
import logging
import sys

from treecut.browser.account_detector import AccountDetector
from treecut.browser.checkpoint_store import CheckpointStore
from treecut.browser.config import load_config
from treecut.browser.local_bridge import CONNECTED, LocalBridge
from treecut.browser.profile_manager import ProfileManager
from treecut.browser.retry_policy import BoundedRetry
from treecut.browser.session_detector import SESSION_UNKNOWN, SessionDetector
from treecut.browser.task_engine import TaskEngine
from treecut.browser.workspace_manager import WorkspaceManager
from treecut.platform.paths import RuntimePaths

log = logging.getLogger("treecut.browser")


class BrowserRuntime:
    """V0.1 运行时容器：Workspace / Profile / Bridge / Store / Engine / Detectors。"""

    def __init__(self, config, paths: RuntimePaths | None = None):
        self.config = config
        self.paths = paths or RuntimePaths.discover()
        self.workspace = WorkspaceManager(config, paths=self.paths)
        self.profile = ProfileManager(config, self.workspace)
        self.bridge = LocalBridge(config.treecut_local_url,
                                  timeout_seconds=config.treecut_health_timeout_seconds)
        self.checkpoint_store = CheckpointStore(self.paths.data_root / "browser" / "checkpoints")
        self.retry = BoundedRetry(max_attempts=config.retry_max_attempts,
                                  delay_seconds=config.retry_delay_seconds)
        self.engine = TaskEngine(self.checkpoint_store, self.retry,
                                 workspace_id=config.workspace_id)
        self.account_detector = AccountDetector(self.workspace)
        self.session_detector = SessionDetector(config)
        self.work_tab = None
        self._context = None

    # ---- §17/18/46 Local Bridge ----
    def local_status(self) -> str:
        health = self.bridge.health()
        log.info("TREECUT_%s", health.status)
        return health.status

    # ---- §6/13/15 固定工作浏览器 ----
    def start_browser(self, headless: bool | None = None) -> None:
        self.workspace.acquire_lock()  # PROFILE_LOCKED → RuntimeError
        context, _browser = self.profile.launch_persistent_context(headless=headless)
        self._context = context
        self.work_tab = context.pages[0] if context.pages else context.new_page()
        if self.work_tab.url == "":
            self.work_tab.goto("about:blank")

    def ensure_work_tab(self):
        """Single Work Tab 复用；tab 崩溃则重建（§25 work tab crash 自动恢复）。"""
        if self._context is None:
            raise RuntimeError("browser not started")
        if self.work_tab is None or self.work_tab.is_closed():
            self.work_tab = self._context.new_page()
            self.work_tab.goto("about:blank")
        return self.work_tab

    def navigate(self, url: str) -> None:
        tab = self.ensure_work_tab()
        tab.goto(url, timeout=60000)

    # ---- §8/9/10 账号 ----
    def check_account(self) -> tuple[str, str | None]:
        tab = self.ensure_work_tab()
        detected = self.account_detector.detect(tab)
        if detected is None:
            return "ACCOUNT_IDENTITY_UNKNOWN", "页面未检测到账号（可能未登录或结构未命中）"
        status, reason = self.account_detector.gate(detected)
        if status == "ACCOUNT_IDENTITY_UNKNOWN" and self.workspace.load_binding() is None:
            return status, (f"首次检测到账号：{detected.platform_account_name} —— "
                            "请人工确认后执行 --bind-account 完成绑定（不保存任何凭证）")
        return status, reason

    def bind_account(self, name: str, xhs_id: str | None = None) -> str:
        """§9 人工确认后的绑定（CLI 传入用户确认的账号名）。"""
        tab = self.ensure_work_tab()
        detected = self.account_detector.detect(tab) or self.account_detector.detect(
            _PageStub(name=name, xhs_id=xhs_id))
        if not detected:
            return "检测不到账号，无法绑定"
        self.account_detector.bind(detected)
        return f"已绑定 {detected.platform_account_name} -> {self.config.workspace_id}"

    # ---- §11/12 登录检测 ----
    def recheck_login(self) -> dict:
        out = {}
        for kind, url in (("creator", self.config.creator_home_url),
                          ("spotlight", self.config.spotlight_home_url)):
            try:
                self.navigate(url)
                result = self.session_detector.check(self.work_tab, kind)
                out[kind] = result.status
                log.info("%s SESSION_%s", kind.upper(), result.status)
            except Exception:
                out[kind] = SESSION_UNKNOWN
        return out

    # ---- §19/21 任务 ----
    def resume_task(self) -> str:
        if self.engine.resume_unfinished():
            result = self.engine.run()
            return f"resumed -> {result.state} @{result.step}"
        return "无未完成任务"

    def close(self) -> None:
        self.profile.close()
        self.workspace.release_lock()


class _PageStub:
    """--bind-account 无页面时的最小桩（不访问网络）。"""

    def __init__(self, name: str, xhs_id: str | None):
        self._name = name
        self._xhs_id = xhs_id or ""

    @property
    def url(self) -> str:
        return "cli://bind"

    def text_content(self, _selector: str) -> str | None:
        return self._name

    def content(self) -> str:
        return f"小红书号: {self._xhs_id}" if self._xhs_id else ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="treecut-xhs-browser",
                                     description="TreeCut XHS Work Browser V0.1")
    parser.add_argument("--workspace", default="B007")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--profile-root", default="", help="覆盖 Profile 根目录（测试用）")
    parser.add_argument("--treecut-url", default="", help="覆盖 TreeCut Local URL")
    parser.add_argument("--bind-account", default="", help="人工确认账号名后绑定（§9）")
    parser.add_argument("--smoke", action="store_true", help="无 UI 自检模式")
    return parser


def run_smoke(config) -> int:
    """§43 Test A 机制自检 + §15/16/32 单 Tab + §25 tab 崩溃重建（headless Edge）。

    用本地临时 HTTP 页面承载 localStorage（about:blank 无 origin 会被拒），
    不访问真实站点，真实登录留给人工验收。
    """
    import http.server
    import threading

    from treecut.browser.policies import utcnow_iso

    class _PageHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = b"<html><body>xhs smoke</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: object) -> None:
            return

    page_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    page_port = page_server.server_address[1]
    page_thread = threading.Thread(target=page_server.serve_forever, daemon=True)
    page_thread.start()
    page_url = f"http://127.0.0.1:{page_port}/"

    runtime = BrowserRuntime(config)
    runtime.workspace.acquire_lock()
    try:
        context, _ = runtime.profile.launch_persistent_context(headless=True)
        runtime._context = context
        runtime.work_tab = context.pages[0]
        key = "xhs_work_browser_smoke"
        value = "persisted_" + utcnow_iso()
        runtime.work_tab.goto(page_url)
        runtime.work_tab.evaluate(f"localStorage.setItem('{key}', '{value}')")

        # 单 Tab 复用：多次导航不新增 Tab（§15/16/32）
        runtime.navigate(page_url)
        runtime.navigate(page_url)
        runtime.navigate(page_url)
        tabs_reuse = len(context.pages) == 1

        # Work Tab 崩溃自动重建（§25），仍只 1 个 Tab
        runtime.work_tab.close()
        tab2 = runtime.ensure_work_tab()
        tab2.goto(page_url)
        tabs_recreate = len(context.pages) == 1 and not tab2.is_closed()

        runtime.profile.close()  # 关闭（模拟退出）

        context2, _ = runtime.profile.launch_persistent_context(headless=True)
        page2 = context2.pages[0]
        page2.goto(page_url)
        readback = page2.evaluate(f"localStorage.getItem('{key}')")
        tabs_restart = len(context2.pages) == 1
        runtime.profile.close()

        results = {
            "persistent_profile": readback == value,
            "single_tab_reuse": tabs_reuse,
            "tab_crash_recreate": tabs_recreate,
            "single_tab_after_restart": tabs_restart,
        }
        ok = all(results.values())
        for name, passed in results.items():
            print(f"SMOKE {name}={'PASS' if passed else 'FAIL'}")
        return 0 if ok else 1
    finally:
        page_server.shutdown()
        page_server.server_close()
        runtime.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")
    config = load_config()
    if args.workspace:
        config.workspace_id = args.workspace
    if args.profile_root:
        config.profile_root = args.profile_root
    if args.treecut_url:
        config.treecut_local_url = args.treecut_url
    config.validate()

    if args.smoke:
        return run_smoke(config)

    runtime = BrowserRuntime(config)
    try:
        runtime.workspace.acquire_lock()  # PROFILE_LOCKED → RuntimeError 并退出
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2

    if args.bind_account:
        print(runtime.bind_account(args.bind_account))
        runtime.close()
        return 0

    local = runtime.local_status()
    print(f"TreeCut Local: {local}")

    if not args.headless:
        try:
            runtime.start_browser(headless=False)
        except Exception as error:
            print(f"浏览器启动失败: {error}")
            runtime.close()
            return 3

    if args.headless:
        # 无 UI 模式：只验证启动链（Workspace/Lock/Bridge/Session 探测逻辑）
        print("startup chain OK: workspace, lock, bridge, detectors ready")
        runtime.close()
        return 0

    # ---- 极简控制台（§14） ----
    from treecut.browser.minimal_dashboard import MinimalDashboard

    def open_creator() -> None:
        runtime.navigate(config.creator_home_url)

    def open_spotlight() -> None:
        runtime.navigate(config.spotlight_home_url)

    def check_account() -> None:
        status, reason = runtime.check_account()
        print(f"Account: {status} {reason or ''}")
        runtime.workspace.workspace_status()

    def recheck_login() -> None:
        out = runtime.recheck_login()
        print(f"Login: creator={out.get('creator')} spotlight={out.get('spotlight')}")

    def resume_task() -> None:
        print(runtime.resume_task())

    def view_errors() -> None:
        print(runtime.engine.checkpoint_store.unfinished(config.workspace_id) or "无错误记录")

    dashboard = MinimalDashboard(
        runtime.workspace, runtime.checkpoint_store,
        callbacks={"on_open_creator": open_creator, "on_open_spotlight": open_spotlight,
                   "on_check_account": check_account, "on_recheck_login": recheck_login,
                   "on_resume_task": resume_task, "on_view_errors": view_errors},
    )
    dashboard.post_status(creator="UNKNOWN", spotlight="UNKNOWN",
                          account="UNKNOWN", treecut_local=local,
                          current_task="IDLE")
    try:
        dashboard.run()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
