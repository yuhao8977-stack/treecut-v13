# -*- coding: utf-8 -*-
"""TreeCut Stage 2 — TemporalActionAnalyzerV2（真实时序：帧间光流）。

使用多帧短序列的光流（Farneback）提取运动方向/幅度/能量，
对纯画面动作分类（不依赖 ASR）：
  STATIC / SPEAKING / EXTEND(PULL_OUT/RETRACT) / DRAWER(开合) / OTHER
输出：action_group + action_sequence[]（保留顺序）。
"""
from __future__ import annotations

import time

import numpy as np

MODEL_VERSION = "temporal-flow-v1"


class TemporalActionAnalyzerV2:
    """基于光流的时序动作分析（多帧短 clip）。"""

    def analyze(self, frames_paths: list[str]) -> dict:
        from treecut.services.visual_cognition import _imread
        import cv2
        grays = []
        for p in frames_paths[:10]:
            img = _imread(p, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                grays.append(cv2.resize(img, (160, 90)))
        if len(grays) < 3:
            return {"prediction": "UNKNOWN", "model_score": 0.0,
                    "action_sequence": [], "model_version": MODEL_VERSION,
                    "visual_evidence": "insufficient-frames"}
        # 光流能量与方向
        flow_mags, flow_angles = [], []
        for i in range(len(grays) - 1):
            flow = cv2.calcOpticalFlowFarneback(
                grays[i], grays[i + 1], None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
            flow_mags.append(mag)
            flow_angles.append(ang)
        mags = np.array([m.mean() for m in flow_mags])
        mean_mag = float(mags.mean())
        max_mag = float(mags.max())
        # 方向直方图（水平为主 → 拉出/缩回）
        dirs = np.concatenate([a.ravel() for a in flow_angles])
        hist = np.histogram(dirs, bins=8, range=(0, 360))[0]
        horiz = hist[0] + hist[4]  # 0°/180° 水平
        horiz_ratio = float(horiz / (hist.sum() + 1e-9))
        # 能量序列峰数
        peaks = sum(1 for i in range(1, len(mags) - 1)
                    if mags[i] > mags[i - 1] and mags[i] > mags[i + 1] and mags[i] > mean_mag + 0.01)
        if mean_mag < 0.015:
            group, seq, score = "STATIC", ["STATIC_DISPLAY"], 0.55
        elif mean_mag < 0.08 and horiz_ratio > 0.5:
            # 水平单向运动：可能是拉出/缩回
            group, seq, score = "EXTEND", ["PULL_OUT"], 0.4
        elif mean_mag < 0.12:
            group, seq, score = "SPEAKING", ["PERSON_SPEAKING"], 0.35
        elif mean_mag >= 0.12 and peaks >= 2:
            group, seq, score = "EXTEND", ["PULL_OUT", "RETRACT"], 0.45
        elif mean_mag >= 0.12:
            group, seq, score = "DRAWER", ["OPEN_DRAWER"], 0.3
        else:
            group, seq, score = "UNKNOWN", [], 0.15
        return {"prediction": group, "model_score": round(score, 3),
                "action_sequence": seq,
                "motion_profile": {"mean": round(mean_mag, 4), "max": round(max_mag, 4),
                                   "horiz_ratio": round(horiz_ratio, 3), "peaks": peaks},
                "model_version": MODEL_VERSION,
                "visual_evidence": "optical-flow-multiframe"}
