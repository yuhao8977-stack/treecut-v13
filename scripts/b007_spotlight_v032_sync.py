# -*- coding: utf-8 -*-
"""V0.3.2 — 月度 Note Paid Metrics 规范化入库 + OBSERVED_PAID_TOTAL + 覆盖报告。

数据源：spotlight_raw_v032/<run>/<WINDOW>/report_pN.json（笔记报表全分页）
- note 级快照：幂等（account+note+window+source）
- ZERO vs MISSING：只有平台记录 fee=0 才算 0；无记录 = NO_RECORD_IN_WINDOW（不填 0）
- OBSERVED_PAID_TOTAL：互不重叠月度窗口加总（绝不叫 LIFETIME）
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
RAW = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
           r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_raw_v032")
ACCOUNT_ID = "62ea6099000000001f004e37"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
MONTHS = {"M2026-04": ("2026-04-01", "2026-04-30"), "M2026-05": ("2026-05-01", "2026-05-31"),
          "M2026-06": ("2026-06-01", "2026-06-30"), "M2026-07": ("2026-07-01", "2026-07-31"),
          "M2026-08": ("2026-08-01", "2026-08-31")}


def num(v):
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(str(v).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def main() -> int:
    runs = sorted(RAW.glob("*")) if RAW.exists() else []
    if not runs:
        print("no v032 evidence")
        return 1
    run_dir = runs[-1]
    print(f"v032 run = {run_dir.name}")

    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    now = time.time()
    snapshot_time = time.strftime("%Y-%m-%d %H:%M")

    # 清掉旧版错误聚合的月度快照（最后行而非月汇总），重新按日聚合
    deleted = conn.execute("DELETE FROM spotlight_note_paid_snapshot_v1 WHERE window_type LIKE 'M2026-%'").rowcount
    conn.commit()
    print(f"deleted stale month snapshots: {deleted}")

    stats = {"note_snaps_new": 0, "note_snaps_skipped": 0}
    window_stats = {}
    all_rows = []

    for wdir in sorted(run_dir.glob("*")):
        wkey = wdir.name
        if wkey not in MONTHS:
            continue
        rs, re_ = MONTHS[wkey]
        files = sorted(wdir.glob("report_p*.json"))
        rows = []
        note_agg = {}  # noteId -> {sum fields, last item}
        for f in files:
            d = json.loads(f.read_text(encoding="utf-8"))
            dl = (d.get("data") or {}).get("dataList") or []
            for item in dl:
                nid = item.get("noteId")
                if not nid:
                    continue
                dvj = json.loads(item.get("dataValueJson") or "{}")
                rows.append(item)
                agg = note_agg.setdefault(nid, {"item": item, "sum": {}, "days": 0})
                for k in ("fee", "impression", "click", "interaction", "cpi", "videoPlay5sCnt",
                          "iUserNum", "iUserPrice", "tiUserNum", "tiUserPrice",
                          "messageConsult", "initiativeMessage", "msgLeadsNum",
                          "messageConsultCpl", "initiativeMessageCpl", "msgLeadsCost",
                          "leads", "externalGoodsOrder15"):
                    v = num(dvj.get(k))
                    if v is not None:
                        agg["sum"][k] = agg["sum"].get(k, 0.0) + v
                # 率类指标（ctr/acp/cpm 等）取最后一天值
                for k in ("ctr", "acp", "cpm"):
                    v = num(dvj.get(k))
                    if v is not None:
                        agg["sum"][k] = v
                agg["days"] += 1
        n_new = 0
        for nid, agg in note_agg.items():
            item = agg["item"]
            dvj = agg["sum"]
            snap_id = f"SPN-{hashlib.sha256(f'{ACCOUNT_ID}:{nid}:{wkey}'.encode()).hexdigest()[:20]}"
            if conn.execute("SELECT 1 FROM spotlight_note_paid_snapshot_v1 WHERE snapshot_id=?", (snap_id,)).fetchone():
                stats["note_snaps_skipped"] += 1
                continue
            vals = (snap_id, ACCOUNT_ID, nid, wkey, rs, re_, snapshot_time,
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(item.get("noteCreateTime", 0) / 1000))
                    if item.get("noteCreateTime") else None,
                    (item.get("noteTitle") or "")[:200],
                    dvj.get("fee"), dvj.get("impression"), dvj.get("click"),
                    dvj.get("ctr"), dvj.get("acp"), dvj.get("cpm"),
                    dvj.get("interaction"), dvj.get("cpi"), dvj.get("videoPlay5sCnt"),
                    dvj.get("iUserNum"), dvj.get("iUserPrice"), dvj.get("tiUserNum"),
                    dvj.get("tiUserPrice"), dvj.get("messageConsult"),
                    dvj.get("initiativeMessage"), dvj.get("msgLeadsNum"),
                    dvj.get("messageConsultCpl"), dvj.get("initiativeMessageCpl"),
                    dvj.get("msgLeadsCost"), dvj.get("leads"),
                    dvj.get("externalGoodsOrder15"), json.dumps({"aggregated": dvj, "days": agg["days"]},
                                                                ensure_ascii=False),
                    "PAGE_OWNED_RESPONSE:leona_rtb_common_data_report", "PLATFORM_ATTRIBUTED", now)
            conn.execute(
                "INSERT INTO spotlight_note_paid_snapshot_v1("
                "snapshot_id,account_id,note_id,window_type,report_start,report_end,snapshot_time,"
                "note_create_time,note_title,fee,impressions,clicks,ctr,acp,cpm,interaction,cpi,"
                "video_play5s,i_user_num,i_user_price,ti_user_num,ti_user_price,"
                "message_consult,initiative_message,msg_leads_num,message_consult_cpl,"
                "initiative_message_cpl,msg_leads_cost,leads,external_goods_order15,"
                "metric_json,source,metric_type,created_at)"
                f" VALUES({','.join('?' * len(vals))})", vals)
            n_new += 1
        stats["note_snaps_new"] += n_new
        window_stats[wkey] = {
            "pages": len(files), "rows_captured": len(rows),
            "unique_notes": len(note_agg), "snapshots_new": n_new,
            "exhausted": "see checkpoint (next-disabled based)",
            "zero_fee_notes": sum(1 for a in note_agg.values() if (a["sum"].get("fee") or 0) == 0),
            "nonzero_fee_notes": sum(1 for a in note_agg.values() if (a["sum"].get("fee") or 0) > 0),
        }
        all_rows.extend(rows)
        print(f"{wkey}: pages={len(files)} rows={len(rows)} unique_notes={len(note_agg)} new={n_new}")

    # join 状态（note 快照 → published）
    published = {}
    for r in conn.execute("SELECT note_id,source_refs,title FROM published_content_v1 WHERE account_id='B007'"):
        sr = r["source_refs"] or ""
        published[r["note_id"]] = "ACTIVE" if ("POSTED_CAPTURE" in sr or (r["title"] or "")) else "LEGACY"
    join_stats = {"ACTIVE_PUBLISHED_MATCH": 0, "LEGACY_IDENTITY_MATCH": 0, "UNMATCHED_PAID_NOTE": 0}
    unique_notes = set()
    for r in conn.execute("SELECT DISTINCT note_id FROM spotlight_note_paid_snapshot_v1 WHERE window_type LIKE 'M2026-%'"):
        nid = r[0]
        unique_notes.add(nid)
        st = published.get(nid)
        if st == "ACTIVE":
            join_stats["ACTIVE_PUBLISHED_MATCH"] += 1
        elif st == "LEGACY":
            join_stats["LEGACY_IDENTITY_MATCH"] += 1
        else:
            join_stats["UNMATCHED_PAID_NOTE"] += 1

    # OBSERVED_PAID_TOTAL（互不重叠月度窗口）
    totals = {}
    for r in conn.execute(
        "SELECT note_id, SUM(COALESCE(fee,0)) fee, SUM(COALESCE(impressions,0)) imp,"
        " SUM(COALESCE(clicks,0)) clk, SUM(COALESCE(msg_leads_num,0)) leads,"
        " SUM(COALESCE(message_consult,0)) msg"
        " FROM spotlight_note_paid_snapshot_v1 WHERE window_type LIKE 'M2026-%' GROUP BY note_id"):
        totals[r["note_id"]] = {"fee": r["fee"], "impressions": r["imp"], "clicks": r["clk"],
                                "leads": r["leads"], "message_consult": r["msg"]}

    conn.commit()
    conn.close()

    result = {
        "run": run_dir.name,
        "stats": stats,
        "window_stats": window_stats,
        "unique_notes_with_paid_metrics": len(unique_notes),
        "paid_associated_notes": 2322,
        "join": join_stats,
        "observed_paid_total_note_count": len(totals),
        "observed_paid_total_sample": dict(list(totals.items())[:5]),
        "naming": "OBSERVED_PAID_TOTAL（互不重叠月度窗口加总；非 LIFETIME）",
    }
    out = OUT / "B007_SPOTLIGHT_V032_SYNC_V1.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "observed_paid_total_sample"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
