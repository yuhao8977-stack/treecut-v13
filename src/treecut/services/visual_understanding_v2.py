"""
TreeCut Visual Understanding Engine V2
=====================================

This module is a concrete, domain-aware second-pass visual understanding layer
for island-table production video.

It does NOT reproduce ChatGPT/OpenAI proprietary visual weights or hidden
reasoning.  It encodes explicit review criteria, domain semantics, temporal
state transitions, contradiction gates and example-driven critic behavior.

Intended integration:
    ProductionSourceService
      -> candidate retrieval
      -> existing VLM/Qwen first pass (L2_MODEL)
      -> TemporalVisualAnalyzer
      -> DomainVisualCritic (this module, L2_CRITIC)
      -> ClaimVisualMatcher
      -> ProductionQAService
      -> Human L3

Key principles:
- object/state presence is not action
- opposite directions are hard contradictions
- path/ASR/OCR cannot prove a visual action
- no valid evidence => UNKNOWN/REWRITE/BLOCK, not forced match
- atomic claims and visual beats are different layers
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import json
import math
import re


class TruthSource(str, Enum):
    PATH_HINT = "PATH_HINT"
    ASR_OCR = "ASR_OCR"
    STATIC_VISUAL = "STATIC_VISUAL"
    TEMPORAL_VISUAL = "TEMPORAL_VISUAL"
    L2_MODEL = "L2_MODEL"
    L2_CRITIC = "L2_CRITIC"
    EXTERNAL_REVIEW = "EXTERNAL_REVIEW"
    L3_HUMAN = "L3_HUMAN"


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNSURE = "UNSURE"
    NO_VALID_SOURCE = "NO_VALID_SOURCE"


class Support(str, Enum):
    SUPPORTED = "SUPPORTED"
    CANDIDATE = "CANDIDATE"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"


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
    STATIC = "STATIC"
    UNKNOWN = "UNKNOWN"


OPPOSITES = {
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


DIRECTIONAL_ACTIONS = set(OPPOSITES)


@dataclass(frozen=True)
class Evidence:
    source: TruthSource
    kind: str
    value: Any
    timestamp_s: Optional[float] = None
    ref: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class FrameObservation:
    timestamp_s: float
    objects: List[str] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    hand_interactions: List[str] = field(default_factory=list)
    geometry: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


@dataclass
class TemporalObservation:
    before: FrameObservation
    middle: FrameObservation
    after: FrameObservation
    model_action: Action = Action.UNKNOWN
    model_confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class TemporalDecision:
    action: Action
    completeness: str
    direction_supported: bool
    object_supported: bool
    reason_codes: List[str]
    support: Support
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class ShotCandidate:
    segment_id: str
    asset_id: str
    start_s: float
    end_s: float
    production_eligible: bool
    contamination_free: bool
    objects: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    scene: Optional[str] = None
    case_cluster_id: Optional[str] = None
    product_cluster_id: Optional[str] = None
    path_hints: List[str] = field(default_factory=list)
    asr_ocr_terms: List[str] = field(default_factory=list)
    temporal: Optional[TemporalDecision] = None
    l2_model_action: Action = Action.UNKNOWN
    visual_cluster_id: Optional[str] = None
    shot_role: Optional[str] = None
    quality: float = 0.5
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class VisualRequirement:
    claim_id: str
    beat_id: str
    text: str
    claim_type: str
    required_object: Optional[str] = None
    required_action: Action = Action.UNKNOWN
    required_state: Optional[str] = None
    preferred_scene: Optional[str] = None
    forbidden_dominant_objects: List[str] = field(default_factory=list)
    story_mode: str = "INFORMATION_MONTAGE"
    required_case_cluster_id: Optional[str] = None
    required_product_cluster_id: Optional[str] = None
    allow_static_for_function: bool = False


@dataclass
class CriticIssue:
    code: str
    severity: str
    message: str


@dataclass
class CriticDecision:
    verdict: Verdict
    support: Support
    issues: List[CriticIssue]
    hard_gate_pass: bool
    semantic_score: float
    action_score: float
    continuity_score: float
    duplicate_penalty: float
    final_score: float
    reason_codes: List[str]

    def to_dict(self):
        return asdict(self)


class TemporalActionValidator:
    """
    Domain-aware validator that sits *after* cheap/model perception.

    It deliberately uses hard logic for direction conflicts.
    Geometry hooks are intentionally simple; TreeCut can later plug in optical
    flow/keypoint/change detectors without changing this contract.
    """

    def validate(
        self,
        requested: Action,
        observation: TemporalObservation,
        target_object: Optional[str] = None,
    ) -> TemporalDecision:
        rc: List[str] = []
        ev = list(observation.evidence)

        if requested in OPPOSITES and observation.model_action == OPPOSITES[requested]:
            return TemporalDecision(
                action=observation.model_action,
                completeness="CONTRADICTED",
                direction_supported=False,
                object_supported=self._object_present(observation, target_object),
                reason_codes=["MODEL_OPPOSITE_DIRECTION"],
                support=Support.CONTRADICTED,
                evidence=ev,
            )

        # Infer a few useful state transitions from structured frame states.
        inferred = self._infer_from_states(observation, target_object)

        # If structured temporal evidence proves the opposite direction, that
        # overrides a weak model guess.
        if requested in OPPOSITES and inferred == OPPOSITES[requested]:
            return TemporalDecision(
                action=inferred,
                completeness="CONTRADICTED",
                direction_supported=False,
                object_supported=self._object_present(observation, target_object),
                reason_codes=["TEMPORAL_STATE_OPPOSITE_DIRECTION"],
                support=Support.CONTRADICTED,
                evidence=ev,
            )

        # A known unrelated action is not support.
        if inferred not in (Action.UNKNOWN, Action.STATIC, requested):
            return TemporalDecision(
                action=inferred,
                completeness="OTHER_ACTION",
                direction_supported=False,
                object_supported=self._object_present(observation, target_object),
                reason_codes=["UNRELATED_ACTION"],
                support=Support.CONTRADICTED,
                evidence=ev,
            )

        if inferred == requested:
            complete = self._is_complete(observation, requested)
            return TemporalDecision(
                action=requested,
                completeness="COMPLETE" if complete else "PARTIAL",
                direction_supported=True,
                object_supported=self._object_present(observation, target_object),
                reason_codes=["TEMPORAL_DIRECTION_SUPPORTED"] + ([] if complete else ["BOUNDARY_INCOMPLETE"]),
                support=Support.SUPPORTED if complete else Support.CANDIDATE,
                evidence=ev,
            )

        # If no state transition, fall back to model only if it is the same
        # requested direction AND the frame sequence shows movement evidence.
        if observation.model_action == requested:
            movement = self._has_motion_signal(observation)
            if movement:
                return TemporalDecision(
                    action=requested,
                    completeness="PARTIAL",
                    direction_supported=True,
                    object_supported=self._object_present(observation, target_object),
                    reason_codes=["MODEL_DIRECTION_WITH_MOTION", "NEEDS_STRONGER_BOUNDARY_EVIDENCE"],
                    support=Support.CANDIDATE,
                    evidence=ev,
                )

        return TemporalDecision(
            action=Action.STATIC if self._object_present(observation, target_object) else Action.UNKNOWN,
            completeness="STATIC_OR_UNKNOWN",
            direction_supported=False,
            object_supported=self._object_present(observation, target_object),
            reason_codes=["STATIC_STATE_NOT_ACTION" if self._object_present(observation, target_object) else "ACTION_NOT_PROVEN"],
            support=Support.UNKNOWN,
            evidence=ev,
        )

    @staticmethod
    def _object_present(obs: TemporalObservation, obj: Optional[str]) -> bool:
        if not obj:
            return True
        return any(obj in f.objects for f in (obs.before, obs.middle, obs.after))

    @staticmethod
    def _state_set(f: FrameObservation) -> set:
        return set(f.states)

    def _infer_from_states(self, obs: TemporalObservation, obj: Optional[str]) -> Action:
        b, m, a = self._state_set(obs.before), self._state_set(obs.middle), self._state_set(obs.after)

        if "TABLETOP_RETRACTED_STATE" in b and "TABLETOP_EXTENDED_STATE" in a:
            return Action.EXTEND
        if "TABLETOP_EXTENDED_STATE" in b and "TABLETOP_RETRACTED_STATE" in a:
            return Action.RETRACT
        if "DRAWER_CLOSED_STATE" in b and "DRAWER_OPEN_STATE" in a:
            return Action.DRAWER_OPEN
        if "DRAWER_OPEN_STATE" in b and "DRAWER_CLOSED_STATE" in a:
            return Action.DRAWER_CLOSE
        if "CABINET_CLOSED_STATE" in b and "CABINET_OPEN_STATE" in a:
            return Action.CABINET_OPEN
        if "CABINET_OPEN_STATE" in b and "CABINET_CLOSED_STATE" in a:
            return Action.CABINET_CLOSE
        if "OBJECT_OUTSIDE_STORAGE" in b and "OBJECT_INSIDE_STORAGE" in a:
            return Action.STORAGE_PUT_IN
        if "OBJECT_INSIDE_STORAGE" in b and "OBJECT_OUTSIDE_STORAGE" in a:
            return Action.STORAGE_TAKE_OUT
        if "SOCKET_MODULE_OUTSIDE" in b and "SOCKET_MODULE_INSERTED" in a:
            return Action.SOCKET_INSERT
        if "SOCKET_MODULE_INSERTED" in b and "SOCKET_MODULE_OUTSIDE" in a:
            return Action.SOCKET_REMOVE

        # Explicit hand interaction can classify an unrelated power action,
        # which is important for rejecting "socket closeup => stretch".
        hi = set(obs.before.hand_interactions + obs.middle.hand_interactions + obs.after.hand_interactions)
        if {"SOCKET_ROTATE", "SOCKET_SLIDE", "SOCKET_ADJUST"} & hi:
            return Action.SOCKET_ADJUST

        return Action.STATIC

    @staticmethod
    def _is_complete(obs: TemporalObservation, action: Action) -> bool:
        b, a = set(obs.before.states), set(obs.after.states)
        mapping = {
            Action.EXTEND: ("TABLETOP_RETRACTED_STATE", "TABLETOP_EXTENDED_STATE"),
            Action.RETRACT: ("TABLETOP_EXTENDED_STATE", "TABLETOP_RETRACTED_STATE"),
            Action.DRAWER_OPEN: ("DRAWER_CLOSED_STATE", "DRAWER_OPEN_STATE"),
            Action.DRAWER_CLOSE: ("DRAWER_OPEN_STATE", "DRAWER_CLOSED_STATE"),
            Action.STORAGE_PUT_IN: ("OBJECT_OUTSIDE_STORAGE", "OBJECT_INSIDE_STORAGE"),
            Action.STORAGE_TAKE_OUT: ("OBJECT_INSIDE_STORAGE", "OBJECT_OUTSIDE_STORAGE"),
            Action.SOCKET_INSERT: ("SOCKET_MODULE_OUTSIDE", "SOCKET_MODULE_INSERTED"),
            Action.SOCKET_REMOVE: ("SOCKET_MODULE_INSERTED", "SOCKET_MODULE_OUTSIDE"),
        }
        if action not in mapping:
            return False
        s1, s2 = mapping[action]
        return s1 in b and s2 in a

    @staticmethod
    def _has_motion_signal(obs: TemporalObservation) -> bool:
        # Generic hooks.  Existing motion/flow service can map values into
        # geometry["motion_magnitude"] or states.
        vals = []
        for f in (obs.before, obs.middle, obs.after):
            if "motion_magnitude" in f.geometry:
                vals.append(float(f.geometry["motion_magnitude"]))
        return bool(vals) and max(vals) > 0.15


class IslandClaimLibrary:
    """
    Converts the current island-business phrases into explicit visual contracts.
    This is intentionally concrete rather than generic.
    """

    def requirement(self, claim_id: str, beat_id: str, text: str, story_mode="INFORMATION_MONTAGE") -> VisualRequirement:
        t = re.sub(r"\s+", "", text)

        if "上层薄抽" in t:
            return VisualRequirement(claim_id, beat_id, text, "OBJECT",
                                     required_object="UPPER_THIN_DRAWER",
                                     story_mode=story_mode)

        if "收纳小物" in t or "不弯腰" in t:
            return VisualRequirement(claim_id, beat_id, text, "USE_CASE",
                                     required_object="UPPER_THIN_DRAWER",
                                     story_mode=story_mode)

        if "打开就能拿到" in t:
            return VisualRequirement(claim_id, beat_id, text, "ACTION",
                                     required_action=Action.DRAWER_OPEN,
                                     story_mode=story_mode)

        if "轨道插座" in t:
            return VisualRequirement(claim_id, beat_id, text, "OBJECT",
                                     required_object="TRACK_SOCKET",
                                     story_mode=story_mode)

        if "插拔" in t:
            return VisualRequirement(claim_id, beat_id, text, "ACTION",
                                     required_object="TRACK_SOCKET",
                                     required_action=Action.SOCKET_INSERT,
                                     story_mode=story_mode)

        if "伸缩桌面" in t:
            return VisualRequirement(claim_id, beat_id, text, "FUNCTION",
                                     required_object="TABLETOP",
                                     allow_static_for_function=True,
                                     story_mode=story_mode)

        if "一拉" in t and ("变宽" in t or "伸" in t):
            return VisualRequirement(claim_id, beat_id, text, "ACTION",
                                     required_object="TABLETOP",
                                     required_action=Action.EXTEND,
                                     forbidden_dominant_objects=["TRACK_SOCKET"],
                                     story_mode=story_mode)

        if "收起来" in t or "不占位" in t:
            return VisualRequirement(claim_id, beat_id, text, "ACTION_SPACE",
                                     required_object="TABLETOP",
                                     required_action=Action.RETRACT,
                                     forbidden_dominant_objects=["TRACK_SOCKET", "DRAWER"],
                                     story_mode=story_mode)

        return VisualRequirement(claim_id, beat_id, text, "GENERIC",
                                 story_mode=story_mode)


class DomainVisualCritic:
    """
    Concrete second-pass critic.

    Hard gates are separated from soft ranking so a high-quality but wrong
    shot can never beat a semantically correct shot.
    """

    def review(self, req: VisualRequirement, shot: ShotCandidate) -> CriticDecision:
        issues: List[CriticIssue] = []
        reasons: List[str] = []

        if not shot.production_eligible or not shot.contamination_free:
            return self._fail("SOURCE_NOT_ELIGIBLE", "P0", "Source not allowed for Production.")

        # Object gate
        if req.required_object:
            if req.required_object not in set(shot.objects):
                # UPPER_THIN_DRAWER may be conservatively downgraded from DRAWER.
                if req.required_object == "UPPER_THIN_DRAWER" and "DRAWER" in shot.objects:
                    issues.append(CriticIssue("UPPER_THIN_DRAWER_UNVERIFIED", "P0",
                                              "Generic drawer does not prove upper thin drawer."))
                else:
                    issues.append(CriticIssue("REQUIRED_OBJECT_MISSING", "P0",
                                              f"Missing visual object: {req.required_object}"))

        # Dominant mismatch
        for obj in req.forbidden_dominant_objects:
            if obj in shot.objects:
                issues.append(CriticIssue("DOMINANT_VISUAL_MISMATCH", "P0",
                                          f"Forbidden/dominant object for this claim: {obj}"))

        # Action gate
        action_score = 1.0
        if req.required_action != Action.UNKNOWN:
            if shot.temporal is None:
                issues.append(CriticIssue("TEMPORAL_EVIDENCE_MISSING", "P0",
                                          "Action claim requires temporal evidence."))
                action_score = 0.0
            else:
                td = shot.temporal
                if td.action in OPPOSITES and OPPOSITES[req.required_action] == td.action:
                    issues.append(CriticIssue("OPPOSITE_ACTION", "P0",
                                              f"Requested {req.required_action.value}, observed {td.action.value}."))
                    action_score = 0.0
                elif td.action == Action.SOCKET_ADJUST and req.required_action in (Action.EXTEND, Action.RETRACT):
                    issues.append(CriticIssue("UNRELATED_SOCKET_ACTION", "P0",
                                              "Socket adjustment cannot support tabletop extension/retraction."))
                    action_score = 0.0
                elif td.action != req.required_action:
                    issues.append(CriticIssue("REQUESTED_ACTION_NOT_PROVEN", "P0",
                                              f"Requested {req.required_action.value}, observed {td.action.value}."))
                    action_score = 0.0
                elif td.completeness != "COMPLETE":
                    issues.append(CriticIssue("ACTION_BOUNDARY_INCOMPLETE", "P1",
                                              "Direction is plausible but full before→motion→after is not shown."))
                    action_score = 0.55

        # For pure function claim (e.g. "伸缩桌面"), static state can pass as
        # function evidence but receives less score than true action demo.
        if req.allow_static_for_function and req.required_object in shot.objects:
            action_score = max(action_score, 0.6)

        # Story consistency
        continuity = 1.0
        if req.story_mode == "SINGLE_CASE":
            if req.required_case_cluster_id and shot.case_cluster_id and req.required_case_cluster_id != shot.case_cluster_id:
                issues.append(CriticIssue("CASE_CLUSTER_CONFLICT", "P0", "Different case used in single-case story."))
                continuity = 0.0
            if req.required_product_cluster_id and shot.product_cluster_id and req.required_product_cluster_id != shot.product_cluster_id:
                issues.append(CriticIssue("PRODUCT_CLUSTER_CONFLICT", "P0", "Different product used in single-product story."))
                continuity = 0.0

        p0 = [x for x in issues if x.severity == "P0"]
        semantic = 0.0 if p0 else 1.0

        if p0:
            return CriticDecision(
                Verdict.FAIL, Support.CONTRADICTED, issues, False,
                semantic_score=semantic,
                action_score=action_score,
                continuity_score=continuity,
                duplicate_penalty=0.0,
                final_score=0.0,
                reason_codes=[x.code for x in issues],
            )

        # P1 means candidate/review, not hard failure.
        final = 0.60 * semantic + 0.25 * action_score + 0.10 * continuity + 0.05 * max(0, min(1, shot.quality))
        if issues:
            return CriticDecision(
                Verdict.UNSURE, Support.CANDIDATE, issues, True,
                semantic_score=semantic,
                action_score=action_score,
                continuity_score=continuity,
                duplicate_penalty=0.0,
                final_score=round(final, 4),
                reason_codes=[x.code for x in issues],
            )

        return CriticDecision(
            Verdict.PASS, Support.SUPPORTED, [], True,
            semantic_score=1.0,
            action_score=action_score,
            continuity_score=continuity,
            duplicate_penalty=0.0,
            final_score=round(final, 4),
            reason_codes=["ALL_EXPLICIT_REQUIREMENTS_PASSED"],
        )

    def _fail(self, code: str, severity: str, message: str) -> CriticDecision:
        issue = CriticIssue(code, severity, message)
        return CriticDecision(Verdict.FAIL, Support.CONTRADICTED, [issue], False, 0, 0, 0, 0, 0, [code])


class VisualBeatGrouper:
    """
    Keeps atomic claim parsing while grouping phrases into visual tasks.

    The current V2 script:
       岛台想好用 / 这三个细节最值得看 / 第一 / 上层薄抽 /
       收纳小物不弯腰 / 打开就能拿到 / 第二 / ...
    should not become 16 independent shot-selection tasks.
    """

    ORDINALS = {"第一", "第二", "第三", "第四", "第五"}

    def group(self, phrases: Sequence[str]) -> List[List[str]]:
        groups: List[List[str]] = []
        cur: List[str] = []

        for raw in phrases:
            t = raw.strip(" ，。！？!?,")
            if not t:
                continue

            # Hook aggregation.
            if not groups and len(cur) < 2 and t not in self.ORDINALS:
                cur.append(raw)
                if len(cur) == 2:
                    groups.append(cur)
                    cur = []
                continue

            # Ordinal starts a feature visual beat.
            if t in self.ORDINALS:
                if cur:
                    groups.append(cur)
                cur = [raw]
                continue

            # Feature phrase aggregation: ordinal + object + use-case/action.
            if cur and cur[0].strip(" ，。！？!?,") in self.ORDINALS:
                cur.append(raw)
                if len(cur) >= 4:
                    groups.append(cur)
                    cur = []
                continue

            cur.append(raw)

        if cur:
            groups.append(cur)

        # Final cleanup: merge tiny trailing CTA fragments.
        merged: List[List[str]] = []
        for g in groups:
            if merged and len(g) <= 1 and len(g[0].strip()) <= 8:
                merged[-1].extend(g)
            else:
                merged.append(g)
        return merged


class NoCandidateResolver:
    """
    Explicitly prevents "差不多拿一个镜头继续剪".
    """

    CORE_TYPES = {"OBJECT", "FUNCTION", "ACTION", "ACTION_SPACE", "USE_CASE"}

    def decide(self, req: VisualRequirement, candidate_count: int) -> Dict[str, Any]:
        if candidate_count > 0:
            return {"decision": "CONTINUE", "rewrite_required": False}

        if req.claim_type in self.CORE_TYPES:
            return {
                "decision": "REWRITE_DROP_OR_BLOCK",
                "rewrite_required": True,
                "reason": "core visual requirement has no supported production source",
            }

        return {
            "decision": "GENERIC_VISUAL_ALLOWED_WITH_WARNING",
            "rewrite_required": False,
        }


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
    """
    Fixes the current over-aggressive narrative-near-duplicate behavior.
    """

    def review(self, e: DuplicateEvidence) -> Dict[str, Any]:
        if e.same_segment or e.source_time_overlap:
            return {"verdict": "HARD_DUPLICATE", "severity": "P0", "reason": "same segment/time overlap"}

        if e.phash_distance is not None and e.phash_distance <= 6:
            return {"verdict": "HARD_DUPLICATE_CANDIDATE", "severity": "P0", "reason": "very strong pHash similarity"}

        narrative_count = sum([
            e.same_person, e.same_product, e.same_composition, e.same_shot_role
        ])

        # Narrative duplicate should not become P0 from vague overlap alone.
        if narrative_count >= 3:
            return {"verdict": "NARRATIVE_NEAR_DUPLICATE", "severity": "P1", "reason": f"{narrative_count}/4 narrative signals"}

        return {"verdict": "NOT_DUPLICATE", "severity": "PASS", "reason": f"{narrative_count}/4 narrative signals"}


class ExampleAdjudicationMemory:
    """
    Small explicit regression/example memory.  It is *not* model training.
    TreeCut can use this for unit tests and retrieval explanations.
    """
    def __init__(self):
        self.examples: Dict[str, Dict[str, Any]] = {}

    def add(self, example_id: str, data: Dict[str, Any]):
        self.examples[example_id] = dict(data)

    def get(self, example_id: str) -> Optional[Dict[str, Any]]:
        return self.examples.get(example_id)

    def to_json(self) -> str:
        return json.dumps(self.examples, ensure_ascii=False, indent=2)


def build_known_stage8_examples() -> ExampleAdjudicationMemory:
    m = ExampleAdjudicationMemory()
    m.add("SEG1985_EXTEND", {
        "segment_id": "1985",
        "request": "EXTEND",
        "review_observation": "track socket close-up; hand adjusts round socket module",
        "verdict": "BAD",
        "actual_semantics": ["TRACK_SOCKET", "SOCKET_ADJUST"],
        "reason_codes": ["DOMINANT_VISUAL_MISMATCH", "REQUESTED_ACTION_NOT_SHOWN"],
    })
    m.add("SEG1984_EXTEND", {
        "segment_id": "1984",
        "request": "EXTEND",
        "review_observation": "static wide shot of tabletop/island already extended-looking",
        "verdict": "BAD_FOR_ACTION",
        "actual_semantics": ["TABLETOP", "TABLETOP_EXTENDED_STATE"],
        "reason_codes": ["STATIC_STATE_NOT_ACTION"],
    })
    m.add("SEG1_DRAWER_OPEN", {
        "segment_id": "1",
        "request": "DRAWER_OPEN",
        "review_observation": "drawer already open with presenter; no clear closed→open transition",
        "verdict": "BAD_FOR_ACTION",
        "actual_semantics": ["DRAWER", "DRAWER_OPEN_STATE"],
        "reason_codes": ["OPEN_STATE_NOT_OPEN_ACTION"],
    })
    m.add("SEG419_STORAGE_PUT_IN", {
        "segment_id": "419",
        "request": "STORAGE_PUT_IN",
        "review_observation": "open storage/cabinet structure; no object transfer into storage",
        "verdict": "BAD",
        "actual_semantics": ["CABINET", "DRAWER_OPEN_STATE"],
        "reason_codes": ["NO_OBJECT_TRANSFER_IN"],
    })
    m.add("SEG2482_2484_EXTEND", {
        "segment_id": "2482-2484",
        "request": "EXTEND",
        "review_observation": "presenter gestures around island; selected windows do not clearly show complete tabletop extension",
        "verdict": "BAD_FOR_DIRECTIONAL_ACTION",
        "actual_semantics": ["ISLAND", "TABLETOP", "PERSON", "STATIC_PRESENTATION"],
        "reason_codes": ["NO_DIRECTION_PROOF", "NO_BEFORE_MOTION_AFTER"],
    })
    return m


if __name__ == "__main__":
    # Demonstrate the exact current failure: socket shot incorrectly used for EXTEND.
    req = IslandClaimLibrary().requirement(
        claim_id="demo1",
        beat_id="VB4",
        text="来客时一拉就变宽",
    )
    temporal = TemporalDecision(
        action=Action.SOCKET_ADJUST,
        completeness="COMPLETE",
        direction_supported=True,
        object_supported=True,
        reason_codes=["SOCKET_ADJUST"],
        support=Support.SUPPORTED,
    )
    shot = ShotCandidate(
        segment_id="1985",
        asset_id="demo",
        start_s=2.78,
        end_s=3.33,
        production_eligible=True,
        contamination_free=True,
        objects=["TRACK_SOCKET", "SOCKET_MODULE"],
        functions=["POWER"],
        temporal=temporal,
        l2_model_action=Action.RETRACT,
    )
    print(json.dumps(DomainVisualCritic().review(req, shot).to_dict(), ensure_ascii=False, indent=2))
