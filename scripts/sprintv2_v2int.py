# -*- coding: utf-8 -*-
"""V2 集成(吸收附录): ①窗口级负例记忆(非全段黑名单, 1985 保留 TRACK_SOCKET 可用性);
②同窗 OPEN+CLOSE 才歧义丢弃(不同时间窗可共存); ③展开检索(有界 qwen) ④OLD-vs-NEW Query20。"""
import json, re, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.action_subclip import build_windows, apply_action_gate, parse_qwen_state, fit_duration
from treecut.services.visual_beat import group_visual_beats, audit_action_availability, suggest_script_fix

now = time.strftime("%Y-%m-%d %H:%M:%S")

# ============ 1) 窗口级负例记忆(用审核包实际展示窗口, 精确 scope) ============
adj = json.loads((OUT / "TREECUT_STAGE8_HUMAN_ADJUDICATION_V1.json").read_text(encoding="utf-8"))
labels = json.loads((OUT / "TREECUT_CURRENT_VIDEO_EXAMPLE_LABELS_V1.json").read_text(encoding="utf-8"))
pkg = json.loads((OUT / "human_review_package" / "TREECUT_G2_CHATGPT_REVIEW_V1.json").read_text(encoding="utf-8"))
# 包内每条候选带被审窗口
pkg_win = {}
for it in pkg.get("queries", []):
    if not it.get("segment_short"):
        continue
    key = (it["requested_action"], str(it["segment_short"]))
    pkg_win.setdefault(key, []).append((it.get("subclip_start"), it.get("subclip_end")))

memory = []
for qid, r in (adj.get("g2", {}).get("results", {})).items():
    act = qid.rsplit("_", 1)[0]
    for tr in r.get("top_results", []):
        mid = str(tr["segment_short"])
        wins = pkg_win.get((act, mid)) or [(None, None)]
        s, e = wins[0]
        memory.append({"requested_action": act, "segment_id": mid,
                       "reviewed_window_start": s, "reviewed_window_end": e,
                       "review_scope": "SUBCLIP_WINDOW",
                       "review_result": tr.get("human_result", "BAD"),
                       "reason_codes": ["DOMINANT_VISUAL_MISMATCH", "NO_TABLETOP_GEOMETRY_CHANGE"]
                       if act in ("EXTEND", "RETRACT") else ["STATE_NOT_ACTION", "NO_DIRECTION_PROOF"],
                       "human_note": r.get("human_note", "")[:150],
                       "review_version": "2026-09-03-v1"})
# supports_by_segment: 来自 example labels(素材可为/不可为)
supports_map = {}
for it in labels.get("items", []):
    for seg in it.get("segments", []):
        sup = supports_map.setdefault(str(seg), {"supports": [], "invalid_for": []})
        sup["invalid_for"].append(it.get("requested_action"))
        sup.setdefault("observed_visual", it.get("observed_visual", ""))
        sup.setdefault("actual_support", it.get("actual_support", ""))
        # 若 actual_support 描述可支持语义(如 SOCKET_ADJUST candidate), 粗拆
        for tok in re.findall(r"[A-Z_]+", it.get("actual_support", "")):
            if tok not in sup["supports"]:
                sup["supports"].append(tok)
mem_json = {"memory": memory, "supports_by_segment": supports_map,
            "note": "窗口级负例记忆(review_scope=SUBCLIP_WINDOW); 不禁止整段素材用于其它动作/窗口; 1985 对 EXTEND/RETRACT 无效但可用于 TRACK_SOCKET/SOCKET_ADJUST"}
(OUT / "TREECUT_REVIEW_EXAMPLE_MEMORY_V1.json").write_text(json.dumps(mem_json, ensure_ascii=False, indent=1), encoding="utf-8")
print("negative memory entries:", len(memory), "| supports segments:", len(supports_map))

# ============ 2) 重建窗口(方向门, 同窗歧义) 后再按记忆窗口过滤(不杀整段) ============
EV = json.loads((OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json").read_text(encoding="utf-8"))["items"]
man = {m["media_id"]: m for m in json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))}
by_mid = {}
for e in EV:
    by_mid.setdefault(e.get("media_id"), []).append(e)

def overlap(a0, a1, b0, b1):
    return not (a1 <= b0 or b1 <= a0)

