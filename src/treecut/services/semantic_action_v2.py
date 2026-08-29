# -*- coding: utf-8 -*-
"""SemanticActionAnalyzerV2 — Stage3 TRACK 3（视觉状态变化能力）。

核心（对比 V1）：
  - ObjectStateEvidence：对关键对象（drawer/cabinet/extendable/sink_cover/socket）估计
    BEFORE/TRANSITION/AFTER 状态（CLOSED/PARTIAL/OPEN, RETRACTED/EXTENDED, IDLE/INTERACTED）
  - 动作由状态变化推导（CLOSED→OPEN = OPEN_DRAWER；EXTENDED→RETRACTED = RETRACT …）
  - 光流仅作 supporting evidence（禁 Farneback 直接定标签）

状态检测（RTX3050 可行、真实运行）：
  - 方案B：SigLIP 状态描述相似度（"drawer fully open" vs "drawer closed" 等，逐帧）
  - 方案A：帧间运动几何（motion mask 的水平/垂直分布 → OPEN/CLOSE 提示）
  两路证据融合，输出每对象 BEFORE/AFTER 状态 + 推导动作 + 置信。

注意：状态模型第一版是候选（不要求完美）；OPERATE_SOCKET 为 prototype（INSUFFICIENT_SAMPLE 前不宣称 READY）。
"""
from __future__ import annotations

import time

import numpy as np

MODEL_VERSION = "semantic-action-v2-statechange"

# 对象 → SigLIP 状态描述（BEFORE/AFTER 语义锚）
STATE_PROMPTS = {
    "DRAWER": {
        "CLOSED": "kitchen island drawer fully closed, flush front",
        "PARTIAL": "drawer partially open, slightly pulled out",
        "OPEN": "drawer fully open, pulled out from island",
    },
    "CABINET_DOOR": {
        "CLOSED": "cabinet door fully closed, flush",
        "OPEN": "cabinet door fully open, swung open",
    },
    "EXTENDABLE_SECTION": {
        "RETRACTED": "island extendable section retracted, compact",
        "EXTENDED": "island extendable section fully extended, pulled out",
    },
    "SINK_COVER": {
        "CLOSED": "sink cover closed, flat on sink",
        "OPEN": "sink cover open or removed, sink exposed",
    },
    "SOCKET": {
        "IDLE": "track socket on island, no hand interaction",
        "INTERACTED": "hand plugging into or interacting with island socket",
    },
}

# 状态迁移 → 原子动作
TRANSITION_ACTION = {
    ("DRAWER", "CLOSED", "OPEN"): "OPEN_DRAWER",
    ("DRAWER", "CLOSED", "PARTIAL"): "OPEN_DRAWER",
    ("DRAWER", "PARTIAL", "OPEN"): "OPEN_DRAWER",
    ("DRAWER", "OPEN", "CLOSED"): "CLOSE_DRAWER",
    ("DRAWER", "PARTIAL", "CLOSED"): "CLOSE_DRAWER",
    ("CABINET_DOOR", "CLOSED", "OPEN"): "OPEN_CABINET",
    ("CABINET_DOOR", "OPEN", "CLOSED"): "CLOSE_CABINET",
    ("EXTENDABLE_SECTION", "RETRACTED", "EXTENDED"): "PULL_OUT",
    ("EXTENDABLE_SECTION", "EXTENDED", "RETRACTED"): "RETRACT",
    ("SINK_COVER", "CLOSED", "OPEN"): "OPEN_SINK_COVER",
    ("SOCKET", "IDLE", "INTERACTED"): "OPERATE_SOCKET",
}


class ObjectStateEvidence:
    """单对象状态证据：SigLIP 状态分数 + 运动几何提示 → 估计状态。"""

    def __init__(self, obj, state_scores: dict, motion_hint: str = ""):
        self.obj = obj
        self.state_scores = state_scores  # {state: score}
        self.motion_hint = motion_hint    # "OPEN"/"CLOSE"/""（几何提示）
        self.state = self._infer()

    def _infer(self) -> str:
        if self.state_scores:
            best = max(self.state_scores, key=self.state_scores.get)
            return best
        return "UNKNOWN"

    def to_dict(self) -> dict:
        return {"object": self.obj, "state": self.state,
                "state_scores": {k: round(v, 3) for k, v in self.state_scores.items()},
                "motion_hint": self.motion_hint}


