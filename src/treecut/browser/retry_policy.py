"""XHS Work Browser V0.1 — 统一 Bounded Retry Policy（§22/24/25）。

默认节奏：
  attempt 1: normal
  attempt 2: retry after delay
  attempt 3: page refresh / state reset
  仍失败 → FAILED 或 NEEDS_HUMAN

硬停（§24）：SESSION_EXPIRED / ACCOUNT_IDENTITY_MISMATCH / captcha / PAGE_STRUCTURE_CHANGED
  → 直接 NEEDS_HUMAN，不自动猜测。
自动恢复（§25）：NETWORK_TIMEOUT / PAGE_LOAD_TIMEOUT / work tab crash → bounded retry/refresh/renavigate。

禁止无限循环重试。
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from treecut.browser.errors import (
    AUTO_RECOVER_CATEGORIES,
    HARD_STOP_CATEGORIES,
    ErrorCategory,
    classify,
)


@dataclass
class RetryDecision:
    action: str  # "normal" | "retry" | "refresh_retry" | "give_up"
    final_state: str | None = None  # "FAILED" | "NEEDS_HUMAN"（give_up 时）
    attempt: int = 1
    reason: str = ""


class BoundedRetry:
    def __init__(self, max_attempts: int = 3, delay_seconds: float = 2.0):
        if not (1 <= max_attempts <= 5):
            raise ValueError("max_attempts 必须在 1–5 之间")
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds

    def decide(self, attempt: int, error: BaseException) -> RetryDecision:
        category = classify(error)
        reason = f"{category.value}: {str(error)[:120]}"

        # 硬停：不得自动猜测解决（§24）
        if category in HARD_STOP_CATEGORIES:
            return RetryDecision(action="give_up", final_state="NEEDS_HUMAN",
                                 attempt=attempt, reason=reason)

        # 非自动恢复分类且不是最后一次：继续重试节奏
        if attempt >= self.max_attempts:
            auto = category in AUTO_RECOVER_CATEGORIES
            return RetryDecision(
                action="give_up",
                final_state="FAILED" if auto else "NEEDS_HUMAN",
                attempt=attempt, reason=reason,
            )

        # 节奏：attempt 2 → 延时重试；attempt 3 → refresh/state reset 后重试
        if attempt == 1:
            action = "retry"
        else:
            action = "refresh_retry"
        return RetryDecision(action=action, attempt=attempt + 1, reason=reason)

    def wait_before_retry(self, decision: RetryDecision) -> None:
        if decision.action in {"retry", "refresh_retry"}:
            time.sleep(self.delay_seconds)
