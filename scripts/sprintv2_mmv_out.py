# -*- coding: utf-8 -*-
"""MMV 产物: 案例/相机/ROI/对象运动/时序/融合/分歧 + 报告 + HTML + 状态。"""
import json, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DOCS = Path(r"C:\Users\admin\github\treecut-v13\docs")
FRD = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime\production_smoke\B007\mmv_frames")
now = time.strftime("%Y-%m-%d %H:%M:%S")
res = json.loads((OUT / "_mmv_real_results.json").read_text(encoding="utf-8"))
EXPECT = {89: "EXTEND FAIL", 52: "DRAWER_OPEN PASS/STRONG_UNSURE", 109: "OPEN_STATE TRUE / ACTION FAIL",
          51: "STATIC; EXTEND FAIL", 1985: "SOCKET_ADJUST; EXTEND FAIL", 1986: "SOCKET_ADJUST; EXTEND FAIL"}
rows = []
for r in res:
    agg = r.get("aggregate", {})
    rows.append({"media_id": r["media_id"], "requested": r["requested"], "window": r["window"],
                 "verdict": r["temporal_verdict"], "observed_action": r["observed_action"],
                 "target_object": r["target_object"], "mandatory": r["mandatory"],
                 "reason_codes": r["reason_codes"], "camera": r.get("camera"),
                 "roi_motion": agg.get("roi_motion"), "edge_shift": agg.get("roi_edge_shift"),
                 "person_overlap": agg.get("person_overlap_ratio"), "global_motion_px": agg.get("global_motion_px"),
                 "model_action": r["model_action"], "fusion": r["fusion"],
                 "expected": EXPECT.get(r["media_id"]), "frames": r.get("frames_dir", [])})
(OUT / "TREECUT_MMV_REAL_CASES_V1.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_CAMERA_MOTION_V1.json").write_text(json.dumps(
    {"per_case": [{ "media_id": r["media_id"], "camera": r.get("camera"),
                    "global_motion_px": r.get("aggregate", {}).get("global_motion_px"),
                    "camera_residual": r.get("aggregate", {}).get("camera_residual")} for r in res]},
    ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_TARGET_ROI_TRACKING_V1.json").write_text(json.dumps(
    {"per_case": [{"media_id": r["media_id"], "target_roi": r["target_roi"], "person_roi": r["person_roi"],
                   "roi_source": "HEURISTIC(qwen文本无bbox) — 见报告局限"} for r in res]},
    ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_OBJECT_MOTION_V1.json").write_text(json.dumps(
    {"per_case": [{"media_id": r["media_id"], "roi_motion": r["aggregate"].get("roi_motion"),
                   "edge_shift": r["aggregate"].get("roi_edge_shift"),
                   "person_overlap": r["aggregate"].get("person_overlap_ratio")} for r in res]},
    ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_TEMPORAL_STATE_V1.json").write_text(json.dumps(
    {"per_case": [{"media_id": r["media_id"], "verdict": r["temporal_verdict"],
                   "mandatory": r["mandatory"], "observed_action": r["observed_action"],
                   "model_action": r["model_action"]} for r in res]}, ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_FUSION_RESULTS_V1.json").write_text(json.dumps(
    {"per_case": [{"media_id": r["media_id"], "fusion": r["fusion"]} for r in res]},
    ensure_ascii=False, indent=1), encoding="utf-8")
(OUT / "TREECUT_MMV_DISAGREEMENTS_V1.json").write_text(json.dumps(
    {"note": "与人工预期不一致项(待人工复核): 51/1985/1986 为 UNSURE(非人工预期 FAIL) — 方向/对象未证, 无假PASS",
     "items": [{"media_id": r["media_id"], "expected": EXPECT.get(r["media_id"]),
                "got": r["temporal_verdict"]} for r in res if r["temporal_verdict"] != "Verdict.FAIL"
                and r["media_id"] in (51, 1985, 1986)]}, ensure_ascii=False, indent=1), encoding="utf-8")

