# -*- coding: utf-8 -*-
"""V0.3.1 — Spotlight 窗口回填规范化 + 入库 + 窗口语义验证。

输入：spotlight_raw_v031/<run>/<WINDOW>/ 证据
  - leona_rtb_common_data_report_*（笔记级指标）→ spotlight_note_paid_snapshot_v1
  - light_campaign_data_list_* → spotlight_paid_snapshot_v1 (CAMPAIGN, window=WINDOW)
  - leona_rtb_unit_search_* → spotlight_paid_snapshot_v1 (UNIT, window=WINDOW)
  - campaignInfo.campaignCreateTime → spotlight_campaign_v1.campaign_create_time
窗口语义验证：同 note 在 7d vs 30d 的 fee/impression 对比。
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from treecut.services.b007_creator_adapter import B007CreatorImportAdapterV1  # noqa: E402

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
RAW = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
           r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_raw_v031")
UNIT_RAW = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                r"\browser_profiles\B007\treecut_inbox\creator\raw\creator\spotlight_unit_v031")
ACCOUNT_ID = "62ea6099000000001f004e37"

NOTE_METRICS = ("fee", "impression", "click", "ctr", "acp", "cpm", "interaction", "cpi",
                "videoPlay5sCnt", "videoPlay5sRate", "iUserNum", "iUserPrice", "tiUserNum",
                "tiUserPrice", "messageConsult", "initiativeMessage", "msgLeadsNum",
                "messageConsultCpl", "initiativeMessageCpl", "msgLeadsCost",
                "externalGoodsOrder15", "outClickEnterStoreCnt15d", "noteMaterialType")


def num(v):
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(str(v).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def latest_run() -> Path:
    """返回所有 run 目录（窗口证据分散在多个时间戳 run 下）。"""
    if not RAW.exists():
        return None
    return RAW  # 用根目录，下面按 WINDOW 收集


def window_files() -> dict[str, list[Path]]:
    """收集各窗口的证据文件（跨所有 run 目录：spotlight_raw_v031 + spotlight_unit_v031）。"""
    out = {k: [] for k in ("LAST_7D", "LAST_14D", "LAST_30D")}
    for root in (RAW, UNIT_RAW):
        if not root.exists():
            continue
        for run in sorted(root.glob("*")):
            for wkey in out:
                wd = run / wkey
                if wd.exists():
                    out[wkey].extend(sorted(wd.glob("*.json")))
    return out


def ensure_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS spotlight_note_paid_snapshot_v1(
      snapshot_id TEXT PRIMARY KEY, account_id TEXT, note_id TEXT,
      window_type TEXT, report_start TEXT, report_end TEXT, snapshot_time TEXT,
      note_create_time TEXT, note_title TEXT,
      fee REAL, impressions REAL, clicks REAL, ctr REAL, acp REAL, cpm REAL,
      interaction REAL, cpi REAL, video_play5s REAL,
      i_user_num REAL, i_user_price REAL, ti_user_num REAL, ti_user_price REAL,
      message_consult REAL, initiative_message REAL, msg_leads_num REAL,
      message_consult_cpl REAL, initiative_message_cpl REAL, msg_leads_cost REAL,
      leads REAL, external_goods_order15 REAL,
      metric_json TEXT, source TEXT, metric_type TEXT, created_at REAL);
    """)


