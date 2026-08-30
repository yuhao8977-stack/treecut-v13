# -*- coding: utf-8 -*-
"""TreeCut XHS Work Browser V0.1 — 测试（§43-49 验收映射）。

Test A/B/C（真实登录/账号）→ 机制自动测试 + 人工验收路径（真实站点登录由用户执行）。
Test D  Local Bridge          → 自动
Test E  Crash Resume          → 自动
Test F  Profile Lock          → 自动
资源/30min（§49）             → 机制（单 Tab/无 Context 泄漏）+ 人工长时间验收
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from treecut.browser.account_detector import AccountDetector  # noqa: E402
from treecut.browser.adapters import ADAPTERS  # noqa: E402
from treecut.browser.checkpoint_store import Checkpoint, CheckpointStore  # noqa: E402
from treecut.browser.config import XhsWorkBrowserConfig, load_config  # noqa: E402
from treecut.browser.errors import (  # noqa: E402
    AccountIdentityMismatchError,
    ErrorCategory,
    NetworkTimeoutError,
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
from treecut.browser.task_engine import TaskEngine  # noqa: E402
from treecut.browser.workspace_manager import WorkspaceManager  # noqa: E402


def make_config(profile_root: Path, workspace: str = "B007") -> XhsWorkBrowserConfig:
    cfg = XhsWorkBrowserConfig(workspace_id=workspace, profile_root=str(profile_root),
                               retry_delay_seconds=0.0)
    cfg.validate()
    return cfg


class FakePage:
    """Detectors 的最小页面桩（不访问网络）。"""

    def __init__(self, url: str = "", name: str | None = None,
                 html: str = "", title: str = ""):
        self._url = url
        self._name = name
        self._html = html
        self._title = title

    @property
    def url(self) -> str:
        return self._url

    def title(self) -> str:
        return self._title

    def content(self) -> str:
        return self._html + " " + self._title

    def text_content(self, _selector: str) -> str | None:
        return self._name


# ============================================================
# 配置
# ============================================================
class TestConfig:
    def test_defaults_valid(self):
        cfg = XhsWorkBrowserConfig()
        cfg.validate()
        assert cfg.workspace_id == "B007"
        assert cfg.work_tab_max == 1
        assert cfg.browser_channel == "msedge"

    def test_load_save_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TREECUT_DATA_ROOT", str(tmp_path / "data"))
        cfg = load_config()
        assert cfg.workspace_id == "B007"
        target = tmp_path / "data" / "config" / "xhs_work_browser.yaml"
        assert target.is_file()
        cfg2 = load_config()
        assert cfg2.workspace_id == cfg.workspace_id

    def test_validation_rejects_multi_tab(self, tmp_path):
        cfg = make_config(tmp_path)
        cfg.work_tab_max = 2
        with pytest.raises(ValueError):
            cfg.validate()


# ============================================================
# Policies / Inbox / Quarantine（§28/29/38/39/40）
# ============================================================
class TestPolicies:
    def test_inbox_dirs(self, tmp_path):
        inbox = InboxManager(tmp_path / "inbox").ensure()
        for sub in ("creator", "spotlight", "media_metadata", "published_media",
                    "processed", "quarantine"):
            assert (inbox / sub).is_dir()

    def test_quarantine_entry(self, tmp_path):
        inbox = InboxManager(tmp_path / "inbox")
        path = inbox.write_quarantine(QuarantineEntry(
            reason="校验失败", source="browser", workspace="B007", task_id="t1"))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["reason"] == "校验失败"
        assert data["workspace"] == "B007"
        assert data["task_id"] == "t1"
        assert "timestamp" in data

    def test_atomic_partial_name(self):
        assert atomic_partial_name("B003_x.mp4") == "B003_x.mp4.part"


# ============================================================
# Checkpoint（§20/21）
# ============================================================
class TestCheckpoint:
    def test_save_load_unfinished(self, tmp_path):
        store = CheckpointStore(tmp_path / "ckpts")
        cp = Checkpoint(task_id="t1", workspace_id="B007", task_type="MOCK",
                        state="RUNNING", step="NAVIGATE")
        store.save(cp)
        loaded = store.load("t1")
        assert loaded.step == "NAVIGATE"
        assert store.unfinished("B007")[0].task_id == "t1"
        assert store.unfinished("OTHER") == []
        store.clear("t1")
        assert store.load("t1") is None

    def test_no_sensitive_fields(self):
        cp = Checkpoint(task_id="t1", workspace_id="B007", task_type="MOCK")
        data = cp.to_dict()
        for key in ("cookie", "token", "authorization", "xsec", "session_key"):
            assert key not in data


# ============================================================
# Retry Policy（§22/24/25）
# ============================================================
class TestRetry:
    def test_hard_stop_needs_human(self):
        retry = BoundedRetry(max_attempts=3, delay_seconds=0)
        d = retry.decide(1, AccountIdentityMismatchError("mismatch"))
        assert d.action == "give_up"
        assert d.final_state == "NEEDS_HUMAN"

    def test_bounded_attempts(self):
        retry = BoundedRetry(max_attempts=3, delay_seconds=0)
        d1 = retry.decide(1, NetworkTimeoutError("net"))
        assert d1.action == "retry"
        d2 = retry.decide(2, NetworkTimeoutError("net"))
        assert d2.action == "refresh_retry"
        d3 = retry.decide(3, NetworkTimeoutError("net"))
        assert d3.action == "give_up"
        assert d3.final_state == "FAILED"

    def test_unknown_error_final_needs_human(self):
        retry = BoundedRetry(max_attempts=1, delay_seconds=0)
        d = retry.decide(1, ValueError("weird"))
        assert d.final_state == "NEEDS_HUMAN"  # 无法可靠分类 → 不自动猜测

    def test_classify(self):
        assert classify(NetworkTimeoutError("x")) == ErrorCategory.NETWORK_TIMEOUT
        assert classify(AccountIdentityMismatchError("x")) == ErrorCategory.ACCOUNT_IDENTITY_MISMATCH
        assert classify(RuntimeError("timeout after 30s")) == ErrorCategory.PAGE_LOAD_TIMEOUT


# ============================================================
# Task Engine + Crash Resume（§19/21/47 → Test E）
# ============================================================
class TestTaskEngine:
    def _engine(self, tmp_path):
        store = CheckpointStore(tmp_path / "ckpts")
        retry = BoundedRetry(max_attempts=3, delay_seconds=0)
        return TaskEngine(store, retry, workspace_id="B007"), store

    def test_mock_run_success(self, tmp_path):
        engine, _ = self._engine(tmp_path)
        engine.new_task(target="mock")
        result = engine.run()
        assert result.state == "SUCCESS"
        assert result.step == "DONE"

    def test_crash_resume_no_restart(self, tmp_path):
        """Test E：跑到中途（模拟崩溃），新引擎从 Checkpoint 继续，不从头重跑。"""
        engine, store = self._engine(tmp_path)
        engine.new_task(target="mock")
        paused = engine.run(pause_after_step="VERIFY_ACCOUNT")
        assert paused.state == "PAUSED"
        assert paused.step == "VERIFY_ACCOUNT"

        # 模拟崩溃：旧引擎丢弃，新引擎加载
        engine2, _ = self._engine(tmp_path)
        assert engine2.resume_unfinished() is True
        seen: list[str] = []

        def handler(_e, step, _cp):
            seen.append(step)
            return None

        result = engine2.run(handler)
        assert result.state == "SUCCESS"
        assert seen[0] == "VERIFY_ACCOUNT"  # 从中断点继续，而非 START
        assert "START" not in seen

    def test_hard_stop_needs_human_then_resume(self, tmp_path):
        engine, _ = self._engine(tmp_path)
        engine.new_task(target="mock")

        def failing(_e, step, _cp):
            if step == "VERIFY_ACCOUNT":
                raise AccountIdentityMismatchError("wrong account")
            return None

        result = engine.run(failing)
        assert result.state == "NEEDS_HUMAN"
        assert result.step == "VERIFY_ACCOUNT"

        # 人工处理后 Resume → 从同一步继续
        engine2, _ = self._engine(tmp_path)
        assert engine2.resume_unfinished()
        result2 = engine2.run()
        assert result2.state == "SUCCESS"

    def test_idempotency_key_designed(self, tmp_path):
        engine, _ = self._engine(tmp_path)
        tid = engine.new_task(target="x", idempotency_key="dedup-1")
        assert engine.checkpoint.idempotency_key == "dedup-1"
        assert engine.checkpoint.task_id == tid


# ============================================================
# Workspace / Profile Lock（§33/34/48 → Test F）
# ============================================================
class TestWorkspace:
    def test_profile_lock(self, tmp_path):
        cfg = make_config(tmp_path)
        ws1 = WorkspaceManager(cfg)
        ws1.acquire_lock()
        ws2 = WorkspaceManager(make_config(tmp_path))
        with pytest.raises(RuntimeError):
            ws2.acquire_lock()  # PROFILE_LOCKED
        assert ws2.locked() is True
        ws1.release_lock()
        ws3 = WorkspaceManager(make_config(tmp_path))
        ws3.acquire_lock()  # 释放后可获取
        ws3.release_lock()

    def test_binding_no_credentials(self, tmp_path):
        from treecut.browser.workspace_manager import AccountBindingRecord
        cfg = make_config(tmp_path)
        ws = WorkspaceManager(cfg)
        ws.save_binding(AccountBindingRecord(workspace_id="B007",
                                             platform_account_name="树剪B007",
                                             xiaohongshu_id="xhs123"))
        loaded = ws.load_binding()
        assert loaded.platform_account_name == "树剪B007"
        text = ws.binding_path().read_text(encoding="utf-8")
        for key in ("cookie", "token", "authorization", "xsec", "password"):
            assert key not in text.lower()


# ============================================================
# Account Detector + Identity Gate（§8/9/10/44/45 → Test B/C）
# ============================================================
class TestAccountGate:
    def _ws(self, tmp_path):
        return WorkspaceManager(make_config(tmp_path))

    def test_detect_and_bind(self, tmp_path):
        ws = self._ws(tmp_path)
        det = AccountDetector(ws)
        page = FakePage(url="https://creator.xiaohongshu.com/explore/abc",
                        name="树剪B007")
        ident = det.detect(page)
        assert ident.platform_account_name == "树剪B007"
        assert ident.current_page_indicator == "creator"

        # 未绑定 → UNKNOWN（绝不凭 Profile 目录名认定身份）
        status, _ = det.gate(ident)
        assert status == "ACCOUNT_IDENTITY_UNKNOWN"

        det.bind(ident)
        status, reason = det.gate(det.detect(page))
        assert status == "ACCOUNT_IDENTITY_VALID"
        assert reason is None

    def test_mismatch_blocks(self, tmp_path):
        """Test C：错误账号 → ACCOUNT_IDENTITY_MISMATCH + BLOCK（不得继续任务）。"""
        ws = self._ws(tmp_path)
        det = AccountDetector(ws)
        good = FakePage(url="https://creator.xiaohongshu.com/", name="树剪B007")
        det.bind(det.detect(good))
        wrong = FakePage(url="https://creator.xiaohongshu.com/", name="错误账号")
        status, reason = det.gate(det.detect(wrong))
        assert status == "ACCOUNT_IDENTITY_MISMATCH"
        assert "BLOCK_SYNC" in reason

    def test_unknown_no_guess(self, tmp_path):
        ws = self._ws(tmp_path)
        det = AccountDetector(ws)
        assert det.detect(FakePage(url="https://creator.xiaohongshu.com/", name=None)) is None
        assert det.gate(None)[0] == "ACCOUNT_IDENTITY_UNKNOWN"


# ============================================================
# Session Detector（§11/12）
# ============================================================
class TestSession:
    def test_valid(self):
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="创作中心 发布笔记", url="https://creator.xiaohongshu.com/")
        assert det.check(page, "creator").status == SESSION_VALID

    def test_login_required(self):
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="扫码登录", url="https://creator.xiaohongshu.com/login")
        assert det.check(page, "creator").status == LOGIN_REQUIRED

    def test_mixed_expired(self):
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="扫码登录 发布笔记")
        assert det.check(page, "creator").status == SESSION_EXPIRED

    def test_unknown_when_page_opens_but_no_signal(self):
        """§11：页面能打开 ≠ SESSION_VALID。"""
        det = SessionDetector(XhsWorkBrowserConfig())
        page = FakePage(html="加载中...")
        assert det.check(page, "creator").status == SESSION_UNKNOWN


# ============================================================
# Local Bridge（§17/18/46 → Test D）
# ============================================================
class TestLocalBridge:
    def test_health_cycle(self):
        """ON → CONNECTED / OFF → DISCONNECTED / 重启 → 自动恢复 CONNECTED。"""
        stub = LocalServiceStub(port=0)
        base = f"http://{stub.start()}"
        bridge = LocalBridge(base, timeout_seconds=2.0)

        assert bridge.health().status == CONNECTED

        stub.stop()
        assert bridge.health().status == DISCONNECTED

        stub2 = LocalServiceStub(host="127.0.0.1", port=stub.port)  # 同端口重启
        stub2.start()
        try:
            assert bridge.health().status == CONNECTED  # 自动恢复
        finally:
            stub2.stop()


# ============================================================
# Adapters（§36/37：全部 NOT_IMPLEMENTED）
# ============================================================
class TestAdapters:
    def test_all_not_implemented(self):
        assert set(ADAPTERS) == {"CreatorExportAdapter", "CreatorObservationAdapter",
                                 "SpotlightExportAdapter", "MediaRecoveryAdapter"}
        for name, adapter in ADAPTERS.items():
            assert adapter.status == "NOT_IMPLEMENTED"
            with pytest.raises(NotImplementedError):
                adapter.execute()


# ============================================================
# 集成（真实 Edge persistent context；§43 Test A 机制，真实登录人工验收）
# 子进程运行 smoke：规避 pytest 进程内 asyncio loop 与 Sync API 冲突，
# 也最接近真实启动路径。
# ============================================================
@pytest.mark.integration
class TestBrowserIntegration:
    def _run_smoke(self, tmp_path):
        import subprocess
        python = sys.executable
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env["TREECUT_DATA_ROOT"] = str(tmp_path / "data")
        env["PYTHONPATH"] = str(repo / "src")
        proc = subprocess.run(
            [python, "-m", "treecut.browser.main", "--smoke",
             "--profile-root", str(tmp_path / "profiles")],
            capture_output=True, text=True, timeout=180, env=env,
            cwd=str(repo),
        )
        return proc

    def test_persistent_profile_and_single_tab(self, tmp_path):
        """Test A 机制 + §15/16/32：Profile 持久化、单 Tab 复用、tab 崩溃重建、重启后单 Tab。"""
        proc = self._run_smoke(tmp_path)
        out = (proc.stdout or "") + (proc.stderr or "")
        assert proc.returncode == 0, out[-2000:]
        for marker in ("persistent_profile=PASS", "single_tab_reuse=PASS",
                       "tab_crash_recreate=PASS", "single_tab_after_restart=PASS"):
            assert marker in (proc.stdout or ""), proc.stdout[-2000:]
