"""TreeCut XHS Work Browser V0.1.1 — 启动流（三固定 Tab + Single Worker）。

用法：
  python -m treecut.browser.main --workspace B007                       # 图形控制台 + 3 固定功能 Tab
  python -m treecut.browser.main --workspace B007 --smoke               # headless 自检（3 Tab/持久化/reconcile/重建）
  python -m treecut.browser.main --workspace B007 --bind-account 昵称   # §9 Creator 主身份绑定（人工确认）
  python -m treecut.browser.main --workspace B007 --bind-spotlight "广告账户ID|名称"  # §10 聚光绑定
  python -m treecut.browser.main --workspace B007 --confirm-frontend 昵称           # §11 前台绑定确认

启动流：加载 Profile → Profile Lock → TreeCut Local health → Persistent Context →
3 Fixed Functional Tabs（Creator/Spotlight/Frontend）→ 控制台。
V0.1.1 不抓任何业务数据；【同步数据】【恢复训练媒体】为占位（NOT_IMPLEMENTED）。
"""
from __future__ import annotations

import argparse
import logging
import sys

from treecut.browser.account_detector import (
    CreatorIdentityDetector,
    FrontendIdentityDetector,
    SpotlightIdentityDetector,
)
from treecut.browser.checkpoint_store import CheckpointStore
from treecut.browser.config import load_config
from treecut.browser.local_bridge import LocalBridge
from treecut.browser.profile_manager import ProfileManager
from treecut.browser.retry_policy import BoundedRetry
from treecut.browser.session_detector import SESSION_UNKNOWN, SessionDetector
from treecut.browser.tab_manager import TabManager
from treecut.browser.task_engine import TaskEngine
from treecut.browser.workspace_manager import WorkspaceManager
from treecut.platform.paths import RuntimePaths

log = logging.getLogger("treecut.browser")


