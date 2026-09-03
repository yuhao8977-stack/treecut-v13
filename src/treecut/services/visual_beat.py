"""STAGE8 — Visual Beat 归组 + 脚本可用性审计(R4/R5 人工反馈).

人工裁决(2026-09-03): 文本 Claim != 必须换镜。"第一/第二/第三" 等结构词不得单独成 Beat;
Hook/CTA 泛化句可与相邻句合并; 核心动作 Beat 无候选 → Production 不得继续, 触发素材不足/脚本改写。
"""
from __future__ import annotations

import re

SEPARATORS = ("第一", "第二", "第三", "第四", "首先", "其次", "最后", "再")
GENERIC_HOOK = ("岛台", "好用", "细节", "值得", "厨房", "想")


def _start_new_feature(text: str) -> bool:
    return any(s in text for s in SEPARATORS) and len(text) <= 6 or bool(re.match(r"^[一二三]+\s*[,，]", text or ""))


def group_visual_beats(claims: list) -> list[dict]:
    """把细碎文本 Claim 归并为视觉 Beat(5 段式: hook / f1 / f2 / f3 / cta)。
    claims: [{claim_id, beat_id, text, claim_type, required_action, required_object}...]"""
    beats: list[dict] = []
    for c in claims:
        text = (c.get("text") or "").strip()
        is_sep = any(text.startswith(s) for s in SEPARATORS)
        if not beats:
            beats.append({"id": "VB1", "texts": [text], "claims": [c],
                          "required_actions": _actions(c), "main_action": _main(c),
                          "kind": "hook"})
            continue
        cur = beats[-1]
        if is_sep and len(beats) < 4:
            # 结构词并入下一功能段(不单独成 Beat)
            beats.append({"id": f"VB{len(beats)+1}", "texts": [text], "claims": [c],
                          "required_actions": _actions(c), "main_action": _main(c), "kind": "feature"})
            continue
        # 其余句并入当前段(保持镜头连续, 泛化 CTA 收尾)
        cur["texts"].append(text)
        cur["claims"].append(c)
        cur["required_actions"] = sorted(set(cur["required_actions"]) | set(_actions(c)))
        if cur["main_action"] is None:
            cur["main_action"] = _main(c)
    # 若最后一段是纯泛化(无动作/对象)→ 归为 cta
    for b in beats:
        b["text"] = "，".join(b["texts"])[:160]
    if beats and len(beats) >= 2 and not beats[-1]["required_actions"] and \
            len([x for x in beats[-1]["claims"] if x.get("claim_type") in ("ACTION", "OBJECT")]) == 0:
        beats[-1]["kind"] = "cta"
    return beats


def _actions(c: dict) -> list:
    a = c.get("required_action")
    return [a] if a else []


def _main(c: dict):
    return c.get("required_action")


def audit_action_availability(required_actions: list, windows_by_action: dict,
                              inventory_hints: dict | None = None) -> dict:
    """每动作: supported(window 存在)/object_only(仅有目录提示)/no_source。"""
    out = {}
    for act in required_actions:
        n_w = len(windows_by_action.get(act, []))
        n_hint = len((inventory_hints or {}).get(act, []))
        if n_w >= 1:
            out[act] = {"status": "SUPPORTED", "windows": n_w, "hints": n_hint}
        elif n_hint >= 1:
            out[act] = {"status": "OBJECT_ONLY_NO_ACTION_EVIDENCE", "windows": 0, "hints": n_hint}
        else:
            out[act] = {"status": "NO_SOURCE", "windows": 0, "hints": 0}
    return out


def suggest_script_fix(text: str, availability: dict) -> dict:
    """无动作素材的动作子句 → 建议删除/改写(Production 不静默继续)。"""
    drops = []
    for act, st in availability.items():
        if st["status"] == "NO_SOURCE":
            drops.append(act)
    fixed = text
    # 简单句级: 若某分句命中缺失动作词 → 标出待改写
    notes = []
    words = {"EXTEND": "变宽|拉出|伸缩|加宽", "RETRACT": "收起|收起来|缩回",
             "SOCKET_INSERT": "插拔|插上|插进", "DRAWER_OPEN": "拉开|打开",
             "STORAGE_PUT_IN": "放进去|收纳小物|放东西"}
    drops = []
    for act, st in availability.items():
        if st["status"] == "NO_SOURCE":
            drops.append(act)
            w = words.get(act, "")
            if w and re.search(w, fixed):
                notes.append(f"动作『{act}』无可用素材(no_source)→ 删除/改写对应子句, 勿静默配错画面")
        elif st["status"] == "OBJECT_ONLY_NO_ACTION_EVIDENCE":
            w = words.get(act, "")
            if w and re.search(w, fixed):
                drops.append(act)
                notes.append(f"动作『{act}』只有对象/静态画面, 无动作证据(ACTION 主张不得用静态冒充)→ 改写为对象主张或删动作子句")
    drops = sorted(set(drops))
    return {"original": text, "action_availability": availability,
            "unsupported_actions": drops,
            "rewrite_required": bool(notes), "notes": notes,
            "production_blocked": bool(notes),
            "fixed_text_placeholder": "由文案层按 note 删除/改写子句后重新审计"}
