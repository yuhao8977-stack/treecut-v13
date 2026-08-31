# -*- coding: utf-8 -*-
"""V0.3 — B007 Spotlight Paid Performance Sync：规范化 + 幂等入库 + binding 升级。

数据源（页面自有响应，非模拟 API）：
  - 账户: spotlight_account/<run>/leona_user_info.json (userId)
  - 计划: spotlight_raw/<run>/light_campaign_data_list_page*.json (campaignInfo + dataValueJson 指标)
  - 单元: spotlight_raw/<run>/leona_rtb_unit_search_page*.json (unit + noteIds + unit.data 指标)
  - 账户汇总: light_ad_manage_data_overall.json
实体：spotlight_account_v1 / spotlight_campaign_v1 / spotlight_unit_v1 /
      spotlight_note_link_v1 / spotlight_paid_snapshot_v1
Join：unit.noteIds → published_content_v1 (2851 ACTIVE vs 459 LEGACY vs UNMATCHED)
Attribution：平台字段原样保存 (PLATFORM_ATTRIBUTED)；公司加微不入库（UNATTRIBUTABLE_CENTRALIZED_B007）
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
RAW_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                r"\browser_profiles\B007\treecut_inbox\creator\raw\creator")
ACCOUNT_ID = "62ea6099000000001f004e37"
ACCOUNT_NAME = "T-KUBON坤宝高端岛台工厂-zx"
REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"

META_FIELDS_CAMP = ("campaignId", "campaignName", "campaignGroupId", "campaignGroupName",
                    "startTime", "expireTime", "state", "campaignEnable", "campaignDayBudget",
                    "promotionTarget", "placement", "conversionChannels", "numberOfUnits",
                    "winHorseNoteNum")
META_FIELDS_UNIT = ("unitId", "unitName", "campaignId", "campaignName", "campaignGroupId",
                    "campaignGroupName", "startTime", "expireTime", "unitCreateTime", "state",
                    "unitEnable", "targetType", "optimizeTarget", "biddingStrategy",
                    "landingPageType", "promotionTarget")
METRIC_FIELDS = ("fee", "impression", "click", "ctr", "acp", "cpm", "interaction", "cpi",
                 "videoPlay5sCnt", "videoPlay5sRate", "iUserNum", "iUserPrice", "tiUserNum",
                 "tiUserPrice", "messageConsult", "initiativeMessage", "msgLeadsNum",
                 "messageConsultCpl", "initiativeMessageCpl", "msgLeadsCost",
                 "externalGoodsOrder15", "externalGoodsOrderRate15New",
                 "outClickEnterStoreCnt15d", "outClickEnterStoreCvr15dNew",
                 "leads", "leadsCvr", "validLeadsCpl", "collect", "follow", "goodsOrder",
                 "wechatCopyCnt", "appActivateAmount1d", "appActivateAmount3d",
                 "appActivateAmount7d", "externalGoodsOrderPrice30", "externalRgmv15",
                 "externalRgmv30", "externalLeads")


def num(v):
    if v is None or v == "" or v == "-":
        return None
    try:
        s = str(v).replace("%", "").replace(",", "")
        return float(s)
    except (TypeError, ValueError):
        return None


def latest_subdir(root: Path, name: str) -> Path:
    d = root / name
    runs = sorted(d.glob("*")) if d.exists() else []
    return runs[-1] if runs else None


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def ensure_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS spotlight_account_v1(
      account_id TEXT PRIMARY KEY, account_name TEXT, platform TEXT,
      seller_id TEXT, role_type INTEGER, professional_name TEXT,
      source TEXT, snapshot_time TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS spotlight_campaign_v1(
      campaign_id TEXT PRIMARY KEY, account_id TEXT, campaign_name TEXT,
      campaign_group_id TEXT, campaign_group_name TEXT,
      start_time TEXT, expire_time TEXT, state INTEGER, campaign_enable INTEGER,
      promotion_target INTEGER, placement INTEGER, conversion_channels INTEGER,
      day_budget REAL, number_of_units INTEGER, win_horse_note_num INTEGER,
      source TEXT, raw_ref TEXT, created_at REAL, updated_at REAL);
    CREATE TABLE IF NOT EXISTS spotlight_unit_v1(
      unit_id TEXT PRIMARY KEY, account_id TEXT, campaign_id TEXT, campaign_name TEXT,
      unit_name TEXT, start_time TEXT, expire_time TEXT, unit_create_time TEXT,
      state INTEGER, unit_enable INTEGER, target_type INTEGER, optimize_target INTEGER,
      bidding_strategy INTEGER, landing_page_type INTEGER,
      note_ids TEXT, source TEXT, raw_ref TEXT, created_at REAL, updated_at REAL);
    CREATE TABLE IF NOT EXISTS spotlight_note_link_v1(
      link_id TEXT PRIMARY KEY, account_id TEXT, unit_id TEXT, campaign_id TEXT,
      note_id TEXT, join_status TEXT, created_at REAL);
    CREATE TABLE IF NOT EXISTS spotlight_paid_snapshot_v1(
      snapshot_id TEXT PRIMARY KEY, account_id TEXT, entity_type TEXT, entity_id TEXT,
      snapshot_time TEXT, report_start TEXT, report_end TEXT,
      delivery_start TEXT, delivery_end TEXT, window TEXT, status TEXT,
      fee REAL, impressions REAL, clicks REAL, ctr REAL, acp REAL, cpm REAL,
      interaction REAL, cpi REAL, video_play5s REAL,
      i_user_num REAL, i_user_price REAL, ti_user_num REAL, ti_user_price REAL,
      message_consult REAL, initiative_message REAL, msg_leads_num REAL,
      message_consult_cpl REAL, initiative_message_cpl REAL, msg_leads_cost REAL,
      leads REAL, external_goods_order15 REAL,
      metric_json TEXT, source TEXT, metric_type TEXT, created_at REAL);
    """)


