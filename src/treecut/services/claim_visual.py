"""STAGE8 G3 — ClaimVisualMatcher：原子主张解析 + 硬闸匹配 + 排序。

§28-§43。硬闸优先(资格/对象/动作/禁止视觉/故事/重复)，性能与软信号不得压过语义失败。
严禁推断：岩板→耐高温、抽屉→静音滑轨、文件夹"伸缩"→动作、ASR插座→视觉插座。
ACTION 动词(拉/推/打开/关闭/伸缩/收起/插入/抽出/放进去)需时序动作证据。
account_id 参数化；B007 仅 fixture。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

ACTION_WORDS = ["拉开", "拉出", "推回", "打开", "关闭", "伸缩", "收起", "插上", "插入",
                "抽出", "放进去", "取出", "旋转", "转动", "移动"]
ACTION_MAP = {
    "伸缩": "EXTEND", "变宽": "EXTEND", "拉出": "EXTEND", "加宽": "EXTEND", "延伸": "EXTEND",
    "收起": "RETRACT", "收起来": "RETRACT", "缩回": "RETRACT",
    "拉开": "DRAWER_OPEN", "打开": "OPEN", "抽拉": "DRAWER_OPEN",
    "推回": "DRAWER_CLOSE", "关上": "CABINET_CLOSE", "关闭": "CLOSE",
    "插上": "SOCKET_INSERT", "插入": "SOCKET_INSERT", "插拔": "SOCKET_INSERT",
    "放进去": "STORAGE_PUT_IN", "收纳": "STORAGE_PUT_IN", "放东西": "STORAGE_PUT_IN",
    "取出": "STORAGE_TAKE_OUT", "拿出": "STORAGE_TAKE_OUT",
    "旋转": "PRODUCT_ROTATE", "转动": "PRODUCT_ROTATE",
}
CASE_MARKERS = ["这一款", "这款", "这个客户", "这套", "这套岛台", "定制", "女士", "先生",
                "小姐", "姐", "客户", "业主", "家里", "我们家"]
MONTAGE_MARKERS = ["这3个", "这三个", "几个功能", "细节", "收纳", "整体来说"]
FORBIDDEN_INFERENCE = [
    ("岩板", "耐高温"), ("岩板", "耐刮"), ("抽屉", "静音滑轨"), ("滑轨", "静音"),
    ("文件夹", "伸缩"), ("插座", "供电"), ("看到", "功能")]
FORBIDDEN_SUBST = [
    ("EXTEND", "SOCKET"), ("RETRACT", "SOCKET"), ("DRAWER_OPEN", "SOCKET"),
    ("UPPER_THIN_DRAWER", "LOWER_DRAWER"),
]


@dataclass
class AtomicClaim:
    claim_id: str
    beat_id: str
    text: str
    claim_type: str
    required_action: str | None = None
    required_object: str | None = None
    required_function: str | None = None
    preferred_scene: str | None = None
    required_context: str | None = None
    forbidden_dominant_object: str | None = None
    knowledge_requirement: str | None = None
    support_status: str = "UNVERIFIED"
    evidence_refs: list = field(default_factory=list)


def parse_script_to_claims(text: str, beat_ids: list[str] | None = None) -> list[AtomicClaim]:
    """按句拆分为原子主张。ACTION 词 → ACTION 型主张(需时序证据)。"""
    sentences = [s.strip() for s in re.split(r"[。！？，,；;\n]", text) if s.strip()]
    claims = []
    for i, s in enumerate(sentences):
        bid = (beat_ids[i] if beat_ids and i < len(beat_ids) else f"B{i+1}")
        ctype, obj, func, kreq = "CLAIM", None, None, None
        # 类型判定(保守: 只认明确词)
        act = None
        # 取文本中最早出现的动作词(而非字典序)
        best_pos = None
        for w, a in ACTION_MAP.items():
            pos = s.find(w)
            if pos >= 0 and (best_pos is None or pos < best_pos):
                best_pos = pos
                act = a
        if act:
            ctype = "ACTION"
        for kw, o in (("薄抽", "UPPER_THIN_DRAWER"), ("抽屉", "DRAWER"), ("轨道插座", "TRACK_SOCKET"),
                      ("插座", "SOCKET"), ("桌面", "TABLETOP"), ("柜门", "CABINET_DOOR"),
                      ("岩板", "SINTERED_STONE"), ("台面", "COUNTERTOP")):
            if kw in s:
                obj = o
                break
        if "滑轨" in s:
            ctype = "HARDWARE_PROPERTY"
            kreq = "hardware property needs physical/audio evidence (not inferred from drawer)"
        elif "耐高温" in s or "耐刮" in s or "防" in s or "静音" in s:
            ctype = "MATERIAL_PROPERTY"
            kreq = "property needs evidence source (not inferred from material)"
        elif "公分" in s or ("米" in s and any(c.isdigit() for c in s)):
            ctype = "DIMENSION"
        elif any(m in s for m in CASE_MARKERS):
            ctype = "CASE_IDENTITY"
        elif "厨房" in s or "空间" in s or "收纳" in s:
            ctype = "SPACE"
        claims.append(AtomicClaim(claim_id=f"C{i+1:02d}", beat_id=bid, text=s, claim_type=ctype,
                                  required_action=act, required_object=obj,
                                  knowledge_requirement=kreq))
    return claims


def classify_story_mode(text: str) -> str:
    case_hits = sum(1 for m in CASE_MARKERS if m in text)
    if case_hits >= 1 and "功能" not in text[:60]:
        return "SINGLE_CASE"
    return "INFORMATION_MONTAGE"


@dataclass
class Candidate:
    media_id: int
    path: str | None = None
    source_role: str | None = None
    eligible: bool = False
    actions: list = field(default_factory=list)      # 时序证据动作(如 EXTEND)
    object_: str | None = None
    scene: str | None = None
    case_id: str | None = None
    subclip: dict | None = None


class ClaimVisualMatcher:
    """输入 claim+beat+story_mode+候选 → 硬闸过滤 → 排序 → TopK + 拒绝原因。"""

    def __init__(self, eligible_check: Callable | None = None, action_profile: Callable | None = None):
        self.eligible_check = eligible_check or (lambda mid, kind="media_file": (True, {}))
        self.action_profile = action_profile or (lambda mid: {"actions": [], "object": None})

    def rank(self, claim: AtomicClaim, story_mode: str, candidates: list[Candidate],
             already_used: list | None = None, top_k: int = 3) -> list[dict]:
        results = []
        for cd in candidates:
            rejects = []
            # 硬闸1: 生产资格
            ok, info = self.eligible_check(cd.media_id)
            if not ok:
                rejects.append(f"SOURCE_NOT_ELIGIBLE:{info.get('reasons')}")
            # 硬闸2: 动作匹配(ACTION 主张)
            prof = self.action_profile(cd.media_id) or {}
            cand_actions = set(prof.get("actions") or cd.actions or [])
            if claim.required_action:
                if claim.required_action not in cand_actions:
                    # 禁止视觉: 主张伸缩却候选是插座特写
                    dom = prof.get("object") or cd.object_
                    if dom in ("SOCKET", "TRACK_SOCKET") and claim.required_action in ("EXTEND", "RETRACT"):
                        rejects.append(f"DOMINANT_VISUAL_MISMATCH: claim {claim.required_action} vs dominant {dom}")
                    else:
                        rejects.append(f"REQUIRED_ACTION_MISSING:{claim.required_action}(cand={sorted(cand_actions)})")
            # 硬闸3: 对象
            if claim.required_object and cd.object_ and claim.required_object != cd.object_:
                if claim.required_object == "UPPER_THIN_DRAWER" and cd.object_ == "DRAWER":
                    rejects.append("THIN_DRAWER_UNVERIFIED:upper-position/thin-geometry not evidenced")
                else:
                    rejects.append(f"OBJECT_MISMATCH:need {claim.required_object} got {cd.object_}")
            # 硬闸4: 故事一致性
            if story_mode == "SINGLE_CASE" and cd.case_id and claim.required_context and \
                    cd.case_id != claim.required_context:
                rejects.append("STORY_CASE_CONFLICT")
            # 硬闸5: 重复(已用镜头)
            if already_used and cd.media_id in {u.get("media_id") for u in already_used}:
                rejects.append("DUPLICATE_USED")
            if rejects:
                results.append({"candidate": cd, "status": "REJECT", "reasons": rejects})
            else:
                results.append({"candidate": cd, "status": "PASS"})
        passed = [r for r in results if r["status"] == "PASS"]
        rejected = [r for r in results if r["status"] == "REJECT"]
        return passed[:top_k] + rejected
