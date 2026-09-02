# -*- coding: utf-8 -*-
"""Corrective Audit A: Sample20 Recency + Recent Universe + Recent12 Feasibility + Templates + Plans（只读）。"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
MANIFEST = OUT / "B007_SAMPLE20_V1.json"
NOW = datetime(2026, 9, 2)


def q(c, sql, args=()):
    return c.execute(sql, args).fetchall()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    samples = man["samples"]
    c = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)

    # ---- 1+2. Sample20 exact recency ----
    rows = []
    year_cnt = {}
    recency = {"30d": 0, "60d": 0, "90d": 0, "180d": 0, "gt180d": 0}
    for s in samples:
        pt = datetime.strptime(s["publish_time"], "%Y-%m-%d %H:%M")
        days = (NOW - pt).days
        ym = s["publish_time"][:7]
        year_cnt[ym[:4]] = year_cnt.get(ym[:4], 0) + 1
        b = "gt180d" if days > 180 else ("180d" if days > 90 else ("90d" if days > 60 else ("60d" if days > 30 else "30d")))
        recency[b] += 1
        rows.append({"sample_id": s["sample_id"], "note_id": s["note_id"],
                     "title": s["title"], "publish_time": s["publish_time"], "year_month": ym,
                     "stratum": s["primary_stratum"], "age_days": days})
    # 2026 count / 180d count
    n2026 = year_cnt.get("2026", 0)
    n180 = sum(v for k, v in recency.items() if k != "gt180d")

    # ---- 5. Recent universe (2851 active) ----
    def window_rows(lo, hi):
        return q(c, "SELECT media_type, paid_associated, paid_metric_status, creator_view, "
                    "observed_paid_fee, observed_paid_leads FROM b007_note_dual_source_fact_v1 "
                    "WHERE published_universe_status='ACTIVE_PUBLISHED_UNIVERSE' AND publish_time>=? AND publish_time<?", (lo, hi))

    def classify_rows(rows_u, p75v):
        out = {"total": len(rows_u),
               "video": sum(1 for r in rows_u if r[0] == "video"),
               "by_paid_status": {},
               "creator_high": 0, "recent_nopaid_control": 0,
               "paid_efficient": 0, "paid_high_input_weak": 0, "cross_source": 0}
        for mt, assoc, ps, cv, fee, leads in rows_u:
            if mt != "video":
                continue
            out["by_paid_status"][ps] = out["by_paid_status"].get(ps, 0) + 1
            if ps == "NO_PAID_ASSOCIATION_OBSERVED":
                if (cv or 0) >= p75v:
                    out["creator_high"] += 1
                else:
                    out["recent_nopaid_control"] += 1
            elif ps == "NOTE_PAID_METRIC_PRESENT":
                out["paid_efficient"] += 1
                if (fee or 0) >= 1.5 and (leads or 0) == 0:
                    out["paid_high_input_weak"] += 1
            elif ps == "PAID_ASSOCIATED_NO_METRIC_RECORD":
                out["cross_source"] += 1
        return out

    univ = {}
    for (label, lo, hi) in (("2026_03_08", "2026-03-01", "2026-09-01"),
                            ("2026_07_08", "2026-07-01", "2026-09-01")):
        rows_u = window_rows(lo, hi)
        vs = sorted([r[3] or 0 for r in rows_u if r[0] == "video"])
        p75v = vs[int(len(vs) * 0.75)] if vs else 0
        univ[label] = classify_rows(rows_u, p75v)
        univ[label]["p75_creator_view"] = p75v

    # ---- 6. Recent12 feasibility ----
    recent_0608 = window_rows("2026-07-01", "2026-09-01")
    recent_0306 = window_rows("2026-03-01", "2026-07-01")
    vs_all = sorted([r[3] or 0 for r in window_rows("2026-03-01", "2026-09-01") if r[0] == "video"])
    p75r = vs_all[int(len(vs_all) * 0.75)] if vs_all else 0

    feasibility = {
        "proposal": "6x 2026-07~08 + 6x 2026-03~06",
        "eligible_2026_07_08_total_video": sum(1 for r in recent_0608 if r[0] == "video"),
        "eligible_2026_03_06_total_video": sum(1 for r in recent_0306 if r[0] == "video"),
        "by_category_07_08": classify_rows(recent_0608, p75r),
        "by_category_03_06": classify_rows(recent_0306, p75r),
        "note": "eligibility counts only; no selection/media recovery performed",
    }

    # ---- 10. Templates ----
    tmpl = []
    for r in q(c, "SELECT template_id, template_name, content_type, structure, slot_rules, cta, version, active "
                  "FROM content_templates"):
        tmpl.append({"template_id": r[0], "template_name": r[1], "content_type": r[2],
                     "structure": (r[3] or "")[:400], "slot_rules": (r[4] or "")[:400],
                     "cta": (r[5] or "")[:200], "version": r[6], "active": r[7],
                     "authoring": "HAND_AUTHORED"})  # 判定在报告脚本中依据字段内容

    # ---- 9. Plans ----
    plans = []
    for r in q(c, "SELECT project_id, template_id, content_type, plan_json, status, output_dir, created_time "
                  "FROM production_plans"):
        plans.append({"project_id": r[0], "template_id": r[1], "content_type": r[2],
                      "plan_json": (r[3] or "")[:600], "status": r[4], "output_dir": r[5],
                      "created_time": r[6]})
    c.close()

    audit = {
        "phase": "CORRECTIVE_STATUS_AUDIT",
        "generated_at": NOW.strftime("%Y-%m-%d"),
        "reference_date": NOW.strftime("%Y-%m-%d"),
        "sample20_exact_recency": rows,
        "sample20_year_distribution": year_cnt,
        "sample20_recency_buckets": recency,
        "sample20_2026_count": n2026,
        "sample20_within_180d_count": n180,
        "recent_universe": univ,
        "recent12_feasibility": feasibility,
        "templates": tmpl,
        "production_plans": plans,
    }
    (OUT / "B007_SAMPLE20_RECENCY_AUDIT_V1.json").write_text(json.dumps(audit, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "B007_RECENT12_FEASIBILITY_V1.json").write_text(json.dumps(feasibility, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"year_dist": year_cnt, "recency": recency, "n2026": n2026, "n180": n180,
                      "universe": univ, "feasibility": feasibility,
                      "plans": plans}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

