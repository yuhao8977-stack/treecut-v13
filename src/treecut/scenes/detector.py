"""P2: Scene detection engine (PySceneDetect ContentDetector).

输出 segments（start_ms/end_ms/scene_no），算法版本记录。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SceneDetectResult:
    segments: tuple[dict, ...]
    seconds: float = 0.0
    algorithm_version: str = "scenedetect-0.7-contentdetector"

    def to_dict(self) -> dict:
        return {"segments": self.segments, "seconds": self.seconds,
                "algorithm_version": self.algorithm_version}


class SceneDetector:
    """Wrap PySceneDetect; falls back to uniform split when unavailable."""

    ALGORITHM_VERSION = "scenedetect-0.7-contentdetector"

    def __init__(self, threshold: float = 27.0, min_scene_len_sec: float = 1.0):
        self.threshold = threshold
        self.min_scene_len_sec = min_scene_len_sec

    def detect(self, video_path: str | Path, duration_sec: float | None = None) -> SceneDetectResult:
        started = time.perf_counter()
        path = Path(video_path)
        segments = []
        try:
            from scenedetect import ContentDetector, detect
            scenes = detect(str(path), ContentDetector(threshold=self.threshold))
            for i, scene in enumerate(scenes):
                start = scene[0].get_seconds()
                end = scene[1].get_seconds()
                if end - start < self.min_scene_len_sec:
                    continue
                segments.append({
                    "scene_no": len(segments),
                    "start_ms": int(start * 1000),
                    "end_ms": int(end * 1000),
                })
            # 无场景切换（单镜头稳定素材）→ 均匀分段保证可用候选
            if not segments:
                if duration_sec is None:
                    from treecut.media.probe import probe_media, bundled_ffprobe
                    import shutil
                    try:
                        ff = bundled_ffprobe(self._install_root())
                    except Exception:
                        ff = Path(shutil.which("ffprobe") or "")
                    if ff.is_file():
                        duration_sec = probe_media(path, ff).duration
                if duration_sec is None:
                    duration_sec = 30.0
                segments = self._uniform_split(path, duration_sec)
                self._fell_back = True
        except Exception:
            # 降级：按均匀分段（无依赖时的兜底，算法版本明确标注）
            segments = self._uniform_split(path, duration_sec)
            self._fell_back = True
        return SceneDetectResult(
            segments=tuple(segments),
            seconds=round(time.perf_counter() - started, 3),
            algorithm_version=self.ALGORITHM_VERSION + ("-uniform" if getattr(self, "_fell_back", False) else ""),
        )

    def _install_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _uniform_split(self, path: Path, duration_sec: float | None) -> list[dict]:
        if duration_sec is None:
            duration_sec = 30.0
        seg_len = 5.0
        segs = []
        pos = 0.0
        while pos < duration_sec:
            end = min(pos + seg_len, duration_sec)
            if end - pos >= 1.0:
                segs.append({"scene_no": len(segs), "start_ms": int(pos * 1000),
                             "end_ms": int(end * 1000)})
            pos = end
        return segs