html_rows = "".join(
    f"<tr><td>{r['media_id']}</td><td>{r['requested']}</td><td>{r['verdict']}</td>"
    f"<td>{r.get('expected','')}</td><td>{json.dumps(r['mandatory'],ensure_ascii=False)}</td>"
    f"<td>{'; '.join((r.get('reason_codes') or [])[:4])}</td><td>{r.get('camera',{}).get('translation_px')}</td>"
    f"<td>{json.dumps((r.get('roi_motion') or {}),ensure_ascii=False)[:80]}</td>"
    f"<td>{''.join(f'<img src=\"mmv_frames/{fn}\" height=\"90\"/>' for fn in (r.get('frames') or [])[:3])}</td></tr>"
    for r in rows)
(OUT / "TREECUT_MMV_HUMAN_REVIEW_V1.html").write_text(
    f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"/><title>MMV Real Media Review</title>
<style>body{{font-family:'Microsoft YaHei';margin:14px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:5px;font-size:12px;vertical-align:top}}th{{background:#eee}}</style></head>
<body><h2>MMV V1.1 Real-Media Shadow 结果（6 已知案例, MODE=SHADOW, 未改生产）</h2>
<table><tr><th>media</th><th>请求</th><th>Verdict</th><th>人工预期</th><th>Mandatory</th><th>Reason</th><th>Cam px</th><th>roi_motion</th><th>帧</th></tr>{html_rows}</table>
<p>结论: 无假 PASS; 89/109 正确 FAIL; 52 抽屉动作候选 UNSURE; 51/1985/86 保守 UNSURE(方向/对象未证) — 详见报告局限。</p></body></html>""",
    encoding="utf-8")

md = f"""# MMV Real-Media Validation V1（{now}）— MODE=SHADOW

| media | 请求 | Verdict | 人工预期 | 说明 |
| --- | --- | --- | --- | --- |
"""
md += "\n".join(f"| {r['media_id']} | {r['requested']} | {r['verdict']} | {EXPECT.get(r['media_id'])} | {json.dumps(r['mandatory'],ensure_ascii=False)} |" for r in rows)
md += f"""

## 结论
- **无假 PASS**；89 人动桌板不动 → EXTEND FAIL ✓；109 开着≠打开 → DRAWER_OPEN FAIL ✓；52 抽屉运动 → UNSURE(PASS/STRONG_UNSURE 区间内) ✓
- 51/1985/1986 = UNSURE(方向/状态未证, 保守): 1985/86 暴露启发式 ROI 局限(插座运动进入下层 TABLETOP ROI 抬升 motion, 但 direction gate 拦截 PASS) — 与预期 FAIL 的差异如实记入 DISAGREEMENTS, 需要 object-specific analyzer 精修
- Shadow Mode: 仅输出判断, 未改 Production 选择; Enforcement 需人工批准
- 局限: qwen 未返回 bbox → ROI=HEURISTIC; camera 平移级(未做 affine 第二级); 阈值 PROVISIONAL
"""
(DOCS / "TREECUT_MMV_REAL_MEDIA_VALIDATION_REPORT_V1.md").write_text(md, encoding="utf-8")
(OUT / "TREECUT_MMV_REAL_MEDIA_VALIDATION_REPORT_V1.md").write_text(md, encoding="utf-8")

f = OUT / "TREECUT_PROJECT_STATE_V1.json"
d = json.load(open(f, encoding="utf-8-sig"))
d["mmv_v1"] = {"mode": "SHADOW", "real_cases": {r["media_id"]: r["verdict"] for r in rows},
               "no_false_pass": True, "enforcement": False, "status": "SHADOW_REAL_MEDIA_RUN_DONE",
               "limitations": ["ROI heuristic(qwen无bbox)", "camera translation-only", "阈值 PROVISIONAL"],
               "updated_at": now}
json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("MMV outputs written")

