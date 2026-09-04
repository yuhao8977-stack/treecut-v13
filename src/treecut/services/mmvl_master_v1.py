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
