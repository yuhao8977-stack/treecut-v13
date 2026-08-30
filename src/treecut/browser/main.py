"""TreeCut XHS Work Browser V0.1.2 — 启动流（三固定 Tab + 自动状态检测 + 中文面板）。

用法：
  python -m treecut.browser.main --workspace B007            # 图形控制台（中文）+ 3 固定 Tab + 自动检测
  python -m treecut.browser.main --workspace B007 --smoke    # headless 自检（3 Tab/持久化/去重/收束/重建）

启动：Profile Lock → TreeCut Local health → 自启 Edge（无 --no-sandbox，CDP 接管）
→ 3 Fixed Tabs → 自动串行检测 Creator/Spotlight/Frontend 状态并显示到面板。
V0.1.2 不抓业务数据；同步数据/恢复训练视频按钮 disabled（下一阶段启用）。
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading

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
from treecut.browser.session_detector import SESSION_VALID, SESSION_UNKNOWN, SessionDetector
from treecut.browser.tab_manager import TabManager
from treecut.browser.task_engine import TaskEngine
from treecut.browser.workspace_manager import WorkspaceManager
from treecut.platform.paths import RuntimePaths

log = logging.getLogger("treecut.browser")

FRONTEND_VIEW_ZH = {SESSION_VALID: "正常 ✅", SESSION_UNKNOWN: "未知"}


class BrowserRuntime:
    """V0.1.2 运行时容器。"""

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
        log.info("TreeCut 本地服务：%s", "已连接" if health.connected else "未连接")
        return health.status

    # ---- 自启 Edge + 3 固定 Tab ----
    def start_browser(self, headless: bool | None = None) -> None:
        self.workspace.acquire_lock()  # PROFILE_LOCKED → RuntimeError
        log.info("工作区启动：%s", self.config.workspace_id)
        context, _browser = self.profile.launch_persistent_context(headless=headless)
        self._context = context
        self.tabs = TabManager(context, self.config)
        self.tabs.create_fixed_tabs()
        log.info("三固定页已建立（Creator / 聚光 / 前台）")

    def ensure_tabs(self) -> TabManager:
        if self.tabs is None:
            raise RuntimeError("browser not started")
        return self.tabs

    # ---- §4/§5 三站自动状态检测（Single Worker 串行，SPA 渲染有界重试） ----
    SPA_RETRY_TRIES = 4
    SPA_RETRY_DELAY = 1.2

    def check_roles(self) -> dict:
        """返回每站 {session, identity, account_name, account_id, binding}。

        XHS 为 SPA，启动后页面可能尚未渲染完 → 检测到 UNKNOWN 时做有界重试
        （最多 SPA_RETRY_TRIES 次，每次间隔 SPA_RETRY_DELAY），避免误报"状态未知"。
        """
        import time as _time
        binding = self.workspace.load_binding()
        roles = {}
        specs = [
            ("CREATOR", "creator", self.creator_detector, "creator_xhs_id"),
            ("SPOTLIGHT", "spotlight", self.spotlight_detector, "spotlight_ad_account_id"),
            ("FRONTEND", "frontend", self.frontend_detector, "frontend_user_id"),
        ]
        for role, kind, detector, bound_field in specs:
            tab = self.ensure_tabs().get(role)
            tab_alive = tab is not None and not tab.is_closed()
            session, identity, account_name, account_id = SESSION_UNKNOWN, "UNKNOWN", None, None
            if tab_alive:
                for attempt in range(self.SPA_RETRY_TRIES):
                    try:
                        session = self.session_detector.check(tab, kind).status
                    except Exception:
                        session = SESSION_UNKNOWN
                    try:
                        detected = detector.detect(tab)
                        identity, _reason = detector.gate(detected)
                        if detected:
                            account_name = detected.display_name
                            account_id = detected.primary_id
                    except Exception:
                        identity = "UNKNOWN"
                    # 已获得明确 Session 结论（已登录/需要登录/过期）→ 停止重试
                    # （身份可能因未绑定保持 UNKNOWN，属正常，不因此空转）
                    if session != SESSION_UNKNOWN:
                        break
                    if attempt < self.SPA_RETRY_TRIES - 1:
                        _time.sleep(self.SPA_RETRY_DELAY)
            binding_state = self._binding_state(role, identity, account_id,
                                                binding, bound_field)
            roles[role] = {
                "tab_alive": tab_alive, "session": session, "identity": identity,
                "account_name": account_name, "account_id": account_id,
                "binding": binding_state,
            }
            log.info("%s 登录状态=%s 身份=%s 绑定=%s",
                     role, session, identity, binding_state)
        return roles

    @staticmethod
    def _binding_state(role, identity, account_id, binding, bound_field) -> str:
        if role == "FRONTEND":
            return "OPTIONAL"  # §10 前台绑定可选，不作 B007 硬性要求
        bound = bool(binding and getattr(binding, bound_field, ""))
        if not bound:
            return "PENDING" if account_id else "NONE"
        if identity == "ACCOUNT_IDENTITY_VALID":
            return "BOUND"
        if identity == "ACCOUNT_IDENTITY_MISMATCH":
            return "MISMATCH"
        return "NONE"

    # ---- 绑定（面板按钮，非 CLI） ----
    def bind_creator(self) -> str:
        tab = self.ensure_tabs().get("CREATOR")
        detected = self.creator_detector.detect(tab) if tab else None
        if not detected:
            log.info("未检测到 Creator 账号，无法绑定")
            return "未检测到 Creator 账号"
        self.creator_detector.bind(detected)
        msg = f"Creator 已绑定：{detected.display_name}（小红书号 {detected.primary_id}）→ {self.config.workspace_id}"
        log.info(msg)
        return msg

    def bind_spotlight(self) -> str:
        tab = self.ensure_tabs().get("SPOTLIGHT")
        detected = self.spotlight_detector.detect(tab) if tab else None
        if not detected:
            log.info("未检测到聚光广告账户，无法绑定")
            return "未检测到聚光广告账户"
        self.spotlight_detector.bind(detected)
        msg = f"聚光广告账户已绑定：{detected.display_name}（{detected.primary_id}）→ {self.config.workspace_id}"
        log.info(msg)
        return msg

    # ---- 任务（V0.1.2 仅续跑，无业务 Action） ----
    def resume_task(self) -> str:
        if self.engine.resume_unfinished():
            result = self.engine.run()
            msg = f"任务续跑 -> {result.state} @{result.step}"
            log.info(msg)
            return msg
        return "无未完成任务"

    def sync_data(self) -> str:
        return "NOT_IMPLEMENTED: 数据同步留待 V0.2/V0.3"

    def recover_media(self) -> str:
        return "NOT_IMPLEMENTED: 训练媒体恢复留待 V0.6"

    def close(self) -> None:
        self.profile.close()
        self.workspace.release_lock()
        log.info("安全退出完成")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="treecut-xhs-browser",
                                     description="TreeCut 小红书工作浏览器 V0.1.2")
    parser.add_argument("--workspace", default="B007")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--profile-root", default="", help="覆盖 Profile 根目录（测试用）")
    parser.add_argument("--treecut-url", default="", help="覆盖 TreeCut Local URL")
    parser.add_argument("--smoke", action="store_true", help="无 UI 自检模式")
    return parser


def run_smoke(config) -> int:
    """Test A 机制 + 三 Tab + 重复页去重 + 收束 + 重建 + 持久化（headless，离线本地页）。"""
    import http.server

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

    config.creator_home_url = page_url
    config.spotlight_home_url = page_url
    config.frontend_home_url = page_url

    runtime = BrowserRuntime(config)
    runtime.workspace.acquire_lock()
    try:
        context, _ = runtime.profile.launch_persistent_context(headless=True)
        runtime._context = context
        runtime.tabs = TabManager(context, config)
        runtime.tabs.create_fixed_tabs()
        three_tabs = len(context.pages) == 3
        runtime.tabs.get("FRONTEND").evaluate(
            "localStorage.setItem('v012_key', 'persisted_v012')")

        # 重复 Frontend 页（§12）：同 origin 非 canonical → 关闭
        dup = context.new_page()
        dup.goto(page_url)  # 与托管页同 origin
        dedupe = runtime.tabs.dedupe_managed()
        dedupe_closed = len(context.pages) == 3 and len(dedupe["closed_duplicates"]) == 1

        # §13：Frontend 反复导航不新增 Tab
        for _ in range(3):
            runtime.tabs.get("FRONTEND").goto(page_url)
        reuse = len(context.pages) == 3

        # §25：Tab 崩溃重建
        runtime.tabs.get("FRONTEND").close()
        runtime.tabs.rebuild("FRONTEND")
        rebuild = len(context.pages) == 3

        runtime.profile.close()
        context2, _ = runtime.profile.launch_persistent_context(headless=True)
        page2 = context2.pages[0]
        page2.goto(page_url)
        persist = page2.evaluate("localStorage.getItem('v012_key')") == "persisted_v012"
        runtime.profile.close()

        results = {
            "three_fixed_tabs": three_tabs,
            "duplicate_tab_deduped": dedupe_closed,
            "tab_reuse_no_new_tabs": reuse,
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

    # ---- 面板先行（日志 handler 早挂，启动事件全部入面板） ----
    from treecut.browser.minimal_dashboard import MinimalDashboard

    def post_roles(roles: dict) -> None:
        def _ident(role):
            r = roles[role]
            identity = r["identity"]
            if identity == "ACCOUNT_IDENTITY_VALID":
                return "BOUND"
            if identity == "ACCOUNT_IDENTITY_MISMATCH":
                return "MISMATCH"
            if r["account_id"]:
                return "PENDING"
            return "NONE"

        dashboard.post_status(
            creator_session=roles["CREATOR"]["session"],
            creator_account=roles["CREATOR"]["account_name"] or "—",
            creator_xhs_id=roles["CREATOR"]["account_id"] or "—",
            creator_binding=roles["CREATOR"]["binding"],
            spotlight_session=roles["SPOTLIGHT"]["session"],
            spotlight_account=roles["SPOTLIGHT"]["account_name"] or "—",
            spotlight_ad_id=roles["SPOTLIGHT"]["account_id"] or "—",
            spotlight_binding=roles["SPOTLIGHT"]["binding"],
            frontend_session=roles["FRONTEND"]["session"],
            frontend_view=FRONTEND_VIEW_ZH.get(roles["FRONTEND"]["session"], "未知"),
            frontend_binding="OPTIONAL",
            current_task="IDLE",
            last_checkpoint=runtime.checkpoint_store.last_timestamp(config.workspace_id),
        )

    def auto_check() -> None:
        try:
            roles = runtime.check_roles()
            post_roles(roles)
        except Exception as error:  # 检测失败不阻塞面板
            log.error("状态检测失败：%s", error)

    def startup() -> None:
        try:
            runtime.workspace.acquire_lock()
        except RuntimeError as error:
            log.error("PROFILE_LOCKED：%s", error)
            dashboard.post_status(current_task="FAILED")
            return
        local = runtime.local_status()
        dashboard.post_status(treecut_local=local)
        try:
            runtime.start_browser(headless=False)
            auto_check()  # §4 启动后自动检测（不要求用户先点按钮）
        except Exception as error:
            log.error("浏览器启动失败：%s", error)
            dashboard.post_status(current_task="FAILED")

    def check_status() -> None:
        auto_check()
        dashboard.post_status(current_task="IDLE")

    def bind_creator() -> None:
        runtime.bind_creator()
        auto_check()

    def bind_spotlight() -> None:
        runtime.bind_spotlight()
        auto_check()

    def safe_exit() -> None:
        log.info("SAFE_SHUTDOWN")
        runtime.close()

    def view_errors() -> None:
        unfinished = runtime.checkpoint_store.unfinished(config.workspace_id)
        text = dashboard.view_errors_text(unfinished)
        log.info("异常列表：%s", text.replace("\n", " / ") if text else "无异常记录")

    dashboard = MinimalDashboard(
        runtime.workspace,
        callbacks={
            "on_sync_data": lambda: log.info("同步数据：尚未实现（下一阶段启用）"),
            "on_recover_media": lambda: log.info("恢复训练视频：尚未实现（下一阶段启用）"),
            "on_resume_task": lambda: log.info(runtime.resume_task()),
            "on_view_errors": view_errors,
            "on_check_status": check_status,
            "on_bind_creator": bind_creator,
            "on_bind_spotlight": bind_spotlight,
            "on_safe_exit": safe_exit,
        },
    )
    dashboard.post_status(current_task="IDLE", last_checkpoint=None)
    threading.Thread(target=startup, daemon=True).start()
    try:
        dashboard.run()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
