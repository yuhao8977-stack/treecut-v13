"""P2: Keyframe extraction — 每 segment 首/中/尾 + 清晰度/差异度筛选，存本地 cache。

GitHub 不上传缩略图（数据目录在 TREECUT_DATA_ROOT/cache/keyframes）。
"""
from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from treecut.platform.paths import RuntimePaths


@dataclass(frozen=True)
class KeyframeResult:
    frames: tuple[dict, ...]
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return {"frames": self.frames, "seconds": self.seconds}


def _sharpness(gray) -> float:
    """Laplacian 方差作为清晰度指标。"""
    try:
        import cv2
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        return 0.0


class KeyframeExtractor:
    """对 segment 抽 2–5 帧（首/中/尾 + 清晰度最高）。"""

    def __init__(self, paths: RuntimePaths | None = None, max_frames_per_segment: int = 5):
        self.paths = paths or RuntimePaths.discover()
        self.max_frames_per_segment = max_frames_per_segment

    def _out_dir(self, asset_id: str) -> Path:
        d = self.paths.cache / "keyframes" / asset_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def extract(self, video_path: str | Path, asset_id: str,
                segments: list[dict]) -> KeyframeResult:
        started = time.perf_counter()
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frames_out: list[dict] = []
        out_dir = self._out_dir(asset_id)

        try:
            for seg in segments:
                start_ms = int(seg.get("start_ms", 0))
                end_ms = int(seg.get("end_ms", 0))
                segment_id = seg["segment_id"]
                # 候选时间点：首/中/尾
                mid_ms = (start_ms + end_ms) // 2
                tail_ms = end_ms - int(1000 / fps)  # 末尾前一帧
                candidates = sorted({start_ms, mid_ms, tail_ms})
                picked = []
                for ts_ms in candidates:
                    if ts_ms < 0:
                        continue
                    frame = self._grab_frame(cap, fps, ts_ms)
                    if frame is None:
                        continue
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    sharp = _sharpness(gray)
                    bright = float(gray.mean())
                    ts_rel = max(0, ts_ms - start_ms)
                    rel = ts_rel / max(1, end_ms - start_ms)
                    picked.append({"ts_ms": ts_ms, "sharpness": sharp,
                                   "brightness": bright, "rel": rel})
                # 按 首/中/尾 优先 + 清晰度补充
                picked.sort(key=lambda p: (abs(p["rel"] - 0.0), abs(p["rel"] - 0.5),
                                           abs(p["rel"] - 1.0), -p["sharpness"]))
                picked = picked[: self.max_frames_per_segment]
                for p in picked:
                    fname = f"seg{seg.get('scene_no', 0):03d}_ms{p['ts_ms']:08d}.jpg"
                    fpath = out_dir / fname
                    frame = self._grab_frame(cap, fps, p["ts_ms"])
                    if frame is None:
                        continue
                    # 中文路径兼容：imencode + 二进制写盘（cv2.imwrite 对非 ASCII 静默失败）
                    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if not ok:
                        continue
                    fpath.write_bytes(buf.tobytes())
                    frames_out.append({
                        "segment_id": segment_id,
                        "timestamp_ms": p["ts_ms"],
                        "image_path": str(fpath),
                        "sharpness": round(p["sharpness"], 2),
                        "brightness": round(p["brightness"], 2),
                        "selected": 1,
                    })
        finally:
            cap.release()
        return KeyframeResult(frames=tuple(frames_out),
                              seconds=round(time.perf_counter() - started, 3))

    def _grab_frame(self, cap, fps: float, ts_ms: int):
        import cv2
        frame_idx = int(round(ts_ms / 1000.0 * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            # 回退到最后一帧附近
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_idx - 5))
            ok, frame = cap.read()
        return frame if ok else None
