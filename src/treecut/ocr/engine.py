"""P2: OCR engine — RapidOCR on keyframes, hard-subtitle detection.

禁止逐帧 OCR：只处理关键帧 + 必要抽样帧。
输出 text / bbox / subtitle_flag / coverage / confidence。
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class OcrResult:
    items: tuple[dict, ...]     # [{frame_id, frame_timestamp_ms, text, bbox, subtitle_flag, coverage, confidence}]
    subtitle_detected: bool = False
    model_name: str = "rapidocr-onnxruntime"
    model_version: str = "1.4.4"
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class OcrEngine:
    """RapidOCR 封装：检测画面文字与硬字幕。"""

    def __init__(self):
        self._engine = None

    def _lazy_load(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()

    def analyze_frames(self, frames: list[dict]) -> OcrResult:
        """frames: [{frame_id, timestamp_ms, image_path}]（来自 keyframes）。"""
        started = time.perf_counter()
        self._lazy_load()
        items = []
        frame_h = frame_w = 0
        subtitle_count = 0
        import cv2
        import numpy as np
        for f in frames:
            path = f.get("image_path")
            if not path or not Path(path).is_file():
                continue
            result, _ = self._engine(str(path))
            if not result:
                continue
            # 中文路径兼容：np.fromfile + imdecode（cv2.imread 对非 ASCII 静默返回 None）
            try:
                data = np.fromfile(str(path), dtype=np.uint8)
                img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            except Exception:
                img = cv2.imread(str(path))
            if img is not None:
                frame_h, frame_w = img.shape[:2]
            frame_area = max(1, frame_h * frame_w)
            for box, text, conf in result:
                if not text or not text.strip():
                    continue
                text = text.strip()
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                bbox = f"{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}"
                w = max(0, x2 - x1)
                h = max(0, y2 - y1)
                coverage = (w * h) / frame_area if frame_area else 0
                # 硬字幕判定：位于画面下半部且宽度占比大
                is_subtitle = bool(frame_h and y1 >= frame_h * 0.6 and w >= frame_w * 0.3)
                if is_subtitle:
                    subtitle_count += 1
                items.append({
                    "frame_id": f.get("frame_id"),
                    "frame_timestamp_ms": int(f.get("timestamp_ms", 0)),
                    "text": text,
                    "bbox": bbox,
                    "subtitle_flag": int(is_subtitle),
                    "coverage": round(coverage, 4),
                    "confidence": round(float(conf), 4),
                })
        return OcrResult(
            items=tuple(items),
            subtitle_detected=subtitle_count > 0,
            seconds=round(time.perf_counter() - started, 3),
        )
