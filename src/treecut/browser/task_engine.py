"""XHS Work Browser V0.1 — Task Engine 底座（§19/20/21/30）。

状态：IDLE / RUNNING / PAUSED / SUCCESS / FAILED / NEEDS_HUMAN
任务内部步骤：START → VERIFY_SESSION → VERIFY_ACCOUNT → NAVIGATE → WAIT_READY →
             ACTION → VALIDATE → SAVE → COMMIT → DONE

V0.1 不实现真实业务 Action（§19：框架必须存在）。
每一步后落 checkpoint → §21 Crash Resume 可从中间步骤继续（不从头重跑）。
idempotency_key 字段设计（§30），业务去重留待后续。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from treecut.browser.checkpoint_store import Checkpoint, CheckpointStore
from treecut.browser.errors import XhsWorkBrowserError, classify
from treecut.browser.retry_policy import BoundedRetry, RetryDecision

TASK_STATES = ("IDLE", "RUNNING", "PAUSED", "SUCCESS", "FAILED", "NEEDS_HUMAN")
# V0.1.1：任务带页面角色（required_tab），SELECT_TAB 为首步（§22）
TASK_STEPS = ("SELECT_TAB", "VERIFY_SESSION", "VERIFY_IDENTITY", "NAVIGATE", "WAIT_READY",
              "ACTION", "VALIDATE", "SAVE", "CHECKPOINT", "DONE")
# NEEDS_HUMAN 视为可继续（人工处理后 Resume），FAILED/SUCCESS 为终态
RESUMABLE_STATES = {"RUNNING", "PAUSED", "NEEDS_HUMAN"}
TAB_ROLES = ("CREATOR", "SPOTLIGHT", "FRONTEND")


@dataclass
class TaskResult:
    task_id: str
    state: str
    step: str
    attempts: int = 0
    message: str = ""


class TaskEngine:
    """可插拔 step executor 的极简任务引擎。

    step_handler(engine, step, checkpoint) -> None（正常）或 raise XhsWorkBrowserError
    或返回 {"needs_human": reason}。
    """

    def __init__(self, store: CheckpointStore, retry: BoundedRetry,
                 workspace_id: str, task_type: str = "MOCK"):
        self.store = store
        self.retry = retry
        self.workspace_id = workspace_id
        self.task_type = task_type
        self.checkpoint: Checkpoint | None = None
        self._step_index = 0

    # ---- 新建任务 ----
    def new_task(self, target: str = "", required_tab: str = "CREATOR",
                 idempotency_key: str | None = None) -> str:
        if required_tab not in TAB_ROLES:
            raise ValueError(f"required_tab 必须是 {TAB_ROLES} 之一: {required_tab}")
        task_id = f"{self.task_type.lower()}_{uuid.uuid4().hex[:12]}"
        self.checkpoint = Checkpoint(
            task_id=task_id,
            workspace_id=self.workspace_id,
            task_type=self.task_type,
            state="RUNNING",
            step=TASK_STEPS[0],
            target=target,
            required_tab=required_tab,
            attempt=1,
            idempotency_key=idempotency_key or task_id,
        )
        self.store.save(self.checkpoint)
        return task_id

    # ---- §21 Crash Resume：从 checkpoint 继续，不从头重跑 ----
    def resume_unfinished(self, task_id: str | None = None) -> bool:
        unfinished = self.store.unfinished(self.workspace_id)
        if task_id:
            cp = self.store.load(task_id)
        else:
            cp = unfinished[-1] if unfinished else None
        if cp is None or cp.state not in RESUMABLE_STATES:
            return False
        self.checkpoint = cp
        self._step_index = TASK_STEPS.index(cp.step) if cp.step in TASK_STEPS else 0
        return True

    def has_unfinished(self) -> bool:
        return bool(self.store.unfinished(self.workspace_id))

    # ---- 执行 ----
    def run(self, step_handler: Callable | None = None,
            pause_after_step: str | None = None) -> TaskResult:
        """step_handler 缺省 → 使用 V0.1 Mock handler（无业务行为，仅供流程/续跑验证）。"""
        handler = step_handler or self._mock_handler
        if self.checkpoint is None:
            self.new_task()
        cp = self.checkpoint
        steps = TASK_STEPS
        self._step_index = max(self._step_index, steps.index(cp.step))
        attempts = 0

        while self._step_index < len(steps):
            step = steps[self._step_index]
            cp.state = "RUNNING"
            cp.step = step
            attempts += 1
            try:
                outcome = handler(self, step, cp)
                if isinstance(outcome, dict) and outcome.get("needs_human"):
                    cp.state = "NEEDS_HUMAN"
                    cp.last_error = str(outcome.get("reason", "需要人工处理"))
                    self.store.save(cp)
                    return TaskResult(cp.task_id, cp.state, step, attempts, cp.last_error)
            except Exception as error:
                decision = self.retry.decide(cp.attempt, error)
                cp.attempt = decision.attempt
                cp.last_error = decision.reason
                if decision.action == "give_up":
                    cp.state = decision.final_state or "FAILED"
                    self.store.save(cp)
                    return TaskResult(cp.task_id, cp.state, step, attempts, decision.reason)
                self.store.save(cp)
                self.retry.wait_before_retry(decision)
                continue  # 同一 step 重试（bounded）

            self._step_index += 1
            self.store.save(cp)  # 每步 checkpoint（§20）
            if pause_after_step and step == pause_after_step:
                cp.state = "PAUSED"
                self.store.save(cp)
                return TaskResult(cp.task_id, cp.state, step, attempts, "PAUSED at " + step)

        cp.state = "SUCCESS"
        cp.step = "DONE"
        cp.last_error = ""
        self.store.save(cp)
        return TaskResult(cp.task_id, cp.state, "DONE", attempts, "ok")

    # ---- V0.1 Mock handler：无业务行为（§19 框架存在即可） ----
    @staticmethod
    def _mock_handler(engine: "TaskEngine", step: str, cp: Checkpoint) -> None:
        if step == "NAVIGATE":
            # 模拟导航等待，验证流程可中断/续跑
            time.sleep(0.01)
        return None
