# -*- coding: utf-8 -*-
"""PeoplePresenceAnalyzerV2 — Stage3 TRACK A 开发。

Primary：Ultralytics YOLOv8n（COCO person 类）段级多帧检测。
Fallback：SigLIP people_presence 文本相似度（当 YOLO 不可用/失败时）。
输出：YES / NO / UNKNOWN + max_person_conf / frame_hit_count / frames_sampled。
禁止输出姓名/年龄/性别/身份。

DEV 纪律：
  - threshold 冻结于 Stage3 DEV（Calibration333 + Stage3 60 人工真值），
    Fresh Holdout V1 只作 KNOWN BENCHMARK 参考，不用于选择。
  - 结果标注为 POST-REVIEW DEV TUNING DATA，不作独立评估。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import numpy as np

DEFAULT_YOLO_WEIGHTS = r"C:\Users\admin\github\treecut\yolov8n.pt"
DEFAULT_THRESHOLD = 0.70  # Stage3 DEV 冻结（A2: Cal333+Stage3 387 段网格，F1 94.2 / bacc 86.4）


@dataclass
class PeopleResult:
    prediction: str          # YES / NO / UNKNOWN
    max_person_conf: float = 0.0
    frame_hit_count: int = 0
    frames_sampled: int = 0
    threshold: float = DEFAULT_THRESHOLD
    provider: str = "yolo"
    model_version: str = "PEOPLE_ANALYZER_V2_DEV"
    created_at: float = field(default_factory=time.time)


class PeoplePresenceAnalyzerV2:
    """YOLO person 检测 → YES/NO；超时/异常 → SigLIP fallback → UNKNOWN。"""

    def __init__(self, runtime=None, weights: str = DEFAULT_YOLO_WEIGHTS,
                 threshold: float = DEFAULT_THRESHOLD, conf_floor: float = 0.10,
                 max_frames: int = 8):
        from treecut.services.vision_runtime import VisionRuntimeProvider
        self.runtime = runtime or VisionRuntimeProvider()
        self.weights = weights
        self.threshold = threshold
        self.conf_floor = conf_floor
        self.max_frames = max_frames
        self._model = None
        self._siglip = None

    # ---------------- YOLO ----------------
    def _ensure_yolo(self):
        if self._model is None:
            from ultralytics import YOLO
            self._model = YOLO(self.weights)
        return self._model

    def _yolo_frames(self, frames_paths: list[str]) -> tuple[list[float], bool]:
        """逐帧检测 person（COCO class 0）。

        返回 (hits, ok)：hits = 各帧最高 person conf（无检测则空）；
        ok = YOLO 至少成功推理一帧（True 表示正常运行，无人=合法 NO）。
        """
        from treecut.services.visual_cognition import _imread
        model = self._ensure_yolo()
        hits = []
        ran = False
        for p in frames_paths[: self.max_frames]:
            img = _imread(p)
            if img is None:
                continue
            try:
                res = model.predict(img, conf=self.conf_floor, classes=[0], verbose=False)
                ran = True
                if len(res) and res[0].boxes is not None and len(res[0].boxes):
                    confs = res[0].boxes.conf.cpu().numpy()
                    hits.append(float(confs.max()))
            except Exception:
                continue
        return hits, ran

    # ---------------- SigLIP fallback ----------------
    def _ensure_siglip(self):
        if self._siglip is None:
            from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
            self._siglip = StaticVisionAnalyzerV2(self.runtime)
        return self._siglip

    def _siglip_predict(self, frames_paths: list[str]) -> str:
        try:
            an = self._ensure_siglip()
            r = an.analyze(frames_paths[:5])
            return r.get("people_presence", {}).get("prediction", "UNKNOWN")
        except Exception:
            return "UNKNOWN"

    # ---------------- 主入口 ----------------
    def analyze(self, frames_paths: list[str]) -> PeopleResult:
        frames_paths = list(frames_paths or [])
        if not frames_paths:
            return PeopleResult("UNKNOWN", provider="none", frames_sampled=0)
        try:
            hits, ran = self._yolo_frames(frames_paths)
        except Exception:
            hits, ran = [], False
        if ran:
            # YOLO 正常运行：无 person 检测 = 合法 NO；不 fallback SigLIP
            if hits:
                best = max(hits)
                pred = "YES" if best >= self.threshold else "NO"
                return PeopleResult(pred, max_person_conf=round(best, 4),
                                    frame_hit_count=len(hits),
                                    frames_sampled=len(frames_paths[: self.max_frames]),
                                    threshold=self.threshold, provider="yolo")
            return PeopleResult("NO", max_person_conf=0.0, frame_hit_count=0,
                                frames_sampled=len(frames_paths[: self.max_frames]),
                                threshold=self.threshold, provider="yolo")
        # YOLO 技术失败（模型加载/推理异常/帧不可用）→ SigLIP fallback 或 UNKNOWN
        sig = self._siglip_predict(frames_paths)
        if sig in ("YES", "NO"):
            return PeopleResult(sig, provider="siglip_fallback",
                                frames_sampled=len(frames_paths[:5]))
        return PeopleResult("UNKNOWN", provider="technical_failure",
                            frames_sampled=len(frames_paths[: self.max_frames]))

    def summary(self) -> dict:
        return {"model_version": "PEOPLE_ANALYZER_V2_DEV",
                "weights": self.weights, "threshold": self.threshold,
                "provider": "YOLOv8n(person) primary + SigLIP fallback",
                "outputs": "YES/NO/UNKNOWN + max_person_conf/frame_hit_count/frames_sampled",
                "guard": "不输出姓名/年龄/性别/身份"}

    def unload(self):
        if self._model is not None:
            del self._model
            self._model = None
        if self._siglip is not None:
            self._siglip.unload()
            self._siglip = None
        self.runtime.unload_all()