def main() -> int:
    wfiles = window_files()
    if not any(wfiles.values()):
        print("no v031 evidence")
        return 1
    print(f"window files: { {k: len(v) for k, v in wfiles.items()} }")

    conn = sqlite3.connect(DB, timeout=30)
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    now = time.time()
    snapshot_time = time.strftime("%Y-%m-%d %H:%M")
    window_dates = {"LAST_7D": ("2026-08-24", "2026-08-30"),
                    "LAST_14D": ("2026-08-17", "2026-08-30"),
                    "LAST_30D": ("2026-08-01", "2026-08-30")}

    stats = {"note_snaps": 0, "camp_snaps": 0, "unit_snaps": 0,
             "camp_create_time_filled": 0}
    window_notes = {}

    for wkey, (rs, re_) in window_dates.items():
        files = wfiles.get(wkey) or []
        if not files:
            continue
        print(f"--- window {wkey} ({rs}~{re_}) ---")

        # 笔记级
        note_rows = {}
        for f in files:
            if "common_data_report" not in f.name:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            dl = (d.get("data") or {}).get("dataList") or []
            for item in dl:
                nid = item.get("noteId")
                if not nid:
                    continue
                dvj = json.loads(item.get("dataValueJson") or "{}")
                note_rows[nid] = {"item": item, "dvj": dvj}
        n_notes = 0
        NOTE_COLS = ("snapshot_id,account_id,note_id,window_type,report_start,report_end,"
                     "snapshot_time,note_create_time,note_title,"
                     "fee,impressions,clicks,ctr,acp,cpm,interaction,cpi,video_play5s,"
                     "i_user_num,i_user_price,ti_user_num,ti_user_price,"
                     "message_consult,initiative_message,msg_leads_num,"
                     "message_consult_cpl,initiative_message_cpl,msg_leads_cost,"
                     "leads,external_goods_order15,metric_json,source,metric_type,created_at")
        for nid, row in note_rows.items():
            item, dvj = row["item"], row["dvj"]
            snap_id = f"SPN-{hashlib.sha256(f'{ACCOUNT_ID}:{nid}:{wkey}'.encode()).hexdigest()[:20]}"
            if conn.execute("SELECT 1 FROM spotlight_note_paid_snapshot_v1 WHERE snapshot_id=?", (snap_id,)).fetchone():
                continue
            vals = (snap_id, ACCOUNT_ID, nid, wkey, rs, re_, snapshot_time,
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(item.get("noteCreateTime", 0) / 1000))
                    if item.get("noteCreateTime") else None,
                    (item.get("noteTitle") or "")[:200],
                    num(dvj.get("fee")), num(dvj.get("impression")), num(dvj.get("click")),
                    num(dvj.get("ctr")), num(dvj.get("acp")), num(dvj.get("cpm")),
                    num(dvj.get("interaction")), num(dvj.get("cpi")), num(dvj.get("videoPlay5sCnt")),
                    num(dvj.get("iUserNum")), num(dvj.get("iUserPrice")), num(dvj.get("tiUserNum")),
                    num(dvj.get("tiUserPrice")), num(dvj.get("messageConsult")),
                    num(dvj.get("initiativeMessage")), num(dvj.get("msgLeadsNum")),
                    num(dvj.get("messageConsultCpl")), num(dvj.get("initiativeMessageCpl")),
                    num(dvj.get("msgLeadsCost")), num(dvj.get("leads")),
                    num(dvj.get("externalGoodsOrder15")), json.dumps(dvj, ensure_ascii=False),
                    "PAGE_OWNED_RESPONSE:leona_rtb_common_data_report", "PLATFORM_ATTRIBUTED", now)
            conn.execute(
                f"INSERT INTO spotlight_note_paid_snapshot_v1({NOTE_COLS}) VALUES({','.join('?' * len(vals))})",
                vals)
            n_notes += 1
        window_notes[wkey] = len(note_rows)
        stats["note_snaps"] += n_notes
        print(f"  notes rows={len(note_rows)} new={n_notes}")

        # campaign 指标快照（window 作用域）
        camp_items = {}
        for f in files:
            if "campaign_data_list" not in f.name:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            dl = (d.get("data") or {}).get("dataList") or []
            for item in dl:
                ci = item.get("campaignInfo") or {}
                cid = ci.get("campaignId")
                if cid:
                    camp_items[cid] = (ci, item.get("dataValueJson") or "{}")
        n_camp = 0
        for cid, (ci, dvj_s) in camp_items.items():
            dvj = json.loads(dvj_s) if isinstance(dvj_s, str) else {}
            snap_id = f"SPC-{hashlib.sha256(f'{ACCOUNT_ID}:CAMP:{cid}:{wkey}'.encode()).hexdigest()[:20]}"
            if conn.execute("SELECT 1 FROM spotlight_paid_snapshot_v1 WHERE snapshot_id=?", (snap_id,)).fetchone():
                continue
            camp_vals = (snap_id, ACCOUNT_ID, "CAMPAIGN", str(cid), snapshot_time, rs, re_,
                         ci.get("startTime", ""), ci.get("expireTime", ""), wkey, ci.get("state"),
                         num(dvj.get("fee")), num(dvj.get("impression")), num(dvj.get("click")),
                         num(dvj.get("ctr")), num(dvj.get("acp")), num(dvj.get("cpm")),
                         num(dvj.get("interaction")), num(dvj.get("cpi")), num(dvj.get("videoPlay5sCnt")),
                         num(dvj.get("iUserNum")), num(dvj.get("iUserPrice")), num(dvj.get("tiUserNum")),
                         num(dvj.get("tiUserPrice")), num(dvj.get("messageConsult")),
                         num(dvj.get("initiativeMessage")), num(dvj.get("msgLeadsNum")),
                         num(dvj.get("messageConsultCpl")), num(dvj.get("initiativeMessageCpl")),
                         num(dvj.get("msgLeadsCost")), None, num(dvj.get("externalGoodsOrder15")),
                         json.dumps(dvj, ensure_ascii=False), "PAGE_OWNED_RESPONSE", "PLATFORM_ATTRIBUTED", now)
            conn.execute(
                "INSERT INTO spotlight_paid_snapshot_v1("
                "snapshot_id,account_id,entity_type,entity_id,"
                "snapshot_time,report_start,report_end,delivery_start,delivery_end,window,status,"
                "fee,impressions,clicks,ctr,acp,cpm,interaction,cpi,video_play5s,"
                "i_user_num,i_user_price,ti_user_num,ti_user_price,"
                "message_consult,initiative_message,msg_leads_num,"
                "message_consult_cpl,initiative_message_cpl,msg_leads_cost,"
                "leads,external_goods_order15,metric_json,source,metric_type,created_at)"
                f" VALUES({','.join('?' * len(camp_vals))})", camp_vals)
            n_camp += 1
        stats["camp_snaps"] += n_camp
        print(f"  campaigns={len(camp_items)} new={n_camp}")

        # unit 快照（window 作用域）
        unit_items = {}
        for f in files:
            if "unit_search" not in f.name:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            dl = (d.get("data") or {}).get("list") or []
            for item in dl:
                uid = item.get("unitId")
                if uid:
                    unit_items[uid] = item
        n_unit = 0
        for uid, item in unit_items.items():
            ud = item.get("data") or {}
            snap_id = f"SPU-{hashlib.sha256(f'{ACCOUNT_ID}:UNIT:{uid}:{wkey}'.encode()).hexdigest()[:20]}"
            if conn.execute("SELECT 1 FROM spotlight_paid_snapshot_v1 WHERE snapshot_id=?", (snap_id,)).fetchone():
                continue
            unit_vals = (snap_id, ACCOUNT_ID, "UNIT", str(uid), snapshot_time, rs, re_,
                         item.get("startTime", ""), item.get("expireTime", ""), wkey, item.get("state"),
                         num(ud.get("fee")), num(ud.get("impression")), num(ud.get("click")),
                         num(ud.get("ctr")), num(ud.get("acp")), num(ud.get("cpm")),
                         num(ud.get("interaction")), num(ud.get("cpi")), num(ud.get("videoPlay5sCnt")),
                         num(ud.get("iUserNum")), num(ud.get("iUserPrice")), num(ud.get("tiUserNum")),
                         num(ud.get("tiUserPrice")), num(ud.get("messageConsult")),
                         num(ud.get("initiativeMessage")), num(ud.get("msgLeadsNum")),
                         num(ud.get("messageConsultCpl")), num(ud.get("initiativeMessageCpl")),
                         num(ud.get("msgLeadsCost")), num(ud.get("leads")), num(ud.get("goodsOrder")),
                         json.dumps(ud, ensure_ascii=False), "PAGE_OWNED_RESPONSE", "PLATFORM_ATTRIBUTED", now)
            conn.execute(
                "INSERT INTO spotlight_paid_snapshot_v1("
                "snapshot_id,account_id,entity_type,entity_id,"
                "snapshot_time,report_start,report_end,delivery_start,delivery_end,window,status,"
                "fee,impressions,clicks,ctr,acp,cpm,interaction,cpi,video_play5s,"
                "i_user_num,i_user_price,ti_user_num,ti_user_price,"
                "message_consult,initiative_message,msg_leads_num,"
                "message_consult_cpl,initiative_message_cpl,msg_leads_cost,"
                "leads,external_goods_order15,metric_json,source,metric_type,created_at)"
                f" VALUES({','.join('?' * len(unit_vals))})", unit_vals)
            n_unit += 1
        stats["unit_snaps"] += n_unit
        print(f"  units={len(unit_items)} new={n_unit}")

    # campaign_create_time 回填（跨所有 run）
    cols = {r[1] for r in conn.execute("PRAGMA table_info(spotlight_campaign_v1)")}
    if "campaign_create_time" not in cols:
        conn.execute("ALTER TABLE spotlight_campaign_v1 ADD COLUMN campaign_create_time TEXT")
    for files in wfiles.values():
        for f in files:
            if "campaign_data_list" not in f.name:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            for item in (d.get("data") or {}).get("dataList") or []:
                ci = item.get("campaignInfo") or {}
                cid = ci.get("campaignId")
                cct = ci.get("campaignCreateTime")
                if cid and cct:
                    cur = conn.execute("SELECT campaign_create_time FROM spotlight_campaign_v1 WHERE campaign_id=?",
                                       (str(cid),)).fetchone()
                    if cur and not cur["campaign_create_time"]:
                        conn.execute("UPDATE spotlight_campaign_v1 SET campaign_create_time=? WHERE campaign_id=?",
                                     (cct, str(cid)))
                        stats["camp_create_time_filled"] += 1
    conn.commit()

    # 窗口语义验证：同 note 7d vs 30d fee 对比
    sem = {}
    try:
        rows = conn.execute(
            "SELECT note_id, window_type, SUM(COALESCE(fee,0)) fee, SUM(COALESCE(impressions,0)) imp"
            " FROM spotlight_note_paid_snapshot_v1 WHERE window_type IN ('LAST_7D','LAST_30D')"
            " GROUP BY note_id, window_type").fetchall()
        by_note = {}
        for r in rows:
            by_note.setdefault(r["note_id"], {})[r["window_type"]] = (r["fee"], r["imp"])
        same_notes = [n for n, w in by_note.items() if "LAST_7D" in w and "LAST_30D" in w]
        grows = [n for n in same_notes if by_note[n]["LAST_30D"][0] >= by_note[n]["LAST_7D"][0]]
        sem = {"notes_in_both": len(same_notes),
               "fee_30d_ge_7d": len(grows),
               "sample": [{"note": n, "7d": by_note[n]["LAST_7D"], "30d": by_note[n]["LAST_30D"]}
                          for n in same_notes[:5]]}
    except Exception as e:
        sem = {"error": str(e)[:200]}

    conn.close()
    result = {
        "evidence_run_dirs": [r.name for r in sorted(RAW.glob("*"))] if RAW.exists() else [],
        "stats": stats, "window_notes": window_notes,
        "window_semantics": {
            "conclusion": "SELECTED_DATE_RANGE" if sem.get("fee_30d_ge_7d", 0) == sem.get("notes_in_both", -1) and sem.get("notes_in_both", 0) > 0 else "UNKNOWN",
            "detail": sem,
        },
    }
    out = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\B007_SPOTLIGHT_V031_SYNC_V1.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
