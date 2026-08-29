# -*- coding: utf-8 -*-
"""Stage 2 — Human24 Adjudication V2b vs V1 比较（Truth Reliability Gate 判定，简化版）。

只比较 Human V1（stage2_business_cognition_review_v1）与
Human V2b（stage2_business_cognition_adjudication_v2b）的 12 条重合段。
不修改 AI。

比较口径（Simplification Gate §9）：
  - V1 user_needs  vs V2 CLEARLY_SUPPORTED needs
  - V1 business_values vs V2 CLEARLY_SUPPORTED values
  - V1 overall_unknown vs V2 evidence sufficiency
  - V1 conflict vs V2 conflict
额外报告 V2 POSSIBLE_BUT_INSUFFICIENT（解释 V1 为什么大量多选）。

判定（§10：不只 0.85 阈值）：
  exact-set agreement / Jaccard / label additions / label removals /
  CLEARLY↔POSSIBLE 迁移数 / HIGH-confidence review agreement / LOW-confidence 数
  综合给出 ADJUDICATED_HUMAN_TRUTH 或 UNRELIABLE_FOR_CALIBRATION。
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
V2_MANIFEST = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_ADJUDICATION_V2.json")
OUT = os.path.join(DATA_ROOT, "HUMAN24_V1_VS_V2_COMPARISON.json")


def _jlist(v):
    if isinstance(v, list):
        return v
    try:
        x = json.loads(v) if v else []
        return x if isinstance(x, list) else []
    except Exception:
        return []


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0


def main():
    man = json.load(open(V2_MANIFEST, encoding="utf-8"))
    v2_ids = [s["segment_id"] for s in man["segments"]]
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    v1 = {}
    for r in conn.execute("SELECT * FROM stage2_business_cognition_review_v1"):
        v1[r["segment_id"]] = dict(r)
    v2 = {}
    try:
        for r in conn.execute("SELECT * FROM stage2_business_cognition_adjudication_v2b"):
            v2[r["segment_id"]] = dict(r)
    except sqlite3.OperationalError:
        pass
    conn.close()

    done = [s for s in v2_ids if s in v2]
    print(f"V2b 已审 {len(done)}/{len(v2_ids)}")
    if not done:
        print("尚未有 V2b 评审结果。")
        return

    # ---------------- 逐条比较 ----------------
    per_seg = []
    label_add = []   # V1 无、V2 明确支持有
    label_rm = []    # V1 有、V2 明确支持无
    possible_moved = []  # V1 有、V2 变为 POSSIBLE（关键：解释 V1 多选）
    hi_agree = hi_total = 0
    conf_stats = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    hi_agree_high_conf = hi_total_high_conf = 0
    exact_sets = 0

    for sid in done:
        h1, h2 = v1[sid], v2[sid]
        row = {"segment_id": sid}
        for fld in ("user_needs", "business_values"):
            s1 = set(_jlist(h1.get(fld)))
            v2k = "clearly_supported_needs" if fld == "user_needs" else "clearly_supported_values"
            pk = "possible_needs" if fld == "user_needs" else "possible_values"
            s2c = set(_jlist(h2.get(v2k)))
            s2p = set(_jlist(h2.get(pk)))
            row[f"{fld}_v1"] = sorted(s1)
            row[f"{fld}_v2_clearly"] = sorted(s2c)
            row[f"{fld}_v2_possible"] = sorted(s2p)
            # 高影响一致率（逐 label）：V1 主张 vs V2 明确支持
            for x in (s1 | s2c):
                hi_total += 1
                if x in s1 and x in s2c:
                    hi_agree += 1
            # exact-set（每字段）
            row[f"{fld}_exact"] = (s1 == s2c)
            # label add / rm / possible-moved
            for x in (s2c - s1):
                label_add.append({"segment_id": sid, "field": fld, "label": x})
            for x in (s1 - s2c):
                label_rm.append({"segment_id": sid, "field": fld, "label": x,
                                 "moved_to_possible": x in s2p})
                if x in s2p:
                    possible_moved.append({"segment_id": sid, "field": fld, "label": x})
        # 字段级 unknown
        row["needs_field_unknown_v2"] = bool(h2.get("needs_field_unknown"))
        row["values_field_unknown_v2"] = bool(h2.get("values_field_unknown"))
        row["evidence_sufficiency_v2"] = h2.get("evidence_sufficiency", "")
        row["overall_unknown_v1"] = h1.get("overall_unknown", "")
        row["conflict_v1"] = h1.get("conflict_observed", "")
        row["conflict_v2"] = h2.get("conflict_observed", "")
        row["review_confidence"] = h2.get("review_confidence", "")
        row["review_duration_seconds"] = h2.get("review_duration_seconds")
        row["review_status_v2"] = h2.get("review_status", "")

        rc = (h2.get("review_confidence") or "").upper()
        conf_stats[rc] = conf_stats.get(rc, 0) + 1
        # 高置信子集的一致率
        if rc == "HIGH":
            for fld in ("user_needs", "business_values"):
                s1 = set(_jlist(h1.get(fld)))
                v2k = "clearly_supported_needs" if fld == "user_needs" else "clearly_supported_values"
                s2c = set(_jlist(h2.get(v2k)))
                for x in (s1 | s2c):
                    hi_total_high_conf += 1
                    if x in s1 and x in s2c:
                        hi_agree_high_conf += 1

        exact_sets += int(row["user_needs_exact"] and row["business_values_exact"])
        per_seg.append(row)

    hi_rate = hi_agree / hi_total if hi_total else 1.0
    exact_rate = exact_sets / len(done)
    hi_high_conf = hi_agree_high_conf / hi_total_high_conf if hi_total_high_conf else None

    # 判定（§10：多指标综合）
    criteria = {
        "high_impact_agreement": round(hi_rate, 3),
        "exact_set_segments": f"{exact_sets}/{len(done)} ({round(exact_rate, 3)})",
        "label_additions": len(label_add),
        "label_removals": len(label_rm),
        "v1_to_possible_migrations": len(possible_moved),
        "high_conf_agreement": round(hi_high_conf, 3) if hi_high_conf is not None else None,
        "low_conf_reviews": conf_stats.get("LOW", 0),
    }
    # 综合判定：高影响一致率为主 + 高置信一致率佐证 + 迁移数提示
    verdict = "ADJUDICATED_HUMAN_TRUTH"
    notes = []
    if hi_rate < 0.70:
        verdict = "UNRELIABLE_FOR_CALIBRATION"
        notes.append(f"高影响一致率 {hi_rate:.3f} < 0.70")
    elif hi_rate < 0.85:
        verdict = "PARTIALLY_RELIABLE"
        notes.append(f"高影响一致率 {hi_rate:.3f} 介于 0.70-0.85，需结合迁移数判断")
    if len(possible_moved) / max(1, len(label_rm)) > 0.5:
        notes.append(f"V1 移除标签中 {len(possible_moved)} 条迁往 POSSIBLE —— 证实 V1 多选主要来自'关联性'而非'证据性'")
    if conf_stats.get("LOW", 0) >= len(done) * 0.4:
        notes.append(f"LOW 把握度占 {conf_stats.get('LOW')}/{len(done)} —— 复核置信度偏低，Truth 存疑")

    print(f"\n===== V1 vs V2b（{len(done)} 条）=====")
    print(f"高影响一致率（needs+values 逐 label）= {hi_rate:.3f} ({hi_agree}/{hi_total})")
    print(f"exact-set 段 = {exact_sets}/{len(done)}")
    print(f"label additions = {len(label_add)} | removals = {len(label_rm)} | V1→POSSIBLE 迁移 = {len(possible_moved)}")
    print(f"review_confidence 分布 = {conf_stats}")
    if hi_high_conf is not None:
        print(f"HIGH-confidence 子集一致率 = {hi_high_conf:.3f}")
    print("判定:", verdict)
    for n in notes:
        print("  ·", n)

    out = {
        "manifest": "HUMAN24_V1_VS_V2_COMPARISON",
        "version": "v2b_simplified",
        "reviewed": len(done), "total": len(v2_ids),
        "high_impact_agreement_rate": round(hi_rate, 4),
        "exact_set_segments": exact_sets,
        "label_additions": label_add,
        "label_removals": label_rm,
        "v1_to_possible_migrations": possible_moved,
        "confidence_distribution": conf_stats,
        "high_confidence_agreement_rate": round(hi_high_conf, 4) if hi_high_conf is not None else None,
        "criteria": criteria,
        "verdict": verdict,
        "verdict_notes": notes,
        "per_segment": per_seg,
        "guard": "仅比较 Human V1 vs V2b；不修改 AI；POSSIBLE 不计 SUPPORTED Truth",
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
