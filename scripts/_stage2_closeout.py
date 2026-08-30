# -*- coding: utf-8 -*-
"""Stage2 收口分析：C-R 全维度（基于 Fresh18 AI_LOCK vs Human Truth）。"""
import io, json, os, sqlite3, sys
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DATA = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA, "database", "materials.db")
lock = json.load(open(os.path.join(DATA, "BUSINESS_COGNITION_FRESH_V1_AI_LOCK.json"), encoding="utf-8"))
fresh = json.load(open(os.path.join(DATA, "BUSINESS_COGNITION_FRESH_VALIDATION_V1.json"), encoding="utf-8"))
fe_by = {s["segment_id"]: s.get("frozen_evidence", {}) for s in fresh["segments"]}
cls_by = {s["segment_id"]: s["evidence_structure_class"] for s in fresh["segments"]}

conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
human = {}
for r in conn.execute("SELECT * FROM stage2_business_cognition_calibration_v3"):
    human[r["segment_id"]] = dict(r)
conn.close()

# ============ C. Claim Status 分布 ============
st_cnt = Counter()
st_seg = Counter()
for r in lock["results"]:
    for c in r["business_claims"]:
        st_cnt[c["claim_status"]] += 1
        st_seg[c["claim_status"]] = st_seg[c["claim_status"]]
print("=== C. Claim Status 分布（claim 数）===")
for st in ("CONFIRMED", "SUPPORTED", "CANDIDATE", "WEAK", "UNKNOWN", "BLOCKED"):
    print(f"  {st}: {st_cnt.get(st, 0)} claim" + (" (NOT_OBSERVED_IN_FRESH18)" if st_cnt.get(st, 0) == 0 else ""))

# ============ E/F/G. 各状态 vs Human ============
print("\n=== E. CANDIDATE vs Human ===")
cand_h = Counter()
for r in lock["results"]:
    labels = json.loads(human[r["segment_id"]]["label_states"] or "{}")
    for c in r["business_claims"]:
        if c["claim_status"] == "CANDIDATE":
            cand_h[labels.get(c["claim_value"], "UNKNOWN")] += 1
print("  CANDIDATE Human 分布:", dict(cand_h))
cand_n = sum(v for k, v in cand_h.items() if k != "UNKNOWN")
cand_clear = cand_h.get("CLEARLY_SUPPORTED", 0)
cand_rel = (cand_h.get("CLEARLY_SUPPORTED", 0) + cand_h.get("POSSIBLE_BUT_INSUFFICIENT", 0)) / cand_n if cand_n else 0
print(f"  candidate_clear_rate={cand_clear/9:.2f} ({cand_clear}/9) | candidate_relevance_rate={cand_rel:.2f}")

print("\n=== F. WEAK ===")
weak_h = Counter()
for r in lock["results"]:
    labels = json.loads(human[r["segment_id"]]["label_states"] or "{}")
    for c in r["business_claims"]:
        if c["claim_status"] == "WEAK":
            weak_h[labels.get(c["claim_value"], "UNKNOWN")] += 1
print("  WEAK Human 分布:", dict(weak_h) if weak_h else "WEAK_NOT_OBSERVED_IN_FRESH18")

print("\n=== G. UNKNOWN 检查（unknown_miss_rate）===")
unknown_total = 0
unknown_with_clearly = 0
for r in lock["results"]:
    labels = json.loads(human[r["segment_id"]]["label_states"] or "{}")
    for c in r["business_claims"]:
        if c["claim_status"] == "UNKNOWN":
            unknown_total += 1
            if labels.get(c["claim_value"]) == "CLEARLY_SUPPORTED":
                unknown_with_clearly += 1
print(f"  AI UNKNOWN total={unknown_total} | 其中 Human 判 CLEARLY={unknown_with_clearly}")
print(f"  unknown_miss_rate={unknown_with_clearly/unknown_total:.3f}" if unknown_total else "  N/A")

# ============ H. Confidence Separation ============
print("\n=== H. Confidence Separation ===")
sup_h = Counter()
for r in lock["results"]:
    labels = json.loads(human[r["segment_id"]]["label_states"] or "{}")
    for c in r["business_claims"]:
        if c["claim_status"] == "SUPPORTED":
            sup_h[labels.get(c["claim_value"], "UNKNOWN")] += 1
sup_clear = sup_h.get("CLEARLY_SUPPORTED", 0) / sum(sup_h.values()) if sup_h else 0
cand_clear_rate = cand_h.get("CLEARLY_SUPPORTED", 0) / 9 if 9 else 0
cand_rel_rate = cand_rel
print(f"  SUPPORTED Human CLEARLY rate = {sup_clear:.3f} ({sup_h.get('CLEARLY_SUPPORTED',0)}/{sum(sup_h.values())})")
print(f"  CANDIDATE Human CLEARLY rate = {cand_clear_rate:.3f} | CLEARLY+POSSIBLE rate = {cand_rel_rate:.3f}")
print(f"  UNKNOWN Human CLEARLY miss rate = {unknown_with_clearly/unknown_total:.3f}" if unknown_total else "")

# ============ I. Storage 专项 ============
print("\n=== I. Storage 专项 ===")
for lab in ("STORAGE", "STORAGE_EFFICIENCY"):
    ai_st = Counter()
    hum_st = Counter()
    for r in lock["results"]:
        labels = json.loads(human[r["segment_id"]]["label_states"] or "{}")
        fe = fe_by.get(r["segment_id"], {})
        comp = fe.get("component", [])
        for c in r["business_claims"]:
            if c["claim_value"] == lab:
                ai_st[c["claim_status"]] += 1
                hum_st[labels.get(lab, "UNKNOWN")] += 1
    print(f"  {lab}: AI={dict(ai_st)} | Human={dict(hum_st)}")

