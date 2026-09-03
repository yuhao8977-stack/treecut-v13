# -*- coding: utf-8 -*-
"""REVIEW_REQUIRED 定向恢复(DB 廉价) + 跨段合并候选结构检查(不自动提升G1)。"""
import json, sqlite3, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
ACT_KW = {"EXTEND": ["伸缩", "变宽"], "RETRACT": ["收起"], "DRAWER_OPEN": ["薄抽", "抽屉"],
          "STORAGE_PUT_IN": ["收纳", "放置"], "SOCKET_INSERT": ["轨道插座", "插拔"]}

# 1) REVIEW_REQUIRED 高概率动作候选(仅列清单; 不绕过G1)
rec = {}
for act, kws in ACT_KW.items():
    like = " OR ".join(["mf.relative_path LIKE ?"] * len(kws))
    rows = c.execute(
        f"""SELECT r.entity_id, r.source_id, r.burned_subtitle_present, r.platform_watermark_present,
                   r.contamination_confidence, substr(mf.relative_path,1,100), a.asset_id
            FROM b007_source_role_v1 r JOIN media_files mf ON mf.id=r.entity_id
            LEFT JOIN assets a ON a.media_id = mf.id
            WHERE r.entity_kind='media_file' AND r.review_status='REVIEW_REQUIRED'
              AND mf.source_id IN (1,2,4) AND ({like}) AND mf.extension='.mp4' LIMIT 60""",
        [f"%{k}%" for k in kws]).fetchall()
    # 廉价污染预筛: 仅保留 burned 非 PRESENT 且 wm 非 PRESENT(需进一步 contamination verify 才能提升)
    pre = []
    for eid, sid, b, w, conf, rel, aid in rows:
        if (b == "PRESENT") or (w == "PRESENT"):
            continue
        pre.append({"media_id": eid, "source_id": sid, "rel": rel, "contamination": "PENDING_VERIFY",
                    "burned": b, "wm": w, "promotable": False})
    rec[act] = {"high_value_candidates": len(pre), "items": pre[:20]}
    print(act, "review_required action-candidates(非PRESENT):", len(pre))
(OUT / "TREECUT_REVIEW_REQUIRED_ACTION_RECOVERY_V1.json").write_text(json.dumps(
    {"note": "定向恢复清单; 不自动提升 G1; 需增量 contamination verify(OCR/视觉) 通过且走正规 eligibility 路径",
     "actions": rec, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False, indent=1), encoding="utf-8")

# 2) 跨段合并候选: 相邻同源 segment(时间连续) 且前段末/后段首存在(无法直接判动作; 输出结构候选供 qwen 补查)
seg_rows = c.execute("""SELECT s.asset_id, mf.id, s.segment_id, s.start_ms, s.end_ms, mf.relative_path
                        FROM segments s JOIN assets a ON a.asset_id=s.asset_id
                        JOIN media_files mf ON mf.id=a.media_id
                        WHERE mf.source_id IN (1,2,4) AND s.end_ms > s.start_ms
                        ORDER BY mf.id, s.start_ms""").fetchall()
groups = {}
for aid, mid, seg, s, e, rel in seg_rows:
    if mid is None:
        continue
    groups.setdefault(mid, []).append((seg, s, e, rel))
merge_candidates = []
for mid, segs in groups.items():
    segs.sort(key=lambda x: x[1])
    for i in range(len(segs) - 1):
        gap = segs[i + 1][1] - segs[i][2]
        if 0 <= gap < 1200:  # 邻段间隔 <1.2s
            merge_candidates.append({"media_id": mid,
                                     "seg_a": segs[i][0], "seg_a_ms": [segs[i][1], segs[i][2]],
                                     "seg_b": segs[i + 1][0], "seg_b_ms": [segs[i + 1][1], segs[i + 1][2]],
                                     "gap_ms": gap, "rel": (segs[i][3] or "")[:80],
                                     "merged_window_ms": [segs[i][1], segs[i + 1][2]],
                                     "needs_temporal_probe": True})
            break  # 每资产取最近一对(避免爆炸)
(OUT / "TREECUT_CROSS_SEGMENT_ACTION_RECOVERY_V1.json").write_text(json.dumps(
    {"candidates": merge_candidates[:50], "count": len(merge_candidates),
     "note": "结构候选(跨段动作可能被切镜切断); 需时序探测确认, 不重写 canonical segment"},
    ensure_ascii=False, indent=1), encoding="utf-8")
print("cross-segment merge candidates:", len(merge_candidates))
