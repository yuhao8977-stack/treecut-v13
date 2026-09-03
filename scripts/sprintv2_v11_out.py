# -*- coding: utf-8 -*-
"""V1.1 收尾: 指标/产物/GAP 状态 + 4条跨段合并新候选动态审核包(含contexts)。"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from hrp_builder import PKG, WORK, title_card, candidate_pieces, concat
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
now = time.strftime("%Y-%m-%d %H:%M:%S")
res = json.loads((OUT / "_v11_results.json").read_text(encoding="utf-8"))
ranked = json.loads((OUT / "_v11_ranked.json").read_text(encoding="utf-8"))
rr = json.loads((OUT / "_v11_rr_promote.json").read_text(encoding="utf-8"))
xs = json.loads((OUT / "_v11_crossseg_scored.json").read_text(encoding="utf-8"))
bv = json.loads((OUT / "_v11_branch_verify.json").read_text(encoding="utf-8"))
fx = json.loads((OUT / "_v11_flexible_merged_direction.json").read_text(encoding="utf-8"))

summary = res["summary"]
metrics = {}
for act, s in summary.items():
    metrics[act] = {"broad_ranked": len(ranked.get(act, [])),
                    "motion_probed": s["probed_motion"], "temporal_shortlist": s["shortlist"],
                    "qwen": s["qwen"], "tvrc_pass": s["tvrc_pass"],
                    "rr_promoted_clean": sum(1 for x in rr.get(act, []) if x.get("result") == "PROMOTED_ELIGIBLE"),
                    "rr_action_verified_pass": sum(1 for x in bv.get(act, []) if x.get("verdict") == "PASS"),
                    "crossseg_merged_motion": len(bv.get("_crossseg_extend", [])),
                    "final_top3": s["final_top"],
                    "note": "Eligible 全量廉价排序+短名单+qwen 后 0 PASS; 跨段合并恢复出 motion 候选(方向待人工)"}
payload = {"version": "V1.1", "metrics": metrics, "generated_at": now}
(OUT / "TREECUT_ACTION_CANDIDATE_DISCOVERY_V1.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

gap = {"status_per_action": {a: "MATERIAL_GAP_CANDIDATE" for a in summary},
       "confirm_blocked_by": ["cross-segment 恢复出 motion 候选(方向未定)需人工/细化",
                              "Eligible/RR 顶候选无动作态"],
       "new_candidates_for_review": fx,
       "conclusion": "Recall 验证 V1.1: Eligible 全量排序+qwen 0 PASS; RR 57 提升(污染干净)但动作验证未过; "
                     "跨段合并恢复 4 条 motion 候选(UNSURE 方向)→ 需人工看片定 EXTEND/RETRACT/对象",
       "generated_at": now}
(OUT / "TREECUT_MATERIAL_GAP_STATUS_V2.json").write_text(json.dumps(gap, ensure_ascii=False, indent=1), encoding="utf-8")

md = f"""# STAGE8 Candidate Discovery Recovery V1.1 报告（{now}）

## 结论
- **不再随机10**：五动作 Eligible 池全量廉价排序(flexible 333 共享 EXTEND/RETRACT, drawer 888, storage 1200, socket 464) → 运动代理 top24 → 短名单12 → qwen top6 → **TVRC 0 PASS**
- REVIEW_REQUIRED 定向验证并**正规 G1 提升 57 条**（EXTEND12/RETRACT9/DRAWER12/STORAGE12/SOCKET12，记录 recovery_v11 证据）——但其顶候选动作验证仍未通过（NO_ACTION/UNCERTAIN）
- **跨段边界恢复有发现**：13,605→动作相关40→31 连续 → 合并窗动作态 PASS 4 条（media 51/109/89/52，flexible 族）——方向复核多为 STATIC/UNCERTAIN、media89=EXTEND(L2) → **UNSURE 待人工**
- 结论：Recall 在三支线均深挖后，Eligible/RR 仍无确认动作；跨段合并证明"切镜切断动作"真实存在并恢复出运动候选 → **不得 CONFIRMED**，先人工看 4 条合并窗

## 漏斗指标（§23）
| Action | 全量廉价 | 运动探测 | 短名单 | Qwen | TVRC PASS | RR提升 | 跨段合并motion |
""" + "\n".join(f"| {a} | {m['broad_ranked']} | {m['motion_probed']} | {m['temporal_shortlist']} | {m['qwen']} | {m['tvrc_pass']} | {m['rr_promoted_clean']} | {len(bv.get('_crossseg_extend', []))} |" for a, m in metrics.items()) + f"""

## 新候选(人工)
- TREECUT_G2_CROSSSEG_REVIEW_V1.mp4/.json：4 条合并窗(含 contexts)，方向/对象待人工
"""
(DOCS / "TREECUT_STAGE8_CANDIDATE_DISCOVERY_REPORT_V1.md").write_text(md, encoding="utf-8")
(OUT / "TREECUT_STAGE8_CANDIDATE_DISCOVERY_REPORT_V1.md").write_text(md, encoding="utf-8")

# 4 条合并窗新候选 → 小型动态审核包
pieces = []
for i, f in enumerate(fx):
    card = title_card([f"MERGE {i+1} | media {f['media_id']} | FLEXIBLE", f"window {f['merged_window_s'][0]}-{f['merged_window_s'][1]}s",
                       f"direction_probe={f['direction']} (STATIC/UNCERTAIN→UNSURE; EXTEND→候选)", ""],
                      WORK / f"v11_card_{i}.mp4")
    if card:
        pieces.append(card)
    pp = candidate_pieces(f["media_id"], float(f["merged_window_s"][0]), float(f["merged_window_s"][1]),
                          f"MERGE {i+1} TOP1 | media {f['media_id']} | req=FLEXIBLE(EXTEND/RETRACT) | dir={f['direction']}",
                          f"v11_{i}")
    pieces += pp
final = PKG / "TREECUT_G2_CROSSSEG_REVIEW_V1.mp4"
ok = concat([str(p) for p in pieces if p is not None], final)
(PKG / "TREECUT_G2_CROSSSEG_REVIEW_V1.json").write_text(json.dumps(
    {"candidates": fx, "level": "HUMAN_REVIEW_EVIDENCE", "human_result": None}, ensure_ascii=False, indent=1), encoding="utf-8")
print("crossseg review video ok:", ok, final.exists() if final.exists() else "missing")

f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["discovery_recovery"]["v11"] = {"random10_removed": True, "metrics": metrics,
                                   "crossseg_merged_review": "TREECUT_G2_CROSSSEG_REVIEW_V1.mp4",
                                   "updated_at": now}
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("V1.1 outputs written")