def window_blocked(act, mid, s, e, mem):
    for m in mem:
        if m["requested_action"] == act and str(m["segment_id"]) == str(mid) and m.get("reviewed_window_start") is not None:
            if overlap(float(m["reviewed_window_start"]), float(m["reviewed_window_end"]), s, e):
                return True
    return False

windows = []
for mid, frames in by_mid.items():
    frames = sorted(frames, key=lambda f: f.get("t_s") or 0)
    dur = next((a.get("duration_s") for a in man.values() if a["media_id"] == mid), None) or 30.0
    a = man.get(mid, {})
    for act in (a.get("probe_actions") or []):
        for f in frames:
            f["state"] = parse_qwen_state(f.get("qwen_l2_raw") or "")
        wins = build_windows(frames, float(dur), act, media_id=mid, asset_path=a.get("full_path"))
        wins = apply_action_gate(wins, frames)
        for w in wins:
            w = fit_duration(w, 3.0, "action")
            wd = w.to_dict()
            wd["media_id"] = mid
            wd["rel"] = (a.get("rel") or "")[:100]
            wd["group"] = a.get("group")
            if window_blocked(act, mid, wd["subclip_start_s"], wd["subclip_end_s"], memory):
                wd["excluded_by_review_memory"] = True
            windows.append(wd)
from collections import Counter
keep = [w for w in windows if not w.get("excluded_by_review_memory")]
(OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").write_text(json.dumps(
    {"generated_at": now, "note": "R2门 + 窗口级负例记忆过滤(非整段黑名单); 素材可跨动作复用",
     "windows": keep}, ensure_ascii=False, indent=1), encoding="utf-8")
print("windows:", len(keep), dict(Counter(w["action"] for w in keep)),
      "| memory-excluded:", len(windows) - len(keep))

# ============ 3) OLD-vs-NEW Query20 ============
QUERIES = ["EXTEND", "RETRACT", "DRAWER_OPEN", "SOCKET_INSERT", "STORAGE_PUT_IN"]
qres = []
for act in QUERIES:
    old_had = sum(1 for q in json.loads((OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").read_text(encoding="utf-8"))["queries"]
                  if q["action"] == act and q["top3_n"])
    for k in range(4):
        top = sorted([w for w in keep if w["action"] == act and w.get("semantic_correct")],
                     key=lambda w: (not w.get("boundary_usable"),
                                    w.get("subclip_end_s", 0) - w.get("subclip_start_s", 0)))[:3]
        qres.append({"qid": f"{act}_{k+1}", "action": act,
                     "top3": [{"media_id": w["media_id"], "subclip": [w["subclip_start_s"], w["subclip_end_s"]],
                               "action_window": [w["action_start_s"], w["action_end_s"]],
                               "boundary_usable": w["boundary_usable"], "motion_support": w.get("motion_support")}
                              for w in top],
                     "top3_n": len(top),
                     "note": "HUMAN_VALIDATION_PENDING" if top else "NO_VALID_SOURCE(CURRENT_SET_EXHAUSTED→EXPAND_RETRIEVAL)"})
(OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").write_text(json.dumps({"queries": qres}, ensure_ascii=False, indent=1), encoding="utf-8")
print("query20 with candidates:", sum(1 for q in qres if q["top3_n"]), "/20")

# ============ 4) 5 视觉 Beat 保留原子 Claims ============
SCRIPT = ("岛台想好用，这三个细节最值得看。第一，上层薄抽，收纳小物不弯腰，打开就能拿到。"
          "第二，轨道插座，吃火锅煮茶都方便，插拔也顺手。"
          "第三，伸缩桌面，来客时一拉就变宽，平时收起来不占位。厨房好不好用，全在这些小细节里。")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.claim_visual import parse_script_to_claims, classify_story_mode
claims = parse_script_to_claims(SCRIPT)
beats = group_visual_beats([c.__dict__ for c in claims])
proj = {"project_id": "tech_rehearsal_v1", "account_id": "B007",
        "story_mode": classify_story_mode(SCRIPT), "script": SCRIPT,
        "visual_beats": [{"id": b["id"], "kind": b["kind"], "text": b["text"],
                          "required_actions": b["required_actions"], "main_action": b["main_action"],
                          "atomic_claims": b["claims"],
                          "candidates": []} for b in beats]}
(OUT / "TREECUT_WORKBENCH_PROJECT_V1.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
print("visual beats:", len(beats), "| total claims retained:", sum(len(b["claims"]) for b in beats))