# component-only STORAGE 是否仍 SUPPORTED
print("\n  component-only STORAGE 检查:")
for r in lock["results"]:
    fe = fe_by.get(r["segment_id"], {})
    comp = fe.get("component", [])
    func = fe.get("function", [])
    if "DRAWER" in comp or "CABINET_DOOR" in comp:
        for c in r["business_claims"]:
            if c["claim_value"] == "STORAGE" and c["claim_status"] == "SUPPORTED":
                print(f"    {r['segment_id'][:12]} comp={comp} func={func} -> STORAGE SUPPORTED")

# ============ J/K. 非 Storage ============
print("\n=== J/K. 非 Storage 专项 ===")
non_storage = {}
for lab in ("CHARGING_POWER", "POWER_CONVENIENCE", "DINING", "DINING_CONVENIENCE",
            "OFFICE", "WORK_FROM_HOME", "GUEST_CAPACITY", "FLEXIBLE_CAPACITY"):
    ai_st = Counter()
    hum_st = Counter()
    for r in lock["results"]:
        labels = json.loads(human[r["segment_id"]]["label_states"] or "{}")
        for c in r["business_claims"]:
            if c["claim_value"] == lab:
                ai_st[c["claim_status"]] += 1
                hum_st[labels.get(lab, "UNKNOWN")] += 1
    n = sum(ai_st.values())
    tag = "SMALL_N" if 0 < n < 3 else ("UNTESTED" if n == 0 else "")
    print(f"  {lab}: AI={dict(ai_st)} Human={dict(hum_st)} {tag}")

# ============ L. Negative Rules ============
print("\n=== L. Negative Rules ===")
bad = []
for r in lock["results"]:
    for c in r["business_claims"]:
        if c["claim_value"] in ("OPERATE_SOCKET", "REAL_CUSTOMER_CASE", "FAMILY_GATHERING"):
            bad.append((r["segment_id"][:12], c["claim_value"]))
print(f"  hard_negative_rule_violation_count = {len(bad)}", bad[:5] if bad else "")

# ============ M. Conflict ============
print("\n=== M. Conflict Resolver V2 ===")
conf = {"both_yes": 0, "ai_only": 0, "human_only": 0, "both_no": 0, "human_unknown": 0}
hypo_conf = []
for r in lock["results"]:
    ai_c = r["conflicts"]["conflict_count"] > 0
    hum = human[r["segment_id"]]["conflict_observed"]
    hum_c = hum == "YES"
    if hum == "UNKNOWN":
        conf["human_unknown"] += 1
    elif ai_c and hum_c:
        conf["both_yes"] += 1
    elif ai_c and not hum_c:
        conf["ai_only"] += 1
    elif not ai_c and hum_c:
        conf["human_only"] += 1
    else:
        conf["both_no"] += 1
    # hypothetical 误报检查
    asr = str(fe_by.get(r["segment_id"], {}).get("asr_text", ""))
    if any(w in asr for w in ("如果", "假如", "要是", "比如", "假设", "有宝宝")):
        types = [c["type"] for c in r["conflicts"]["conflicts"]]
        if "CONFLICTING_EVIDENCE" in types:
            hypo_conf.append(r["segment_id"][:12])
print("  conflict 对照:", conf)
print("  hypothetical 误报 CONFLICTING:", hypo_conf if hypo_conf else "无（0）")

# ============ N. Coverage ============
print("\n=== N. Coverage ===")
total = sum(st_cnt.values())
print(f"  SUPPORTED_COVERAGE={st_cnt.get('SUPPORTED',0)/total:.3f} | "
      f"ACTIONABLE={(st_cnt.get('SUPPORTED',0)+st_cnt.get('CANDIDATE',0))/total:.3f} | "
      f"ABSTENTION={(st_cnt.get('WEAK',0)+st_cnt.get('UNKNOWN',0))/total:.3f}")

# ============ P. 六类 ============
print("\n=== P. 六类 Challenge raw ===")
for cls in ("STRONG_SINGLE_EVIDENCE", "MULTI_SOURCE_AGREEMENT", "CONFLICTING_EVIDENCE",
            "WEAK_EVIDENCE", "NEGATIVE_RULE_TRIGGER", "AMBIGUOUS_MULTI_PURPOSE"):
    sids = [s for s in cls_by if cls_by[s] == cls]
    ai = Counter()
    hum = Counter()
    for sid in sids:
        r = next(x for x in lock["results"] if x["segment_id"] == sid)
        labels = json.loads(human[sid]["label_states"] or "{}")
        for c in r["business_claims"]:
            ai[c["claim_status"]] += 1
            hum[labels.get(c["claim_value"], "UNKNOWN")] += 1
    print(f"  {cls} (n={len(sids)}): AI={dict(ai)} | Human={dict(hum)}")

# ============ Q. 与 V3 比较 ============
print("\n=== Q. 与 V3 趋势 ===")
print("  V3: precision_clear=0.853 hard_false=0.118 insufficiency=0.147")
print(f"  Fresh18: precision_clear=0.765 hard_false=0.118 insufficiency=0.235")
print("  → 需综合：precision 略降（Storage-heavy 更严），hard_false 持平，insufficiency 升")
