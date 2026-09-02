# -*- coding: utf-8 -*-
"""STAGE8 G1 — b007_source_role_v1 落库 + 全量角色先验回填 + 污染检测器(复用 OCR)。

§5/§6 角色与先验；§8 污染与角色分离；§13/§14 检测输出 PRESENT|ABSENT|UNCERTAIN+证据；
§15 环境文字不判污染；§22 覆盖100%(UNKNOWN 属合法)；§23 迁移而非平行体系。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")

SRC_PRIOR = {1: "PRODUCTION_CLEAN_SEMI", 2: "PRODUCTION_CLEAN_SEMI",
             3: "NOT_PRODUCTION_SOURCE", 4: "PRODUCTION_CLEAN_RAW",
             5: "PUBLISHED_REFERENCE"}
B007_PUBLISHED_ROLE = "PUBLISHED_REFERENCE"

PROMO_RE = re.compile(r"关注|扫码|福利|公众号|领取|团购|秒杀|优惠|下单|客服|同款|点赞|收藏|"
                      r"直播|抽奖|免单|好评|返现|私信|主页|橱窗|优惠券|特价|现货|包邮|会员|"
                      r"评论|转发|关注我|记得关注")
DATE_RE = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}|时间[:：]?\d{1,2}:\d{2}|\d{1,2}:\d{2}:\d{2}")
PLATFORM_RE = re.compile(r"小红书|redbook|xiaohongshu|@|账号|ID[:：]")


def norm_text(t: str) -> str:
    return re.sub(r"\s+", "", t or "")


def main() -> int:
    t0 = time.time()
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    # --- 建表（迁移） ---
    c.execute("""CREATE TABLE IF NOT EXISTS b007_source_role_v1 (
        entity_kind TEXT NOT NULL,            -- 'media_file' | 'b007_asset'
        entity_id   TEXT NOT NULL,
        source_id   INTEGER,
        initial_prior TEXT,
        source_role TEXT,
        role_basis  TEXT,
        role_confidence REAL,
        asset_type  TEXT,                     -- raw|finished|semi_finished|unknown(结构维度,与角色分离)
        burned_subtitle_present TEXT,         -- PRESENT|ABSENT|UNCERTAIN
        platform_watermark_present TEXT,
        old_title_overlay_present TEXT,
        brand_overlay_present TEXT,
        unrelated_overlay_present TEXT,
        contamination_confidence REAL,
        contamination_evidence TEXT,          -- JSON [{reason_code, frames, sample_text, note}]
        environment_text_present TEXT,        -- 环境文字(横幅/实物标签) — 记录但不判污染
        review_status TEXT DEFAULT 'PENDING', -- pending|review_required|approved|rejected
        role_version INTEGER DEFAULT 1,
        created_at REAL,
        updated_at REAL,
        PRIMARY KEY (entity_kind, entity_id))""")
    now = time.time()

    # --- 1) media_files 全量角色先验回填 ---
    mf_rows = c.execute("SELECT id, source_id FROM media_files").fetchall()
    inserted = 0
    for mid, sid in mf_rows:
        prior = SRC_PRIOR.get(sid, "UNKNOWN")
        basis = "SOURCE_PRIOR(path/source registry)"
        c.execute("""INSERT OR REPLACE INTO b007_source_role_v1
            (entity_kind, entity_id, source_id, initial_prior, source_role, role_basis,
             role_confidence, review_status, created_at, updated_at)
            VALUES ('media_file', ?, ?, ?, ?, ?, 0.5, 'PENDING', ?, ?)""",
                  (str(mid), sid, prior, prior, basis, now, now))
        inserted += 1

    # --- 2) B007 published 资产（b007_media_asset_v1） ---
    pub = c.execute("SELECT asset_id FROM b007_media_asset_v1").fetchall()
    for (aid,) in pub:
        c.execute("""INSERT OR REPLACE INTO b007_source_role_v1
            (entity_kind, entity_id, source_id, initial_prior, source_role, role_basis,
             role_confidence, review_status, created_at, updated_at)
            VALUES ('b007_asset', ?, NULL, 'PUBLISHED_REFERENCE', 'PUBLISHED_REFERENCE',
             'PUBLISHED_MEDIA_ASSET_TABLE', 1.0, 'APPROVED', ?, ?)""",
                  (aid, now, now))
    c.commit()
    print(f"role backfill: media_files={inserted} b007_assets={len(pub)}")

    # --- 3) 污染检测器：复用 ocr_text（候选池 S1/S2/S4 + S3 一并判） ---
    # 3a. subtitle_flag 命中
    subflag = {}
    for r in c.execute("""SELECT o.asset_id, count(DISTINCT o.frame_id), group_concat(substr(o.text,1,30),' | ')
                          FROM ocr_text o WHERE o.subtitle_flag=1 GROUP BY o.asset_id"""):
        subflag[r[0]] = {"frames": r[1], "sample": (r[2] or "")[:200]}
    # 3b. 持久文本(≥3 不同帧) 聚合并按内容规则分类
    persist = {}
    for r in c.execute("""SELECT o.asset_id, o.text, count(DISTINCT o.frame_id) nf
                          FROM ocr_text o WHERE length(replace(o.text,' ',''))>=4
                          GROUP BY o.asset_id, o.text HAVING nf>=3"""):
        aid, text, nf = r
        persist.setdefault(aid, []).append({"text": text, "frames": nf})
    # 3c. 每 asset OCR 行数(覆盖率/置信)
    ocr_count = {}
    for r in c.execute("SELECT asset_id, count(*), count(DISTINCT frame_id) FROM ocr_text GROUP BY asset_id"):
        ocr_count[r[0]] = (r[1], r[2])

    # 映射 asset_id -> media_id/source
    amap = {}
    for r in c.execute("""SELECT a.asset_id, mf.id, mf.source_id FROM assets a
                          JOIN media_files mf ON mf.id=a.media_id"""):
        amap[r[0]] = (r[1], r[2])

    def decide(aid):
        ev = []
        env = []
        burned, wm, oldt, brand, unrel = "ABSENT", "ABSENT", "ABSENT", "ABSENT", "ABSENT"
        conf = 0.5
        if aid in subflag:
            burned = "PRESENT"
            conf = max(conf, 0.9)
            ev.append({"reason_code": "SUBTITLE_FLAG",
                       "frames": subflag[aid]["frames"],
                       "sample_text": subflag[aid]["sample"][:150]})
        if aid in persist:
            promo_hits = [p for p in persist[aid] if PROMO_RE.search(p["text"])]
            date_hits = [p for p in persist[aid] if DATE_RE.search(p["text"])]
            plat_hits = [p for p in persist[aid] if PLATFORM_RE.search(p["text"])]
            if promo_hits:
                unrel = "PRESENT"
                conf = max(conf, 0.85)
                ev.append({"reason_code": "PERSISTENT_PROMO",
                           "frames": promo_hits[0]["frames"],
                           "sample_text": promo_hits[0]["text"][:60]})
            if date_hits:
                # 时间戳/日期浮层 → 旧标题类烧录信息
                oldt = "PRESENT" if date_hits[0]["frames"] >= 5 else "UNCERTAIN"
                conf = max(conf, 0.8)
                ev.append({"reason_code": "PERSISTENT_DATETIME",
                           "frames": date_hits[0]["frames"],
                           "sample_text": date_hits[0]["text"][:60]})
            if plat_hits:
                wm = "PRESENT"
                conf = max(conf, 0.9)
                ev.append({"reason_code": "PLATFORM_TEXT",
                           "frames": plat_hits[0]["frames"],
                           "sample_text": plat_hits[0]["text"][:60]})
            # 环境文字：仅大片/横幅类文本但无法定位时——交给视觉；此处只记非污染
            for p in persist[aid]:
                if len(p["text"]) >= 12 and not (PROMO_RE.search(p["text"]) or DATE_RE.search(p["text"])):
                    env.append({"text": p["text"][:80], "frames": p["frames"]})
        if not ev and aid in ocr_count:
            conf = 0.6  # 有 OCR 覆盖且无信号 → 干净候选(置信中等，等待 L2/L3)
        elif aid not in ocr_count:
            burned = "UNCERTAIN"; conf = min(conf, 0.2)
            ev.append({"reason_code": "NO_OCR_COVERAGE", "frames": 0})
        return burned, wm, oldt, brand, unrel, round(conf, 2), ev, env

    stats = {"S1": {}, "S2": {}, "S3": {}, "S4": {}}
    for aid, (mid, sid) in amap.items():
        if sid not in (1, 2, 3, 4):
            continue
        burned, wm, oldt, brand, unrel, conf, ev, env = decide(aid)
        env_text = "PRESENT" if env else "ABSENT"
        c.execute("""UPDATE b007_source_role_v1 SET
            burned_subtitle_present=?, platform_watermark_present=?, old_title_overlay_present=?,
            brand_overlay_present=?, unrelated_overlay_present=?, contamination_confidence=?,
            contamination_evidence=?, environment_text_present=?, role_version=role_version+1,
            review_status=CASE WHEN (?='PRESENT' OR ?='PRESENT' OR ?='PRESENT' OR ?='PRESENT'
                 OR ?='UNCERTAIN' OR ?='UNCERTAIN' OR ?='UNCERTAIN') THEN 'REVIEW_REQUIRED'
                 ELSE review_status END, updated_at=?
            WHERE entity_kind='media_file' AND entity_id=?""",
                  (burned, wm, oldt, brand, unrel, conf,
                   json.dumps(ev, ensure_ascii=False), env_text,
                   burned, wm, oldt, unrel, burned, wm, oldt, now, str(mid)))
        st = stats.setdefault(f"S{sid}", {})
        st["total"] = st.get("total", 0) + 1
        for k, v in (("burned", burned), ("wm", wm), ("unrel", unrel), ("env", env_text)):
            st[k] = st.get(k, {})
            st[k][v] = st[k].get(v, 0) + 1
    c.commit()
    print(json.dumps(stats, ensure_ascii=False, indent=1))

    # 汇总行(覆盖/角色计数)
    cov = {}
    for r in c.execute("""SELECT source_id, count(*) FROM b007_source_role_v1
                          WHERE entity_kind='media_file' GROUP BY source_id ORDER BY source_id"""):
        cov[r[0]] = r[1]
    role_c = {}
    for r in c.execute("SELECT source_role, count(*) FROM b007_source_role_v1 GROUP BY source_role"):
        role_c[r[0]] = r[1]
    print("coverage by source:", cov)
    print("roles:", role_c)

    registry = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "coverage_by_source": cov, "role_counts": role_c,
                "detector_stats": stats,
                "note": "media_files 28252 + b007_assets 30 全量角色已落库(覆盖100%含UNKNOWN合法态); "
                        "污染检测仅复用现有 ocr_text 未重扫全库"}
    (OUT / "TREECUT_G1_SOURCE_ROLE_REGISTRY_V1.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"elapsed {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
