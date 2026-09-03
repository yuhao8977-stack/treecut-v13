# -*- coding: utf-8 -*-
"""R2 收尾: Known6 复跑产物 + 报告(状态 NEEDS_REPAIR + 阻塞证据) + 状态。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
now = time.strftime("%Y-%m-%d %H:%M:%S")
r = json.loads((OUT / "_mmv_r2_results.json").read_text(encoding="utf-8"))
EXPECT = {89: "FAIL", 52: "PASS/STRONG_UNSURE", 109: "FAIL", 51: "FAIL", 1985: "FAIL", 1986: "FAIL"}
rows = [{"media_id": x["media_id"], "requested": x["requested"], "verdict": x["verdict"],
         "expected": EXPECT.get(x["media_id"]), "met": (x["verdict"] == "Verdict.FAIL" and EXPECT.get(x["media_id"]) == "FAIL")
         or (EXPECT.get(x["media_id"]) == "PASS/STRONG_UNSURE" and x["verdict"] in ("Verdict.PASS", "Verdict.UNSURE")),
         "core_motion": x.get("core_motion"), "person_motion": (x.get("roi_motion") or {}).get("PERSON"),
         "small_other_motion": (x.get("roi_motion") or {}).get("SOCKET_OR_SMALL_OTHER"),
         "roi_source": x.get("roi_source")} for x in r]
(OUT / "TREECUT_MMV_KNOWN6_R2_V1.json").write_text(json.dumps({"cases": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_SEMANTIC_ROI_V1.json").write_text(json.dumps(
    {"status": "BLOCKED", "evidence": "qwen2.5vl 对多对象JSON bbox 回显联合名/绝对坐标/伪JSON(见调试原样), 无法可信 MODEL_DETECTED ROI",
     "fallback": "布局启发式 + 运动簇归属(小簇排除) — 不足: 残差高/人带重叠弱"}, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_ROI_OWNERSHIP_V1.json").write_text(json.dumps(
    {"ownership": "ISLAND_BODY 含 TABLETOP/DRAWER/TRACK_SOCKET; SOCKET motion 不得计入 TABLETOP",
     "mechanism": "person 带 mask + 小移动簇(connectedComponents) 从目标核心排除", "limitation": "见 KNOWN6_R2 结果"}, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_TARGET_CORE_MOTION_V2.json").write_text(json.dumps(
    {"per_case": [{"media_id": x["media_id"], "core_motion": x.get("core_motion"),
                   "person_motion": (x.get("roi_motion") or {}).get("PERSON"),
                   "small_other": (x.get("roi_motion") or {}).get("SOCKET_OR_SMALL_OTHER")} for x in r]},
    ensure_ascii=False, indent=1), encoding="utf-8")

md = f"""# MMV Real-Media Hardening R2 — Semantic ROI + Target Motion（{now}）

状态: **MMVV_R2_KNOWN_CASE_NEEDS_REPAIR**（无假 PASS；3/6 未达预期）

| media | 请求 | Verdict | 预期 | 达标 |
| --- | --- | --- | --- | --- |
""" + "\n".join(f"| {x['media_id']} | {x['requested']} | {x['verdict']} | {x['expected']} | {'✅' if x['met'] else '❌'} |" for x in rows) + f"""

## 阻塞(非阈值问题, 未调阈值)
1. **Semantic ROI 获取不可行(当前)**: qwen2.5vl 对"多对象 bbox JSON"任务回显允许名联合/绝对像素坐标/伪 JSON(已存原样证据) → MODEL_DETECTED ROI 无法获得
2. **机械归属不足**: 布局启发式 person 带(顶部)+小簇排除 仍让残差/人带重叠抬升目标核心运动 → 51/1985/1986 仍 UNSURE 而非 FAIL(方向门保守, 无假 PASS)
3. 相机 translation+部分 affine 补偿不够干净(残差高)

## 建议(等架构师拍板, 未执行)
- 允许 **HUMAN 首帧 ROI**(6 案例人工框选, roi_source=HUMAN) 作为校准基线 → 再验归属/门序
- 或引入轻量检测器(受模型禁令约束, 需批准)
- 之后重跑 Known6 → 达标才 Blind30-50(仍 Shadow)
"""
(DOCS / "TREECUT_MMV_REAL_MEDIA_HARDENING_R2.md").write_text(md, encoding="utf-8")
(OUT / "TREECUT_MMV_REAL_MEDIA_HARDENING_R2.md").write_text(md, encoding="utf-8")
f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["mmv_v1"]["r2"] = {"status": "MMVV_R2_KNOWN_CASE_NEEDS_REPAIR", "cases": {x["media_id"]: x["verdict"] for x in rows},
                     "blockers": ["qwen ROI 不可信", "启发式+簇归属不足", "相机补偿残差高"], "updated_at": now}
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("R2 outputs written")