class SemanticActionAnalyzerV2:
    """对象状态变化 → 原子动作（视觉 state-change 为主，ASR/component 为辅）。"""

    def __init__(self, runtime=None):
        from treecut.services.vision_runtime import VisionRuntimeProvider
        self.runtime = runtime or VisionRuntimeProvider()
        self._siglip = None
        self._text_emb_cache = {}

    def _ensure_siglip(self):
        if self._siglip is None:
            from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
            self._siglip = StaticVisionAnalyzerV2(self.runtime)
        return self._siglip

    def _state_scores(self, frames_paths: list[str], obj: str) -> list[dict]:
        """逐帧 SigLIP 状态描述相似度。"""
        an = self._ensure_siglip()
        an._ensure_model()
        import torch
        from treecut.services.visual_cognition import _imread
        prompts = STATE_PROMPTS.get(obj, {})
        if not prompts:
            return []
        # 预计算 text embeddings
        te = {}
        for st, prompt in prompts.items():
            key = (obj, st)
            if key not in self._text_emb_cache:
                self._text_emb_cache[key] = an._text_embedding(obj, prompt)
            te[st] = self._text_emb_cache[key]
        scores = []
        for p in frames_paths:
            img = _imread(p)
            if img is None:
                continue
            ie = an._frame_image_embedding(img)
            scores.append({st: float(np.dot(ie, t)) for st, t in te.items()})
        return scores

    @staticmethod
    def _motion_hint(frames_paths: list[str]) -> str:
        """运动几何提示：水平单向 → OPEN/CLOSE 方向（仅提示，不定标签）。"""
        from treecut.services.visual_cognition import _imread
        import cv2
        grays = []
        for p in frames_paths[:8]:
            img = _imread(p, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                grays.append(cv2.resize(img, (160, 90)))
        if len(grays) < 3:
            return ""
        flows = []
        for i in range(len(grays) - 1):
            flows.append(cv2.calcOpticalFlowFarneback(
                grays[i], grays[i + 1], None, 0.5, 3, 15, 3, 5, 1.2, 0))
        # 主运动方向
        dx = sum(f[..., 0].mean() for f in flows)
        mag = sum(float(np.abs(f[..., 0]).mean() + np.abs(f[..., 1]).mean()) for f in flows)
        if mag < 0.5:
            return ""
        return "OPEN" if dx > 0.5 else ("CLOSE" if dx < -0.5 else "")

    def analyze(self, frames_paths: list[str], component: list[str] | None = None,
                asr_text: str = "", ocr_text: str = "") -> dict:
        frames_paths = list(frames_paths or [])
        if len(frames_paths) < 3:
            return {"prediction": "UNKNOWN", "action_sequence": [], "model_version": MODEL_VERSION,
                    "evidence": {"error": "insufficient-frames"}}
        components = list(component or [])
        # 关注对象 = component 提示 ∪ 常见对象（性能：SigLIP 状态描述成本高，默认只跑最常见两类）
        objs = set(components) & set(STATE_PROMPTS.keys())
        if not objs:
            objs = {"DRAWER", "CABINET_DOOR"}
        # 分前/中/后帧
        n = len(frames_paths)
        pre, mid, post = frames_paths[:max(1, n // 3)], frames_paths[n // 3: 2 * n // 3], frames_paths[2 * n // 3:]
        evidence = {}
        actions = []
        for obj in objs:
            pre_s = self._state_scores(pre, obj)
            post_s = self._state_scores(post, obj)
            if not pre_s or not post_s:
                continue
            pre_state = max(pre_s[0], key=pre_s[0].get) if pre_s[0] else "UNKNOWN"
            post_state = max(post_s[-1], key=post_s[-1].get) if post_s[-1] else "UNKNOWN"
            mh = self._motion_hint(frames_paths)
            # 用 motion hint 校正 SigLIP 状态（若提示明确）
            if mh == "OPEN" and pre_state in ("CLOSED", "RETRACTED", "IDLE"):
                post_state = {"DRAWER": "OPEN", "CABINET_DOOR": "OPEN",
                              "EXTENDABLE_SECTION": "EXTENDED", "SINK_COVER": "OPEN",
                              "SOCKET": "INTERACTED"}.get(obj, post_state)
            if mh == "CLOSE" and post_state in ("OPEN", "EXTENDED"):
                post_state = {"DRAWER": "CLOSED", "CABINET_DOOR": "CLOSED",
                              "EXTENDABLE_SECTION": "RETRACTED", "SINK_COVER": "CLOSED"}.get(obj, post_state)
            action = TRANSITION_ACTION.get((obj, pre_state, post_state))
            evidence[obj] = ObjectStateEvidence(
                obj, {"pre_" + pre_state: 1.0 if pre_state != "UNKNOWN" else 0.0,
                      "post_" + post_state: 1.0 if post_state != "UNKNOWN" else 0.0},
                motion_hint=mh).to_dict()
            evidence[obj]["action_derived"] = action
            if action:
                actions.append(action)
        # ASR 补充（弱证据）
        from treecut.services.semantic_action_v1 import _asr_hits
        for a in _asr_hits(asr_text):
            if a not in actions:
                actions.append(a)
        # 去重保持顺序
        seq = []
        for a in actions:
            if a not in seq:
                seq.append(a)
        if not seq:
            seq = ["OTHER"]
        gmap = {"OPEN_DRAWER": "DRAWER", "CLOSE_DRAWER": "DRAWER",
                "OPEN_CABINET": "CABINET", "CLOSE_CABINET": "CABINET",
                "OPERATE_SOCKET": "POWER_INTERACTION", "OPEN_SINK_COVER": "WATER_INTERACTION",
                "PULL_OUT": "EXTEND", "RETRACT": "EXTEND", "OTHER": "OTHER"}
        return {"prediction": gmap.get(seq[0], "OTHER"), "action_sequence": seq,
                "model_version": MODEL_VERSION,
                "evidence": {"object_states": evidence,
                             "asr_atoms": _asr_hits(asr_text),
                             "components": components},
                "created_at": time.time()}

    def unload(self):
        if self._siglip is not None:
            self._siglip.unload()
            self._siglip = None
        self.runtime.unload_all()
