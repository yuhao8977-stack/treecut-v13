# -*- coding: utf-8 -*-
"""Discovery 收尾: 产物文件(TREECUT_*_DISCOVERY_V1 / GAP_STATUS_V2 / 报告) + 状态。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
now = time.strftime("%Y-%m-%d %H:%M:%S")
prog = json.loads((OUT / "_g2_discovery_progress.json").read_text(encoding="utf-8"))
rr = json.loads((OUT / "TREECUT_REVIEW_REQUIRED_ACTION_RECOVERY_V1.json").read_text(encoding="utf-8"))
xs = json.loads((OUT / "TREECUT_CROSS_SEGMENT_ACTION_RECOVERY_V1.json").read_text(encoding="utf-8"))

per = {}
for act, m in prog["metrics"].items():
    fn = f"TREECUT_{act}_DISCOVERY_V1.json"
    payload = {"action": act, "funnel": {
        "broad_eligible_union": m["broad_eligible_union"],
        "cheap_sample": m["cheap_sample"],
        "motion_shortlist": m["motion_high_shortlist"],
        "qwen_reviewed": m["qwen_reviewed"],
        "tvrc_pass": m["tvrc_pass"],
        "tvrc_fail": m["tvrc_fail"]},
        "note": m["note"],
        "material_gap": "CANDIDATE_NOT_CONFIRMED",
        "generated_at": now}
    (OUT / fn).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    per[act] = payload

agg = {"actions": per,
       "review_required_recovery": {a: v["high_value_candidates"] for a, v in rr["actions"].items()},
       "cross_segment_merge_candidates": xs["count"],
       "generated_at": now}
(OUT / "TREECUT_ACTION_CANDIDATE_DISCOVERY_V1.json").write_text(json.dumps(agg, ensure_ascii=False, indent=1), encoding="utf-8")

gap_v2 = {"status_per_action": {a: "MATERIAL_GAP_CANDIDATE" for a in per},
          "cannot_confirm_until": ["REVIEW_REQUIRED 高价值定向 contamination verify",
                                   "cross-segment 合并候选时序探测",
                                   "更大廉价样本(样本非穷举)"],
          "review_required_pending_verify": {a: v["high_value_candidates"] for a, v in rr["actions"].items()},
          "cross_segment_pending_probe": xs["count"],
          "conclusion": "Recall 验证: Eligible 池样本中动作证据稀缺(0 通过动作门), 但 REVIEW_REQUIRED(157 高价值) 与跨段(13,605)未核 → 不得标 CONFIRMED; 不要求补拍",
          "generated_at": now}
(OUT / "TREECUT_MATERIAL_GAP_STATUS_V2.json").write_text(json.dumps(gap_v2, ensure_ascii=False, indent=1), encoding="utf-8")

md = f"""# STAGE8 Candidate Discovery Recovery V1 报告（{now}）

## 结论
- Recall 验证(分层漏斗, 非 Top3): Eligible 池每动作宽召回数百(EXTEND 327/DRAWER 395/STORAGE 396/SOCKET 394), 样本(10/动作)+qwen(4/动作) 后 **0 通过动作门**(方向 UNCERTAIN/静态 保守拒绝) → Eligible 池标签下动作证据稀缺
- **不得标 MATERIAL_GAP_CONFIRMED**：REVIEW_REQUIRED 高价值候选(EXTEND 21/DRAWER 59/STORAGE 60/SOCKET 17=157) 未做 contamination verify；跨段合并结构候选 13,605 未做时序探测；样本非穷举
- 不要求补拍；下一步 = 定向 verify REVIEW_REQUIRED 高价值 + 跨段候选时序探测(有界 qwen)

## 每动作漏斗
| Action | Broad | Sample | Motion短名单 | Qwen | TVRC PASS | TVRC FAIL |
| --- | --- | --- | --- | --- | --- | --- |
""" + "\n".join(f"| {a} | {m['broad_eligible_union']} | {m['cheap_sample']} | {m['motion_high_shortlist']} | {m['qwen_reviewed']} | {m['tvrc_pass']} | {m['tvrc_fail']} |" for a, m in prog["metrics"].items()) + f"""

## 输出
- TREECUT_ACTION_CANDIDATE_DISCOVERY_V1.json / TREECUT_{{EXTEND,RETRACT,DRAWER_OPEN,STORAGE_PUT_IN,SOCKET_INSERT}}_DISCOVERY_V1.json
- TREECUT_REVIEW_REQUIRED_ACTION_RECOVERY_V1.json（未提升 G1；promotable=False 待 verify）
- TREECUT_CROSS_SEGMENT_ACTION_RECOVERY_V1.json（13,605 结构候选；不重写 canonical）
- TREECUT_MATERIAL_GAP_STATUS_V2.json（CANDIDATE，非 CONFIRMED）
- 新有效候选 0 → 未生成新动态审核包（无可播新画面）；REVIEW_REQUIRED/跨段验证出候选后再重建
"""
(DOCS / "TREECUT_STAGE8_CANDIDATE_DISCOVERY_REPORT_V1.md").write_text(md, encoding="utf-8")
(OUT / "TREECUT_STAGE8_CANDIDATE_DISCOVERY_REPORT_V1.md").write_text(md, encoding="utf-8")

f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["stage8_gates"]["G2_ACTION_SUBCLIP"]["status"] = "BLOCKED_BY_CANDIDATE_RECALL_VALIDATION"
d["stage8_gates"]["G3_CLAIM_VISUAL"]["status"] = "BLOCKED_BY_G2_VALID_ACTION_SOURCE"
d["stage8_gates"]["DEDUP"]["status"] = "PROVISIONAL_PASS_AFTER_TUNING"
d["stage8_gates"]["G5_PRODUCTION_QA"]["status"] = "PROVISIONAL_PASS"
d["discovery_recovery"] = {"report": "docs/TREECUT_STAGE8_CANDIDATE_DISCOVERY_REPORT_V1.md",
                           "funnel": prog["metrics"], "material_gap": "CANDIDATE_NOT_CONFIRMED",
                           "review_required_pending": 157, "cross_segment_pending": 13605,
                           "updated_at": now}
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("discovery outputs + report + state written")
