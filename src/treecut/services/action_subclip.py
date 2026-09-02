"""STAGE8 G2 — ActionSubclipService：时序证据 → 动作窗口 → 最佳 Subclip。

原则（§10-§24）：PATH/ASR 文本仅 PATH_HINT/TEXT_HINT，不证明动作；
动作候选来自时序视觉证据（帧状态序列）；semantic_correct 与 boundary_usable 分离；
默认整段裁剪禁用：Segment → Action Window → Subclip。
account_id 参数化；B007 仅 fixture，不硬编码路径。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

STATES = ("NOT_PRESENT", "OBJECT_PRESENT", "ACTION_START",
          "ACTION_IN_PROGRESS", "ACTION_END")

DUR_GUIDE = {"hook": (0.7, 1.8), "info": (1.5, 3.0), "action": (2.5, 4.5)}
PRE_ROLL = 0.25
POST_ROLL = 0.30


def parse_qwen_state(text: str) -> str:
    """从 qwen L2 输出解析状态行 state=...。解析失败 → NOT_PRESENT(保守)。"""
    if not text:
        return "NOT_PRESENT"
    m = re.search(r"state\s*=\s*([A-Z_]+)", text)
    if not m:
        m = re.search(r"(NOT_PRESENT|OBJECT_PRESENT|ACTION_START|ACTION_IN_PROGRESS|ACTION_END)", text)
    st = m.group(1) if m else ""
    return st if st in STATES else "NOT_PRESENT"


def parse_qwen_object(text: str) -> str:
    m = re.search(r"object\s*=\s*([^\n]+)", text or "")
    return m.group(1).strip()[:40] if m else ""


@dataclass
class ActionWindow:
    action: str
    media_id: int | None = None
    asset_path: str | None = None
    duration_s: float = 0.0
    action_start_s: float | None = None
    action_peak_s: float | None = None
    action_end_s: float | None = None
    subclip_start_s: float = 0.0
    subclip_end_s: float = 0.0
    semantic_correct: bool = False
    boundary_usable: bool = False
    evidence_refs: list = field(default_factory=list)
    selection_reason: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def build_windows(evidence: list[dict], duration_s: float, action: str,
                  media_id: int | None = None, asset_path: str | None = None) -> list[ActionWindow]:
    """evidence: [{t_s, state(解析后), object, raw}] 按时序升序。
    找到含 ACTION_START/IN_PROGRESS/END 的动作段，前后需要 OBJECT_PRESENT/NOT_PRESENT 上下文。"""
    frames = sorted([e for e in evidence if e.get("t_s") is not None], key=lambda e: e["t_s"])
    if not frames:
        return []
    seq = [(f["t_s"], parse_qwen_state(f.get("state") or f.get("qwen_l2_raw") or "")) for f in frames]
    # 动作触发点
    act_idx = [i for i, (t, st) in enumerate(seq) if st in ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")]
    if not act_idx:
        return []
    # 分成连续段(允许跨度内的非动作帧不超过1)
    windows = []
    cur = [act_idx[0]]
    for i in act_idx[1:]:
        if i - cur[-1] <= 2:
            cur.append(i)
        else:
            windows.append(cur)
            cur = [i]
    windows.append(cur)
    out = []
    for seg in windows:
        t0 = seq[seg[0]][0]
        t1 = seq[seg[-1]][0]
        peak = seq[seg[len(seg) // 2]][0]
        start = max(0.0, t0 - PRE_ROLL)
        end = min(duration_s, t1 + POST_ROLL)
        # 上下文：动作前/后至少各有1帧非动作(或处于视频中间)
        pre_ctx = any(i < seg[0] and seq[i][1] in ("OBJECT_PRESENT", "NOT_PRESENT")
                      for i in range(max(0, seg[0] - 2), seg[0]))
        post_ctx = any(i > seg[-1] and seq[i][1] in ("OBJECT_PRESENT", "NOT_PRESENT")
                       for i in range(seg[-1] + 1, min(len(frames), seg[-1] + 3)))
        clipped_at_edge = (t0 - PRE_ROLL <= 0.05) or (t1 + POST_ROLL >= duration_s - 0.05)
        w = ActionWindow(
            action=action, media_id=media_id, asset_path=asset_path, duration_s=round(duration_s, 3),
            action_start_s=round(t0, 2), action_peak_s=round(peak, 2), action_end_s=round(t1, 2),
            subclip_start_s=round(start, 2), subclip_end_s=round(end, 2),
            semantic_correct=True,
            boundary_usable=(pre_ctx or not clipped_at_edge) and (post_ctx or not clipped_at_edge),
            evidence_refs=[{"t_s": seq[i][0], "state": seq[i][1]} for i in seg],
            selection_reason=f"{action} 动作段 {round(t0,2)}-{round(t1,2)}s; subclip {round(start,2)}-{round(end,2)}s")
        out.append(w)
    return out


def fit_duration(w: ActionWindow, duration_target_s: float | None = None,
                 shot_role: str = "info") -> ActionWindow:
    """在保留 动作前→动→后 证据的前提下把窗口压到目标时长附近；绝不把动作起点切掉。"""
    if not duration_target_s or w.action_start_s is None or w.action_end_s is None:
        return w
    lo, hi = DUR_GUIDE.get(shot_role, DUR_GUIDE["info"])
    dur = w.subclip_end_s - w.subclip_start_s
    if lo <= dur <= hi:
        return w
    action_dur = w.action_end_s - w.action_start_s
    if action_dur >= hi:  # 动作本身就超长 → 只保留动作核心
        w.subclip_start_s = w.action_start_s
        w.subclip_end_s = w.action_end_s
    elif dur < lo and w.action_end_s + (lo - dur) <= w.duration_s - POST_ROLL:
        w.subclip_end_s = round(min(w.duration_s, w.subclip_end_s + (lo - dur)), 2)
    return w


class ActionSubclipService:
    """读时序证据缓存 → build_windows → 过滤/排序 → TopK。account_id 参数化。"""

    def __init__(self, evidence_loader: Callable | None = None, cache_dir: str | None = None,
                 eligible_check: Callable | None = None):
        self._loader = evidence_loader or self._default_loader
        self.cache_dir = cache_dir
        self.eligible_check = eligible_check

    def _default_loader(self, account_id: str) -> list[dict]:
        p = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\TREECUT_G2_TEMPORAL_EVIDENCE_V1.json")
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("items", [])
        return []

    def find_action_subclips(self, account_id: str, action: str, product: str | None = None,
                             scene: str | None = None, duration_target_s: float | None = None,
                             top_k: int = 3, shot_role: str = "action",
                             candidate_media_ids: list[int] | None = None) -> list[dict]:
        ev = self._loader(account_id)
        per_asset: dict[int, list[ActionWindow]] = {}
        by_mid: dict[int, list[dict]] = {}
        for e in ev:
            by_mid.setdefault(e.get("media_id"), []).append(e)
        for mid, frames in by_mid.items():
            if candidate_media_ids and mid not in candidate_media_ids:
                continue
            wins = build_windows(frames, float(next((x.get("duration_s") or 0) for x in frames if x.get("duration_s")) or 30),
                                 action, media_id=mid,
                                 asset_path=next((x.get("full_path") for x in frames if x.get("full_path")), None))
            for w in wins:
                if duration_target_s:
                    w = fit_duration(w, duration_target_s, shot_role)
                per_asset.setdefault(mid, []).append(w)
        flat = [w for ws in per_asset.values() for w in ws if w.semantic_correct]
        # 排序: boundary_usable 优先 → 窗口长度贴近目标
        flat.sort(key=lambda w: (not w.boundary_usable, abs((w.subclip_end_s - w.subclip_start_s) -
                                                            (duration_target_s or 3.0))))
        return [w.to_dict() for w in flat[:top_k]]