class BrowserRuntime:
    """V0.1.1 运行时容器：Workspace / Profile / Tabs / Bridge / Store / Engine / Detectors。"""

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
        self.session_detector = SessionDetector(config)
        self.creator_detector = CreatorIdentityDetector(self.workspace)
        self.spotlight_detector = SpotlightIdentityDetector(self.workspace)
        self.frontend_detector = FrontendIdentityDetector(self.workspace)
        self.tabs: TabManager | None = None
        self._context = None

    # ---- §17/18/46 Local Bridge ----
    def local_status(self) -> str:
        health = self.bridge.health()
        log.info("TREECUT_%s", health.status)
        return health.status

    # ---- §6/13 固定工作浏览器 + 3 固定 Tab ----
    def start_browser(self, headless: bool | None = None) -> None:
        self.workspace.acquire_lock()  # PROFILE_LOCKED → RuntimeError
        context, _browser = self.profile.launch_persistent_context(headless=headless)
        self._context = context
        self.tabs = TabManager(context, self.config)
        self.tabs.create_fixed_tabs()

    def ensure_tabs(self) -> TabManager:
        if self.tabs is None:
            raise RuntimeError("browser not started")
        return self.tabs

    # ---- §26 三站独立健康检查 ----
    def check_roles(self) -> dict:
        roles = {}
        for role, kind in (("CREATOR", "creator"), ("SPOTLIGHT", "spotlight"),
                           ("FRONTEND", "frontend")):
            tab = self.ensure_tabs().get(role)
            tab_alive = tab is not None and not tab.is_closed()
            session = SESSION_UNKNOWN
            identity = "UNKNOWN"
            account = "—"
            if tab_alive:
                try:
                    session = self.session_detector.check(tab, kind).status
                except Exception:
                    session = SESSION_UNKNOWN
                detector = {"CREATOR": self.creator_detector,
                            "SPOTLIGHT": self.spotlight_detector,
                            "FRONTEND": self.frontend_detector}[role]
                try:
                    detected = detector.detect(tab)
                    identity, _reason = detector.gate(detected)
                    account = detected.display_name if detected else "—"
                except Exception:
                    identity = "UNKNOWN"
            roles[role] = {"tab_alive": tab_alive, "session": session,
                           "identity": identity, "account": account}
            log.info("%s TAB_ALIVE=%s SESSION=%s IDENTITY=%s",
                     role, tab_alive, session, identity)
        return roles

    # ---- §10/11 绑定 ----
    def bind_creator(self, name: str) -> str:
        tab = self.ensure_tabs().get("CREATOR")
        detected = self.creator_detector.detect(tab) if tab else None
        if not detected:
            return "Creator 页面未检测到账号，无法绑定"
        self.creator_detector.bind(detected)
        return f"Creator 已绑定 {detected.display_name} (xhs_id={detected.primary_id}) -> {self.config.workspace_id}"

    def bind_spotlight(self, spec: str) -> str:
        """spec 格式：广告账户ID|名称（用户从聚光后台人工确认后传入）。"""
        if "|" in spec:
            ad_id, name = spec.split("|", 1)
        else:
            ad_id, name = spec, spec
        from treecut.browser.account_detector import RoleIdentity
        self.spotlight_detector.bind(RoleIdentity(role="spotlight",
                                                  primary_id=ad_id.strip(),
                                                  display_name=name.strip(),
                                                  source_page="cli:confirm"))
        return f"聚光广告账户已绑定 {name.strip()} ({ad_id.strip()}) -> {self.config.workspace_id}"

    def confirm_frontend(self, name: str) -> str:
        from treecut.browser.account_detector import RoleIdentity
        self.frontend_detector.confirm(RoleIdentity(role="frontend",
                                                    primary_id=name.strip(),
                                                    display_name=name.strip(),
                                                    source_page="cli:confirm"))
        return f"前台账号已确认绑定 {name.strip()} -> {self.config.workspace_id}"

    # ---- §19/21 任务（V0.1.1 仅 mock/续跑，无业务 Action） ----
    def resume_task(self) -> str:
        if self.engine.resume_unfinished():
            result = self.engine.run()
            return f"resumed -> {result.state} @{result.step}"
        return "无未完成任务"

    # ---- 占位（V0.1.1 不抓业务数据） ----
    def sync_data(self) -> str:
        return "NOT_IMPLEMENTED: 数据同步（Creator/Spotlight）留待 V0.2/V0.3"

    def recover_media(self) -> str:
        return "NOT_IMPLEMENTED: 训练媒体恢复留待 V0.6"

    def close(self) -> None:
        self.profile.close()
        self.workspace.release_lock()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="treecut-xhs-browser",
                                     description="TreeCut XHS Work Browser V0.1.1")
    parser.add_argument("--workspace", default="B007")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--profile-root", default="", help="覆盖 Profile 根目录（测试用）")
    parser.add_argument("--treecut-url", default="", help="覆盖 TreeCut Local URL")
    parser.add_argument("--bind-account", default="", help="Creator 主身份绑定（人工确认）")
    parser.add_argument("--bind-spotlight", default="", help="聚光广告账户绑定 广告ID|名称")
    parser.add_argument("--confirm-frontend", default="", help="前台账号绑定确认")
    parser.add_argument("--smoke", action="store_true", help="无 UI 自检模式")
    return parser


