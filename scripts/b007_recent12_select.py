# -*- coding: utf-8 -*-
"""V0.8.2 — RECENT12 SELECTION（LATEST 6 + EARLIER_RECENT 6，配额分层，唯一性，时效优先，不覆盖 Historical20）。"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
HIST = OUT / "B007_SAMPLE20_V1.json"

LATEST_LO, LATEST_HI = "2026-07-01", "2026-09-01"
EARLY_LO, EARLY_HI = "2026-04-01", "2026-07-01"

QUOTA = [
    ("LATEST", "Creator High", 2), ("LATEST", "No Paid Control", 2), ("LATEST", "Paid Efficient", 2),
    ("EARLIER", "Creator High", 1), ("EARLIER", "Paid Efficient", 1),
    ("EARLIER", "Paid High-input Weak", 2), ("EARLIER", "Cross-source", 2),
]


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def norm_title(t):
    t = re.sub(r"[\U00010000-\U0010FFFF]", "", t or "")
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    hist = {s["note_id"] for s in json.loads(HIST.read_text(encoding="utf-8"))["samples"]}
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)

    def window(lo, hi):
        return q(c, "SELECT note_id, title, publish_time, duration, media_type, creator_view, "
                    "paid_associated, paid_metric_status, observed_paid_fee, observed_paid_impression, "
                    "observed_paid_leads, associated_unit_count "
                    "FROM b007_note_dual_source_fact_v1 "
                    "WHERE published_universe_status='ACTIVE_PUBLISHED_UNIVERSE' "
                    "AND media_type='video' AND publish_time>=? AND publish_time<?", (lo, hi))

    latest = window(LATEST_LO, LATEST_HI)
    early = window(EARLY_LO, EARLY_HI)

    def classify(rows, p75v):
        pools = {"Creator High": [], "No Paid Control": [], "Paid Efficient": [],
                 "Paid High-input Weak": [], "Cross-source": []}
        for r in rows:
            nid, title, pt, dur, mt, cv, assoc, ps, fee, imp, leads, units = r
            if nid in hist:
                continue
            rec = {"note_id": nid, "title": title, "publish_time": pt, "duration": dur,
                   "creator_view": cv, "paid_metric_status": ps,
                   "observed_paid_fee": fee, "observed_paid_impression": imp,
                   "observed_paid_leads": leads, "associated_unit_count": units}
            if ps == "NO_PAID_ASSOCIATION_OBSERVED":
                pools["Creator High" if (cv or 0) >= p75v else "No Paid Control"].append(rec)
            elif ps == "NOTE_PAID_METRIC_PRESENT":
                if (fee or 0) > 0 and (imp or 0) > 0:
                    pools["Paid Efficient"].append(rec)
                if (fee or 0) >= 1.5 and (leads or 0) == 0:
                    pools["Paid High-input Weak"].append(rec)
            elif ps == "PAID_ASSOCIATED_NO_METRIC_RECORD":
                pools["Cross-source"].append(rec)
        return pools

    def p75(rows):
        vs = sorted([r[5] or 0 for r in rows])
        return vs[int(len(vs) * 0.75)] if vs else 0

    latest_pools = classify(latest, p75(latest))
    early_pools = classify(early, p75(early))

    def pick(pool, n, used, used_norm):
        # 时效优先：publish_time desc；多样性：去重 norm title / 日期簇 / 时长簇
        pool = sorted(pool, key=lambda r: r["publish_time"], reverse=True)
        chosen = []
        for r in pool:
            if len(chosen) >= n:
                break
            if r["note_id"] in used:
                continue
            nt = norm_title(r["title"])
            if nt and nt in used_norm:
                continue
            dur_cluster = round((r["duration"] or 0) / 5)
            date = r["publish_time"][:10]
            # 允许同日/同时长但避免过度集中：仅当已选同簇>2 才跳过
            same_dur = sum(1 for x in chosen if round((x["duration"] or 0) / 5) == dur_cluster)
            if same_dur >= 2:
                continue
            chosen.append(r)
            used.add(r["note_id"])
            if nt:
                used_norm.add(nt)
        return chosen

    selected = []
    used = set()
    used_norm = set()
    pool_map = {"LATEST": latest_pools, "EARLIER": early_pools}
    for window_label, stratum, n in QUOTA:
        picks = pick(pool_map[window_label].get(stratum, []), n, used, used_norm)
        for r in picks:
            r["primary_stratum"] = {
                "Creator High": "RC_CREATOR_HIGH",
                "No Paid Control": "RC_NO_PAID_CONTROL",
                "Paid Efficient": "RC_PAID_EFFICIENT",
                "Paid High-input Weak": "RC_PAID_HIGH_INPUT_WEAK_OUTCOME",
                "Cross-source": "RC_CROSS_SOURCE_CONTRAST"}[stratum]
            r["window"] = window_label
            r["selection_stratum"] = stratum
            selected.append(r)

    # 校验配额
    quota_check = {}
    for window_label, stratum, n in QUOTA:
        got = sum(1 for r in selected if r["window"] == window_label and r["selection_stratum"] == stratum)
        quota_check[f"{window_label}|{stratum}"] = {"target": n, "got": got, "ok": got == n}
    ok_all = all(v["ok"] for v in quota_check.values())

    # 输出
    latest6 = [r for r in selected if r["window"] == "LATEST"]
    early6 = [r for r in selected if r["window"] == "EARLIER"]
    # sample_id
    for i, r in enumerate(sorted(selected, key=lambda x: (x["window"], x["publish_time"]), reverse=True)):
        r["sample_id"] = f"RC-{r['note_id'][:8].upper()}"
    rec = {
        "phase": "V0.8.2", "rule_version": "RECENT12_SELECTION_RULE_V1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "historical20_not_overwritten": True,
        "windows": {"LATEST": "2026-07-01..08-31", "EARLIER": "2026-04-01..06-30"},
        "quota_check": quota_check, "all_quotas_ok": ok_all,
        "latest6": latest6, "earlier6": early6, "samples": selected,
        "note": "PAID semantics: NOTE_PAID_METRIC_PRESENT=paid facts exist in window; "
                "NO_PAID_ASSOCIATION_OBSERVED != ORGANIC; no causality labels",
    }
    (OUT / "B007_RECENT12_V1.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    import csv
    with open(OUT / "B007_RECENT12_V1.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "window", "selection_stratum", "primary_stratum", "note_id", "title",
                    "publish_time", "duration", "creator_view", "paid_metric_status",
                    "observed_paid_fee", "observed_paid_impression", "observed_paid_leads"])
        for r in sorted(selected, key=lambda x: (x["window"], x["publish_time"]), reverse=True):
            w.writerow([r["sample_id"], r["window"], r["selection_stratum"], r["primary_stratum"],
                        r["note_id"], r["title"], r["publish_time"], r["duration"], r["creator_view"],
                        r["paid_metric_status"], r["observed_paid_fee"], r["observed_paid_impression"],
                        r["observed_paid_leads"]])

    md = ["# B007 Recent12 Selection Report", "",
          f"Generated: {rec['generated_at']} | all quotas ok: {ok_all}", "",
          "| sample | window | stratum | note_id | title | publish | dur | paid_status | fee |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(selected, key=lambda x: (x["window"], x["publish_time"]), reverse=True):
        md.append(f"| {r['sample_id']} | {r['window']} | {r['selection_stratum']} | {r['note_id']} | "
                  f"{(r['title'] or '')[:28]} | {r['publish_time']} | {r['duration']} | "
                  f"{r['paid_metric_status']} | {r['observed_paid_fee']} |")
    md += ["", "## Quota check", ""]
    for k, v in quota_check.items():
        md.append(f"- {k}: {v}")
    md += ["", "## Diversity note", "",
           "- metadata diversity recorded (title norm / date / duration-cluster); no visual dedup claim", ""]
    (OUT / "B007_RECENT12_SELECTION_REPORT_V1.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"all_quotas_ok": ok_all, "quota_check": quota_check,
                      "selected": [{"sample_id": r["sample_id"], "window": r["window"],
                                    "stratum": r["selection_stratum"], "note_id": r["note_id"],
                                    "publish": r["publish_time"], "dur": r["duration"],
                                    "title": r["title"][:30]} for r in selected]},
                     ensure_ascii=False, indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
