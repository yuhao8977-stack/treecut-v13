# -*- coding: utf-8 -*-
"""V2 收尾: 展开检索后仍无候选 → MATERIAL_GAP_CANDIDATE + 拍摄请求 + OLD-vs-NEW 表 + 状态/查询刷新。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
now = time.strftime("%Y-%m-%d %H:%M:%S")
exp = json.loads((OUT / "_g2_expand_results.json").read_text(encoding="utf-8"))

SHOOT = {
    "EXTEND": {"required_action": "EXTEND", "before_state": "桌面收起/较短", "motion": "手拉动+桌面滑出/变宽",
               "after_state": "桌面完全展开/较长", "framing": "岛台侧向全景可见桌面几何变化",
               "min_usable_s": 2.5, "example": "收起→拉出→完全展开"},
    "RETRACT": {"required_action": "RETRACT", "before_state": "展开状态", "motion": "桌面收回变短",
                "after_state": "紧凑收起(并可见空间环境以证不占位)", "framing": "岛台侧向全景+收回后环境",
                "min_usable_s": 2.5},
    "DRAWER_OPEN": {"required_action": "DRAWER_OPEN", "before_state": "抽屉关闭", "motion": "手拉→滑轨外移",
                    "after_state": "完全打开", "framing": "正面/侧面含关闭→打开全程", "min_usable_s": 2.5},
    "SOCKET_INSERT": {"required_action": "SOCKET_INSERT", "before_state": "插头在外/模块未用",
                      "motion": "插头插入/模块接电", "after_state": "插入固定/通电", "framing": "插座区近景",
                      "min_usable_s": 2.0, "note": "静态轨道插座素材充足(对象可用); 仅缺插入动作; 可先 SEMANTIC_REWRITE"},
    "STORAGE_PUT_IN": {"required_action": "STORAGE_PUT_IN", "before_state": "物品在外", "motion": "手放物品入收纳",
                       "after_state": "物品进入/抽屉内", "framing": "抽屉/柜内+手部动作", "min_usable_s": 2.5},
}
GAP = {"semantics": "CURRENT_CANDIDATE_SET_EXHAUSTED_AFTER_BOUNDED_EXPANSION(非整库结论; 已在 Eligible 池另探 15 资产)",
       "per_action": {}, "generated_at": now}
for act in ("EXTEND", "RETRACT", "DRAWER_OPEN", "SOCKET_INSERT", "STORAGE_PUT_IN"):
    GAP["per_action"][act] = {"status": "MATERIAL_GAP_CANDIDATE",
                              "expand_searched": exp["summary"].get(act, {}).get("searched", 0),
                              "expand_found": exp["summary"].get(act, {}).get("found_windows", 0),
                              "shooting_request": SHOOT[act]}
(OUT / "TREECUT_STAGE8_MATERIAL_GAP_V1.json").write_text(json.dumps(GAP, ensure_ascii=False, indent=1), encoding="utf-8")

# Query20 OLD-vs-NEW 标注(现候选=空 → MATERIAL_GAP_CANDIDATE)
q = json.loads((OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").read_text(encoding="utf-8"))
for x in q["queries"]:
    if x["top3_n"] == 0:
        x["note"] = "NO_VALID(展开检索15新素材仍无候选) → MATERIAL_GAP_CANDIDATE; 见 TREECUT_STAGE8_MATERIAL_GAP_V1.json"
q["material_gap"] = True
(OUT / "TREECUT_G2_ACTION_QUERY20_V1.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")

f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["v2_integration"]["expanded_retrieval"] = {"searched_fresh_assets": 15, "found_windows": 0}
d["v2_integration"]["material_gap"] = {a: "MATERIAL_GAP_CANDIDATE" for a in GAP["per_action"]}
d["stage8_gates"]["G2_ACTION_SUBCLIP"]["status"] = "NEEDS_REPAIR_R_WAVE_V2_INTEGRATED_EXPAND_EMPTY"
d["stage8_gates"]["G3_CLAIM_VISUAL"]["status"] = "NEEDS_REPAIR_VB_GROUPING_ACTIVE"
d["stage8_gates"]["DEDUP"]["status"] = "NEEDS_TUNING_R7+DuplicateCritic"
d["updated_at"] = now
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("material gap + state saved")
print(json.dumps({a: v["status"] for a, v in GAP["per_action"].items()}, ensure_ascii=False))
