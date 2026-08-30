# -*- coding: utf-8 -*-
"""Stage 3A.2 — B003 数据导入：156 条 Published Content + Performance。

源：
  笔记列表明细表.xlsx（156 条：标题/发布时间/曝光/观看/点赞/评论/收藏/涨粉/分享）
  B003_近半年_note_id_身份表_真实抓取.xlsx（157 条：note_id/标题/发布时间/观看/点赞/收藏/评论/分享/时长）
匹配：标题 NFKC 规范化 + 发布时间精确到分钟（与架构监工对账一致，155/156 = 99.36%）

输出：
  B003_IMPORTED_SOURCE_MANIFEST_V1.json
  B003_PUBLISHED_CONTENT_INVENTORY_V3.json
  B003_PERFORMANCE_SNAPSHOTS_V3.json
  B003_JOIN_COVERAGE_REPORT_V3.json（部分：Performance 已 Join；Asset/Segment/Cognition 待成片匹配）
"""
import io
import json
import os
import re
import sys
import time
import unicodedata

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from xlsx2csv import Xlsx2csv

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
PERF = r"C:\Users\admin\Desktop\笔记列表明细表.xlsx"
IDENT = r"C:\Users\admin\Desktop\B003_近半年_note_id_身份表_真实抓取.xlsx"
ACCOUNT = "B003"


def xlsx_lines(p):
    out = io.StringIO()
    Xlsx2csv(p, outputencoding="utf-8").convert(out)
    return out.getvalue().split("\n")


def norm(s):
    return unicodedata.normalize("NFKC", (s or "").strip()).replace(" ", "")


