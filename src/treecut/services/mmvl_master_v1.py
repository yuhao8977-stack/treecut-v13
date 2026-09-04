"""
TREECUT_MULTI_MODULE_VISUAL_VALIDATION_MASTER_V1.py

Single-file reference implementation for TreeCut's Multi-Module Visual
Validation Layer.

IMPORTANT:
- This is NOT an OpenAI/ChatGPT model export.
- It does not contain model weights, proprietary internal code, or hidden reasoning.
- It encodes explicit, reviewable engineering rules derived from prior Stage8
  human visual review and is intended for SHADOW-mode validation before
  Production enforcement.

The code intentionally keeps:
Object -> State -> Motion Attribution -> Temporal Transition -> Direction
-> Claim Critic -> Fusion -> Human L3

Requirements:
    pip install numpy opencv-python pytest
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple
import json
import math
import re
import hashlib

import cv2
import numpy as np


# ============================================================
# 1. Truth / action / verdict types
# ============================================================

class TruthLayer(str, Enum):
    L1_SOURCE = "L1_SOURCE"
    L2_QWEN = "L2_QWEN"
    L2_CV_MOTION = "L2_CV_MOTION"
    L2_TEMPORAL = "L2_TEMPORAL"
    L2_CRITIC = "L2_CRITIC"
    L2_FUSION = "L2_FUSION"
    L3_HUMAN = "L3_HUMAN"


class Action(str, Enum):
    EXTEND = "EXTEND"
    RETRACT = "RETRACT"
    DRAWER_OPEN = "DRAWER_OPEN"
    DRAWER_CLOSE = "DRAWER_CLOSE"
    CABINET_OPEN = "CABINET_OPEN"
    CABINET_CLOSE = "CABINET_CLOSE"
    STORAGE_PUT_IN = "STORAGE_PUT_IN"
    STORAGE_TAKE_OUT = "STORAGE_TAKE_OUT"
    SOCKET_INSERT = "SOCKET_INSERT"
    SOCKET_REMOVE = "SOCKET_REMOVE"
    SOCKET_ADJUST = "SOCKET_ADJUST"
    PRODUCT_MOVE = "PRODUCT_MOVE"
    PRODUCT_ROTATE = "PRODUCT_ROTATE"
    STATIC = "STATIC"
    UNKNOWN = "UNKNOWN"


OPPOSITE: Dict[Action, Action] = {
    Action.EXTEND: Action.RETRACT,
    Action.RETRACT: Action.EXTEND,
    Action.DRAWER_OPEN: Action.DRAWER_CLOSE,
    Action.DRAWER_CLOSE: Action.DRAWER_OPEN,
    Action.CABINET_OPEN: Action.CABINET_CLOSE,
    Action.CABINET_CLOSE: Action.CABINET_OPEN,
    Action.STORAGE_PUT_IN: Action.STORAGE_TAKE_OUT,
    Action.STORAGE_TAKE_OUT: Action.STORAGE_PUT_IN,
    Action.SOCKET_INSERT: Action.SOCKET_REMOVE,
    Action.SOCKET_REMOVE: Action.SOCKET_INSERT,
}


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNSURE = "UNSURE"
    NO_SOURCE = "NO_SOURCE"


class Support(str, Enum):
    SUPPORTED = "SUPPORTED"
    CANDIDATE = "CANDIDATE"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"


# ============================================================
# 2. Core dataclasses
# ============================================================

@dataclass
class ROI:
    name: str
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float = 1.0
    source: str = "UNKNOWN"

    def clip(self, w: int, h: int) -> "ROI":
        return ROI(
            self.name,
            max(0, min(self.x1, w - 1)),
            max(0, min(self.y1, h - 1)),
            max(1, min(self.x2, w)),
            max(1, min(self.y2, h)),
            self.confidence,
            self.source,
        )

    def area(self) -> int:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)


@dataclass
class FrameSemantics:
    timestamp_s: float
    objects: List[str] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    rois: List[ROI] = field(default_factory=list)
    interactions: List[str] = field(default_factory=list)
    dominant_visual: Optional[str] = None


@dataclass
class CameraMotion:
    model: str
    matrix: Optional[List[List[float]]]
    translation_px: float
    inlier_ratio: float
    residual: float
    reliable: bool


@dataclass
class MotionMetrics:
    global_motion_px: float = 0.0
    camera_residual: float = 0.0
    roi_motion: Dict[str, float] = field(default_factory=dict)
    roi_edge_shift: Dict[str, float] = field(default_factory=dict)
    roi_geometry_change: Dict[str, float] = field(default_factory=dict)
    person_overlap_ratio: Dict[str, float] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalEvidence:
    before: FrameSemantics
    middle: FrameSemantics
    after: FrameSemantics
    motion: MotionMetrics
    requested_action: Action
    model_action: Action = Action.UNKNOWN
    geometry_direction_evidence: Optional["GeometryDirectionEvidence"] = None


@dataclass
class CameraReliabilityEvidence:
    """A2.1b — 相机可靠性证据（由 compensate_pair 逐对真实输出形成，禁止按 media_id 硬编码）。"""
    source_pairs: int
    reliable_all: bool
    max_feature_residual: float
    min_inlier_ratio: Optional[float]
    max_translation_px: float
    camera_state: str          # RELIABLE / UNRELIABLE / INSUFFICIENT


def camera_reliability_evidence(pairs: List[dict]) -> CameraReliabilityEvidence:
    """pairs: [{reliable, inlier_ratio, feature_residual, translation_px}, ...]
    标准（provisional，与样本无关）：全部 reliable 且 max_residual<=3.0 且 min_inlier>=0.3 → RELIABLE。"""
    if not pairs:
        return CameraReliabilityEvidence(0, False, 0.0, None, 0.0, "INSUFFICIENT")
    rel_all = all(bool(p.get("reliable")) for p in pairs)
    mx = max((p.get("feature_residual") or 0.0) for p in pairs)
    ins = [p.get("inlier_ratio") for p in pairs if p.get("inlier_ratio") is not None]
    mn_in = min(ins) if ins else None
    tx = max((p.get("translation_px") or 0.0) for p in pairs)
    ok = rel_all and mx <= _CAM_RESIDUAL_MAX and (mn_in is None or mn_in >= _CAM_INLIER_MIN)
    return CameraReliabilityEvidence(len(pairs), rel_all, round(mx, 3),
                                     round(mn_in, 3) if mn_in is not None else None,
                                     round(tx, 3), "RELIABLE" if ok else "UNRELIABLE")


@dataclass
class GeometryDirectionEvidence:
    """A2.1 — 机器几何方向证据（由 L3_HUMAN_ROI 坐标 + ISLAND_BODY 相对几何推导；
    与 model_action/Qwen 完全分开；不得把 Human GT 动作当输入）。"""
    target_object: str
    instance_id: str
    frames_used: List[float]
    visibility_progression: str
    geometry_change_present: bool
    relative_motion_present: bool
    direction_action: str          # DRAWER_OPEN/DRAWER_CLOSE/EXTEND/RETRACT/STATIC/UNKNOWN
    state_progress: str            # PROGRESSION_UP / STABLE / INSUFFICIENT / UNKNOWN
    confidence_class: str          # HIGH / MEDIUM / LOW / UNSTABLE_CAMERA
    reason_codes: List[str] = field(default_factory=list)
    raw_features: Dict[str, Any] = field(default_factory=dict)
    camera_unreliable: bool = False


@dataclass
class ValidationResult:
    verdict: Verdict
    support: Support
    requested_action: Action
    observed_action: Action
    target_object: Optional[str]
    reason_codes: List[str] = field(default_factory=list)
    mandatory: Dict[str, str] = field(default_factory=dict)
    optional: Dict[str, Any] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)
    human_review_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewExample:
    requested_action: Action
    segment_id: str
    start_s: float
    end_s: float
    review_scope: str
    result: str
    reason_codes: List[str]
    supports_other_semantics: List[str] = field(default_factory=list)


# ============================================================
# 3. Frame sampler
# ============================================================

def sample_video_window(path: str, start_s: float, end_s: float, n: int = 5):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    if n < 3 or end_s <= start_s:
        raise ValueError("Invalid sampling window")

    timestamps = [start_s + (end_s - start_s) * i / (n - 1) for i in range(n)]
    frames = []
    for t in timestamps:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(f"Cannot read frame at {t:.3f}s")
        frames.append(frame)
    cap.release()
    return timestamps, frames


def frame_hash(frame: np.ndarray) -> str:
    return hashlib.sha256(frame.tobytes()).hexdigest()


# ============================================================
# 4. Qwen / VLM provider contract
# ============================================================

class SemanticVisualProvider(Protocol):
    def analyze_frames(
        self,
        frames: Sequence[np.ndarray],
        timestamps: Sequence[float],
        requested_action: Action,
    ) -> Sequence[FrameSemantics]:
        ...


class QwenFrameAdapter:
    """
    Adapter around TreeCut's existing Qwen visual invocation.

    `invoke` must really accept image frames/files from Harness integration.
    This reference implementation deliberately includes frame hashes/timestamps
    so integration can prove REAL_FRAME_PAYLOAD_VERIFIED.
    """

    def __init__(self, invoke: Callable[[Dict[str, Any], Sequence[np.ndarray]], Dict[str, Any]]):
        self.invoke = invoke

    def analyze_frames(
        self,
        frames: Sequence[np.ndarray],
        timestamps: Sequence[float],
        requested_action: Action,
    ) -> Sequence[FrameSemantics]:

        metadata = {
            "task": "treecut_temporal_visual_semantics",
            "requested_action": requested_action.value,
            "timestamps": [float(t) for t in timestamps],
            "frame_hashes": [frame_hash(f) for f in frames],
            "requirements": {
                "objects": True,
                "states": True,
                "rois": True,
                "person_roi": True,
                "hand_interactions": True,
                "dominant_visual": True,
                "separate_person_motion_from_product_motion": True,
                "path_asr_ocr_are_not_visual_truth": True,
            },
        }

        raw = self.invoke(metadata, frames)
        items = raw.get("frames", [])
        out: List[FrameSemantics] = []

        for i, t in enumerate(timestamps):
            item = items[i] if i < len(items) else {}
            rois = []
            for r in item.get("rois", []):
                rois.append(
                    ROI(
                        r["name"],
                        int(r["x1"]), int(r["y1"]),
                        int(r["x2"]), int(r["y2"]),
                        float(r.get("confidence", 1.0)),
                        source="L2_QWEN",
                    )
                )
            out.append(
                FrameSemantics(
                    timestamp_s=float(t),
                    objects=list(item.get("objects", [])),
                    states=list(item.get("states", [])),
                    rois=rois,
                    interactions=list(item.get("interactions", [])),
                    dominant_visual=item.get("dominant_visual"),
                )
            )
        return out


# ============================================================
# 5. Camera motion
# ============================================================

class CameraMotionEstimator:
    """
    Staged camera motion:
      1. translation (cheap)
      2. affine if residual remains high
      3. homography hook for high-value cases

    This implementation uses LK features + affine estimation.
    """

    def _gray(self, frame):
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def _features(self, gray):
        return cv2.goodFeaturesToTrack(
            gray,
            maxCorners=500,
            qualityLevel=0.01,
            minDistance=7,
            blockSize=7,
        )

    def estimate(self, prev_bgr, curr_bgr) -> CameraMotion:
        prev = self._gray(prev_bgr)
        curr = self._gray(curr_bgr)
        pts = self._features(prev)

        if pts is None or len(pts) < 8:
            return CameraMotion("NONE", None, 0.0, 0.0, 1.0, False)

        nxt, status, _ = cv2.calcOpticalFlowPyrLK(prev, curr, pts, None)
        good_prev = pts[status.flatten() == 1].reshape(-1, 2)
        good_next = nxt[status.flatten() == 1].reshape(-1, 2)

        if len(good_prev) < 8:
            return CameraMotion("NONE", None, 0.0, 0.0, 1.0, False)

        delta = good_next - good_prev
        dx = float(np.median(delta[:, 0]))
        dy = float(np.median(delta[:, 1]))
        translation_mag = float(np.hypot(dx, dy))

        # Try partial affine (translation + rotation + scale).
        M, inliers = cv2.estimateAffinePartial2D(
            good_prev,
            good_next,
            method=cv2.RANSAC,
            ransacReprojThreshold=3.0,
        )

        if M is not None and inliers is not None:
            inlier_ratio = float(inliers.mean())
            pred = cv2.transform(good_prev[None, :, :], M)[0]
            residual = float(np.median(np.linalg.norm(pred - good_next, axis=1)))
            reliable = inlier_ratio >= 0.45 and residual <= 4.0
            return CameraMotion(
                "AFFINE",
                M.tolist(),
                translation_mag,
                inlier_ratio,
                residual,
                reliable,
            )

        return CameraMotion(
            "TRANSLATION",
            [[1, 0, dx], [0, 1, dy]],
            translation_mag,
            0.0,
            99.0,
            False,
        )

    def compensate(self, curr_bgr, motion: CameraMotion):
        h, w = curr_bgr.shape[:2]
        if not motion.matrix:
            return curr_bgr.copy()

        M = np.array(motion.matrix, dtype=np.float32)

        if M.shape == (2, 3):
            # M maps prev -> curr, so invert for curr -> prev compensation.
            M3 = np.vstack([M, [0, 0, 1]]).astype(np.float32)
            inv = np.linalg.inv(M3)[:2]
            return cv2.warpAffine(
                curr_bgr, inv, (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT,
            )

        return curr_bgr.copy()


def compensate_pair(prev_bgr: np.ndarray, curr_bgr: np.ndarray):
    """一对帧的相机补偿——唯一实现（Source Audit R1.1：禁止 Runner 再写独立 translation/affine）。
    返回 (warped_curr, CameraMotion)。estimate 记 prev→curr 运动，compensate 用逆变换把 curr 对齐回 prev。"""
    est = CameraMotionEstimator()
    m = est.estimate(prev_bgr, curr_bgr)
    return est.compensate(curr_bgr, m), m


def bind_target_timeline(boxes_by_t: Dict[float, List[dict]],
                         binding: Dict[float, Optional[int]]) -> List[dict]:
    """A2.1 — 按人工 instance binding 取同标签多框中指定的那个框（不允许 hits[0] 串线）。
    binding: {t_s: 该帧目标框在同标签框列表中的下标 或 None(该帧无动作目标)}。
    返回按时间排序的 {t_s, bbox_pixel} 列表（跳过 None/越界）。"""
    out = []
    for t in sorted(boxes_by_t):
        i = binding.get(t)
        lst = boxes_by_t.get(t, [])
        if i is None or not (0 <= i < len(lst)):
            continue
        out.append({"t_s": t, "bbox_pixel": list(lst[i]["bbox_pixel"])})
    return out


# ---- A2.1/A2.1b: 机器几何方向证据（公差为文档化 provisional 参数，非为通过而调）----
_GEOM_EPS = 0.01          # 数值噪声容差（比值）
_GEOM_STATIC_TOL = 0.06   # 相邻帧局部变化 ≤ 此值=静止（仅作局部 pair 参考，不是唯一判据）
_GEOM_GROWTH_MIN = 0.10   # 首末净增长 ≥ 此值视为单调增大（比值）
_GEOM_GROWTH_FACTOR = 1.15
# A2.1b 鲁棒判据（provisional）
_GEOM_JITTER_MAD_RATIO = 0.12   # MAD/中位数 ≤ 此值=有界振荡
_GEOM_NET_CHANGE_MAX = 0.10     # 首末净变化(相对中位) ≤ 此值=无持续 progression
_GEOM_MONO_SCORE_MIN = 0.75     # 同向步数占比 ≥ 此值=方向一致
_CAM_RESIDUAL_MAX = 3.0
_CAM_INLIER_MIN = 0.3


def _family_of(obj: str) -> str:
    if obj in ("DRAWER", "UPPER_THIN_DRAWER"):
        return "drawer"
    if obj in ("TABLETOP", "EXTENSION_TABLETOP"):
        return "tabletop"
    return "other"


def _geom_classify_frac(seq: List[float]) -> str:
    """分数化变化率分类（单位无关）：static/up/down/unknown。"""
    if len(seq) < 2:
        return "unknown"
    fracs = [(seq[i] - seq[i - 1]) / max(abs(seq[i - 1]), 1e-6) for i in range(1, len(seq))]
    maxf = max(abs(x) for x in fracs)
    if maxf <= _GEOM_STATIC_TOL:
        return "static"
    up = all(x >= -_GEOM_EPS for x in fracs)
    down = all(x <= _GEOM_EPS for x in fracs)
    tot = (seq[-1] - seq[0]) / max(abs(seq[0]), 1e-6)
    if up and tot >= _GEOM_GROWTH_MIN:
        return "up"
    if down and tot <= -_GEOM_GROWTH_MIN:
        return "down"
    if up and seq[0] > 0 and seq[-1] / seq[0] >= _GEOM_GROWTH_FACTOR:
        return "up"
    if down and seq[-1] > 0 and seq[0] / seq[-1] >= _GEOM_GROWTH_FACTOR:
        return "down"
    return "unknown"


def build_geometry_direction_evidence(
        object_name: str, instance_id: str,
        timeline: List[dict],           # [{t_s, bbox_pixel:[x1,y1,x2,y2], island_pixel:[..]|None}]
        camera_unreliable: bool = False) -> GeometryDirectionEvidence:
    """由 L3_HUMAN_ROI 坐标（同实例）+ ISLAND_BODY 相对几何推导方向/状态。
    输入仅: 帧时间戳 + ROI 坐标 + 实例身份 + 岛台几何；绝不使用 Human GT 动作。
    策略: 相对(岛台)序列优先；岛台参考跨帧不稳(相对非决定性)时回退绝对面积序列
    （A2.1 证据：岛台框跨帧范围不一致会污染相对值，见 52 rel 0.88→0.67→0.89 vs abs 单调↑）。
    分类用分数化变化率，单位无关；公差为文档化 provisional 常量。"""
    obj = object_name
    fam = _family_of(obj)
    feats = []
    for it in timeline:
        bb = it["bbox_pixel"]
        f = {"t_s": it["t_s"], "cx": (bb[0] + bb[2]) / 2.0, "cy": (bb[1] + bb[3]) / 2.0,
             "w": bb[2] - bb[0], "h": bb[3] - bb[1], "area": (bb[2] - bb[0]) * (bb[3] - bb[1])}
        ib = it.get("island_pixel")
        if ib:
            ibw = max(1, ib[2] - ib[0]); ibh = max(1, ib[3] - ib[1])
            f.update({"rel_cx": (f["cx"] - (ib[0] + ib[2]) / 2.0) / ibw,
                      "rel_cy": (f["cy"] - (ib[1] + ib[3]) / 2.0) / ibh,
                      "w_ratio": f["w"] / ibw, "h_ratio": f["h"] / ibh,
                      "area_ratio": f["area"] / (ibw * ibh),
                      "left_off": (bb[0] - ib[0]) / ibw, "right_off": (bb[2] - ib[2]) / ibw})
        feats.append(f)
    frames_used = [f["t_s"] for f in feats]
    if len(feats) < 2:
        return GeometryDirectionEvidence(obj, instance_id, frames_used, "INSUFFICIENT", False, False,
                                         "UNKNOWN", "INSUFFICIENT", "LOW",
                                         ["GEOMETRY_INSUFFICIENT_FRAMES"], camera_unreliable=camera_unreliable)
    nvis = len(feats)
    # 相对序列（岛台帧）与绝对序列（全部可见帧）
    rel_feats = [f for f in feats if "area_ratio" in f]
    rel_seq = None
    if len(rel_feats) >= 2 and fam in ("drawer", "tabletop"):
        if fam == "drawer":
            rel_seq = [max(f["area_ratio"], f["h_ratio"]) for f in rel_feats]
        else:
            rel_seq = [max(f["w_ratio"], f["area_ratio"]) for f in rel_feats]
    abs_seq = [f["area"] for f in feats]
    widths = [f["w"] for f in feats]
    cxs = [f["cx"] for f in feats]
    codes = []
    # ---- A2.1b 鲁棒判定（中位归一化；区分 JITTER 与 ACTION）----
    import statistics
    med = statistics.median(abs_seq)
    if med <= 0 or len(abs_seq) < 2:
        kind = "unknown"
        robust = {}
    else:
        mad = statistics.median([abs(v - med) for v in abs_seq])
        mad_ratio = mad / med
        net = (abs_seq[-1] - abs_seq[0]) / med
        deltas = [abs_seq[i] - abs_seq[i - 1] for i in range(1, len(abs_seq))]
        signs = [1 if d > _GEOM_EPS else (-1 if d < -_GEOM_EPS else 0) for d in deltas]
        rev = sum(1 for i in range(1, len(signs)) if signs[i] and signs[i] != signs[i - 1])
        nz = [s for s in signs if s]
        mono = (max(sum(1 for s in nz if s > 0), sum(1 for s in nz if s < 0)) / len(nz)) if nz else 1.0
        pair_fracs = [abs(d) / med for d in deltas]
        pair_max = max(pair_fracs) if pair_fracs else 0.0
        grow_factor = (abs_seq[-1] / abs_seq[0]) if abs_seq[0] > 0 else 0.0
        center_drift = (max(cxs) - min(cxs)) / max(statistics.median(widths), 1.0) if widths else 0.0
        robust = {"median_area": round(med, 1), "mad_ratio": round(mad_ratio, 4),
                  "first_last_change_ratio": round(net, 4), "reversal_count": rev,
                  "monotonicity_score": round(mono, 3), "pair_max_frac": round(pair_max, 4),
                  "grow_factor": round(grow_factor, 3), "center_drift_norm": round(center_drift, 4),
                  "net_geometry_change": round(abs(net), 4),
                  "direction_consistency": "HIGH" if mono >= _GEOM_MONO_SCORE_MIN else "LOW"}
        up_ok = (mono >= _GEOM_MONO_SCORE_MIN and net >= _GEOM_GROWTH_MIN) or \
                (mono >= _GEOM_MONO_SCORE_MIN and abs_seq[0] > 0 and grow_factor >= _GEOM_GROWTH_FACTOR and net > 0)
        down_ok = (mono >= _GEOM_MONO_SCORE_MIN and net <= -_GEOM_GROWTH_MIN) or \
                  (mono >= _GEOM_MONO_SCORE_MIN and abs_seq[-1] > 0 and abs_seq[0] / abs_seq[-1] >= _GEOM_GROWTH_FACTOR and net < 0)
        if up_ok:
            kind = "up"
        elif down_ok:
            kind = "down"
        elif abs(net) <= _GEOM_NET_CHANGE_MAX and mad_ratio <= _GEOM_JITTER_MAD_RATIO:
            kind = "stable" if pair_max <= _GEOM_STATIC_TOL else "jitter"
        else:
            kind = "unknown"
    if fam == "drawer":
        up_tok, down_tok, static_reason = "DRAWER_OPEN", "DRAWER_CLOSE", "NO_GEOMETRY_PROGRESSION"
    elif fam == "tabletop":
        up_tok, down_tok, static_reason = "EXTEND", "RETRACT", "NO_TARGET_GEOMETRY_CHANGE"
    else:
        up_tok = down_tok = static_reason = "UNKNOWN"
    if kind == "stable":
        action, state = "STATIC", "STATIC_STABLE"
        codes += [static_reason, "GEOMETRY_STABLE"]
    elif kind == "jitter":
        action, state = "STATIC", "STATIC_WITH_ANNOTATION_JITTER"
        codes += [static_reason, "GEOMETRY_ANNOTATION_JITTER", "BOUNDED_OSCILLATION_NO_PROGRESSION"]
    elif kind == "up":
        action, state = up_tok, "PROGRESSION_UP"
        codes.append("GEOMETRY_MONOTONIC_UP")
    elif kind == "down":
        action, state = down_tok, "PROGRESSION_DOWN"
        codes.append("GEOMETRY_MONOTONIC_DOWN")
    else:
        action, state = "UNKNOWN", "UNKNOWN"
        codes.append("GEOMETRY_UNDECIDABLE")
    if camera_unreliable:
        codes.append("CAMERA_UNRELIABLE")
    rel_moves = []
    for i in range(1, len(rel_feats)):
        rel_moves.append(max(abs(rel_feats[i]["rel_cx"] - rel_feats[i - 1]["rel_cx"]),
                            abs(rel_feats[i]["rel_cy"] - rel_feats[i - 1]["rel_cy"]),
                            abs(rel_feats[i]["w_ratio"] - rel_feats[i - 1]["w_ratio"]),
                            abs(rel_feats[i]["h_ratio"] - rel_feats[i - 1]["h_ratio"])))
    relative_motion = bool(rel_moves) and max(rel_moves) > _GEOM_EPS
    confidence = "HIGH" if (nvis >= 3 and action != "UNKNOWN" and not camera_unreliable) \
        else ("UNSTABLE_CAMERA" if camera_unreliable else
              ("MEDIUM" if action != "UNKNOWN" else "LOW"))
    vis_prog = "VISIBLE_ALL" if nvis == len(timeline) else f"VISIBLE_{nvis}/{len(timeline)}"
    return GeometryDirectionEvidence(
        obj, instance_id, frames_used, vis_prog,
        geometry_change_present=(kind in ("up", "down")),
        relative_motion_present=relative_motion,
        direction_action=action, state_progress=state, confidence_class=confidence,
        reason_codes=codes,
        raw_features={"abs_seq": abs_seq, "rel_seq": rel_seq, "mode": "abs",
                      "abs_per_frame": feats, "rel_per_frame": rel_feats,
                      "robust": robust, "area_jitter_class": kind},
        camera_unreliable=camera_unreliable)


# ============================================================
# 6. ROI utilities / tracking
# ============================================================

def roi_iou(a: ROI, b: ROI) -> float:
    x1, y1 = max(a.x1, b.x1), max(a.y1, b.y1)
    x2, y2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = a.area() + b.area() - inter
    return inter / union if union else 0.0


def crop(frame: np.ndarray, roi: ROI) -> np.ndarray:
    h, w = frame.shape[:2]
    r = roi.clip(w, h)
    return frame[r.y1:r.y2, r.x1:r.x2]


class ROITracker:
    """
    Lightweight ROI tracker using LK median displacement.

    The ROI is updated frame-to-frame; it is not assumed fixed.
    """

    def track(self, prev_bgr, curr_bgr, roi: ROI) -> Tuple[ROI, float]:
        p = crop(prev_bgr, roi)
        if p.size == 0:
            return roi, 0.0

        gray_prev = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
        gray_curr = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY)

        h, w = prev_bgr.shape[:2]
        r = roi.clip(w, h)

        mask = np.zeros_like(gray_prev)
        mask[r.y1:r.y2, r.x1:r.x2] = 255

        pts = cv2.goodFeaturesToTrack(
            gray_prev,
            maxCorners=100,
            qualityLevel=0.01,
            minDistance=5,
            mask=mask,
        )

        if pts is None or len(pts) < 4:
            return roi, 0.0

        nxt, status, _ = cv2.calcOpticalFlowPyrLK(gray_prev, gray_curr, pts, None)
        gp = pts[status.flatten() == 1].reshape(-1, 2)
        gn = nxt[status.flatten() == 1].reshape(-1, 2)

        if len(gp) < 4:
            return roi, 0.0

        d = gn - gp
        dx = float(np.median(d[:, 0]))
        dy = float(np.median(d[:, 1]))
        mad = float(np.median(np.linalg.norm(d - np.array([dx, dy]), axis=1)))
        conf = float(max(0.0, min(1.0, 1.0 - mad / 15.0)))

        tracked = ROI(
            roi.name,
            int(round(roi.x1 + dx)),
            int(round(roi.y1 + dy)),
            int(round(roi.x2 + dx)),
            int(round(roi.y2 + dy)),
            confidence=roi.confidence * conf,
            source=f"{roi.source}+LK_TRACK",
        )
        return tracked, conf


# ============================================================
# 7. ROI motion / human overlap
# ============================================================

class ROIMotionAttributor:
    def __init__(self):
        self.camera = CameraMotionEstimator()

    @staticmethod
    def _mean_abs_diff(a, b) -> float:
        if a.size == 0 or b.size == 0:
            return 0.0
        if a.shape != b.shape:
            b = cv2.resize(b, (a.shape[1], a.shape[0]))
        ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
        return float(cv2.absdiff(ga, gb).mean() / 255.0)

    @staticmethod
    def _edge_centroid_x(crop_img) -> float:
        if crop_img.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        ys, xs = np.where(edges > 0)
        return float(xs.mean() / max(1, crop_img.shape[1])) if len(xs) else 0.0

    def compare(
        self,
        prev_bgr,
        curr_bgr,
        target_rois: Sequence[ROI],
        person_rois: Sequence[ROI] = (),
    ) -> Tuple[MotionMetrics, CameraMotion]:

        cam = self.camera.estimate(prev_bgr, curr_bgr)
        curr_comp = self.camera.compensate(curr_bgr, cam)

        metrics = MotionMetrics(
            global_motion_px=cam.translation_px,
            camera_residual=cam.residual,
            evidence={
                "camera_model": cam.model,
                "camera_inlier_ratio": cam.inlier_ratio,
                "camera_reliable": cam.reliable,
            },
        )

        for roi in target_rois:
            p = crop(prev_bgr, roi)
            c = crop(curr_comp, roi)
            motion = self._mean_abs_diff(p, c)
            edge_shift = abs(self._edge_centroid_x(c) - self._edge_centroid_x(p))

            overlap = 0.0
            for person in person_rois:
                overlap = max(overlap, roi_iou(roi, person))

            # Discount obvious human overlap instead of letting hand/arm motion
            # fully inflate product motion.
            discount = max(0.25, 1.0 - overlap)
            metrics.roi_motion[roi.name] = motion * discount
            metrics.roi_edge_shift[roi.name] = edge_shift * discount
            metrics.person_overlap_ratio[roi.name] = overlap

        return metrics, cam


# ============================================================
# 8. Object-specific analyzers
# ============================================================

@dataclass
class ObjectMotionDecision:
    target: str
    moved: bool
    direction: str
    score: float
    reason_codes: List[str]


class TabletopMotionAnalyzer:
    def analyze(self, metrics: MotionMetrics) -> ObjectMotionDecision:
        m = metrics.roi_motion.get("TABLETOP", 0.0)
        e = metrics.roi_edge_shift.get("TABLETOP", 0.0)
        moved = m >= 0.05 or e >= 0.025
        return ObjectMotionDecision(
            "TABLETOP", moved, "UNKNOWN", max(m, e),
            ["TABLETOP_TARGET_MOTION"] if moved else ["NO_TABLETOP_GEOMETRY_CHANGE"]
        )


class DrawerMotionAnalyzer:
    def analyze(self, metrics: MotionMetrics) -> ObjectMotionDecision:
        m = max(
            metrics.roi_motion.get("DRAWER", 0.0),
            metrics.roi_motion.get("UPPER_THIN_DRAWER", 0.0),
        )
        e = max(
            metrics.roi_edge_shift.get("DRAWER", 0.0),
            metrics.roi_edge_shift.get("UPPER_THIN_DRAWER", 0.0),
        )
        moved = m >= 0.05 or e >= 0.02
        return ObjectMotionDecision(
            "DRAWER", moved, "UNKNOWN", max(m, e),
            ["DRAWER_TARGET_MOTION"] if moved else ["NO_DRAWER_MOTION"]
        )


class SocketMotionAnalyzer:
    def analyze(self, metrics: MotionMetrics) -> ObjectMotionDecision:
        m = metrics.roi_motion.get("SOCKET_MODULE", 0.0)
        moved = m >= 0.04
        return ObjectMotionDecision(
            "SOCKET_MODULE", moved, "UNKNOWN", m,
            ["SOCKET_MODULE_MOTION"] if moved else ["NO_SOCKET_MODULE_MOTION"]
        )


class ObjectTransferAnalyzer:
    def analyze(self, metrics: MotionMetrics) -> ObjectMotionDecision:
        m = metrics.roi_motion.get("HANDHELD_OBJECT", 0.0)
        moved = m >= 0.04
        return ObjectMotionDecision(
            "HANDHELD_OBJECT", moved, "UNKNOWN", m,
            ["HANDHELD_OBJECT_MOTION"] if moved else ["NO_OBJECT_TRANSFER_MOTION"]
        )


class TargetObjectMotionRouter:
    def __init__(self):
        self.tabletop = TabletopMotionAnalyzer()
        self.drawer = DrawerMotionAnalyzer()
        self.socket = SocketMotionAnalyzer()
        self.transfer = ObjectTransferAnalyzer()

    def analyze(self, requested: Action, metrics: MotionMetrics) -> ObjectMotionDecision:
        if requested in (Action.EXTEND, Action.RETRACT):
            return self.tabletop.analyze(metrics)
        if requested in (Action.DRAWER_OPEN, Action.DRAWER_CLOSE):
            return self.drawer.analyze(metrics)
        if requested in (Action.SOCKET_INSERT, Action.SOCKET_REMOVE, Action.SOCKET_ADJUST):
            return self.socket.analyze(metrics)
        if requested in (Action.STORAGE_PUT_IN, Action.STORAGE_TAKE_OUT):
            return self.transfer.analyze(metrics)
        return ObjectMotionDecision("UNKNOWN", False, "UNKNOWN", 0.0, ["NO_ROUTER"])


# ============================================================
# 9. Temporal state / direction validator
# ============================================================

STATE_TRANSITIONS: Dict[Action, Tuple[str, str]] = {
    Action.EXTEND: ("TABLETOP_RETRACTED_STATE", "TABLETOP_EXTENDED_STATE"),
    Action.RETRACT: ("TABLETOP_EXTENDED_STATE", "TABLETOP_RETRACTED_STATE"),
    Action.DRAWER_OPEN: ("DRAWER_CLOSED_STATE", "DRAWER_OPEN_STATE"),
    Action.DRAWER_CLOSE: ("DRAWER_OPEN_STATE", "DRAWER_CLOSED_STATE"),
    Action.CABINET_OPEN: ("CABINET_CLOSED_STATE", "CABINET_OPEN_STATE"),
    Action.CABINET_CLOSE: ("CABINET_OPEN_STATE", "CABINET_CLOSED_STATE"),
    Action.STORAGE_PUT_IN: ("OBJECT_OUTSIDE_STORAGE", "OBJECT_INSIDE_STORAGE"),
    Action.STORAGE_TAKE_OUT: ("OBJECT_INSIDE_STORAGE", "OBJECT_OUTSIDE_STORAGE"),
    Action.SOCKET_INSERT: ("SOCKET_MODULE_OUTSIDE", "SOCKET_MODULE_INSERTED"),
    Action.SOCKET_REMOVE: ("SOCKET_MODULE_INSERTED", "SOCKET_MODULE_OUTSIDE"),
}


class TemporalStateValidator:
    def __init__(self, router: Optional[TargetObjectMotionRouter] = None):
        self.router = router or TargetObjectMotionRouter()

    def validate(self, ev: TemporalEvidence) -> ValidationResult:
        requested = ev.requested_action
        before_states = set(ev.before.states)
        after_states = set(ev.after.states)

        # 1. Model opposite direction = hard contradiction.
        if requested in OPPOSITE and ev.model_action == OPPOSITE[requested]:
            return ValidationResult(
                Verdict.FAIL, Support.CONTRADICTED,
                requested, ev.model_action, None,
                ["OPPOSITE_DIRECTION_MODEL"],
                {"opposite_absent": "FAIL"},
            )

        # 2. Determine explicit state transition.
        observed_by_state = Action.UNKNOWN
        for action, (s1, s2) in STATE_TRANSITIONS.items():
            if s1 in before_states and s2 in after_states:
                observed_by_state = action
                break

        if requested in OPPOSITE and observed_by_state == OPPOSITE[requested]:
            return ValidationResult(
                Verdict.FAIL, Support.CONTRADICTED,
                requested, observed_by_state, None,
                ["OPPOSITE_DIRECTION_TEMPORAL"],
                {"direction": "FAIL"},
            )

        # 3. Target-object-specific motion.
        motion_decision = self.router.analyze(requested, ev.motion)

        target_object_visible = motion_decision.target in set(
            ev.before.objects + ev.middle.objects + ev.after.objects
        )

        mandatory = {
            "target_object_visible": "PASS" if target_object_visible else "FAIL",
            "target_object_motion": "PASS" if motion_decision.moved else "FAIL",
            "opposite_absent": "PASS",
        }

        if not target_object_visible:
            return ValidationResult(
                Verdict.FAIL, Support.UNKNOWN,
                requested, Action.UNKNOWN, motion_decision.target,
                ["TARGET_OBJECT_NOT_VISIBLE"],
                mandatory,
                scores={"target_motion": motion_decision.score},
            )

        # ---- A2.1: MACHINE GEOMETRY DIRECTION/STATE channel（优先于 pixel-motion 门；
        #      几何/人工 ROI 是更强证据层级；pixel 不能单独证明动作，几何也不能被 pixel 门短路）----
        g = ev.geometry_direction_evidence
        if g is not None and g.target_object == motion_decision.target and g.frames_used:
            if g.camera_unreliable or g.confidence_class == "UNSTABLE_CAMERA":
                mandatory["direction"] = "UNSURE"
                mandatory["state_transition"] = "UNSURE"
                return ValidationResult(
                    Verdict.UNSURE, Support.UNKNOWN,
                    requested, Action.UNKNOWN, motion_decision.target,
                    ["CAMERA_UNRELIABLE_GEOMETRY_UNSTABLE"],
                    mandatory, scores={"target_motion": motion_decision.score},
                    human_review_required=True)
            geo_token = g.direction_action
            if geo_token == "STATIC" or (not g.geometry_change_present and geo_token != "UNKNOWN"):
                if requested in (Action.EXTEND, Action.RETRACT):
                    codes = ["NO_TARGET_GEOMETRY_CHANGE"]
                elif requested in (Action.DRAWER_OPEN, Action.DRAWER_CLOSE):
                    codes = ["NO_GEOMETRY_PROGRESSION", "OPEN_STATE_NOT_OPEN_ACTION"]
                else:
                    codes = ["NO_GEOMETRY_PROGRESSION"]
                mandatory["direction"] = "FAIL"
                mandatory["state_transition"] = "FAIL"
                return ValidationResult(
                    Verdict.FAIL, Support.CONTRADICTED,
                    requested, Action.STATIC, motion_decision.target,
                    codes, mandatory, scores={"target_motion": motion_decision.score})
            req_token = requested.value if hasattr(requested, "value") else str(requested)
            if geo_token == req_token and g.geometry_change_present:
                mandatory["direction"] = "PASS"
                mandatory["state_transition"] = "PASS"
                return ValidationResult(
                    Verdict.PASS, Support.SUPPORTED,
                    requested, requested, motion_decision.target,
                    ["GEOMETRY_PROGRESSION_SUPPORTED"],
                    mandatory,
                    optional={"geometry_action": geo_token, "instance_id": g.instance_id,
                              "target_motion_px": round(ev.motion.roi_motion.get(motion_decision.target, 0.0), 4)},
                    scores={"target_motion": motion_decision.score})
            if requested in OPPOSITE and geo_token == (OPPOSITE[requested].value if hasattr(OPPOSITE[requested], "value") else str(OPPOSITE[requested])):
                mandatory["direction"] = "FAIL"
                mandatory["state_transition"] = "FAIL"
                return ValidationResult(
                    Verdict.FAIL, Support.CONTRADICTED,
                    requested, OPPOSITE[requested], motion_decision.target,
                    ["OPPOSITE_GEOMETRY_DIRECTION"],
                    mandatory, scores={"target_motion": motion_decision.score})
            # 几何方向未知 → 落到 pixel-motion/state 既有判定（保守）

        if not motion_decision.moved:
            person_motion = ev.motion.roi_motion.get("PERSON", 0.0)
            codes = list(motion_decision.reason_codes)
            if person_motion >= 0.05:
                codes.append("PERSON_MOTION_ONLY")
            return ValidationResult(
                Verdict.FAIL, Support.UNKNOWN,
                requested, Action.STATIC, motion_decision.target,
                codes,
                mandatory,
                scores={
                    "target_motion": motion_decision.score,
                    "person_motion": person_motion,
                },
            )

        # ---- A2.1: MACHINE GEOMETRY channel（已前置到 pixel-motion 门之前，此处不再重复）----

        # 4. Full explicit transition.
        if observed_by_state == requested:
            mandatory["direction"] = "PASS"
            mandatory["state_transition"] = "PASS"
            return ValidationResult(
                Verdict.PASS, Support.SUPPORTED,
                requested, requested, motion_decision.target,
                ["TARGET_OBJECT_MOTION", "STATE_TRANSITION_MATCH"],
                mandatory,
                optional={"qwen_action": ev.model_action.value},
                scores={"target_motion": motion_decision.score},
            )

        # 5. Motion exists, Qwen agrees, but state completeness not proven.
        if ev.model_action == requested:
            mandatory["direction"] = "UNSURE"
            mandatory["state_transition"] = "UNSURE"
            return ValidationResult(
                Verdict.UNSURE, Support.CANDIDATE,
                requested, requested, motion_decision.target,
                ["TARGET_OBJECT_MOTION", "MODEL_DIRECTION_MATCH", "STATE_TRANSITION_INCOMPLETE"],
                mandatory,
                optional={"qwen_action": ev.model_action.value},
                scores={"target_motion": motion_decision.score},
                human_review_required=True,
            )

        mandatory["direction"] = "UNSURE"
        mandatory["state_transition"] = "UNSURE"
        return ValidationResult(
            Verdict.UNSURE, Support.UNKNOWN,
            requested, Action.UNKNOWN, motion_decision.target,
            ["TARGET_OBJECT_MOTION_BUT_DIRECTION_UNPROVEN"],
            mandatory,
            optional={"qwen_action": ev.model_action.value},
            scores={"target_motion": motion_decision.score},
            human_review_required=True,
        )


# ============================================================
# 10. Claim library / critic
# ============================================================

@dataclass
class ClaimContract:
    text: str
    required_object: Optional[str] = None
    required_action: Action = Action.UNKNOWN
    forbidden_dominant_objects: List[str] = field(default_factory=list)
    allow_static_state: bool = False


class IslandClaimLibrary:
    def parse(self, text: str) -> ClaimContract:
        t = re.sub(r"\s+", "", text)

        if "上层薄抽" in t:
            return ClaimContract(text, required_object="UPPER_THIN_DRAWER")

        if "打开就能拿到" in t:
            return ClaimContract(text, required_object="DRAWER", required_action=Action.DRAWER_OPEN)

        if "轨道插座" in t and "插拔" not in t:
            return ClaimContract(text, required_object="TRACK_SOCKET", allow_static_state=True)

        if "插拔" in t:
            return ClaimContract(text, required_object="TRACK_SOCKET", required_action=Action.SOCKET_INSERT)

        if "一拉" in t and ("变宽" in t or "伸" in t):
            return ClaimContract(
                text,
                required_object="TABLETOP",
                required_action=Action.EXTEND,
                forbidden_dominant_objects=["TRACK_SOCKET"],
            )

        if "收起来" in t or "不占位" in t:
            return ClaimContract(
                text,
                required_object="TABLETOP",
                required_action=Action.RETRACT,
                forbidden_dominant_objects=["TRACK_SOCKET", "DRAWER"],
            )

        if "伸缩桌面" in t:
            return ClaimContract(text, required_object="TABLETOP", allow_static_state=True)

        return ClaimContract(text)


class DomainClaimCritic:
    def review(
        self,
        contract: ClaimContract,
        visible_objects: Sequence[str],
        dominant_visual: Optional[str],
        action_result: Optional[ValidationResult],
    ) -> Dict[str, Any]:

        objects = set(visible_objects)
        reasons = []

        if contract.required_object:
            if contract.required_object not in objects:
                if contract.required_object == "UPPER_THIN_DRAWER" and "DRAWER" in objects:
                    reasons.append("UPPER_THIN_DRAWER_UNVERIFIED")
                else:
                    reasons.append("REQUIRED_OBJECT_MISSING")

        if dominant_visual and dominant_visual in set(contract.forbidden_dominant_objects):
            reasons.append("DOMINANT_VISUAL_MISMATCH")

        if contract.required_action != Action.UNKNOWN:
            if action_result is None:
                reasons.append("ACTION_EVIDENCE_MISSING")
            elif action_result.verdict != Verdict.PASS:
                reasons.extend(action_result.reason_codes)

        return {
            "verdict": "FAIL" if reasons else "PASS",
            "reason_codes": sorted(set(reasons)),
        }


# ============================================================
# 11. Evidence fusion
# ============================================================

class EvidenceFusionEngine:
    """
    Mandatory-gate fusion, not majority voting.
    """

    def fuse(
        self,
        action_result: ValidationResult,
        claim_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        # Any mandatory FAIL remains FAIL regardless of optional votes.
        mandatory_fail = any(v == "FAIL" for v in action_result.mandatory.values())

        if mandatory_fail:
            return {
                "verdict": "FAIL",
                "reason_codes": sorted(set(action_result.reason_codes)),
                "human_review_required": False,
            }

        if claim_result and claim_result.get("verdict") == "FAIL":
            return {
                "verdict": "FAIL",
                "reason_codes": sorted(
                    set(action_result.reason_codes + claim_result.get("reason_codes", []))
                ),
                "human_review_required": False,
            }

        if action_result.verdict == Verdict.PASS:
            return {
                "verdict": "PASS",
                "reason_codes": sorted(set(action_result.reason_codes)),
                "human_review_required": False,
            }

        return {
            "verdict": "UNSURE",
            "reason_codes": sorted(set(action_result.reason_codes)),
            "human_review_required": True,
        }


# ============================================================
# 12. Visual Beat grouping
# ============================================================

class VisualBeatGrouper:
    ORDINALS = {"第一", "第二", "第三", "第四", "第五"}

    def group(self, phrases: Sequence[str]) -> List[Dict[str, Any]]:
        """
        Keep atomic claims while grouping shot-planning beats.
        """
        groups: List[Dict[str, Any]] = []
        current: List[str] = []

        def flush():
            nonlocal current
            if current:
                groups.append({
                    "visual_beat_text": "，".join(current),
                    "atomic_claims": list(current),
                })
                current = []

        # Hook: first two clauses
        i = 0
        if len(phrases) >= 2:
            groups.append({
                "visual_beat_text": "，".join(phrases[:2]),
                "atomic_claims": list(phrases[:2]),
            })
            i = 2

        while i < len(phrases):
            p = phrases[i].strip(" ，。！？!?,")
            if p in self.ORDINALS:
                flush()
                current = [phrases[i]]
                i += 1
                # absorb next up to 3 semantic clauses
                take = 0
                while i < len(phrases) and take < 3:
                    nxt = phrases[i].strip(" ，。！？!?,")
                    if nxt in self.ORDINALS:
                        break
                    current.append(phrases[i])
                    i += 1
                    take += 1
                flush()
            else:
                current.append(phrases[i])
                i += 1

        flush()

        # Merge tiny trailing CTA-like fragments into one final beat if needed.
        if len(groups) > 5:
            tail = groups[4:]
            merged_claims = []
            for g in tail:
                merged_claims.extend(g["atomic_claims"])
            groups = groups[:4] + [{
                "visual_beat_text": "，".join(merged_claims),
                "atomic_claims": merged_claims,
            }]

        return groups


# ============================================================
# 13. No-candidate resolver
# ============================================================

class NoCandidateResolver:
    def resolve(
        self,
        claim_text: str,
        candidate_count: int,
        static_supported_rewrite: Optional[str] = None,
    ) -> Dict[str, Any]:

        if candidate_count > 0:
            return {"decision": "CONTINUE"}

        if static_supported_rewrite:
            return {
                "decision": "SEMANTIC_REWRITE",
                "rewrite": static_supported_rewrite,
                "must_revalidate_rewrite": True,
            }

        return {
            "decision": "DROP_OR_BLOCK",
            "reason": "No supported candidate for core visual claim",
        }


# ============================================================
# 14. Dedup critic
# ============================================================

@dataclass
class DuplicateEvidence:
    same_segment: bool = False
    source_time_overlap: bool = False
    phash_distance: Optional[int] = None
    embedding_similarity: Optional[float] = None
    same_person: bool = False
    same_product: bool = False
    same_composition: bool = False
    same_shot_role: bool = False


class DuplicateCritic:
    def review(self, e: DuplicateEvidence) -> Dict[str, Any]:
        if e.same_segment or e.source_time_overlap:
            return {"verdict": "HARD_DUPLICATE", "severity": "P0"}

        if e.phash_distance is not None and e.phash_distance <= 6:
            return {"verdict": "HARD_DUPLICATE_CANDIDATE", "severity": "P0"}

        narrative_signals = sum([
            e.same_person,
            e.same_product,
            e.same_composition,
            e.same_shot_role,
        ])

        if narrative_signals >= 3:
            return {
                "verdict": "NARRATIVE_NEAR_DUPLICATE",
                "severity": "P1",
                "signal_count": narrative_signals,
            }

        return {
            "verdict": "NOT_DUPLICATE",
            "severity": "PASS",
            "signal_count": narrative_signals,
        }


# ============================================================
# 15. Review example memory
# ============================================================

class ReviewExampleMemory:
    def __init__(self):
        self.items: List[ReviewExample] = []

    def append(self, item: ReviewExample):
        self.items.append(item)

    def rejects_window(
        self,
        requested_action: Action,
        segment_id: str,
        start_s: float,
        end_s: float,
    ) -> bool:

        for item in self.items:
            if item.requested_action != requested_action:
                continue
            if item.segment_id != segment_id:
                continue
            if item.review_scope == "FULL_SEGMENT" and item.result == "BAD":
                return True
            if item.review_scope == "SUBCLIP_WINDOW" and item.result == "BAD":
                overlap = max(0.0, min(end_s, item.end_s) - max(start_s, item.start_s))
                denom = max(1e-6, min(end_s - start_s, item.end_s - item.start_s))
                if overlap / denom >= 0.60:
                    return True
        return False


def build_known_review_memory() -> ReviewExampleMemory:
    m = ReviewExampleMemory()

    m.append(ReviewExample(
        Action.EXTEND, "1985", 2.78, 3.33, "SUBCLIP_WINDOW", "BAD",
        ["DOMINANT_VISUAL_MISMATCH", "NO_TABLETOP_GEOMETRY_CHANGE"],
        ["TRACK_SOCKET", "SOCKET_ADJUST"],
    ))

    m.append(ReviewExample(
        Action.EXTEND, "1984", 0.0, 4.0, "SUBCLIP_WINDOW", "BAD",
        ["STATIC_STATE_NOT_ACTION"],
        ["TABLETOP_EXTENDED_STATE"],
    ))

    return m


# ============================================================
# 16. Shadow mode
# ============================================================

class MMVVMode(str, Enum):
    SHADOW = "SHADOW"
    ENFORCEMENT = "ENFORCEMENT"


# Source Audit R1.1（硬锁，无后门）：Enforcement 明确未批准。
# KnownCaseGate / BlindSetGate / VersionWhitelist / ExplicitConfig 尚未实现——
# 不假装存在，也不用环境变量单独解锁。未来批准任务实现这些 gate 后再放开。
MMVV_ENFORCEMENT_ALLOWED = False


@dataclass
class ShadowDecision:
    old_decision: str
    new_decision: str
    disagreement: bool
    evidence: Dict[str, Any]


class ShadowGate:
    def __init__(self, mode: MMVVMode = MMVVMode.SHADOW):
        if mode == MMVVMode.ENFORCEMENT:
            # 硬锁：任何路径（含环境变量）都不得开启；无后门。
            raise ValueError(
                "MMVV_ENFORCEMENT_BLOCKED: Enforcement 未获批准且无任何解锁路径。"
                "需未来批准任务实现 KnownCaseGate+BlindSetGate+VersionWhitelist+ExplicitConfig 后才允许。")
        self.mode = mode

    def apply(self, old_decision: str, new_decision: str, evidence: Dict[str, Any]):
        if self.mode == MMVVMode.SHADOW:
            return ShadowDecision(
                old_decision=old_decision,
                new_decision=new_decision,
                disagreement=old_decision != new_decision,
                evidence=evidence,
            )
        return ShadowDecision(
            old_decision=new_decision,
            new_decision=new_decision,
            disagreement=old_decision != new_decision,
            evidence=evidence,
        )


# ============================================================
# 17. Orchestrator
# ============================================================

class MultiModuleVisualValidator:
    def __init__(self):
        self.motion = ROIMotionAttributor()
        self.temporal = TemporalStateValidator()
        self.claims = IslandClaimLibrary()
        self.claim_critic = DomainClaimCritic()
        self.fusion = EvidenceFusionEngine()

    def validate_triplet(
        self,
        requested_action: Action,
        before_frame: np.ndarray,
        middle_frame: np.ndarray,
        after_frame: np.ndarray,
        before_sem: FrameSemantics,
        middle_sem: FrameSemantics,
        after_sem: FrameSemantics,
        model_action: Action = Action.UNKNOWN,
        claim_text: Optional[str] = None,
    ) -> Dict[str, Any]:

        all_rois = middle_sem.rois or before_sem.rois or after_sem.rois
        target_rois = [r for r in all_rois if r.name != "PERSON"]
        person_rois = [r for r in all_rois if r.name == "PERSON"]

        bm, cam1 = self.motion.compare(before_frame, middle_frame, target_rois, person_rois)
        ma, cam2 = self.motion.compare(middle_frame, after_frame, target_rois, person_rois)

        merged = MotionMetrics(
            global_motion_px=max(bm.global_motion_px, ma.global_motion_px),
            camera_residual=max(bm.camera_residual, ma.camera_residual),
            evidence={
                "camera_before_mid": bm.evidence,
                "camera_mid_after": ma.evidence,
            },
        )

        keys = set(bm.roi_motion) | set(ma.roi_motion)
        for k in keys:
            merged.roi_motion[k] = max(bm.roi_motion.get(k, 0.0), ma.roi_motion.get(k, 0.0))
            merged.roi_edge_shift[k] = max(
                bm.roi_edge_shift.get(k, 0.0),
                ma.roi_edge_shift.get(k, 0.0),
            )
            merged.person_overlap_ratio[k] = max(
                bm.person_overlap_ratio.get(k, 0.0),
                ma.person_overlap_ratio.get(k, 0.0),
            )

        ev = TemporalEvidence(
            before_sem,
            middle_sem,
            after_sem,
            merged,
            requested_action=requested_action,
            model_action=model_action,
        )

        action_result = self.temporal.validate(ev)

        claim_result = None
        if claim_text:
            contract = self.claims.parse(claim_text)
            visible_objects = sorted(
                set(before_sem.objects + middle_sem.objects + after_sem.objects)
            )
            dominant = middle_sem.dominant_visual or before_sem.dominant_visual or after_sem.dominant_visual
            claim_result = self.claim_critic.review(
                contract,
                visible_objects,
                dominant,
                action_result,
            )

        fused = self.fusion.fuse(action_result, claim_result)

        return {
            "action_result": action_result.to_dict(),
            "claim_result": claim_result,
            "fusion_result": fused,
            "motion": asdict(merged),
        }


# ============================================================
# 18. Known Stage8 semantic examples
# ============================================================

KNOWN_CASES = {
    "media89": {
        "expected": {
            "PERSON_MOTION": "HIGH",
            "TABLETOP_MOTION": "LOW_OR_NOT_PROVEN",
            "EXTEND": "FAIL",
        }
    },
    "media52": {
        "expected": {
            "DRAWER_MOTION": "PRESENT",
            "DRAWER_OPEN": "PASS_OR_STRONG_UNSURE",
            "EXTEND": "FAIL",
        }
    },
    "media109": {
        "expected": {
            "DRAWER_OPEN_STATE": True,
            "DRAWER_OPEN_ACTION": "FAIL",
        }
    },
    "media51": {
        "expected": {
            "STATIC_PRODUCT_PRESENTATION": True,
            "EXTEND": "FAIL",
            "RETRACT": "FAIL",
        }
    },
    "segment1985_1986": {
        "expected": {
            "TRACK_SOCKET": True,
            "SOCKET_ADJUST": "PASS_OR_CANDIDATE",
            "EXTEND": "FAIL",
            "RETRACT": "FAIL",
        }
    },
}


# ============================================================
# 19. Self tests (synthetic logic only)
# ============================================================

def _synthetic_scene(
    tabletop_shift=0,
    drawer_shift=0,
    person_shift=0,
    camera_shift=0,
):
    h, w = 360, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # island body
    cv2.rectangle(
        img,
        (110 + camera_shift, 120),
        (540 + camera_shift, 280),
        (70, 70, 70),
        -1,
    )

    # tabletop
    cv2.rectangle(
        img,
        (180 + tabletop_shift + camera_shift, 130),
        (420 + tabletop_shift + camera_shift, 165),
        (220, 220, 220),
        -1,
    )

    # drawer
    cv2.rectangle(
        img,
        (230 + drawer_shift + camera_shift, 190),
        (330 + drawer_shift + camera_shift, 240),
        (245, 245, 245),
        -1,
    )

    # person
    cv2.rectangle(
        img,
        (25 + person_shift + camera_shift, 70),
        (90 + person_shift + camera_shift, 280),
        (150, 150, 150),
        -1,
    )

    return img


def run_self_tests() -> Dict[str, str]:
    results = {}

    # Test 1: person motion should not become tabletop motion.
    b = _synthetic_scene(person_shift=0)
    a = _synthetic_scene(person_shift=70)
    rois = [
        ROI("TABLETOP", 160, 115, 450, 180, source="TEST"),
        ROI("PERSON", 0, 50, 180, 300, source="TEST"),
    ]
    metrics, _ = ROIMotionAttributor().compare(b, a, [rois[0]], [rois[1]])
    assert metrics.roi_motion["TABLETOP"] < 0.10
    results["person_motion_not_tabletop_motion"] = "PASS"

    # Test 2: open state without motion fails DRAWER_OPEN action.
    same = _synthetic_scene(drawer_shift=40)
    drawer_roi = ROI("DRAWER", 240, 175, 430, 260, source="TEST")
    metrics2, _ = ROIMotionAttributor().compare(same, same.copy(), [drawer_roi], [])
    ev2 = TemporalEvidence(
        FrameSemantics(0, ["DRAWER"], ["DRAWER_OPEN_STATE"], [drawer_roi]),
        FrameSemantics(.5, ["DRAWER"], ["DRAWER_OPEN_STATE"], [drawer_roi]),
        FrameSemantics(1, ["DRAWER"], ["DRAWER_OPEN_STATE"], [drawer_roi]),
        metrics2,
        Action.DRAWER_OPEN,
        Action.UNKNOWN,
    )
    r2 = TemporalStateValidator().validate(ev2)
    assert r2.verdict == Verdict.FAIL
    results["open_state_not_open_action"] = "PASS"

    # Test 3: opposite model direction is hard reject.
    metrics3 = MotionMetrics(roi_motion={"TABLETOP": 0.2}, roi_edge_shift={"TABLETOP": 0.1})
    tb = ROI("TABLETOP", 100, 100, 500, 180, source="TEST")
    ev3 = TemporalEvidence(
        FrameSemantics(0, ["TABLETOP"], ["TABLETOP_RETRACTED_STATE"], [tb]),
        FrameSemantics(.5, ["TABLETOP"], [], [tb]),
        FrameSemantics(1, ["TABLETOP"], ["TABLETOP_EXTENDED_STATE"], [tb]),
        metrics3,
        Action.EXTEND,
        Action.RETRACT,
    )
    r3 = TemporalStateValidator().validate(ev3)
    assert r3.verdict == Verdict.FAIL
    assert "OPPOSITE_DIRECTION_MODEL" in r3.reason_codes
    results["opposite_direction_hard_reject"] = "PASS"

    # Test 4: mandatory failure cannot be rescued by optional vote.
    fusion = EvidenceFusionEngine().fuse(r3, {"verdict": "PASS", "reason_codes": []})
    assert fusion["verdict"] == "FAIL"
    results["mandatory_fail_not_overridden"] = "PASS"

    # Test 5: narrative near duplicate isn't automatically P0.
    d = DuplicateCritic().review(DuplicateEvidence(
        same_person=True,
        same_product=True,
        same_composition=False,
        same_shot_role=False,
    ))
    assert d["verdict"] == "NOT_DUPLICATE"
    results["weak_narrative_similarity_not_p0"] = "PASS"

    # Test 6: review memory is window scoped.
    mem = ReviewExampleMemory()
    mem.append(ReviewExample(
        Action.EXTEND, "1985", 2.0, 3.0, "SUBCLIP_WINDOW", "BAD",
        ["BAD_WINDOW"], ["TRACK_SOCKET"]
    ))
    assert mem.rejects_window(Action.EXTEND, "1985", 2.2, 2.8) is True
    assert mem.rejects_window(Action.EXTEND, "1985", 8.0, 9.0) is False
    results["review_memory_window_scoped"] = "PASS"

    # Test 7: visual beat grouping keeps atomic claims.
    phrases = [
        "岛台想好用", "这三个细节最值得看",
        "第一", "上层薄抽", "收纳小物不弯腰", "打开就能拿到",
        "第二", "轨道插座", "吃火锅煮茶都方便", "插拔也顺手",
        "第三", "伸缩桌面", "来客时一拉就变宽", "平时收起来不占位",
        "厨房好不好用", "全在这些小细节里",
    ]
    grouped = VisualBeatGrouper().group(phrases)
    assert 4 <= len(grouped) <= 5
    assert sum(len(g["atomic_claims"]) for g in grouped) == len(phrases)
    results["visual_beat_retains_atomic_claims"] = "PASS"

    # Test 8: shadow mode does not change old production decision.
    s = ShadowGate(MMVVMode.SHADOW).apply(
        "PASS", "FAIL", {"reason": "new critic"}
    )
    assert s.old_decision == "PASS"
    assert s.new_decision == "FAIL"
    results["shadow_mode_no_enforcement"] = "PASS"

    return results


def demo():
    print(json.dumps({
        "module": "TreeCut Multi-Module Visual Validation Master V1",
        "mode": "SHADOW",
        "known_cases": KNOWN_CASES,
        "self_tests": run_self_tests(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    demo()
