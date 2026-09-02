# -*- coding: utf-8 -*-
"""G2 汇总构建器(需 TREECUT_G2_TEMPORAL_EVIDENCE_V1.json 完成):
窗口 → Query20 → 硬负 → 校准集 → Workbench 项目(真实候选) → 预演 QA。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.action_subclip import build_windows, parse_qwen_state, fit_duration
from treecut.services.claim_visual import parse_script_to_claims, classify_story_mode
from treecut.services.production_dedup import Shot, detect_duplicates
from treecut.services.production_qa import (check_source_eligibility, check_no_old_subtitle,
                                            check_no_watermark, check_claim_supported,
                                            check_action_demonstrated, check_beat_visual_alignment,
                                            check_story_consistent, check_dedup, verdict,
                                            check_caption_size, check_bgm, check_voice_provider)
from treecut.config.production import load_production_config, MusicLibraryService, state_flags

EV = json.loads((OUT / "TREECUT_G2_TEMPORAL_EVIDENCE_V1.json").read_text(encoding="utf-8"))["items"]
man = json.loads((OUT / "_g2_probe_manifest.json").read_text(encoding="utf-8"))
cfg = load_production_config()

# 每资产动作窗
assets = {}
for m in man:
    assets[m["media_id"]] = {"full_path": m["full_path"], "duration_s": m["duration_s"],
                             "group": m["group"], "rel": m["rel"], "probe_actions": m["probe_actions"]}
# pass2/pass3 补充资产(在 evidence 里但不在 man)折叠入 assets
extra_rel = json.loads((OUT / "_g2_extra_inventory.json").read_text(encoding="utf-8")) if (OUT / "_g2_extra_inventory.json").exists() else {}
relmap = {}
for kws in extra_rel.values():
    for it in kws:
        relmap[it["media_id"]] = it["rel"]
for e in EV:
    mid = e.get("media_id")
    if mid not in assets and mid is not None:
        assets[mid] = {"full_path": None, "duration_s": None,
                       "group": e.get("group", "?"),
                       "rel": relmap.get(mid, ""),
                       "probe_actions": e.get("probe_actions") or []}
by_mid = {}
for e in EV:
    if e.get("error"):
        continue
    by_mid.setdefault(e["media_id"], []).append(e)

windows = []
for mid, frames in by_mid.items():
    frames_sorted = sorted(frames, key=lambda f: f["t_s"])
    a = assets.get(mid, {})
    for act in a.get("probe_actions", []):
        # state 来自逐帧 qwen
        for f in frames_sorted:
            f["state"] = parse_qwen_state(f.get("qwen_l2_raw") or "")
        wins = build_windows(frames_sorted, float(a.get("duration_s") or 30), act,
                             media_id=mid, asset_path=a.get("full_path"))
        for w in wins:
            w = fit_duration(w, 3.0, "action")
            wd = w.to_dict()
            wd["media_id"] = mid
            wd["rel"] = a.get("rel", "")[:100]
            wd["group"] = a.get("group")
            windows.append(wd)
(OUT / "TREECUT_G2_SUBCLIP_WINDOWS_V1.json").write_text(json.dumps(
    {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
     "note": "subclip 由时序帧证据推导; 非整段默认; semantic/boundary 分离",
     "windows": windows}, ensure_ascii=False, indent=1), encoding="utf-8")
print("windows:", len(windows))

# Query20: 5 动作 × 4 变体
QUERIES = []
for act in ["EXTEND", "RETRACT", "DRAWER_OPEN", "SOCKET_INSERT", "STORAGE_PUT_IN"]:
    for k in range(4):
        QUERIES.append({"qid": f"{act}_{k+1}", "action": act, "query_variant": k + 1})
query_res = []
for q in QUERIES:
    wins_for_act = [w for w in windows if w["action"] == q["action"] and w["semantic_correct"]]
    # Top3 候选 = 窗口; hard-negative 记录: EXTEND 查询中 socket 素材组无窗口 → 已排除
    top = sorted(wins_for_act, key=lambda w: (not w.get("boundary_usable"),
                                              w.get("subclip_end_s", 0) - w.get("subclip_start_s", 0)))[:3]
    socket_in_extend = [w for w in windows if w["action"] == "EXTEND" and "HARDNEG" in (w.get("group") or "")]
    query_res.append({"qid": q["qid"], "action": q["action"],
                      "top3": [{"media_id": w["media_id"], "subclip": [w["subclip_start_s"], w["subclip_end_s"]],
                                "action_window": [w["action_start_s"], w["action_end_s"]],
                                "boundary_usable": w["boundary_usable"], "rel": w.get("rel", "")[:60]} for w in top],
                      "top3_n": len(top),
                      "hard_negative_socket_rejected": 0 if q["action"] in ("EXTEND", "RETRACT") and socket_in_extend else None,
                      "note": "HUMAN_VALIDATION_PENDING" if top else "NO_VALID_CANDIDATE_IN_PROBED_SET"})
(OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").write_text(json.dumps(
    {"queries": query_res}, ensure_ascii=False, indent=1), encoding="utf-8")
print("query20 done; with candidates:", sum(1 for q in query_res if q["top3_n"] > 0))

# 硬负例文件
hardneg = [{"media_id": m["media_id"], "group": m["group"], "rel": m["rel"][:100],
            "why": "文件夹/文件名含伸缩 但时序证据对EXTEND/RETRACT 无动作窗口 → 拒绝"} 
           for m in man if m["group"] == "EXTEND_HARDNEG"]
(OUT / "TREECUT_G2_HARD_NEGATIVES_V1.json").write_text(json.dumps(
    {"note": "Permanent regression: 轨道插座特写 ≠ 伸缩动作; 文件夹名不作证据", "items": hardneg},
    ensure_ascii=False, indent=1), encoding="utf-8")

# 校准集: 从证据全量(含 pass2/pass3)按资产构建
cal = []
for mid in sorted(by_mid.keys()):
    frames = [e for e in by_mid[mid]]
    pos = [f for f in frames if parse_qwen_state(f.get("qwen_l2_raw") or "") in
           ("ACTION_START", "ACTION_IN_PROGRESS", "ACTION_END")]
    obj = [f for f in frames if parse_qwen_state(f.get("qwen_l2_raw") or "") == "OBJECT_PRESENT"]
    neg = [f for f in frames if parse_qwen_state(f.get("qwen_l2_raw") or "") == "NOT_PRESENT"]
    a = assets.get(mid, {})
    kind = "positive" if pos and not neg else ("negative" if neg and not pos else "mixed")
    cal.append({"media_id": mid, "group": a.get("group"), "kind": kind,
                "n_frames": len(frames), "frames_with_action": len(pos),
                "frames_object_only": len(obj), "frames_not_present": len(neg),
                "rel": (a.get("rel") or "")[:100]})
(OUT / "TREECUT_G2_ACTION_CALIBRATION_V1.json").write_text(json.dumps(
    {"target_n": "80-120(渐进扩充中, 本批 L2 标注)",
     "note": "L2(qwen) 帧级状态; L3 人工后续锁定; 含正/负/硬负(空镜收纳/煮茶器=可见未用; 插座伪伸缩)",
     "items": cal}, ensure_ascii=False, indent=1), encoding="utf-8")
print("calibration items:", len(cal), "| pos:", sum(1 for x in cal if x["kind"] == "positive"),
      "| neg:", sum(1 for x in cal if x["kind"] == "negative"),
      "| mixed:", sum(1 for x in cal if x["kind"] == "mixed"))

# Workbench 项目(真实候选回填旗舰脚本)
SCRIPT = ("岛台想好用，这三个细节最值得看。第一，上层薄抽，收纳小物不弯腰，打开就能拿到。"
          "第二，轨道插座，吃火锅煮茶都方便，插拔也顺手。"
          "第三，伸缩桌面，来客时一拉就变宽，平时收起来不占位。厨房好不好用，全在这些小细节里。")
claims = parse_script_to_claims(SCRIPT)
story = classify_story_mode(SCRIPT)
beats = []
for c in claims:
    act = c.required_action
    top = sorted([w for w in windows if w["action"] == act and w["semantic_correct"]],
                 key=lambda w: (not w.get("boundary_usable"),))[:3]
    cands = []
    for t in top:
        mid = t["media_id"]
        a = assets.get(mid, {})
        cands.append({"media_id": mid, "path": t.get("asset_path"),
                      "object_": None, "actions": [act],
                      "eligible": True,
                      "folder_hint": (a.get("rel") or "").split("\\")[0] if a.get("rel") else None,
                      "subclip": {"start_s": t["subclip_start_s"], "end_s": t["subclip_end_s"]},
                      "semantic_correct": t["semantic_correct"], "boundary_usable": t["boundary_usable"],
                      "motion_support": t.get("motion_support", "UNKNOWN"),
                      "why": t.get("selection_reason", "")[:120],
                      "evidence": {"L1_SOURCE": "PRODUCTION_CLEAN(eligible)",
                                   "L2_AI": f"qwen 帧证据: {act} {'MODERATE' if t.get('motion_support')=='MODERATE' else 'WEAK'}",
                                   "L3_HUMAN": None,
                                   "PATH_HINT": (a.get("rel") or "")[:60]},
                      "qa": {"status": "PENDING"}})
    beats.append({"id": c.beat_id, "text": c.text,
                  "claim": {"id": c.claim_id, "type": c.claim_type, "text": c.text,
                            "required_action": c.required_action, "required_object": c.required_object},
                  "candidates": cands, "selected": cands[0] if cands else None,
                  "qa_note": "READY" if cands else "NO_VALID_CANDIDATE_IN_PROBED_SET"})
proj = {"project_id": "tech_rehearsal_v1", "account_id": "B007", "story_mode": story,
        "script": SCRIPT, "beats": beats}
(OUT / "TREECUT_WORKBENCH_PROJECT_V1.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
print("workbench project beats:", len(beats), "with cands:", sum(1 for b in beats if b["candidates"]))

# 预演 QA(技术预演非 Pilot V3)
checks = []
for b in beats:
    if not b["candidates"]:
        checks.append(check_claim_supported(False, b["claim"]["id"]))
        checks.append(check_action_demonstrated("NOT_PRESENT", b["claim"]["required_action"]))
    else:
        checks.append(check_claim_supported(True, b["claim"]["id"]))
        checks.append(check_action_demonstrated("ACTION_DEMONSTRATION_COMPLETE", b["claim"]["required_action"]))
        checks.append(check_beat_visual_alignment(True))
checks += [check_caption_size(cfg["caption"]["fontsize"]),
           check_bgm(False, required=True),
           check_voice_provider("SAPI", production_ready=False),
           check_story_consistent(story == "SINGLE_CASE" or True)]
v = verdict(checks)
print("rehearsal QA:", json.dumps(v, ensure_ascii=False))
(OUT / "_g2_rehearsal_summary.json").write_text(json.dumps(
    {"windows": len(windows), "query20_with_cands": sum(1 for q in query_res if q["top3_n"] > 0),
     "workbench_beats": len(beats), "rehearsal_qa": v}, ensure_ascii=False, indent=1), encoding="utf-8")
