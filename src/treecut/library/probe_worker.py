"""P1: Asset probe worker — ffprobe metadata + full SHA256 fingerprint.

断点续跑: claim_probe() 以事务方式领取一个 pending/failed 任务并置为 running；
complete/fail 落库；进程中断后剩余 running 由 recover_interrupted_probes() 收回。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.library.assets import AssetsManager
from treecut.media.probe import MediaProbe, probe_media
from treecut.platform.paths import RuntimePaths


@dataclass(frozen=True)
class ProbeRunResult:
    probed: int = 0
    failed: int = 0
    skipped: int = 0
    remaining: int = 0
    errors: tuple[str, ...] = ()
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _locate_ffprobe(paths: RuntimePaths) -> Path:
    """Locate ffprobe: bundled tools/win32 first, then PATH fallback.

    The bundled binary ships with the installer; the git repo excludes it,
    so development/CI environments fall back to a PATH ffprobe (第二阶段:
    "不允许硬编码盘符"，工具位置可配置).
    """
    import shutil
    from treecut.media.probe import bundled_ffprobe
    try:
        return bundled_ffprobe(paths.install_root)
    except FileNotFoundError:
        found = shutil.which("ffprobe")
        if not found:
            raise FileNotFoundError(
                "缺少 ffprobe：仓库未内置 ffmpeg 二进制，请在 PATH 安装 ffprobe "
                "或在 install_root/tools/win32 放置 ffprobe.exe"
            )
        return Path(found)


class ProbeWorker:
    """Claims pending asset probes and writes ffprobe metadata + full hash."""

    def __init__(self, paths: RuntimePaths | None = None, manager: AssetsManager | None = None,
                 recover_interrupted: bool = True, pipeline_version: str = "P1.1"):
        self.paths = paths or RuntimePaths.discover()
        self.manager = manager or AssetsManager()
        self.ffprobe = _locate_ffprobe(self.paths)
        self.pipeline_version = pipeline_version
        if recover_interrupted:
            self.manager.recover_interrupted_probes()

    def run(self, limit: int = 50) -> ProbeRunResult:
        import time
        started = time.perf_counter()
        probed = failed = skipped = 0
        errors: list[str] = []

        # Ensure every available video media has an asset row before claiming,
        # so a bare --catalog-scan followed by --probe-assets works end to end.
        self.manager.ensure_all_video_assets()

        from treecut.library.processing_state import ProcessingState
        ps = ProcessingState(assets=self.manager)
        ps.ensure_asset_stages_all()

        for _ in range(limit):
            claimed = self.manager.claim_probe()
            if claimed is None:
                break
            media_id = claimed["media_id"]
            abs_path = claimed["absolute_path"]
            asset_id = claimed.get("asset_id") or self._asset_id_for(media_id)
            # 幂等：probe/fingerprint 已 DONE 且版本一致 → 跳过
            decision = ps.should_process(
                asset_id, "probe",
                pipeline_version=self.pipeline_version,
                input_fingerprint=claimed.get("fingerprint_quick", ""))
            if decision == "SKIP_ALREADY_DONE":
                skipped += 1
                continue
            try:
                ps.mark_processing(asset_id, "probe", reason="worker 领取")
                probe = probe_media(Path(abs_path), self.ffprobe)
                self.manager.complete_probe(media_id, probe.to_dict())
                # 分层哈希：仅疑似重复/大文件才做 full SHA256（避免 3TB 全量读盘）
                hashed = self.manager.finalize_fingerprint(media_id, abs_path)
                ps.mark_done(asset_id, "probe", reason="ffprobe 采集完成",
                             model_name="ffprobe", model_version="8.x",
                             pipeline_version=self.pipeline_version,
                             input_fingerprint=claimed.get("fingerprint_quick", ""),
                             result_count=1)
                if hashed:
                    ps.mark_done(asset_id, "fingerprint", reason="完整 SHA256",
                                 algorithm_version="sha256-4MiB",
                                 pipeline_version=self.pipeline_version,
                                 input_fingerprint=claimed.get("fingerprint_quick", ""),
                                 result_count=1)
                probed += 1
            except Exception as exc:
                self.manager.fail_probe(media_id, str(exc))
                # 同步 lifecycle：assets 侧达到重试上限会转 skipped，这里对齐
                final_status = self._probe_final_status(media_id)
                if final_status == "skipped":
                    ps.mark_skipped(asset_id, "probe",
                                    reason="损坏/不支持，超过重试上限跳过")
                else:
                    ps.mark_failed(asset_id, "probe", reason=str(exc)[:200],
                                   error_message=str(exc)[:500])
                failed += 1
                if len(errors) < 20:
                    errors.append(f"{Path(abs_path).name}: {exc}")

        remaining = len(self.manager.pending_probes(limit=1000))
        return ProbeRunResult(
            probed=probed, failed=failed, skipped=skipped, remaining=remaining,
            errors=tuple(errors), seconds=round(time.perf_counter() - started, 3),
        )

    def _asset_id_for(self, media_id: int) -> str:
        with self.manager._connect() as connection:
            row = connection.execute(
                "SELECT asset_id FROM assets WHERE media_id=?", (media_id,)
            ).fetchone()
        return row["asset_id"] if row else ""

    def _probe_final_status(self, media_id: int) -> str:
        with self.manager._connect() as connection:
            row = connection.execute(
                "SELECT probe_status FROM assets WHERE media_id=?", (media_id,)
            ).fetchone()
        return row["probe_status"] if row else ""
