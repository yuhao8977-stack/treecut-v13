# -*- coding: utf-8 -*-
"""V0.4 Preflight — 月度 Paid Note Snapshot 的 Derived Rate 规范化。

问题：现有 5193 条月度快照的率指标（ctr/acp/cpm/...）取的是"末日值"，不是月度 Truth。
修复：从聚合后的基础量重新推导（不重抓 225 页 Raw）：
  CTR_DERIVED  = SUM(click)  / SUM(impression)
  CPC_DERIVED  = SUM(fee)    / SUM(click)
  CPM_DERIVED  = SUM(fee)    / SUM(impression) * 1000
  LEAD_COST_DERIVED = SUM(fee) / SUM(msgLeadsNum)
  MSG_CONSULT_COST_DERIVED = SUM(fee) / SUM(messageConsult)
分母为 0 → NULL（禁止 Infinity/0 伪值）。
每日 Source 原始率保留在 Raw（不删）；derived 标记 DERIVED_FROM_AGGREGATED_BASE_METRICS。
Precheck：5193 数量不变；fee/count 合计与修正前一致；只改 rate 推导。
输出：B007_V04_PAID_RATE_NORMALIZATION_CHECK_V1.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1\database\materials.db"
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")


def main() -> int:
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT snapshot_id, note_id, window_type, fee, impressions, clicks, ctr, acp, cpm,"
        " message_consult, initiative_message, msg_leads_num, message_consult_cpl,"
        " initiative_message_cpl, msg_leads_cost, metric_json"
        " FROM spotlight_note_paid_snapshot_v1 WHERE window_type LIKE 'M2026-%'").fetchall()
    n = len(rows)
    print(f"month snapshots: {n}")

    # 修正前合计
    before = conn.execute(
        "SELECT SUM(COALESCE(fee,0)) fee, SUM(COALESCE(impressions,0)) imp,"
        " SUM(COALESCE(clicks,0)) clk, SUM(COALESCE(msg_leads_num,0)) leads,"
        " SUM(COALESCE(message_consult,0)) msg FROM spotlight_note_paid_snapshot_v1"
        " WHERE window_type LIKE 'M2026-%'").fetchone()

    updated = 0
    null_denom = 0
    for r in rows:
        fee = r["fee"]
        imp = r["impressions"]
        clk = r["clicks"]
        leads = r["msg_leads_num"]
        msg = r["message_consult"]
        init_msg = r["initiative_message"]
        # 推导率（分母 0 → NULL）
        def rate(num_v, den_v):
            if num_v is None or den_v is None or den_v == 0:
                return None
            return round(num_v / den_v, 6)
        ctr_d = rate(clk, imp)
        cpc_d = rate(fee, clk)
        cpm_d = rate(fee * 1000, imp) if fee is not None and imp not in (None, 0) else None
        lead_cost_d = rate(fee, leads)
        msg_cost_d = rate(fee, msg)
        init_msg_cost_d = rate(fee, init_msg)
        if ctr_d is None or cpc_d is None or cpm_d is None or lead_cost_d is None:
            null_denom += 1
        # 更新率字段 + 标记
        mj = {}
        try:
            mj = json.loads(r["metric_json"] or "{}")
        except Exception:
            mj = {}
        mj["derived_rates"] = {
            "ctr": ctr_d, "cpc_acp": cpc_d, "cpm": cpm_d,
            "msg_leads_cost": lead_cost_d, "message_consult_cost": msg_cost_d,
            "initiative_message_cost": init_msg_cost_d,
            "label": "DERIVED_FROM_AGGREGATED_BASE_METRICS",
        }
        conn.execute(
            "UPDATE spotlight_note_paid_snapshot_v1 SET ctr=?, acp=?, cpm=?,"
            " message_consult_cpl=?, initiative_message_cpl=?, msg_leads_cost=?, metric_json=?"
            " WHERE snapshot_id=?",
            (ctr_d, cpc_d, cpm_d, msg_cost_d, init_msg_cost_d, lead_cost_d,
             json.dumps(mj, ensure_ascii=False), r["snapshot_id"]))
        updated += 1
    conn.commit()

    # 修正后合计（应一致）
    after = conn.execute(
        "SELECT SUM(COALESCE(fee,0)) fee, SUM(COALESCE(impressions,0)) imp,"
        " SUM(COALESCE(clicks,0)) clk, SUM(COALESCE(msg_leads_num,0)) leads,"
        " SUM(COALESCE(message_consult,0)) msg FROM spotlight_note_paid_snapshot_v1"
        " WHERE window_type LIKE 'M2026-%'").fetchone()
    n_after = conn.execute(
        "SELECT COUNT(*) FROM spotlight_note_paid_snapshot_v1 WHERE window_type LIKE 'M2026-%'").fetchone()[0]
    conn.close()

    # 一致性（容差）
    def close(a, b, tol=0.01):
        return abs((a or 0) - (b or 0)) <= tol

    consistent = (n == n_after and
                  close(before["fee"], after["fee"]) and close(before["imp"], after["imp"]) and
                  close(before["clk"], after["clk"]) and close(before["leads"], after["leads"]) and
                  close(before["msg"], after["msg"]))

    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_count": n,
        "count_unchanged": n == n_after,
        "before_totals": dict(before),
        "after_totals": dict(after),
        "base_totals_unchanged": consistent,
        "rate_derivation": {
            "ctr": "SUM(click)/SUM(impression)",
            "cpc_acp": "SUM(fee)/SUM(click)",
            "cpm": "SUM(fee)/SUM(impression)*1000",
            "msg_leads_cost": "SUM(fee)/SUM(msgLeadsNum)",
            "message_consult_cost": "SUM(fee)/SUM(messageConsult)",
            "denominator_zero": "NULL (never Infinity/0)",
        },
        "derived_flag": "DERIVED_FROM_AGGREGATED_BASE_METRICS",
        "source_preservation": "每日 source 率保留在 Raw/Daily（未删除）",
        "updated_rows": updated,
        "rows_with_null_denominator_rate": null_denom,
        "no_recapture": True,
        "pass": consistent,
    }
    out = OUT / "B007_V04_PAID_RATE_NORMALIZATION_CHECK_V1.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if consistent else 1


if __name__ == "__main__":
    sys.exit(main())
