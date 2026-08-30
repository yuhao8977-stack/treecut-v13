"""XHS Work Browser V0.1 — Adapter 接口占位（§36/37）。

CreatorExportAdapter / CreatorObservationAdapter / SpotlightExportAdapter / MediaRecoveryAdapter
V0.1 全部 NOT_IMPLEMENTED，禁止提前实现。

统一契约（§37）：prepare() / verify_account() / execute() / validate() / save_snapshot() / report()
每个 Adapter 不得各自设计 Task 体系——统一由 TaskEngine 驱动。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Adapter(ABC):
    """未来采集/导出适配器统一契约（§37）。V0.1 仅定义接口。"""

    name = "adapter"
    status = "NOT_IMPLEMENTED"

    @abstractmethod
    def prepare(self) -> None:
        """校验依赖、准备资源。"""

    @abstractmethod
    def verify_account(self) -> str:
        """返回 ACCOUNT_IDENTITY_VALID / MISMATCH / UNKNOWN。"""

    @abstractmethod
    def execute(self) -> None:
        """执行采集/导出（业务行为，V0.1 不实现）。"""

    @abstractmethod
    def validate(self) -> bool:
        """对产物做校验（Validation Gate）。"""

    @abstractmethod
    def save_snapshot(self) -> None:
        """保存 RAW SNAPSHOT（IMMUTABLE，见 policies.RAW_SNAPSHOT_POLICY）。"""

    @abstractmethod
    def report(self) -> dict:
        """返回结构化报告（无敏感信息）。"""


class _NotImplementedAdapter(Adapter):
    def _raise(self) -> None:
        raise NotImplementedError(f"{self.name}: NOT_IMPLEMENTED（V0.1 禁止提前实现）")

    def prepare(self) -> None:
        self._raise()

    def verify_account(self) -> str:
        self._raise()

    def execute(self) -> None:
        self._raise()

    def validate(self) -> bool:
        self._raise()

    def save_snapshot(self) -> None:
        self._raise()

    def report(self) -> dict:
        self._raise()


class CreatorExportAdapter(_NotImplementedAdapter):
    name = "CreatorExportAdapter"
    status = "NOT_IMPLEMENTED"


class CreatorObservationAdapter(_NotImplementedAdapter):
    name = "CreatorObservationAdapter"
    status = "NOT_IMPLEMENTED"


class SpotlightExportAdapter(_NotImplementedAdapter):
    name = "SpotlightExportAdapter"
    status = "NOT_IMPLEMENTED"


class MediaRecoveryAdapter(_NotImplementedAdapter):
    name = "MediaRecoveryAdapter"
    status = "NOT_IMPLEMENTED"


ADAPTERS: dict[str, Adapter] = {
    a.name: a() for a in (
        CreatorExportAdapter, CreatorObservationAdapter,
        SpotlightExportAdapter, MediaRecoveryAdapter,
    )
}
