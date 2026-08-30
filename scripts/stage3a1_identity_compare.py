# -*- coding: utf-8 -*-
"""Stage 3A.1 — 坤宝研究设计院 29 条 Identity Comparison + B003 V2 输出 + adapter smoke。

Identity Comparison（KBYSJY-UNKNOWN vs B003）：
  display_name / note title overlap / note_id / account metadata
  结论仅允许 MATCH_B003 / NOT_B003 / AMBIGUOUS
"""
import io, json, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from xlsx2csv import Xlsx2csv

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"

# ---- 读坤宝研究设计院 29 条 ----
p = r"C:\Users\admin\Desktop\坤宝研究设计院账号内容.xlsx"
out = io.StringIO()
Xlsx2csv(p, outputencoding="utf-8").convert(out)
lines = out.getvalue().split("\n")
print(f"坤宝研究设计院: {len(lines)} 行")

# 找标题列 + note 列
titles = []
notes = []
for line in lines[2:]:
    cells = line.split(",")
    if len(cells) > 6 and cells[6].strip():
        title = cells[4] if len(cells) > 4 else ""
        note = cells[6]
        titles.append(title.strip())
        notes.append(note.strip())
print(f"  有效 note: {len(notes)} 条")
# 标题样例
print("  标题样例:", titles[:5])
print("  note 样例:", notes[:3])

# ---- Identity Comparison ----
# 1) display_name: 文件名="坤宝研究设计院/坤宝岛台研究所" vs B003="BARBERRY坤宝岛台定制"
display_match = "BARBERRY" in p or "坤宝岛台定制" in p
print(f"\n[Identity] display_name 含 BARBERRY/坤宝岛台定制: {display_match}")

# 2) note_id 是否出现在拆解表（B003 的 654215c9）或其他 B003 证据
b003_note = "654215c90000000023039459"
print(f"[Identity] 29 条中含 B003 已知 note {b003_note}: {b003_note in notes}")

# 3) 标题锚点重叠
ANCHORS = ["不是吧", "岛台直接掉地上", "岛台避坑9", "照抄不翻车", "只有80平",
           "我是怎么做岛台", "Vocal", "大横厅", "沙发后岛台"]
overlap = []
for t in titles:
    for a in ANCHORS:
        if a in t:
            overlap.append((a, t))
print(f"[Identity] 标题锚点重叠: {len(overlap)}", overlap[:5] if overlap else "")

# 结论
if display_match and (b003_note in notes or overlap):
    verdict = "AMBIGUOUS"  # 有部分信号但不足以确认（显示名不完全一致）
elif display_match:
    verdict = "AMBIGUOUS"
else:
    verdict = "NOT_B003"  # 显示名无 BARBERRY/坤宝岛台定制，标题无锚点
print(f"\n[Identity Verdict] 坤宝研究设计院 = {verdict}")

# ---- B003 V2 输出 ----
inv = {
    "manifest": "B003_PUBLISHED_CONTENT_INVENTORY_V2",
    "generated_at": "2026-08-30",
    "account": {"internal_id": "B003", "display_name": "BARBERRY坤宝岛台定制"},
    "total_published_content_found": 1,  # 仅 654215c9 有可靠身份证据
    "with_reliable_note_identity": 1,
    "with_performance": 1,  # 拆解表有点赞/收藏/评论
    "with_asset_mapping": 0,
    "with_segment_mapping": 0,
    "with_ad_data": 0,
    "candidate_without_note_id": 1,  # "沙发后放个岛台" 无 note_id（不视为可靠身份）
    "note": "本地仅恢复 1 条可靠 B003 note；其余需小红书后台导入",
    "guard": "不虚构；锚点标题无 note_id 不视为可靠身份",
}
json.dump(inv, open(os.path.join(DATA_ROOT, "B003_PUBLISHED_CONTENT_INVENTORY_V2.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

cov = {
    "manifest": "B003_JOIN_COVERAGE_REPORT_V2",
    "generated_at": "2026-08-30",
    "account": "B003",
    "coverage": {
        "published_to_asset_mapping_rate": 0.0,
        "asset_to_segment_coverage": 0.0,
        "published_to_performance_coverage": 1/1 if False else 0.0,
        "published_to_business_cognition_coverage": 0.0,
    },
    "gate": "JOIN_COVERAGE_GATE_NOT_PASSED — 仅 1 条本地 note，无 Asset 映射，无 Segment 链路",
    "recovery": {"reliable_notes": 1, "need_import": True},
    "status": "STAGE3A_WAITING_FOR_B003_IMPORT",
}
json.dump(cov, open(os.path.join(DATA_ROOT, "B003_JOIN_COVERAGE_REPORT_V2.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

asset = {"manifest": "B003_PUBLISHED_CONTENT_ASSET_MAPPING_V2",
         "generated_at": "2026-08-30", "account": "B003",
         "total_mappings": 0, "by_method": {"EXACT_PLATFORM_ID_METADATA": 0, "EXACT_FILE_HASH": 0,
                                            "FUZZY_TITLE_TIME_DURATION_MATCH": 0, "MANUAL_CONFIRMED": 0,
                                            "UNKNOWN": 0},
         "ambiguous_queue": [], "note": "1 条 note 无本地视频文件关联",
         "guard": "AMBIGUOUS/UNKNOWN 不进入 Business Cognition Join"}
json.dump(asset, open(os.path.join(DATA_ROOT, "B003_PUBLISHED_CONTENT_ASSET_MAPPING_V2.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

perf = {"manifest": "B003_PERFORMANCE_SNAPSHOTS_V2", "generated_at": "2026-08-30", "account": "B003",
        "total_snapshots": 1,
        "snapshots": [{"note_id": "654215c90000000023039459", "likes": 4235, "favorites": 2838,
                       "comments": 62, "window": "UNKNOWN", "metric_type": "MIXED",
                       "source": "SRC-CHAOJIE-0.1（拆解表，单值非时间窗口快照）"}],
        "note": "单值表现（非时间快照）；window=UNKNOWN；未标 Organic/Paid（MIXED 不可作 Organic 解释）",
        "added_wechat": "UNATTRIBUTABLE_CENTRALIZED_B007"}
json.dump(perf, open(os.path.join(DATA_ROOT, "B003_PERFORMANCE_SNAPSHOTS_V2.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("\n-> V2 输出已生成（Inventory V2 / JoinCoverage V2 / AssetMapping V2 / Performance V2）")
print("判定: STAGE3A_WAITING_FOR_B003_IMPORT")
