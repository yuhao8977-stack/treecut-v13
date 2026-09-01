# -*- coding: utf-8 -*-
"""V0.5 — 20 条分层代表性视频样本选择（SAMPLE_SELECTION_RULE_V1）。

事实层：b007_note_dual_source_fact_v1（V0.4，不可修改）+ 关联/月事实。
分层 A4/B3/C4/D4/E3/F2；无单一评分；CREATOR_OBSERVED 语义；量门槛（分布型）；
METADATA_DIVERSITY_GATE；逐条证据 reason；稳定 tie-break note_id。
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
REPO = Path(r"C:\Users\admin\github\treecut-v13")
RULE_VERSION = "SAMPLE_SELECTION_RULE_V1"
FACT_VERSION = "B007_V04_DUAL_SOURCE_JOIN_PASS"


def pct_rank(values, v):
    """v 在 values 中的百分位（0-100）：<= v 的比例。"""
    if not values:
        return None
    le = sum(1 for x in values if x <= v)
    return round(le / len(values) * 100, 1)


def percentile(values, p):
    """values 的 p 分位值。"""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = f + 1 if f + 1 < len(s) else f
    return s[f] + (s[c] - s[f]) * (k - f) if c != f else s[f]


def norm_title(t):
    if not t:
        return ""
    t = unicodedata.normalize("NFKC", str(t))
    t = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", t)
    t = re.sub(r"[^\w\u4e00-\u9fff]+", "", t)
    return t


def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    facts = [dict(r) for r in conn.execute("SELECT * FROM b007_note_dual_source_fact_v1")]
    # 关联（campaign/unit 计数已含在 fact；这里取 link 详情用于多样性）
    links = conn.execute("SELECT note_id, unit_id, campaign_id FROM b007_note_paid_association_fact_v1").fetchall()
    link_by_note = defaultdict(list)
    for l in links:
        link_by_note[l["note_id"]].append((l["unit_id"], l["campaign_id"]))
    conn.close()

    video = [f for f in facts if f["media_type"] == "video"]
    video_ids = {f["note_id"] for f in video}
    print(f"video eligible universe: {len(video)}")

    # ---- Creator percentiles（video + creator present） ----
    cr_pool = [f for f in video if f["creator_perf_status"] == "CREATOR_PERFORMANCE_PRESENT"]
    cr_views = [f["creator_view"] or 0 for f in cr_pool]
    cr_likes = [f["creator_like"] or 0 for f in cr_pool]
    for f in cr_pool:
        f["_view_pct"] = pct_rank(cr_views, f["creator_view"] or 0)
        f["_like_pct"] = pct_rank(cr_likes, f["creator_like"] or 0)
    # 全部 video 也赋 view 分位（creator missing -> None）
    for f in video:
        if "_view_pct" not in f:
            f["_view_pct"] = pct_rank(cr_views, f["creator_view"] or 0) if f["creator_view"] is not None else None
    cr_view_p75 = percentile(cr_views, 75)
    cr_view_p50 = percentile(cr_views, 50)
    cr_view_p25 = percentile(cr_views, 25)

    # ---- Paid percentiles（video + paid metric + fee>0 & imp>0 量门槛池） ----
    paid_pool = [f for f in video if f["paid_metric_status"] == "NOTE_PAID_METRIC_PRESENT"]
    vol_pool = [f for f in paid_pool if (f["observed_paid_fee"] or 0) > 0 and (f["observed_paid_impression"] or 0) > 0]
    fee_vals = [f["observed_paid_fee"] for f in vol_pool]
    imp_vals = [f["observed_paid_impression"] for f in vol_pool]
    for f in vol_pool:
        f["_fee_pct"] = pct_rank(fee_vals, f["observed_paid_fee"])
        f["_imp_pct"] = pct_rank(imp_vals, f["observed_paid_impression"])
        f["_lead_cost"] = round(f["observed_paid_fee"] / f["observed_paid_leads"], 2) if (f["observed_paid_leads"] or 0) > 0 else None
        f["_msg_cost"] = round(f["observed_paid_fee"] / f["observed_paid_message_consult"], 2) if (f["observed_paid_message_consult"] or 0) > 0 else None
        f["_cpc"] = round(f["observed_paid_fee"] / f["observed_paid_click"], 2) if (f["observed_paid_click"] or 0) > 0 else None
        f["_ctr"] = round(f["observed_paid_click"] / f["observed_paid_impression"], 4) if f["observed_paid_impression"] > 0 else None
    fee_p25 = percentile(fee_vals, 25)
    fee_p75 = percentile(fee_vals, 75)
    imp_p25 = percentile(imp_vals, 25)
    imp_p75 = percentile(imp_vals, 75)
    # 量门槛：fee >= P25(正值分布) AND imp >= P25
    gate_pool = [f for f in vol_pool if f["observed_paid_fee"] >= fee_p25 and f["observed_paid_impression"] >= imp_p25]
    print(f"volume gate pool (fee>=P25 {round(fee_p25,2)} & imp>=P25 {round(imp_p25)}): {len(gate_pool)}")

    no_assoc = [f for f in video if f["paid_metric_status"] == "NO_PAID_ASSOCIATION_OBSERVED"]
    assoc_no_metric = [f for f in video if f["paid_metric_status"] == "PAID_ASSOCIATED_NO_METRIC_RECORD"]

    # ---- 分层选择（稳定 tie-break note_id） ----
    selected = {}
    strata_report = {}

    def pick(pool, n, key_fn, label):
        pool = sorted(pool, key=lambda f: (-key_fn(f), f["note_id"]))
        picked = []
        used_units = set()
        for f in pool:
            if len(picked) >= n:
                break
            if f["note_id"] in selected:
                continue
            # 多样性：避免同 unit 扎堆（除非池太小）
            units = {u for u, c in link_by_note.get(f["note_id"], [])}
            if units and units & used_units and len(pool) > n * 3:
                continue
            picked.append(f)
            used_units |= units
        return picked

    # A: creator high, no paid assoc
    a_pool = [f for f in no_assoc if f["creator_perf_status"] == "CREATOR_PERFORMANCE_PRESENT" and (f["_view_pct"] or 0) >= 75]
    a_picked = pick(a_pool, 4, lambda f: f["creator_view"] or 0, "A")
    for f in a_picked:
        f["_stratum"] = "A_CREATOR_HIGH_NO_PAID_ASSOC_OBSERVED"
        selected[f["note_id"]] = f
    strata_report["A"] = {"target": 4, "actual": len(a_picked), "eligible": len(a_pool),
                          "rule": "video + NO_PAID_ASSOCIATION_OBSERVED + creator present + creator_view percentile>=P75",
                          "threshold": f"view>=P75({round(cr_view_p75,1)})", "selected": [f["note_id"] for f in a_picked]}

    # B: creator mid-low, no paid assoc（P25~P50 区间为主，不选最差异常）
    b_pool = [f for f in no_assoc if f["creator_perf_status"] == "CREATOR_PERFORMANCE_PRESENT"
              and 25 <= (f["_view_pct"] or 0) < 50]
    b_picked = pick(b_pool, 3, lambda f: f["creator_view"] or 0, "B")
    for f in b_picked:
        f["_stratum"] = "B_CREATOR_MID_LOW_NO_PAID_ASSOC_OBSERVED"
        selected[f["note_id"]] = f
    strata_report["B"] = {"target": 3, "actual": len(b_picked), "eligible": len(b_pool),
                          "rule": "video + NO_PAID_ASSOCIATION_OBSERVED + creator view P25<=pct<P50",
                          "threshold": f"P25={round(cr_view_p25,1)} <= view < P50={round(cr_view_p50,1)}",
                          "selected": [f["note_id"] for f in b_picked]}

    # C: paid high efficiency（量门槛内；lead/msg/click 效率独立）
    c_leads = [f for f in gate_pool if (f["observed_paid_leads"] or 0) > 0]
    c_msg = [f for f in gate_pool if (f["observed_paid_message_consult"] or 0) > 0]
    c_clicks = [f for f in gate_pool if (f["observed_paid_click"] or 0) > 0]
    c_picked = []
    # lead cost 低分位（leads>0 中）
    if c_leads:
        lc_vals = sorted(f["_lead_cost"] for f in c_leads)
        lc_p25 = lc_vals[max(0, int(len(lc_vals) * 0.25) - 1)]
        for f in sorted(c_leads, key=lambda f: (f["_lead_cost"], f["note_id"])):
            if f["_lead_cost"] <= lc_p25 and f["note_id"] not in selected and len(c_picked) < 2:
                f["_stratum"] = "C_PAID_HIGH_EFFICIENCY_CANDIDATE"
                f["_eff_dim"] = "lead_cost"
                selected[f["note_id"]] = f
                c_picked.append(f)
    if c_msg:
        mc_vals = sorted(f["_msg_cost"] for f in c_msg)
        mc_p25 = mc_vals[max(0, int(len(mc_vals) * 0.25) - 1)]
        for f in sorted(c_msg, key=lambda f: (f["_msg_cost"], f["note_id"])):
            if f["_msg_cost"] <= mc_p25 and f["note_id"] not in selected and len(c_picked) < 3:
                f["_stratum"] = "C_PAID_HIGH_EFFICIENCY_CANDIDATE"
                f["_eff_dim"] = "message_cost"
                selected[f["note_id"]] = f
                c_picked.append(f)
    # click efficiency（CPC 低 / CTR 高 双维度补充）
    for f in sorted(c_clicks, key=lambda f: (f["_cpc"] or 999, f["note_id"])):
        if f["note_id"] not in selected and len(c_picked) < 4:
            f["_stratum"] = "C_PAID_HIGH_EFFICIENCY_CANDIDATE"
            f["_eff_dim"] = "click_efficiency"
            selected[f["note_id"]] = f
            c_picked.append(f)
    strata_report["C"] = {"target": 4, "actual": len(c_picked),
                          "eligible": {"gate_pool": len(gate_pool), "leads>0": len(c_leads),
                                       "msg>0": len(c_msg), "clicks>0": len(c_clicks)},
                          "rule": "volume gate(fee>=P25&imp>=P25) + lead/message/click 效率独立",
                          "selected": [f["note_id"] for f in c_picked]}

    # D: high input weak outcome（fee/imp 高分位 + leads=0 & msg=0）
    d_pool = [f for f in vol_pool if (f["_fee_pct"] or 0) >= 75 and (f["_imp_pct"] or 0) >= 75
              and not (f["observed_paid_leads"] or 0) > 0 and not (f["observed_paid_message_consult"] or 0) > 0]
    d_picked = pick(d_pool, 4, lambda f: f["observed_paid_fee"] or 0, "D")
    for f in d_picked:
        f["_stratum"] = "D_PAID_HIGH_INPUT_WEAK_OUTCOME"
        selected[f["note_id"]] = f
    strata_report["D"] = {"target": 4, "actual": len(d_picked), "eligible": len(d_pool),
                          "rule": "video + fee>=P75 & imp>=P75 + platform leads=0 & msg=0 (WEAK_OUTCOME_OBSERVED)",
                          "threshold": f"fee>=P75({round(fee_p75,2)}) imp>=P75({round(imp_p75)})",
                          "selected": [f["note_id"] for f in d_picked]}

    # E: cross-source contrast（creator high + paid weak；或 creator mid + paid strong）
    e_pool = []
    for f in vol_pool:
        if f["note_id"] in selected:
            continue
        cv = f["_view_pct"] or 0
        if cv >= 75 and (f["observed_paid_leads"] or 0) == 0 and (f["observed_paid_message_consult"] or 0) == 0:
            f["_contrast"] = "CREATOR_HIGH_PAID_WEAK"
            e_pool.append(f)
        elif cv < 50 and ((f["observed_paid_leads"] or 0) > 0 or (f["observed_paid_message_consult"] or 0) > 0
                          or (f["_fee_pct"] or 0) >= 75):
            f["_contrast"] = "CREATOR_MID_PAID_STRONG"
            e_pool.append(f)
    e_picked = pick(e_pool, 3, lambda f: 1 if f.get("_contrast") == "CREATOR_MID_PAID_STRONG" else 0, "E")
    for f in e_picked:
        f["_stratum"] = "E_CROSS_SOURCE_CONTRAST"
        selected[f["note_id"]] = f
    strata_report["E"] = {"target": 3, "actual": len(e_picked), "eligible": len(e_pool),
                          "rule": "creator high + paid weak OR creator mid + paid strong",
                          "window": "WINDOW_ALIGNMENT=UNALIGNED NO_CAUSAL_COMPARISON",
                          "selected": [f["note_id"] for f in e_picked]}

    # F: paid assoc no note metric（467 中取视频）
    f_pool = [f for f in assoc_no_metric]
    f_picked = pick(f_pool, 2, lambda f: 0, "F")
    for f in f_picked:
        f["_stratum"] = "F_PAID_ASSOCIATED_NO_NOTE_METRIC"
        selected[f["note_id"]] = f
    strata_report["F"] = {"target": 2, "actual": len(f_picked), "eligible": len(f_pool),
                          "rule": "video + PAID_ASSOCIATED_NO_METRIC_RECORD (数据/关联控制)",
                          "selected": [f["note_id"] for f in f_picked]}

    # ---- Metadata diversity gate ----
    samples = list(selected.values())
    norm_titles = [norm_title(f["title"]) for f in samples]
    dup_titles = len(norm_titles) - len(set(norm_titles))
    months = defaultdict(int)
    for f in samples:
        pt = (f["publish_time"] or "")[:7]
        months[pt] += 1
    durations = [f["duration"] for f in samples if f["duration"]]
    dur_span = (max(durations) - min(durations)) if len(durations) >= 2 else 0
    units_used = set()
    for f in samples:
        for u, c in link_by_note.get(f["note_id"], []):
            units_used.add(u)
    diversity = {"normalized_title_duplicates": dup_titles,
                 "publish_month_distribution": dict(months),
                 "duration_range_seconds": round(dur_span, 1),
                 "distinct_units_in_paid_samples": len(units_used),
                 "note": "METADATA_DIVERSITY only; no visual dedup claim (V0.6/V0.7)"}

    # ---- 汇总 + 证据 ----
    manifest = {"rule_version": RULE_VERSION, "fact_version": FACT_VERSION,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "fee_unit": "YUAN (MONEY_UNIT_VALIDATED=TRUE, B007_V05_FEE_UNIT_CHECK_V1.json)",
                "video_eligible_universe": len(video),
                "strata": strata_report, "diversity": diversity,
                "samples": []}
    for f in samples:
        reason = f"_stratum_reason"
        manifest["samples"].append({
            "sample_id": f"S{f['_stratum'][0]}-{f['note_id'][:8]}",
            "note_id": f["note_id"], "title": f["title"],
            "publish_time": f["publish_time"], "duration": f["duration"],
            "primary_stratum": f["_stratum"],
            "secondary_eligible_strata": [],
            "creator": {"status": f["creator_perf_status"], "view": f["creator_view"],
                        "like": f["creator_like"], "collect": f["creator_collect"],
                        "comment": f["creator_comment"], "share": f["creator_share"],
                        "view_percentile": f.get("_view_pct")},
            "paid": {"status": f["paid_metric_status"],
                     "associated_units": f["associated_unit_count"],
                     "associated_campaigns": f["associated_campaign_count"],
                     "observed_fee": f["observed_paid_fee"], "impressions": f["observed_paid_impression"],
                     "clicks": f["observed_paid_click"], "msg": f["observed_paid_message_consult"],
                     "leads": f["observed_paid_leads"], "months": f["paid_observed_month_count"],
                     "fee_percentile": f.get("_fee_pct"), "imp_percentile": f.get("_imp_pct"),
                     "lead_cost_derived": f.get("_lead_cost"), "msg_cost_derived": f.get("_msg_cost"),
                     "cpc_derived": f.get("_cpc"), "ctr_derived": f.get("_ctr")},
            "reason": _build_reason(f),
            "limitations": ["Creator/Paid window UNALIGNED; 不解释为自然表现或因果关系",
                            "NO_PAID_ASSOCIATION_OBSERVED 仅=当前 Spotlight 事实未观察到（非 NEVER_PAID）"],
            "provenance": {"fact_version": FACT_VERSION, "rule_version": RULE_VERSION,
                           "source": "b007_note_dual_source_fact_v1 (V0.4)"},
        })

    (OUT / "B007_SAMPLE20_V1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "B007_SAMPLE20_V1.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "note_id", "primary_stratum", "title", "publish_time", "duration",
                    "creator_view", "creator_like", "creator_collect", "creator_comment", "creator_share",
                    "view_percentile", "paid_status", "observed_fee", "paid_impressions", "paid_clicks",
                    "paid_leads", "paid_msg", "fee_percentile", "imp_percentile", "lead_cost_derived",
                    "msg_cost_derived", "cpc_derived", "ctr_derived", "paid_months"])
        for s in manifest["samples"]:
            w.writerow([s["sample_id"], s["note_id"], s["primary_stratum"], s["title"], s["publish_time"],
                        s["duration"], s["creator"]["view"], s["creator"]["like"], s["creator"]["collect"],
                        s["creator"]["comment"], s["creator"]["share"], s["creator"]["view_percentile"],
                        s["paid"]["status"], s["paid"]["observed_fee"], s["paid"]["impressions"],
                        s["paid"]["clicks"], s["paid"]["leads"], s["paid"]["msg"], s["paid"]["fee_percentile"],
                        s["paid"]["imp_percentile"], s["paid"]["lead_cost_derived"], s["paid"]["msg_cost_derived"],
                        s["paid"]["cpc_derived"], s["paid"]["ctr_derived"], s["paid"]["months"]])

    # candidate audit（各 stratum 候选池 top，非全 2851）
    with open(OUT / "B007_SAMPLE_SELECTION_CANDIDATES_V1.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["stratum", "note_id", "title", "creator_view", "view_pct", "fee", "imp", "leads", "msg",
                    "fee_pct", "imp_pct", "lead_cost", "msg_cost", "cpc", "ctr", "paid_months"])
        for label, pool in [("A", a_pool[:15]), ("B", b_pool[:15]), ("D", d_pool[:15]), ("E", e_pool[:15]),
                            ("F", f_pool[:10])]:
            for f in pool:
                w.writerow([label, f["note_id"], (f["title"] or "")[:40], f["creator_view"], f.get("_view_pct"),
                            f["observed_paid_fee"], f["observed_paid_impression"], f["observed_paid_leads"],
                            f["observed_paid_message_consult"], f.get("_fee_pct"), f.get("_imp_pct"),
                            f.get("_lead_cost"), f.get("_msg_cost"), f.get("_cpc"), f.get("_ctr"),
                            f["paid_observed_month_count"]])
        for f in c_picked:
            w.writerow(["C", f["note_id"], (f["title"] or "")[:40], f["creator_view"], f.get("_view_pct"),
                        f["observed_paid_fee"], f["observed_paid_impression"], f["observed_paid_leads"],
                        f["observed_paid_message_consult"], f.get("_fee_pct"), f.get("_imp_pct"),
                        f.get("_lead_cost"), f.get("_msg_cost"), f.get("_cpc"), f.get("_ctr"),
                        f["paid_observed_month_count"]])

    (OUT / "B007_SAMPLE_SELECTION_STRATA_V1.json").write_text(
        json.dumps({"rule_version": RULE_VERSION, "strata": strata_report, "diversity": diversity},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"selected": len(samples), "strata": {k: v["actual"] for k, v in strata_report.items()},
                      "diversity": diversity, "dup_titles": dup_titles}, ensure_ascii=False, indent=2))
    return 0


def _build_reason(f):
    st = f.get("_stratum", "")
    parts = []
    if st.startswith("A"):
        parts.append(f"video + 未观察到投放关联；creator_view 分位 {f.get('_view_pct')}%（>=P75 高分组）")
    elif st.startswith("B"):
        parts.append(f"video + 未观察到投放关联；creator_view 分位 {f.get('_view_pct')}%（P25-P50 中低组，对照组）")
    elif st.startswith("C"):
        parts.append(f"有效投放量(fee>0&imp>0, >=P25)内；{f.get('_eff_dim')} 效率维度：lead_cost={f.get('_lead_cost')}"
                     f" msg_cost={f.get('_msg_cost')} cpc={f.get('_cpc')} ctr={f.get('_ctr')}")
    elif st.startswith("D"):
        parts.append(f"fee 分位 {f.get('_fee_pct')}% / imp 分位 {f.get('_imp_pct')}%（高投入）；平台 leads=0 & msg=0（WEAK_OUTCOME_OBSERVED）")
    elif st.startswith("E"):
        parts.append(f"跨源反差：{f.get('_contrast')}；WINDOW_ALIGNMENT=UNALIGNED，仅并排事实不比较因果")
    elif st.startswith("F"):
        parts.append("video + PAID_ASSOCIATED_NO_METRIC_RECORD（投放关联但 Apr-Aug 无 note 记录 → 数据/关联控制样本）")
    parts.append("未与其他已选样本形成明显 metadata 重复")
    return "；".join(parts)


if __name__ == "__main__":
    sys.exit(main())
