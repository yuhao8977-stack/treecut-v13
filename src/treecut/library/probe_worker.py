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
                 recover_interrupted: bool = True):
        self.paths = paths or RuntimePaths.discover()
        self.manager = manager or AssetsManager()
        self.ffprobe = _locate_ffprobe(self.paths)
        if recover_interrupted:
            self.manager.recover_interrupted_probes()

    def run(self, limit: int = 50) -> ProbeRunResult:
        import time
        started = time.perf_counter()
        probed = failed = 0
        errors: list[str] = []

        # Ensure every available video media has an asset row before claiming,
        # so a bare --catalog-scan followed by --probe-assets works end to end.
        self.manager.ensure_all_video_assets()

        for _ in range(limit):
            claimed = self.manager.claim_probe()
            if claimed is None:
                break
            media_id = claimed["media_id"]
            abs_path = claimed["absolute_path"]
            try:
                probe = probe_media(Path(abs_path), self.ffprobe)
                self.manager.complete_probe(media_id, probe.to_dict())
                # Finalize exact fingerprint (full streaming SHA256)
                self.manager.finalize_fingerprint(media_id, abs_path)
                probed += 1
            except Exception as exc:
                self.manager.fail_probe(media_id, str(exc))
                failed += 1
                if len(errors) < 20:
                    errors.append(f"{Path(abs_path).name}: {exc}")

        remaining = len(self.manager.pending_probes(limit=1000))
        return ProbeRunResult(
            probed=probed, failed=failed, remaining=remaining,
            errors=tuple(errors), seconds=round(time.perf_counter() - started, 3),
        )
