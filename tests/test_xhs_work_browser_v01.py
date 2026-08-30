# -*- coding: utf-8 -*-
"""TreeCut XHS Work Browser V0.1.1 — 测试（三 Tab 修订版）。

Test A/B/C（真实登录/账号）→ 机制自动测试 + 人工验收路径。
Test D  Local Bridge → 自动；Test E  Crash Resume → 自动；Test F  Profile Lock → 自动。
新增：三 Tab 创建/收束/重建、三身份分别绑定与核验、三站 Session 独立性、
note_id 不匹配硬停、Session 误报消除。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.account_detector import (  # noqa: E402
    CreatorIdentityDetector,
    FrontendIdentityDetector,
    RoleIdentity,
    SpotlightIdentityDetector,
)
from treecut.browser.adapters import ADAPTERS  # noqa: E402
from treecut.browser.checkpoint_store import Checkpoint, CheckpointStore  # noqa: E402
from treecut.browser.config import XhsWorkBrowserConfig, load_config  # noqa: E402
from treecut.browser.errors import (  # noqa: E402
    AccountIdentityMismatchError,
    ErrorCategory,
    NetworkTimeoutError,
    NoteIdMismatchError,
    classify,
)
from treecut.browser.local_bridge import CONNECTED, DISCONNECTED, LocalBridge, LocalServiceStub  # noqa: E402
from treecut.browser.policies import InboxManager, QuarantineEntry, atomic_partial_name  # noqa: E402
from treecut.browser.retry_policy import BoundedRetry  # noqa: E402
from treecut.browser.session_detector import (  # noqa: E402
    LOGIN_REQUIRED,
    SESSION_EXPIRED,
    SESSION_UNKNOWN,
    SESSION_VALID,
    SessionDetector,
)
from treecut.browser.tab_manager import TabManager  # noqa: E402
from treecut.browser.task_engine import TASK_STEPS, TaskEngine  # noqa: E402
from treecut.browser.workspace_manager import (  # noqa: E402
    WorkspaceBinding,
    WorkspaceManager,
)


def make_config(profile_root: Path, workspace: str = "B007") -> XhsWorkBrowserConfig:
    cfg = XhsWorkBrowserConfig(workspace_id=workspace, profile_root=str(profile_root),
                               retry_delay_seconds=0.0)
    cfg.validate()
    return cfg


class FakePage:
    """Detectors/TabManager 的最小页面桩（不访问网络）。"""

    def __init__(self, url: str = "", name: str | None = None,
                 html: str = "", title: str = "", storage: dict | None = None):
        self._url = url
        self._name = name
        self._html = html
        self._title = title
        self._storage = storage if storage is not None else {}
        self._closed = False

    @property
    def url(self) -> str:
        return self._url

    def title(self) -> str:
        return self._title

    def content(self) -> str:
        return self._html + " " + self._title

    def text_content(self, _selector: str) -> str | None:
        return self._name

    def goto(self, url: str, timeout: int | None = None) -> None:
        self._url = url

    def evaluate(self, _expr: str):
        return None

    def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed


class FakeContext:
    def __init__(self, pages: list | None = None):
        self._pages = list(pages or [])

    @property
    def pages(self) -> list:
        # 模拟 playwright：已关闭页面从 context.pages 移除
        return [p for p in self._pages if not p.is_closed()]

    def new_page(self) -> FakePage:
        page = FakePage(url="about:blank")
        self._pages.append(page)
        return page


# ============================================================
# 配置
# ============================================================
class TestConfig:
    def test_defaults(self):
        cfg = XhsWorkBrowserConfig()
        cfg.validate()
        assert cfg.expected_tab_count == 3
        assert cfg.allow_temporary_popup == 1
        assert "frontend" in cfg.session_markers
        for kind in ("creator", "spotlight", "frontend"):
            assert "expired" in cfg.session_markers[kind]

    def test_load_save_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TREECUT_DATA_ROOT", str(tmp_path / "data"))
        cfg = load_config()
        assert cfg.expected_tab_count == 3
        target = tmp_path / "data" / "config" / "xhs_work_browser.yaml"
        assert target.is_file()

    def test_validation_rejects_wrong_tab_count(self, tmp_path):
        cfg = make_config(tmp_path)
        cfg.expected_tab_count = 2
        with pytest.raises(ValueError):
            cfg.validate()


# ============================================================
# Policies / Inbox / Quarantine
# ============================================================
class TestPolicies:
    def test_inbox_dirs_and_published_media(self, tmp_path):
        inbox = InboxManager(tmp_path / "inbox").ensure()
        for sub in ("creator", "spotlight", "media_metadata", "published_media",
                    "processed", "quarantine"):
            assert (inbox / sub).is_dir()
        media = InboxManager(tmp_path / "inbox").published_media_path("B007")
        assert media.is_dir()
        assert media.name == "B007"

    def test_quarantine_entry(self, tmp_path):
        inbox = InboxManager(tmp_path / "inbox")
        path = inbox.write_quarantine(QuarantineEntry(
            reason="校验失败", source="browser", workspace="B007", task_id="t1"))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["reason"] == "校验失败"
        assert data["task_id"] == "t1"

    def test_atomic_partial_name(self):
        assert atomic_partial_name("B007_x.mp4") == "B007_x.mp4.part"


# ============================================================
# Checkpoint
# ============================================================
class TestCheckpoint:
    def test_required_tab_field(self, tmp_path):
        store = CheckpointStore(tmp_path / "ckpts")
        cp = Checkpoint(task_id="t1", workspace_id="B007", task_type="SYNC_CREATOR",
                        required_tab="CREATOR", step="VERIFY_IDENTITY")
        store.save(cp)
        loaded = store.load("t1")
        assert loaded.required_tab == "CREATOR"
        assert loaded.step == "VERIFY_IDENTITY"

    def test_no_sensitive_fields(self):
        data = Checkpoint(task_id="t1", workspace_id="B007", task_type="MOCK").to_dict()
        for key in ("cookie", "token", "authorization", "xsec", "session_key", "password"):
            assert key not in data


# ============================================================
# Retry Policy（含 note_id 硬停）
# ============================================================
class TestRetry:
    def test_note_id_mismatch_hard_stop(self):
        retry = BoundedRetry(max_attempts=3, delay_seconds=0)
        d = retry.decide(1, NoteIdMismatchError("expected 6a8d75aa got 9999"))
        assert d.action == "give_up"
        assert d.final_state == "NEEDS_HUMAN"  # §24：绝不猜 note 身份

    def test_identity_mismatch_hard_stop(self):
        retry = BoundedRetry(max_attempts=3, delay_seconds=0)
        d = retry.decide(1, AccountIdentityMismatchError("wrong account"))
        assert d.final_state == "NEEDS_HUMAN"

    def test_bounded_attempts(self):
        retry = BoundedRetry(max_attempts=3, delay_seconds=0)
        assert retry.decide(1, NetworkTimeoutError("n")).action == "retry"
        assert retry.decide(2, NetworkTimeoutError("n")).action == "refresh_retry"
        d3 = retry.decide(3, NetworkTimeoutError("n"))
        assert d3.action == "give_up" and d3.final_state == "FAILED"

    def test_classify(self):
        assert classify(NoteIdMismatchError("x")) == ErrorCategory.NOTE_ID_MISMATCH
        assert classify(RuntimeError("timeout after 30s")) == ErrorCategory.PAGE_LOAD_TIMEOUT
        assert classify(NetworkTimeoutError("x")) == ErrorCategory.NETWORK_TIMEOUT


# ============================================================
# Task Engine（required_tab + Crash Resume）
# ============================================================
class TestTaskEngine:
    def _engine(self, tmp_path):
        store = CheckpointStore(tmp_path / "ckpts")
        retry = BoundedRetry(max_attempts=3, delay_seconds=0)
        return TaskEngine(store, retry, workspace_id="B007"), store

    def test_steps_have_select_tab_and_required_tab(self, tmp_path):
        engine, _ = self._engine(tmp_path)
        assert TASK_STEPS[0] == "SELECT_TAB"
        tid = engine.new_task(target="x", required_tab="SPOTLIGHT")
        assert engine.checkpoint.required_tab == "SPOTLIGHT"
        assert tid

    def test_mock_run_success(self, tmp_path):
        engine, _ = self._engine(tmp_path)
        engine.new_task(target="mock", required_tab="FRONTEND")
        result = engine.run()
        assert result.state == "SUCCESS"
        assert result.step == "DONE"

    def test_crash_resume_no_restart(self, tmp_path):
        """Test E：中途 PAUSED（模拟崩溃）→ 新引擎从断点继续，不从头重跑。"""
        engine, store = self._engine(tmp_path)
        engine.new_task(target="mock", required_tab="CREATOR")
        paused = engine.run(pause_after_step="VERIFY_IDENTITY")
        assert paused.state == "PAUSED"
        assert paused.step == "VERIFY_IDENTITY"

        engine2, _ = self._engine(tmp_path)
        assert engine2.resume_unfinished() is True
        seen: list[str] = []

        def handler(_e, step, _cp):
            seen.append(step)
            return None

        result = engine2.run(handler)
        assert result.state == "SUCCESS"
        assert seen[0] == "VERIFY_IDENTITY"  # 从中断点继续，而非 SELECT_TAB
        assert "SELECT_TAB" not in seen

    def test_hard_stop_then_resume(self, tmp_path):
        engine, _ = self._engine(tmp_path)
        engine.new_task(target="mock", required_tab="CREATOR")

        def failing(_e, step, _cp):
            if step == "VERIFY_IDENTITY":
                raise AccountIdentityMismatchError("wrong creator account")
            return None

        result = engine.run(failing)
        assert result.state == "NEEDS_HUMAN"
        assert result.step == "VERIFY_IDENTITY"

        engine2, _ = self._engine(tmp_path)
        assert engine2.resume_unfinished()
        assert engine2.run().state == "SUCCESS"


# ============================================================
# Workspace Binding（三身份）
# ============================================================
class TestWorkspaceBinding:
    def test_three_identities_binding(self, tmp_path):
        ws = WorkspaceManager(make_config(tmp_path))
        binding = WorkspaceBinding(
            workspace_id="B007",
            creator_xhs_id="xhsB007",
            creator_display_name="KUBON坤宝高端岛台工厂",
            spotlight_ad_account_id="ad888",
            spotlight_ad_account_name="T-KUBON-运营",
        )
        ws.save_binding(binding)
        loaded = ws.load_binding()
        assert loaded.creator_xhs_id == "xhsB007"
        assert loaded.spotlight_ad_account_name == "T-KUBON-运营"
        assert loaded.frontend_confirmed is False
        text = ws.binding_path().read_text(encoding="utf-8")
        for key in ("cookie", "token", "authorization", "xsec", "password"):
            assert key not in text.lower()

    def test_profile_lock(self, tmp_path):
        cfg = make_config(tmp_path)
        ws1 = WorkspaceManager(cfg)
        ws1.acquire_lock()
        with pytest.raises(RuntimeError):
            WorkspaceManager(make_config(tmp_path)).acquire_lock()
        ws1.release_lock()
        ws3 = WorkspaceManager(make_config(tmp_path))
        ws3.acquire_lock()
        ws3.release_lock()


# ============================================================
# 三身份 Detector + Gate
# ============================================================
class TestIdentityGates:
    def _ws(self, tmp_path):
        return WorkspaceManager(make_config(tmp_path))

    def test_creator_primary_anchor_id_stable(self, tmp_path):
        """§9：XHS ID 不变即仍为 B007（昵称可改仍 VALID）。"""
        ws = self._ws(tmp_path)
        det = CreatorIdentityDetector(ws)
        page = FakePage(url="https://creator.xiaohongshu.com/",
                        name="KUBON坤宝高端岛台工厂",
                        html="小红书号: xhsB007")
        ident = det.detect(page)
        assert ident.primary_id == "xhsB007"

        assert det.gate(ident)[0] == "ACCOUNT_IDENTITY_UNKNOWN"  # 未绑定 → UNKNOWN（绝不凭目录名）
        det.bind(ident)
        assert det.gate(ident)[0] == "ACCOUNT_IDENTITY_VALID"

        # 昵称改了，ID 不变 → 仍 VALID
        renamed = FakePage(url="https://creator.xiaohongshu.com/",
                           name="改名后的名字", html="小红书号: xhsB007")
        status, _ = det.gate(det.detect(renamed))
        assert status == "ACCOUNT_IDENTITY_VALID"

    def test_creator_mismatch_blocks(self, tmp_path):
        ws = self._ws(tmp_path)
        det = CreatorIdentityDetector(ws)
        good = FakePage(url="https://creator.xiaohongshu.com/", name="A", html="小红书号: xhsB007")
        det.bind(det.detect(good))
        wrong = FakePage(url="https://creator.xiaohongshu.com/", name="B", html="小红书号: other")
        status, reason = det.gate(det.detect(wrong))
        assert status == "ACCOUNT_IDENTITY_MISMATCH"
        assert "BLOCK_SYNC" in reason

    def test_spotlight_binding_separate_from_creator(self, tmp_path):
        """§10：聚光广告账户名不需要与 Creator 一致，单独绑定。"""
        ws = self._ws(tmp_path)
        creator = CreatorIdentityDetector(ws)
        spotlight = SpotlightIdentityDetector(ws)
        c_page = FakePage(url="https://creator.xiaohongshu.com/", name="KUBON坤宝高端岛台工厂",
                          html="小红书号: xhsB007")
        creator.bind(creator.detect(c_page))

        assert spotlight.gate(None)[0] == "ACCOUNT_IDENTITY_UNKNOWN"  # 聚光未绑定
        ad_page = FakePage(url="https://ad.xiaohongshu.com/", name="T-KUBON-运营",
                           html="广告账户ID: ad888")
        spotlight.bind(spotlight.detect(ad_page))
        assert spotlight.gate(spotlight.detect(ad_page))[0] == "ACCOUNT_IDENTITY_VALID"

    def test_frontend_unconfirmed_never_fake(self, tmp_path):
        """§11：前台账号未确认 → UNCONFIRMED，不假装对应；确认后才 VALID。"""
        ws = self._ws(tmp_path)
        det = FrontendIdentityDetector(ws)
        page = FakePage(url="https://www.xiaohongshu.com/explore/abc",
                        name="前台昵称", html="小红书号: front123")
        ident = det.detect(page)
        assert det.gate(ident)[0] == "FRONTEND_IDENTITY_UNCONFIRMED"

        det.confirm(ident)
        assert det.gate(det.detect(page))[0] == "ACCOUNT_IDENTITY_VALID"

        other = FakePage(url="https://www.xiaohongshu.com/", name="别的号", html="小红书号: other")
        status, _ = det.gate(det.detect(other))
        assert status == "ACCOUNT_IDENTITY_MISMATCH"

    def test_no_guess_unknown(self, tmp_path):
        ws = self._ws(tmp_path)
        det = CreatorIdentityDetector(ws)
        assert det.detect(FakePage(url="https://creator.xiaohongshu.com/", name=None)) is None


# ============================================================
# Session Detector（三站独立 + 误报消除）
# ============================================================
class TestSession:
    def test_valid_wins_over_stray_login_words(self, tmp_path):
        """V0.1.1 修复：已登录页出现"登录"字样（页脚/浮层）不再误判 EXPIRED。"""
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="创作中心 发布笔记 登录", url="https://creator.xiaohongshu.com/")
        assert det.check(page, "creator").status == SESSION_VALID

    def test_expired_strong_signal(self):
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="登录已过期 请重新登录")
        assert det.check(page, "creator").status == SESSION_EXPIRED

    def test_login_required(self):
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="扫码登录")
        assert det.check(page, "creator").status == LOGIN_REQUIRED

    def test_login_url_wins_over_valid_markers(self):
        """登录页 URL 是最强信号：即使页面含功能词也判需要登录。"""
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="创作中心 发布笔记", url="https://creator.xiaohongshu.com/login")
        assert det.check(page, "creator").status == LOGIN_REQUIRED

    def test_unknown_when_page_opens_but_no_signal(self):
        """§11：页面能打开 ≠ SESSION_VALID。"""
        det = SessionDetector(XhsWorkBrowserConfig())
        assert det.check(FakePage(html="加载中..."), "creator").status == SESSION_UNKNOWN

    def test_three_sites_independent(self):
        """§23：Creator 掉登录不影响 Spotlight/Frontend 判定。"""
        det = SessionDetector(XhsWorkBrowserConfig())
        creator = FakePage(html="扫码登录", url="https://creator.xiaohongshu.com/")
        spotlight = FakePage(html="推广 广告管理", url="https://ad.xiaohongshu.com/")
        frontend = FakePage(html="首页 发现", url="https://www.xiaohongshu.com/")
        assert det.check(creator, "creator").status == LOGIN_REQUIRED
        assert det.check(spotlight, "spotlight").status == SESSION_VALID
        assert det.check(frontend, "frontend").status == SESSION_VALID


# ============================================================
# Tab Manager（三固定 Tab / reconcile / rebuild）
# ============================================================
class TestTabManager:
    def _setup(self):
        config = make_config(Path("unused"), workspace="B007")
        context = FakeContext([FakePage(url="about:blank")])
        return TabManager(context, config), context, config

    def test_create_three_fixed_tabs(self):
        tm, context, _ = self._setup()
        tabs = tm.create_fixed_tabs()
        assert set(tabs) == {"CREATOR", "SPOTLIGHT", "FRONTEND"}
        assert len(context.pages) == 3
        assert tabs["CREATOR"].url.startswith("https://creator.xiaohongshu.com")

    def test_reconcile_closes_blank_extras_keeps_user_pages(self):
        """§14：3 固定 + 1 临时弹窗（共4）不动作；再多空白页收束，用户页（非 blank）不关闭。"""
        tm, context, _ = self._setup()
        tm.create_fixed_tabs()

        popup = context.new_page()  # about:blank 临时弹窗（允许 1 个）
        result = tm.reconcile()
        assert result["actual"] == 4  # 3 固定 + 1 允许弹窗，不盲目收束
        assert result["closed_extras"] == []
        popup.close()  # 弹窗处理完关闭

        blank2 = context.new_page()  # 超限空白页 → 收束
        user_page = FakePage(url="https://example.com/note/1")
        context._pages.append(user_page)
        result2 = tm.reconcile()
        assert result2["actual"] == 4  # 空白页被关；用户页保留
        assert result2["closed_extras"] == ["blank-temp"]
        assert result2["left_untouched"] == 1
        assert user_page.is_closed() is False  # 用户页未被动

    def test_rebuild_keeps_three_tabs(self):
        tm, context, _ = self._setup()
        tm.create_fixed_tabs()
        tm.get("FRONTEND").close()
        page = tm.rebuild("FRONTEND")
        assert len(context.pages) == 3
        assert not page.is_closed()
        assert page.url.startswith("https://www.xiaohongshu.com")

    def test_reuse_no_new_tabs(self):
        tm, context, _ = self._setup()
        tm.create_fixed_tabs()
        for _ in range(3):
            tm.get("FRONTEND").goto("https://www.xiaohongshu.com/explore/1")
        assert len(context.pages) == 3  # 反复导航不新增 Tab

    def test_dedupe_duplicate_managed_keeps_user_pages(self):
        """§12：同托管域重复页关闭（确认由 TreeCut 创建）；用户页（非托管域）不动。"""
        tm, context, _ = self._setup()
        tm.create_fixed_tabs()
        dup = FakePage(url="https://www.xiaohongshu.com/explore/dup-note")
        context._pages.append(dup)
        result = tm.dedupe_managed()
        assert len(result["closed_duplicates"]) == 1
        assert dup.is_closed()
        assert len(context.pages) == 3  # 严格 3 托管 Tab

        user = FakePage(url="https://example.com/note/1")  # 非托管域 → 不动
        context._pages.append(user)
        result2 = tm.dedupe_managed()
        assert result2["closed_duplicates"] == []
        assert user.is_closed() is False


# ============================================================
# BrowserRuntime.check_roles（SPA 渲染有界重试）
# ============================================================
class ProgressivePage:
    """模拟 SPA：前 ready_at 次检测返回"加载中"，之后出现功能页内容。"""

    def __init__(self, url: str, name: str, html: str, ready_at: int = 2):
        self._url = url
        self._name = name
        self._html = html
        self._ready_at = ready_at
        self.content_calls = 0
        self.text_calls = 0

    @property
    def url(self) -> str:
        return self._url

    def is_closed(self) -> bool:
        return False

    def content(self) -> str:
        self.content_calls += 1
        return self._html if self.content_calls >= self._ready_at else "页面加载中..."

    def title(self) -> str:
        return ""

    def text_content(self, _selector: str) -> str | None:
        self.text_calls += 1
        return self._name if self.content_calls >= self._ready_at else None


class _FakeTabs:
    def __init__(self, pages: dict):
        self._pages = pages

    def get(self, role: str):
        return self._pages.get(role)


class TestCheckRolesSpaRetry:
    def _runtime(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TREECUT_DATA_ROOT", str(tmp_path / "data"))
        from treecut.browser.main import BrowserRuntime
        cfg = make_config(tmp_path / "profiles")
        return BrowserRuntime(cfg)

    def test_session_recovers_after_spa_render(self, tmp_path, monkeypatch):
        """SPA 前几秒未渲染 → 有界重试后得出 已登录 + 识别账号（真实验收 C/D 的机制保障）。"""
        runtime = self._runtime(tmp_path, monkeypatch)
        page = ProgressivePage(url="https://creator.xiaohongshu.com/",
                               name="KUBON坤宝高端岛台工厂",
                               html="创作中心 发布笔记 小红书号: xhsB007", ready_at=2)
        runtime.tabs = _FakeTabs({"CREATOR": page})
        roles = runtime.check_roles()
        creator = roles["CREATOR"]
        assert creator["session"] == SESSION_VALID
        assert creator["account_name"] == "KUBON坤宝高端岛台工厂"
        assert creator["account_id"] == "xhsB007"
        # 第 2 次尝试即成功（每次尝试 session+body 各读一次 content → 2 次尝试 = 4 次封顶），未空转
        assert page.content_calls <= 4

    def test_never_ready_bounded(self, tmp_path, monkeypatch):
        """页面始终无信号 → 有界重试（SPA_RETRY_TRIES 次）后保持 UNKNOWN，不无限循环。"""
        runtime = self._runtime(tmp_path, monkeypatch)
        page = ProgressivePage(url="https://creator.xiaohongshu.com/",
                               name=None, html="", ready_at=99)
        runtime.tabs = _FakeTabs({"CREATOR": page})
        roles = runtime.check_roles()
        assert roles["CREATOR"]["session"] == SESSION_UNKNOWN
        # 每次尝试 session+body 各读一次 → 总调用 = 2 × SPA_RETRY_TRIES（有界）
        assert page.content_calls == runtime.SPA_RETRY_TRIES * 2


# ============================================================
# Local Bridge（Test D）
# ============================================================
class TestLocalBridge:
    def test_health_cycle(self):
        stub = LocalServiceStub(port=0)
        base = f"http://{stub.start()}"
        bridge = LocalBridge(base, timeout_seconds=2.0)
        assert bridge.health().status == CONNECTED
        stub.stop()
        assert bridge.health().status == DISCONNECTED
        stub2 = LocalServiceStub(host="127.0.0.1", port=stub.port)
        stub2.start()
        try:
            assert bridge.health().status == CONNECTED  # 自动恢复
        finally:
            stub2.stop()


# ============================================================
# Adapters（全部 NOT_IMPLEMENTED）
# ============================================================
class TestAdapters:
    def test_all_not_implemented(self):
        assert set(ADAPTERS) == {"CreatorExportAdapter", "CreatorObservationAdapter",
                                 "SpotlightExportAdapter", "MediaRecoveryAdapter"}
        for adapter in ADAPTERS.values():
            assert adapter.status == "NOT_IMPLEMENTED"
            with pytest.raises(NotImplementedError):
                adapter.execute()


# ============================================================
# 集成（Edge headless smoke：三 Tab + 持久化 + reconcile + 重建）
# ============================================================
@pytest.mark.integration
class TestBrowserIntegration:
    def _run_smoke(self, tmp_path):
        python = sys.executable
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env["TREECUT_DATA_ROOT"] = str(tmp_path / "data")
        env["PYTHONPATH"] = str(repo / "src")
        return subprocess.run(
            [python, "-m", "treecut.browser.main", "--smoke",
             "--profile-root", str(tmp_path / "profiles")],
            capture_output=True, text=True, timeout=240, env=env, cwd=str(repo),
        )

    def test_three_tab_foundation_smoke(self, tmp_path):
        proc = self._run_smoke(tmp_path)
        out = (proc.stdout or "") + (proc.stderr or "")
        assert proc.returncode == 0, out[-2000:]
        for marker in ("three_fixed_tabs=PASS", "duplicate_tab_deduped=PASS",
                       "tab_reuse_no_new_tabs=PASS", "tab_crash_rebuild=PASS",
                       "persistent_profile=PASS"):
            assert marker in (proc.stdout or ""), proc.stdout[-2000:]
