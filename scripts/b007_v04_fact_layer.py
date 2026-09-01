# -*- coding: utf-8 -*-
"""V0.4 — 双源事实层构建：note fact(2851) + note-month paid fact + note-paid-association fact。

Join 键：account + note_id（ACTIVE 2851；legacy 459 排除，LEGACY_REFERENCE 独立）。
Creator = CREATOR_OBSERVED_PERFORMANCE（不叫 organic；不推断；不 rewrite 2840 snapshots）。
Paid = OBSERVED_PAID_TOTAL_2026_04_TO_2026_08（互不重叠穷尽月；绝不叫 LIFETIME）。
状态：CREATOR_PERFORMANCE_PRESENT/MISSING；PAID_ASSOCIATED/NO_PAID_ASSOCIATION_OBSERVED；
      NOTE_PAID_METRIC_PRESENT/PAID_ASSOCIATED_NO_METRIC_RECORD/NO_PAID_ASSOCIATION_OBSERVED。
不评分；不填 0（NO_RECORD）；不混 7d/14d/30d；公司加微排除。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
ACCOUNT_ID = "B007"
CLOSED_MONTHS = ("M2026-04", "M2026-05", "M2026-06", "M2026-07", "M2026-08")


def ensure_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS b007_note_dual_source_fact_v1(
      note_id TEXT PRIMARY KEY, title TEXT, publish_time TEXT, media_type TEXT,
      duration REAL, cover_url_safe TEXT, published_universe_status TEXT,
      creator_perf_status TEXT, creator_view REAL, creator_like REAL, creator_collect REAL,
      creator_comment REAL, creator_share REAL, creator_snapshot_time TEXT,
      paid_associated INTEGER, associated_unit_count INTEGER, associated_campaign_count INTEGER,
      association_record_count INTEGER,
      paid_metric_status TEXT, paid_observed_month_count INTEGER,
      first_observed_paid_month TEXT, last_observed_paid_month TEXT,
      observed_paid_fee REAL, observed_paid_impression REAL, observed_paid_click REAL,
      observed_paid_message_consult REAL, observed_paid_leads REAL,
      window_alignment_status TEXT, provenance TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS b007_note_month_paid_fact_v1(
      fact_id TEXT PRIMARY KEY, note_id TEXT, report_month TEXT,
      fee REAL, impression REAL, click REAL, message_consult REAL, msg_leads_num REAL,
      ctr_derived REAL, cpc_derived REAL, cpm_derived REAL, msg_leads_cost_derived REAL,
      rate_label TEXT, source TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS b007_note_paid_association_fact_v1(
      assoc_id TEXT PRIMARY KEY, note_id TEXT, unit_id TEXT, campaign_id TEXT, created_at REAL);
    """)