def main() -> int:
    raw_run = latest_subdir(RAW_ROOT, "spotlight_raw")
    acct_run = latest_subdir(RAW_ROOT, "spotlight_account")
    if raw_run is None or acct_run is None:
        print("missing evidence dirs")
        return 1
    print(f"raw_run = {raw_run.name}, acct_run = {acct_run.name}")

    # ---- 账户 ----
    ui = load_json(acct_run / "leona_user_info.json").get("data") or {}
    account_id = ui.get("userId") or ui.get("loginAccount") or ACCOUNT_ID
    account_name = ui.get("nickName") or ACCOUNT_NAME
    print(f"account = {account_name} / {account_id}")

    # ---- 读取分页文件 ----
    def read_pages(pattern):
        pages = {}
        for f in sorted(raw_run.glob(pattern)):
            d = load_json(f)
            data = d.get("data")
            if not isinstance(data, dict):
                continue
            pn = data.get("pageNum") or (len(pages) + 1)
            lst = data.get("list") or data.get("dataList") or []
            for item in lst:
                cid = item.get("campaignId") or item.get("campaignInfo", {}).get("campaignId") \
                    if isinstance(item, dict) else None
                pages[cid] = item
        return pages

    camp_items = read_pages("light_campaign_data_list_page*.json")
    unit_items = read_pages("leona_rtb_unit_search_page*.json")
    print(f"campaigns={len(camp_items)} units={len(unit_items)}")

    overall_file = raw_run / "light_ad_manage_data_overall.json"
    overall = load_json(overall_file).get("data", {}) if overall_file.exists() else {}
    overall_agg = overall.get("aggregationData") or {}

    conn = sqlite3.connect(DB, timeout=30)
    ensure_schema(conn)
    conn.row_factory = sqlite3.Row
    now = time.time()
    snapshot_time = time.strftime("%Y-%m-%d %H:%M")
    report_start = "2026-08-31"
    report_end = "2026-08-31"

    # 账户实体
    conn.execute(
        "INSERT OR REPLACE INTO spotlight_account_v1(account_id,account_name,platform,seller_id,"
        "role_type,professional_name,source,snapshot_time,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (account_id, account_name, "XIAOHONGSHU_SPOTLIGHT", ui.get("sellerId") or "",
         ui.get("roleType"), (ui.get("professionalInfo") or {}).get("professionalName"),
         f"PAGE_OWNED_RESPONSE:leona_user_info:{acct_run.name}", snapshot_time, now))

    # 账户级指标快照
    def snap(exists_check, insert_sql, vals):
        if exists_check is not None and conn.execute(exists_check, vals[:len(vals) - 4] if False else ()).fetchone():
            return False
        return True

    # 计划 + 指标快照
    camp_count = snap_insert = 0
    for cid, item in sorted(camp_items.items()):
        ci = item.get("campaignInfo") or item
        dvj = json.loads(item.get("dataValueJson") or "{}") if isinstance(item.get("dataValueJson"), str) else (item.get("dataValueJson") or {})
        cid_s = str(ci.get("campaignId") or cid)
        conn.execute(
            "INSERT OR REPLACE INTO spotlight_campaign_v1(campaign_id,account_id,campaign_name,"
            "campaign_group_id,campaign_group_name,start_time,expire_time,state,campaign_enable,"
            "promotion_target,placement,conversion_channels,day_budget,number_of_units,"
            "win_horse_note_num,source,raw_ref,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid_s, account_id, ci.get("campaignName", ""), ci.get("campaignGroupId", ""),
             ci.get("campaignGroupName", ""), ci.get("startTime", ""), ci.get("expireTime", ""),
             ci.get("state"), ci.get("campaignEnable"), ci.get("promotionTarget"),
             ci.get("placement"), ci.get("conversionChannels"), num(ci.get("campaignDayBudget")),
             ci.get("numberOfUnits"), ci.get("winHorseNoteNum"),
             "PAGE_OWNED_RESPONSE:light_campaign_data_list", raw_run.name, now, now))
        snap_id = f"SPC-{hashlib.sha256(f'{account_id}:CAMP:{cid_s}:{report_start}:{report_end}'.encode()).hexdigest()[:20]}"
        if not conn.execute("SELECT 1 FROM spotlight_paid_snapshot_v1 WHERE snapshot_id=?", (snap_id,)).fetchone():
            conn.execute(
                "INSERT INTO spotlight_paid_snapshot_v1(snapshot_id,account_id,entity_type,entity_id,"
                "snapshot_time,report_start,report_end,delivery_start,delivery_end,window,status,"
                "fee,impressions,clicks,ctr,acp,cpm,interaction,cpi,video_play5s,"
                "i_user_num,i_user_price,ti_user_num,ti_user_price,"
                "message_consult,initiative_message,msg_leads_num,"
                "message_consult_cpl,initiative_message_cpl,msg_leads_cost,"
                "leads,external_goods_order15,metric_json,source,metric_type,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (snap_id, account_id, "CAMPAIGN", cid_s, snapshot_time, report_start, report_end,
                 ci.get("startTime", ""), ci.get("expireTime", ""), "REPORT_RANGE", ci.get("state"),
                 num(dvj.get("fee")), num(dvj.get("impression")), num(dvj.get("click")),
                 num(dvj.get("ctr")), num(dvj.get("acp")), num(dvj.get("cpm")),
                 num(dvj.get("interaction")), num(dvj.get("cpi")), num(dvj.get("videoPlay5sCnt")),
                 num(dvj.get("iUserNum")), num(dvj.get("iUserPrice")), num(dvj.get("tiUserNum")),
                 num(dvj.get("tiUserPrice")), num(dvj.get("messageConsult")),
                 num(dvj.get("initiativeMessage")), num(dvj.get("msgLeadsNum")),
                 num(dvj.get("messageConsultCpl")), num(dvj.get("initiativeMessageCpl")),
                 num(dvj.get("msgLeadsCost")), None, num(dvj.get("externalGoodsOrder15")),
                 json.dumps(dvj, ensure_ascii=False), "PAGE_OWNED_RESPONSE", "PLATFORM_ATTRIBUTED", now))
            snap_insert += 1
        camp_count += 1

    # 单元 + note 关联 + 单元指标快照
    unit_count = link_count = uniq_notes = 0
    join_stats = {"ACTIVE_PUBLISHED_MATCH": 0, "LEGACY_IDENTITY_MATCH": 0,
                  "UNMATCHED_PAID_NOTE": 0}
    active_ids = {r[0] for r in conn.execute(
        "SELECT note_id FROM published_content_v1 WHERE account_id='B007' AND note_id IN ("
        "SELECT DISTINCT note_id FROM spotlight_note_link_v1 WHERE account_id='B007')").fetchall()}  # placeholder
    # 真实 active/legacy 判定：用 content_join_status 无法区分 → 用 evidence 集：published_content 中 source 含 POSTED_CAPTURE 或 title 非空
    published = {}
    for r in conn.execute("SELECT note_id,title,source_refs FROM published_content_v1 WHERE account_id='B007'"):
        sr = r["source_refs"] or ""
        published[r["note_id"]] = "ACTIVE" if ("POSTED_CAPTURE" in sr or (r["title"] or "")) else "LEGACY"

    for uid, item in sorted(unit_items.items()):
        u = item
        uid_s = str(u.get("unitId") or uid)
        note_ids = u.get("noteIds") or []
        conn.execute(
            "INSERT OR REPLACE INTO spotlight_unit_v1(unit_id,account_id,campaign_id,campaign_name,"
            "unit_name,start_time,expire_time,unit_create_time,state,unit_enable,target_type,"
            "optimize_target,bidding_strategy,landing_page_type,note_ids,source,raw_ref,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid_s, account_id, str(u.get("campaignId") or ""), u.get("campaignName", ""),
             u.get("unitName", ""), u.get("startTime", ""), u.get("expireTime", ""),
             u.get("unitCreateTime", ""), u.get("state"), u.get("unitEnable"),
             u.get("targetType"), u.get("optimizeTarget"), u.get("biddingStrategy"),
             u.get("landingPageType"), json.dumps(note_ids, ensure_ascii=False),
             "PAGE_OWNED_RESPONSE:leona_rtb_unit_search", raw_run.name, now, now))
        unit_count += 1
        # note links
        for nid in note_ids:
            link_id = f"SPL-{hashlib.sha256(f'{account_id}:{uid_s}:{nid}'.encode()).hexdigest()[:20]}"
            st = published.get(nid)
            js = "ACTIVE_PUBLISHED_MATCH" if st == "ACTIVE" else ("LEGACY_IDENTITY_MATCH" if st == "LEGACY" else "UNMATCHED_PAID_NOTE")
            join_stats[js] = join_stats.get(js, 0) + 1
            conn.execute(
                "INSERT OR REPLACE INTO spotlight_note_link_v1(link_id,account_id,unit_id,campaign_id,"
                "note_id,join_status,created_at) VALUES(?,?,?,?,?,?,?)",
                (link_id, account_id, uid_s, str(u.get("campaignId") or ""), nid, js, now))
            link_count += 1
        # unit metrics snapshot
        ud = u.get("data") or {}
        snap_id = f"SPU-{hashlib.sha256(f'{account_id}:UNIT:{uid_s}:{report_start}:{report_end}'.encode()).hexdigest()[:20]}"
        if not conn.execute("SELECT 1 FROM spotlight_paid_snapshot_v1 WHERE snapshot_id=?", (snap_id,)).fetchone():
            conn.execute(
                "INSERT INTO spotlight_paid_snapshot_v1(snapshot_id,account_id,entity_type,entity_id,"
                "snapshot_time,report_start,report_end,delivery_start,delivery_end,window,status,"
                "fee,impressions,clicks,ctr,acp,cpm,interaction,cpi,video_play5s,"
                "i_user_num,i_user_price,ti_user_num,ti_user_price,"
                "message_consult,initiative_message,msg_leads_num,"
                "message_consult_cpl,initiative_message_cpl,msg_leads_cost,"
                "leads,external_goods_order15,metric_json,source,metric_type,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (snap_id, account_id, "UNIT", uid_s, snapshot_time, report_start, report_end,
                 u.get("startTime", ""), u.get("expireTime", ""), "REPORT_RANGE", u.get("state"),
                 num(ud.get("fee")), num(ud.get("impression")), num(ud.get("click")),
                 num(ud.get("ctr")), num(ud.get("acp")), num(ud.get("cpm")),
                 num(ud.get("interaction")), num(ud.get("cpi")), num(ud.get("videoPlay5sCnt")),
                 num(ud.get("iUserNum")), num(ud.get("iUserPrice")), num(ud.get("tiUserNum")),
                 num(ud.get("tiUserPrice")), num(ud.get("messageConsult")),
                 num(ud.get("initiativeMessage")), num(ud.get("msgLeadsNum")),
                 num(ud.get("messageConsultCpl")), num(ud.get("initiativeMessageCpl")),
                 num(ud.get("msgLeadsCost")), num(ud.get("leads")), num(ud.get("goodsOrder")),
                 json.dumps(ud, ensure_ascii=False), "PAGE_OWNED_RESPONSE", "PLATFORM_ATTRIBUTED", now))
            snap_insert += 1
    uniq_notes = len({nid for item in unit_items.values() for nid in (item.get("noteIds") or [])})

    # 账户汇总快照
    snap_id = f"SPA-{hashlib.sha256(f'{account_id}:ACCOUNT:{report_start}:{report_end}'.encode()).hexdigest()[:20]}"
    if not conn.execute("SELECT 1 FROM spotlight_paid_snapshot_v1 WHERE snapshot_id=?", (snap_id,)).fetchone():
        conn.execute(
            "INSERT INTO spotlight_paid_snapshot_v1(snapshot_id,account_id,entity_type,entity_id,"
            "snapshot_time,report_start,report_end,delivery_start,delivery_end,window,status,"
            "fee,impressions,clicks,ctr,acp,cpm,interaction,cpi,video_play5s,"
            "i_user_num,i_user_price,ti_user_num,ti_user_price,"
            "message_consult,initiative_message,msg_leads_num,"
            "message_consult_cpl,initiative_message_cpl,msg_leads_cost,"
            "leads,external_goods_order15,metric_json,source,metric_type,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (snap_id, account_id, "ACCOUNT", account_id, snapshot_time, report_start, report_end,
             None, None, "REPORT_RANGE", None,
             num(overall_agg.get("fee")), num(overall_agg.get("impression")),
             num(overall_agg.get("click")), num(overall_agg.get("ctr")),
             num(overall_agg.get("acp")), num(overall_agg.get("cpm")),
             num(overall_agg.get("interaction")), num(overall_agg.get("cpi")), None,
             None, None, None, None,
             num(overall_agg.get("messageConsult")), num(overall_agg.get("initiativeMessage")),
             num(overall_agg.get("msgLeadsNum")), None, None, num(overall_agg.get("msgLeadsCost")),
             None, None, json.dumps(overall_agg, ensure_ascii=False),
             "PAGE_OWNED_RESPONSE", "PLATFORM_ATTRIBUTED", now))
        snap_insert += 1

    # binding 升级：account_id = canonical anchor（§7：真实平台字段已取得）
    binding_path = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
                        r"\browser_profiles\B007\account_binding.json")
    if binding_path.exists():
        b = json.loads(binding_path.read_text(encoding="utf-8"))
        b["spotlight_ad_account_id"] = account_id
        b["spotlight_ad_account_name"] = account_name
        b["spotlight_id_calibrated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        binding_path.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"BINDING_UPGRADED: spotlight_ad_account_id={account_id}")

    conn.commit()
    conn.close()

    result = {
        "run": raw_run.name,
        "account": {"account_id": account_id, "account_name": account_name,
                    "id_source": "PAGE_OWNED_RESPONSE:leona/user/info",
                    "id_calibration": "CANONICAL_ANCHOR_UPGRADED"},
        "report_range": {"start": report_start, "end": report_end,
                         "note": "今日默认视图（日期选择器文本未探测到 → AVAILABLE_PAID_DATE_RANGE 待扩展）"},
        "campaigns": camp_count, "units": unit_count,
        "unique_promoted_notes": uniq_notes, "note_links": link_count,
        "paid_snapshots_inserted": snap_insert,
        "join": join_stats,
        "attribution": {
            "metric_fields": METRIC_FIELDS,
            "class": "PLATFORM_ATTRIBUTED (平台字段原样保存)",
            "company_centralized_wechat": "UNATTRIBUTABLE_CENTRALIZED_B007 (未导入，不参与 note attribution)",
        },
    }
    out = OUT / "B007_SPOTLIGHT_SYNC_RESULT_V1.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
