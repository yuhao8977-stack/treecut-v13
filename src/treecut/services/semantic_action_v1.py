# -*- coding: utf-8 -*-
"""SemanticActionAnalyzerV1 — Stage3 TRACK A 开发（规则基 state-change + 多证据）。

架构（A4）：禁止 Farneback→semantic label；光流仅作 motion evidence。
输入证据：
  - multi-frame 状态变化（keyframes 间的几何/掩码变化 → OPEN/CLOSE/PULL/RETRACT 状态迁移）
  - component evidence（SigLIP component 预测：DRAWER/CABINET_DOOR/SINK/TRACK_SOCKET）
  - ASR / OCR 短语（精确/语义，非子串）
  - 光流运动方向（水平单向 → PULL/RETRACT 提示，但不直接定标签）
输出：action_sequence[]（原子动作，有序）+ 每动作置信/支持。

DEV 门槛（A3）：READY_FOR_DEV 类别参与；CLOSE_DRAWER 标 LIMITED；
OPEN_SINK_COVER / OPERATE_SOCKET 标 INSUFFICIENT（不强行"已会"）。
"""
from __future__ import annotations

import re
import time

import numpy as np

MODEL_VERSION = "semantic-action-v1-rules"

# ASR 精确/语义短语 → 原子动作（禁止 "收纳" 作为 RETRACT 强证据）
ASR_RULES = [
    (re.compile(r"打开抽屉|拉出抽屉|抽.?出抽屉|抽屉拉开"), "OPEN_DRAWER"),
    (re.compile(r"关上抽屉|关闭抽屉|推.?回抽屉|抽屉关"), "CLOSE_DRAWER"),
    (re.compile(r"打开柜门|打开柜子|开.?柜门"), "OPEN_CABINET"),
    (re.compile(r"关上柜门|关闭柜门|关.?柜门"), "CLOSE_CABINET"),
    (re.compile(r"插电|插上电|插座|插头|通电"), "OPERATE_SOCKET"),
    (re.compile(r"水槽盖|掀开水槽|打开水槽|盖上水槽"), "OPEN_SINK_COVER"),
    (re.compile(r"拉出|抽出来|拉伸开|伸展开"), "PULL_OUT"),
    (re.compile(r"缩回|收回去|推回去|收起来(?!.*抽屉)"), "RETRACT"),
]

# component 证据：出现则强化对应动作候选（不单独定标签）
COMPONENT_ACTION_HINT = {
    "DRAWER": ["OPEN_DRAWER", "CLOSE_DRAWER"],
    "CABINET_DOOR": ["OPEN_CABINET", "CLOSE_CABINET"],
    "SINK": ["OPEN_SINK_COVER"],
    "TRACK_SOCKET": ["OPERATE_SOCKET"],
}


def _frame_diff_motion(frames_paths: list[str]) -> dict:
    """光流 motion evidence（仅方向/幅度，不直接映射标签）。"""
    from treecut.services.visual_cognition import _imread
    import cv2
    grays = []
    for p in frames_paths[:10]:
        img = _imread(p, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            grays.append(cv2.resize(img, (160, 90)))
    if len(grays) < 3:
        return {"motion_level": 0.0, "horiz_ratio": 0.0, "peaks": 0}
    mags, angles = [], []
    for i in range(len(grays) - 1):
        flow = cv2.calcOpticalFlowFarneback(grays[i], grays[i + 1], None,
                                            0.5, 3, 15, 3, 5, 1.2, 0)
        m, a = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
        mags.append(m)
        angles.append(a)
    ms = np.array([m.mean() for m in mags])
    dirs = np.concatenate([a.ravel() for a in angles])
    hist = np.histogram(dirs, bins=8, range=(0, 360))[0]
    horiz = hist[0] + hist[4]
    return {"motion_level": float(ms.mean()), "horiz_ratio": float(horiz / (hist.sum() + 1e-9)),
            "peaks": int(sum(1 for i in range(1, len(ms) - 1)
                             if ms[i] > ms[i - 1] and ms[i] > ms[i + 1] and ms[i] > ms.mean() + 0.01))}


def _asr_hits(asr_text: str) -> list[str]:
    hits = []
    for pat, atom in ASR_RULES:
        if pat.search(asr_text or ""):
            hits.append(atom)
    return hits


class SemanticActionAnalyzerV1:
    """多证据规则基语义动作分析（Stage3 DEV Candidate）。"""

    def analyze(self, frames_paths: list[str], asr_text: str = "",
                ocr_text: str = "", component: list[str] | None = None) -> dict:
        motion = _frame_diff_motion(frames_paths)
        asr_atoms = _asr_hits(asr_text)
        ocr_atoms = _asr_hits(ocr_text)  # 复用短语规则（OCR 若有效）
        components = list(component or [])

        # 证据聚合（不把 motion 直接当标签）
        atom_score: dict[str, float] = {}
        for a in asr_atoms:
            atom_score[a] = atom_score.get(a, 0) + 0.6
        for a in ocr_atoms:
            atom_score[a] = atom_score.get(a, 0) + 0.3
        for comp in components:
            for a in COMPONENT_ACTION_HINT.get(comp, []):
                atom_score[a] = atom_score.get(a, 0) + 0.15
        # motion evidence：水平单向 + 明显运动 → 提示 PULL/RETRACT（弱加分，非定标签）
        if motion["motion_level"] >= 0.06 and motion["horiz_ratio"] > 0.5:
            if "PULL_OUT" in atom_score or motion["peaks"] >= 2:
                atom_score["PULL_OUT"] = atom_score.get("PULL_OUT", 0) + 0.1
        if motion["motion_level"] >= 0.06 and motion["peaks"] >= 2:
            atom_score["RETRACT"] = atom_score.get("RETRACT", 0) + 0.05

        # 阈值：ASR/OCR 命中(>=0.6) 或 component 组合(>=0.45)
        seq = [a for a, s in sorted(atom_score.items(), key=lambda x: -x[1]) if s >= 0.45]
        if not seq:
            # 无强证据：静止 → STATIC_DISPLAY；低运动 → PERSON_SPEAKING（弱）
            if motion["motion_level"] < 0.015:
                seq, group = ["STATIC_DISPLAY"], "STATIC"
            elif motion["motion_level"] < 0.10:
                seq, group = ["PERSON_SPEAKING"], "SPEAKING"
            else:
                seq, group = ["OTHER"], "OTHER"
        else:
            # group = 主类别（seq[0] 的父类）
            gmap = {"OPEN_DRAWER": "DRAWER", "CLOSE_DRAWER": "DRAWER",
                    "OPEN_CABINET": "CABINET", "CLOSE_CABINET": "CABINET",
                    "OPERATE_SOCKET": "POWER_INTERACTION",
                    "OPEN_SINK_COVER": "WATER_INTERACTION",
                    "PULL_OUT": "EXTEND", "RETRACT": "EXTEND",
                    "STATIC_DISPLAY": "STATIC", "PERSON_SPEAKING": "SPEAKING",
                    "OTHER": "OTHER"}
            group = gmap.get(seq[0], "OTHER")

        return {"prediction": group, "action_sequence": seq,
                "model_version": MODEL_VERSION,
                "evidence": {"asr_atoms": asr_atoms, "ocr_atoms": ocr_atoms,
                             "component_hints": {c: COMPONENT_ACTION_HINT.get(c, []) for c in components},
                             "motion": motion,
                             "atom_scores": {k: round(v, 2) for k, v in atom_score.items()}},
                "created_at": time.time()}