def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    now = datetime.now().timestamp()

    # 清空重建（幂等：可重复运行）
    for t in ("b007_note_dual_source_fact_v1", "b007_note_month_paid_fact_v1",
              "b007_note_paid_association_fact_v1"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()

    # ---- ACTIVE universe（2851）：B007_ACTIVE_PUBLISHED_UNIVERSE = posted capture 集 ----
    active = {}
    legacy_ids = []
    for r in conn.execute("SELECT * FROM published_content_v1 WHERE account_id='B007'"):
        sr = r["source_refs"] or ""
        if "POSTED_CAPTURE" in sr:
            active[r["note_id"]] = dict(r)
        else:
            legacy_ids.append(r["note_id"])
    print(f"active={len(active)} legacy={len(legacy_ids)}")

    # ---- Creator perf：取每个 note 最新 snapshot ----
    creator = {}
    for r in conn.execute(
        "SELECT p.note_id, s.views, s.likes, s.favorites, s.comments, s.shares, s.snapshot_time"
        " FROM performance_snapshot_v1 s JOIN published_content_v1 p"
        " ON p.published_content_id = s.published_content_id"
        " WHERE s.source='SRC-B007-POSTED-OBSERVED' AND p.account_id='B007'"
        " ORDER BY s.created_at ASC"):
        creator[r["note_id"]] = {"views": r["views"], "likes": r["likes"],
                                 "collect": r["favorites"], "comment": r["comments"],
                                 "share": r["shares"], "snapshot_time": r["snapshot_time"]}
    print(f"creator perf notes: {len(creator)}")

    # ---- Paid association（spotlight_note_link_v1） ----
    assoc = {}
    for r in conn.execute("SELECT note_id, unit_id, campaign_id FROM spotlight_note_link_v1 WHERE account_id='62ea6099000000001f004e37'"):
        a = assoc.setdefault(r["note_id"], {"units": set(), "campaigns": set(), "count": 0})
        a["units"].add(r["unit_id"])
        a["campaigns"].add(r["campaign_id"])
        a["count"] += 1
    print(f"paid-associated notes: {len(assoc)}")

    # ---- Paid history（月度，closed months only） ----
    paid = {}
    for r in conn.execute(
        "SELECT note_id, window_type, fee, impressions, clicks, message_consult, msg_leads_num"
        " FROM spotlight_note_paid_snapshot_v1"
        f" WHERE window_type IN ({','.join('?' * len(CLOSED_MONTHS))})", CLOSED_MONTHS):
        p = paid.setdefault(r["note_id"], {"months": set(), "fee": 0.0, "imp": 0.0, "clk": 0.0,
                                           "msg": 0.0, "leads": 0.0})
        p["months"].add(r["window_type"])
        p["fee"] += r["fee"] or 0
        p["imp"] += r["impressions"] or 0
        p["clk"] += r["clicks"] or 0
        p["msg"] += r["message_consult"] or 0
        p["leads"] += r["msg_leads_num"] or 0
    print(f"paid metric notes: {len(paid)}")

    # ---- Build fact rows ----
    n_fact = 0
    for nid, pc in sorted(active.items()):
        cr = creator.get(nid)
        as_ = assoc.get(nid)
        pd = paid.get(nid)
        months_sorted = sorted(pd["months"]) if pd else []
        creator_status = "CREATOR_PERFORMANCE_PRESENT" if cr else "CREATOR_PERFORMANCE_MISSING"
        paid_associated = 1 if as_ else 0
        if pd:
            paid_metric_status = "NOTE_PAID_METRIC_PRESENT"
        elif as_:
            paid_metric_status = "PAID_ASSOCIATED_NO_METRIC_RECORD"
        else:
            paid_metric_status = "NO_PAID_ASSOCIATION_OBSERVED"
        provenance = json.dumps({
            "creator_source": "SRC-B007-POSTED-OBSERVED" if cr else None,
            "paid_assoc_source": "spotlight_note_link_v1" if as_ else None,
            "paid_metric_source": "leona_rtb_common_data_report (note report)" if pd else None,
            "paid_window": "2026-04-01~2026-08-31 closed months" if pd else None,
            "normalization_version": "V0.4-PREFLIGHT-RATE-DERIVED",
        }, ensure_ascii=False)
        conn.execute(
            "INSERT OR REPLACE INTO b007_note_dual_source_fact_v1("
            "note_id,title,publish_time,media_type,duration,cover_url_safe,published_universe_status,"
            "creator_perf_status,creator_view,creator_like,creator_collect,creator_comment,creator_share,"
            "creator_snapshot_time,"
            "paid_associated,associated_unit_count,associated_campaign_count,association_record_count,"
            "paid_metric_status,paid_observed_month_count,first_observed_paid_month,last_observed_paid_month,"
            "observed_paid_fee,observed_paid_impression,observed_paid_click,"
            "observed_paid_message_consult,observed_paid_leads,"
            "window_alignment_status,provenance,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (nid, pc.get("title", ""), pc.get("publish_time", ""), pc.get("content_type", ""),
             pc.get("duration"), pc.get("cover_url_safe", ""), "ACTIVE_PUBLISHED_UNIVERSE",
             creator_status, cr["views"] if cr else None, cr["likes"] if cr else None,
             cr["collect"] if cr else None, cr["comment"] if cr else None, cr["share"] if cr else None,
             cr["snapshot_time"] if cr else None,
             paid_associated, len(as_["units"]) if as_ else 0, len(as_["campaigns"]) if as_ else 0,
             as_["count"] if as_ else 0,
             paid_metric_status, len(months_sorted) if pd else 0,
             months_sorted[0] if months_sorted else None, months_sorted[-1] if months_sorted else None,
             round(pd["fee"], 2) if pd else None, round(pd["imp"]) if pd else None,
             round(pd["clk"]) if pd else None, round(pd["msg"]) if pd else None,
             round(pd["leads"]) if pd else None,
             "UNALIGNED (creator snapshot window vs paid Apr-Aug closed months)",
             provenance, now))
        n_fact += 1

    # ---- note-month paid fact ----
    n_month = 0
    for r in conn.execute(
        "SELECT snapshot_id, note_id, window_type, fee, impressions, clicks, message_consult,"
        " msg_leads_num, ctr, acp, cpm, msg_leads_cost"
        " FROM spotlight_note_paid_snapshot_v1"
        f" WHERE window_type IN ({','.join('?' * len(CLOSED_MONTHS))})", CLOSED_MONTHS):
        conn.execute(
            "INSERT OR IGNORE INTO b007_note_month_paid_fact_v1("
            "fact_id,note_id,report_month,fee,impression,click,message_consult,msg_leads_num,"
            "ctr_derived,cpc_derived,cpm_derived,msg_leads_cost_derived,rate_label,source,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"MF-{r['snapshot_id']}", r["note_id"], r["window_type"], r["fee"], r["impressions"],
             r["clicks"], r["message_consult"], r["msg_leads_num"], r["ctr"], r["acp"], r["cpm"],
             r["msg_leads_cost"], "DERIVED_FROM_AGGREGATED_BASE_METRICS",
             "leona_rtb_common_data_report", now))
        n_month += 1

    # ---- note-paid-association fact ----
    n_assoc = 0
    for r in conn.execute("SELECT note_id, unit_id, campaign_id FROM spotlight_note_link_v1 WHERE account_id='62ea6099000000001f004e37'"):
        conn.execute(
            "INSERT OR IGNORE INTO b007_note_paid_association_fact_v1(assoc_id,note_id,unit_id,campaign_id,created_at)"
            " VALUES(?,?,?,?,?)",
            (f"NA-{r['note_id']}-{r['unit_id']}", r["note_id"], r["unit_id"], r["campaign_id"], now))
        n_assoc += 1

    conn.commit()

    # 校验
    facts = conn.execute("SELECT COUNT(*) FROM b007_note_dual_source_fact_v1").fetchone()[0]
    dups = conn.execute("SELECT note_id, COUNT(*) n FROM b007_note_dual_source_fact_v1 GROUP BY note_id HAVING n>1").fetchall()
    creator_present = conn.execute("SELECT COUNT(*) FROM b007_note_dual_source_fact_v1 WHERE creator_perf_status='CREATOR_PERFORMANCE_PRESENT'").fetchone()[0]
    paid_assoc = conn.execute("SELECT COUNT(*) FROM b007_note_dual_source_fact_v1 WHERE paid_associated=1").fetchone()[0]
    paid_metric = conn.execute("SELECT COUNT(*) FROM b007_note_dual_source_fact_v1 WHERE paid_metric_status='NOTE_PAID_METRIC_PRESENT'").fetchone()[0]
    assoc_no_metric = conn.execute("SELECT COUNT(*) FROM b007_note_dual_source_fact_v1 WHERE paid_metric_status='PAID_ASSOCIATED_NO_METRIC_RECORD'").fetchone()[0]
    no_assoc = conn.execute("SELECT COUNT(*) FROM b007_note_dual_source_fact_v1 WHERE paid_metric_status='NO_PAID_ASSOCIATION_OBSERVED'").fetchone()[0]
    months = conn.execute("SELECT COUNT(*) FROM b007_note_month_paid_fact_v1").fetchone()[0]
    assoc_rows = conn.execute("SELECT COUNT(*) FROM b007_note_paid_association_fact_v1").fetchone()[0]
    conn.close()

    print(json.dumps({
        "active_facts": facts, "dup_note_id": len(dups), "creator_present": creator_present,
        "creator_missing": facts - creator_present, "paid_associated": paid_assoc,
        "paid_metric": paid_metric, "assoc_no_metric": assoc_no_metric, "no_assoc": no_assoc,
        "month_facts": months, "assoc_facts": assoc_rows,
        "consistency_2851": paid_metric + assoc_no_metric + no_assoc == 2851,
        "consistency_2322": paid_metric + assoc_no_metric == 2322,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