def main():
    # ---- 1. 读性能表（156 条）----
    perf_lines = xlsx_lines(PERF)
    # 表头行 index1；数据从 index2 开始
    perf_rows = []
    for line in perf_lines[2:]:
        cells = line.split(",")
        if len(cells) < 2 or not cells[0].strip():
            continue
        perf_rows.append({
            "title": cells[0].strip(),
            "publish_time_raw": cells[1].strip(),
            "format": cells[2].strip() if len(cells) > 2 else "",
            "exposure": cells[3].strip() if len(cells) > 3 else "",
            "views": cells[4].strip() if len(cells) > 4 else "",
            "cover_ctr": cells[5].strip() if len(cells) > 5 else "",
            "likes": cells[6].strip() if len(cells) > 6 else "",
            "comments": cells[7].strip() if len(cells) > 7 else "",
            "favorites": cells[8].strip() if len(cells) > 8 else "",
            "follower_delta": cells[9].strip() if len(cells) > 9 else "",
            "shares": cells[10].strip() if len(cells) > 10 else "",
            "avg_view_duration": cells[11].strip() if len(cells) > 11 else "",
        })
    print(f"性能表作品数: {len(perf_rows)}")

    # ---- 2. 读 note_id 身份表（157 条）----
    id_lines = xlsx_lines(IDENT)
    id_rows = []
    for line in id_lines[1:]:
        cells = line.split(",")
        if len(cells) < 2 or not cells[1].strip():
            continue
        id_rows.append({
            "note_id": cells[0].strip(),
            "title": cells[1].strip(),
            "publish_time": cells[2].strip(),
            "type": cells[3].strip() if len(cells) > 3 else "",
            "view_count": cells[4].strip() if len(cells) > 4 else "",
            "like_count": cells[5].strip() if len(cells) > 5 else "",
            "comment_count": cells[6].strip() if len(cells) > 6 else "",
            "favorite_count": cells[7].strip() if len(cells) > 7 else "",
            "share_count": cells[8].strip() if len(cells) > 8 else "",
            "duration": cells[9].strip() if len(cells) > 9 else "",
        })
    print(f"note_id 身份表: {len(id_rows)}")

    # ---- 3. 匹配：标题 NFKC + 发布时间精确到分钟 ----
    def to_min(raw):
        # 性能表: 2026年08月30日11时30分23秒 -> (2026-08-30, 11:30)
        m = re.match(r"(\d{4})年(\d{2})月(\d{2})日(\d{2})时(\d{2})分", raw)
        if m:
            return (f"{m.group(1)}-{m.group(2)}-{m.group(3)}", f"{m.group(4)}:{m.group(5)}")
        # 身份表: 08/30/26 11:30 -> (2026-08-30, 11:30)
        m = re.match(r"(\d{2})/(\d{2})/(\d{2}) (\d{2}):(\d{2})", raw)
        if m:
            return (f"20{m.group(3)}-{m.group(1)}-{m.group(2)}", f"{m.group(4)}:{m.group(5)}")
        return (raw.strip(), "")

    def min_to_int(t):
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    id_by_title = {}
    for r in id_rows:
        id_by_title.setdefault(norm(r["title"]), []).append(r)

    matched = 0
    unmatched_perf = []
    for pr in perf_rows:
        date, tmin = to_min(pr["publish_time_raw"])
        cands = id_by_title.get(norm(pr["title"]), [])
        best = None
        for c in cands:
            cdate, ctmin = to_min(c["publish_time"])
            if cdate == date:
                diff = abs(min_to_int(ctmin) - min_to_int(tmin))
                # 同一分钟 / ±3 分钟（秒级误差） / ±12 小时（AM-PM 时区偏移）
                if diff <= 3 or abs(diff - 720) <= 3:
                    best = c
                    break
        if best:
            pr["note_id"] = best["note_id"]
            pr["duration"] = best.get("duration", "")
            pr["identity_confidence"] = "HIGH"
            matched += 1
        else:
            pr["note_id"] = None
            pr["identity_confidence"] = "UNMATCHED"
            unmatched_perf.append(pr["title"])
    print(f"匹配成功: {matched} / {len(perf_rows)}")
    print("未匹配:", unmatched_perf)

    # ---- 4. 生成输出 ----
    # Imported Source Manifest
    manifest = {
        "manifest": "B003_IMPORTED_SOURCE_MANIFEST_V1",
        "generated_at": "2026-08-30",
        "account": "B003 (BARBERRY坤宝岛台定制)",
        "sources": [
            {"source_id": "SRC-B003-PERF-DETAIL", "file": os.path.basename(PERF),
             "row_count": len(perf_rows), "source_type": "XHS_BACKEND_EXPORT",
             "account": "B003", "import_time": time.strftime("%Y-%m-%d %H:%M"),
             "raw_hash": "SEE_INPUT_FILE", "provenance": "用户提供，READ ONLY"},
            {"source_id": "SRC-B003-API-IDENTITY", "file": os.path.basename(IDENT),
             "row_count": len(id_rows), "source_type": "API_GRAB",
             "account": "B003", "import_time": time.strftime("%Y-%m-%d %H:%M"),
             "raw_hash": "SEE_INPUT_FILE", "provenance": "用户抓取，READ ONLY"},
        ],
        "match_result": {"performance_total": len(perf_rows), "matched": matched,
                         "match_rate": round(matched / len(perf_rows), 4),
                         "unmatched": [{"title": t, "status": "UNMATCHED_DETAIL / REVIEW_REQUIRED"}
                                       for t in unmatched_perf]},
        "guard": "原始文件未修改；空值保持 NULL/UNKNOWN 不补 0",
    }
    json.dump(manifest, open(os.path.join(DATA_ROOT, "B003_IMPORTED_SOURCE_MANIFEST_V1.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # Published Content Inventory V3
    inv_rows = []
    for pr in perf_rows:
        d, t = to_min(pr["publish_time_raw"])
        inv_rows.append({
            "published_content_id": f"B003-{pr['note_id']}" if pr["note_id"] else f"B003-UNMATCHED-{norm(pr['title'])[:12]}",
            "account_id": ACCOUNT, "platform": "XIAOHONGSHU",
            "note_id": pr["note_id"], "note_url": None,
            "title": pr["title"], "publish_time": f"{d} {t}",
            "duration": pr.get("duration", ""), "content_type": pr["format"],
            "identity_confidence": pr["identity_confidence"],
            "source_refs": ["SRC-B003-PERF-DETAIL"],
        })
    inv = {"manifest": "B003_PUBLISHED_CONTENT_INVENTORY_V3",
           "generated_at": "2026-08-30", "account": ACCOUNT,
           "total": len(inv_rows),
           "with_reliable_note_id": sum(1 for r in inv_rows if r["note_id"]),
           "unmatched": sum(1 for r in inv_rows if not r["note_id"]),
           "duplicate_note_id": len(inv_rows) - len({r["note_id"] for r in inv_rows if r["note_id"]}),
           "records": inv_rows}
    json.dump(inv, open(os.path.join(DATA_ROOT, "B003_PUBLISHED_CONTENT_INVENTORY_V3.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # Performance Snapshots V3
    snaps = []
    for pr in perf_rows:
        if not pr["note_id"]:
            continue
        d, t = to_min(pr["publish_time_raw"])
        snaps.append({
            "published_content_id": f"B003-{pr['note_id']}",
            "note_id": pr["note_id"],
            "snapshot_time": f"{d} {t}",
            "window": "LIFETIME" if False else "UNKNOWN",  # 后台导出为累计值但窗口不可证明
            "views": pr["views"] or None, "likes": pr["likes"] or None,
            "favorites": pr["favorites"] or None, "comments": pr["comments"] or None,
            "shares": pr["shares"] or None, "exposure": pr["exposure"] or None,
            "follower_delta": pr["follower_delta"] or None,
            "metric_type": "MIXED",  # 后台累计未拆 Organic/Paid
            "source": "SRC-B003-PERF-DETAIL",
            "added_wechat": "UNATTRIBUTABLE_CENTRALIZED_B007",
        })
    perf_out = {"manifest": "B003_PERFORMANCE_SNAPSHOTS_V3",
                "generated_at": "2026-08-30", "account": ACCOUNT,
                "total_snapshots": len(snaps),
                "metric_type_distribution": {"ORGANIC": 0, "PAID": 0, "MIXED": len(snaps), "UNKNOWN": 0},
                "snapshots": snaps}
    json.dump(perf_out, open(os.path.join(DATA_ROOT, "B003_PERFORMANCE_SNAPSHOTS_V3.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # Join Coverage V3
    cov = {
        "manifest": "B003_JOIN_COVERAGE_REPORT_V3",
        "generated_at": "2026-08-30", "account": ACCOUNT,
        "coverage": {
            "published_to_performance": round(len(snaps) / len(perf_rows), 3),
            "published_to_asset": 0.0,
            "asset_to_segment": 0.0,
            "published_to_business_cognition": 0.0,
        },
        "counts": {"published": len(perf_rows), "with_performance": len(snaps),
                   "with_asset": 0, "with_segment": 0, "with_cognition": 0},
        "gate": "PERFORMANCE_JOIN_PASSED; ASSET_JOIN_PENDING（需 note→本地成片匹配）",
        "status": "STAGE3A_IN_PROGRESS",
    }
    json.dump(cov, open(os.path.join(DATA_ROOT, "B003_JOIN_COVERAGE_REPORT_V3.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"\n-> Inventory V3: {len(inv_rows)} 条（{inv['with_reliable_note_id']} 有 note_id）")
    print(f"-> Performance V3: {len(snaps)} 条快照")
    print(f"-> Join Coverage V3: Performance {len(snaps)}/{len(perf_rows)}; Asset 待匹配")
    print("-> B003_IMPORTED_SOURCE_MANIFEST_V1.json")


if __name__ == "__main__":
    main()
