# -*- coding: utf-8 -*-
"""Stage 2 — Human24 打分（AI Business Cognition vs Human Business Review）。

输入：
  BUSINESS_COGNITION_STAGE2_AI_LOCK.json        （AI 60/60，冻结）
  BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json（Human24 manifest）
  stage2_business_cognition_review_v1 表         （人工评审结果）

方法：
  24 条人审结果与 AI claims 对比：
  - precision：AI 主张（need/value）中被人类判定 SUPPORTED 的比例
  - recall：人类判定 SUPPORTED 的主张中被 AI 主张的比例
  - UNSUPPORTED_CLAIM_RATE：AI 主张中人类明确判 NOT_SUPPORTED 的比例（最重要指标）
  - 按六类分桶报告（4 条/类）
  - 冲突观察一致性：AI conflicts vs 人类 conflict_observed

输出：BUSINESS_COGNITION_STAGE2_SCORE_V1.json
"""
import io
import json
import os
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
AI_LOCK = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_AI_LOCK.json")
HUMAN_MANIFEST = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_HUMAN_REVIEW_V1.json")
OUT = os.path.join(DATA_ROOT, "BUSINESS_COGNITION_STAGE2_SCORE_V1.json")


def main():
    ai = json.load(open(AI_LOCK, encoding="utf-8"))
    man = json.load(open(HUMAN_MANIFEST, encoding="utf-8"))
    ai_by_sid = {r["segment_id"]: r for r in ai["results"]}
    human_ids = [s["segment_id"] for s in man["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = {}
    try:
        for r in conn.execute(f"SELECT * FROM stage2_business_cognition_review_v1 WHERE segment_id IN "
                              f"({','.join('?' * len(human_ids))})", human_ids):
            rows[r["segment_id"]] = dict(r)
    except sqlite3.OperationalError:
        pass  # 表尚未创建（人审未开始）
    conn.close()
    print(f"Human24: {len(human_ids)} 条 | 已评审 {len(rows)} 条")
    if not rows:
        print("尚未有人工评审结果，无法打分。")
        return

    def human_verdicts(sid):
        """返回 {need: SUPPORTED/NOT_SUPPORTED/UNSURE} 全集（未勾选=NOT_SUPPORTED 视为未主张）。"""
        r = rows.get(sid)
        if not r:
            return {}
        judged_n = set(json.loads(r.get("judged_needs") or "[]"))
        judged_v = set(json.loads(r.get("judged_values") or "[]"))
        out = {}
        for n in man_needs():
            out[("need", n)] = "SUPPORTED" if n in judged_n else "NOT_SUPPORTED"
        for v in man_values():
            out[("value", v)] = "SUPPORTED" if v in judged_v else "NOT_SUPPORTED"
        return out

    # 候选全集（从 manifest 第一段读）
    _fe = man["segments"][0]
    man_needs = lambda: _fe["need_candidates"]
    man_values = lambda: _fe["value_candidates"]

    # 逐条对比
    per_seg = []
    tp = fp = tn = fn = 0  # need+value 合并统计
    unsupported = []  # AI 主张但人类 NOT_SUPPORTED
    by_class = {c: {"tp": 0, "fp": 0, "fn": 0, "unsupported": 0} for c in
                ("STRONG_SINGLE_EVIDENCE", "MULTI_SOURCE_AGREEMENT", "CONFLICTING_EVIDENCE",
                 "WEAK_EVIDENCE", "NEGATIVE_RULE_TRIGGER", "AMBIGUOUS_MULTI_PURPOSE")}
    conflict_cmp = {"agree": 0, "ai_only": 0, "human_only": 0, "both_none": 0}

    for s in man["segments"]:
        sid = s["segment_id"]
        if sid not in rows:
            continue
        h = human_verdicts(sid)
        a = ai_by_sid[sid]
        ai_needs = set(a["user_needs"])
        ai_vals = set(a["business_values"])
        cls = s["challenge_class"]
        row_stat = {"segment_id": sid, "class": cls,
                    "ai_needs": sorted(ai_needs), "ai_values": sorted(ai_vals)}
        for key, verdict in h.items():
            kind, name = key
            ai_claims = ai_needs if kind == "need" else ai_vals
            pred = name in ai_claims
            if verdict == "SUPPORTED":
                if pred:
                    tp += 1; by_class[cls]["tp"] += 1
                else:
                    fn += 1; by_class[cls]["fn"] += 1
            else:  # NOT_SUPPORTED
                if pred:
                    fp += 1; by_class[cls]["fp"] += 1
                    unsupported.append({"segment_id": sid, "class": cls, "kind": kind, "name": name})
                else:
                    tn += 1
        # 冲突观察一致性
        ai_conf = a["conflicts"]["conflict_count"] > 0
        hum_conf = rows[sid].get("conflict_observed") in ("SCENE_ASR_CONFLICT", "MATERIAL_WEAK_CONFLICT")
        if ai_conf and hum_conf:
            conflict_cmp["agree"] += 1
        elif ai_conf and not hum_conf:
            conflict_cmp["ai_only"] += 1
        elif not ai_conf and hum_conf:
            conflict_cmp["human_only"] += 1
        else:
            conflict_cmp["both_none"] += 1
        row_stat["human_conflict_observed"] = rows[sid].get("conflict_observed")
        row_stat["ai_conflict_count"] = a["conflicts"]["conflict_count"]
        per_seg.append(row_stat)

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    n_ai_claims = tp + fp
    unsupported_rate = fp / n_ai_claims if n_ai_claims else 0.0

    print(f"\n===== Human24 打分（{len(per_seg)} 条已审）=====")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"precision={prec:.3f} recall={rec:.3f} F1={f1:.3f}")
    print(f"UNSUPPORTED_CLAIM_RATE={unsupported_rate:.3f} ({fp}/{n_ai_claims})")
    print("冲突观察:", conflict_cmp)
    print("\n按类别：")
    for c, st in by_class.items():
        p = st["tp"] / (st["tp"] + st["fp"]) if (st["tp"] + st["fp"]) else 0.0
        print(f"  {c}: tp={st['tp']} fp={st['fp']} fn={st['fn']} precision={p:.3f}")

    out = {
        "manifest": "BUSINESS_COGNITION_STAGE2_SCORE_V1",
        "method": "AI_LOCK claims vs Human24 判定（need+value 合并）; UNSUPPORTED=AI主张但人类NOT_SUPPORTED",
        "reviewed": len(per_seg), "total": len(human_ids),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "unsupported_claim_rate": round(unsupported_rate, 4),
        "unsupported_claims": unsupported,
        "conflict_agreement": conflict_cmp,
        "by_class": {c: {**st, "precision": round(st["tp"] / (st["tp"] + st["fp"]), 4)
                         if (st["tp"] + st["fp"]) else 0.0} for c, st in by_class.items()},
        "per_segment": per_seg,
        "guard": "Human24 仅评审打分；不得在同 24 上重调规则后声称新准确率；"
                 "同 24 将成为 KNOWN_DEV_BENCHMARK",
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