def run_smoke(config) -> int:
    """Test A 机制（三站持久化）+ §13-16 三 Tab + §14 reconcile + §25 重建（headless）。

    本地临时 HTTP 页面承载 localStorage；不访问真实站点，真实登录人工验收。
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
    threading.Thread(target=page_server.serve_forever, daemon=True).start()
    page_url = f"http://127.0.0.1:{page_port}/"

    # smoke 离线：三个固定 Tab 的导航目标指向本地页面服务器（不访问真实站点）
    config.creator_home_url = page_url
    config.spotlight_home_url = page_url
    config.frontend_home_url = page_url

    runtime = BrowserRuntime(config)
    runtime.workspace.acquire_lock()
    try:
        context, _ = runtime.profile.launch_persistent_context(headless=True)
        runtime._context = context
        runtime.tabs = TabManager(context, config)
        runtime.tabs.create_fixed_tabs()  # 3 个固定 Tab
        three_tabs = len(context.pages) == 3
        frontend = runtime.tabs.get("FRONTEND")
        frontend.evaluate("localStorage.setItem('v011_key', 'persisted_three_tab')")

        # §13：Frontend Tab 反复导航仍是同一 Tab（不为每条视频开新 Tab）
        for _ in range(3):
            runtime.tabs.get("FRONTEND").goto(page_url)
        reuse = len(context.pages) == 3

        # §14：3 固定 + 1 允许弹窗不动作；弹窗处理完关闭；再多空白页收束；用户页不盲目关闭
        popup = context.new_page()
        popup.goto("about:blank")
        result = runtime.tabs.reconcile()
        popup_allowed = result["actual"] == 4 and result["closed_extras"] == []
        popup.close()
        blank2 = context.new_page()  # 超限空白页
        user_page = context.new_page()
        user_page.goto(page_url + "user-like-page")  # 模拟用户页（非 blank、非我方）
        result2 = runtime.tabs.reconcile()
        reconcile_closed = result2["actual"] == 4 and \
            result2["closed_extras"] == ["blank-temp"] and result2["left_untouched"] == 1
        user_page.close()  # 收束测试结束，清理模拟用户页

        # §25：Frontend Tab 崩溃 → 重建，仍是 3 Tab
        frontend.close()
        runtime.tabs.rebuild("FRONTEND")
        rebuild = len(context.pages) == 3

        runtime.profile.close()  # 模拟退出

        context2, _ = runtime.profile.launch_persistent_context(headless=True)
        page2 = context2.pages[0]
        page2.goto(page_url)
        readback = page2.evaluate("localStorage.getItem('v011_key')")
        persist = readback == "persisted_three_tab"
        runtime.profile.close()

        results = {
            "three_fixed_tabs": three_tabs,
            "tab_reuse_no_new_tabs": reuse,
            "popup_allowed_within_limit": popup_allowed,
            "reconcile_closes_blank_extras": reconcile_closed,
            "tab_crash_rebuild": rebuild,
            "persistent_profile": persist,
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
        runtime.workspace.acquire_lock()
    except RuntimeError as error:
        print(f"PROFILE_LOCKED: {error}")
        return 2

    if args.bind_account or args.bind_spotlight or args.confirm_frontend:
        if args.bind_account:
            print(runtime.bind_creator(args.bind_account))
        if args.bind_spotlight:
            print(runtime.bind_spotlight(args.bind_spotlight))
        if args.confirm_frontend:
            print(runtime.confirm_frontend(args.confirm_frontend))
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
        print("startup chain OK: workspace, lock, bridge, detectors ready (3-tab UI off)")
        runtime.close()
        return 0

    from treecut.browser.minimal_dashboard import MinimalDashboard

    def check_status() -> None:
        roles = runtime.check_roles()
        for role, info in roles.items():
            log.info("%s -> session=%s identity=%s account=%s",
                     role, info["session"], info["identity"], info["account"])

    def safe_exit() -> None:
        log.info("SAFE_SHUTDOWN")
        runtime.close()

    def view_errors() -> None:
        unfinished = runtime.checkpoint_store.unfinished(config.workspace_id)
        print(runtime.engine.checkpoint_store.unfinished(config.workspace_id) or "无错误记录")

    dashboard = MinimalDashboard(
        runtime.workspace,
        callbacks={
            "on_sync_data": lambda: print(runtime.sync_data()),
            "on_recover_media": lambda: print(runtime.recover_media()),
            "on_resume_task": lambda: print(runtime.resume_task()),
            "on_view_errors": view_errors,
            "on_check_status": check_status,
            "on_safe_exit": safe_exit,
        },
    )
    dashboard.post_status(treecut_local=local, current_task="IDLE")
    try:
        dashboard.run()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
