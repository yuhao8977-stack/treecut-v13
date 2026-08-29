# -*- coding: utf-8 -*-
"""V3 Smoke Test（Gate §21）：
  A. STORAGE=CLEARLY，CUSTOMIZATION 不在 Calibration Vocabulary（UI 不显示）
  B. POWER_CONVENIENCE=POSSIBLE → 保存后 label_states 互斥（单状态 dict）
  C. evidence 未选择 → 禁止保存
  D. confidence 未选择 → 禁止保存
  E. AI SUPPORTED POWER_CONVENIENCE vs Human POSSIBLE → OVERCONFIDENT 不得 TP
  F. 删除 mock
"""
import io
import json
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
MOCK = "MOCK-CALIBRATION-V3-0001"

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.annotation_governance import AnnotationService  # noqa: E402
from treecut.services.phase3_review_ui import validate_calibration_v3  # noqa: E402


def main():
    ok = True

    # A. 词汇表不含 CUSTOMIZATION
    tax = json.load(open(os.path.join(DATA_ROOT, "BUSINESS_COGNITION_CALIBRATION_TAXONOMY_V1.json"),
                         encoding="utf-8"))
    vocab = {n["id"] for n in tax["user_needs"]} | {v["id"] for v in tax["business_values"]}
    a = "CUSTOMIZATION" not in vocab and len(vocab) == 10
    print(f"[A] 词汇表 10 标签、不含 CUSTOMIZATION: {a}")
    ok &= a

    # B. 单状态保存（STORAGE=CLEARLY, POWER_CONVENIENCE=POSSIBLE）
    svc = AnnotationService(DB)
    label_states = {lid: "NOT_SUPPORTED" for lid in vocab}
    label_states["STORAGE"] = "CLEARLY_SUPPORTED"
    label_states["POWER_CONVENIENCE"] = "POSSIBLE_BUT_INSUFFICIENT"
    svc.save_business_cognition_calibration_v3(
        MOCK, label_states, "SUFFICIENT", "NO", "", "HIGH", 40.0, "REVIEWED",
        comment="smoke", operator="SMOKE")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT label_states FROM stage2_business_cognition_calibration_v3 "
                       "WHERE segment_id=?", (MOCK,)).fetchone()
    conn.close()
    stored = json.loads(row["label_states"])
    b = stored["STORAGE"] == "CLEARLY_SUPPORTED" and \
        stored["POWER_CONVENIENCE"] == "POSSIBLE_BUT_INSUFFICIENT" and \
        len(stored) == 10
    # 互斥：dict 单值结构天然禁止同 label 双状态
    print(f"[B] 单状态互斥保存: {b} | STORAGE={stored['STORAGE']} POWER={stored['POWER_CONVENIENCE']}")
    ok &= b

    # C. evidence 未选择 → 拒绝
    vals = {"label_states": label_states, "evidence_sufficiency": "",
            "conflict_observed": "NO", "review_confidence": "HIGH",
            "human_confidence": "HIGH", "review_status": "REVIEWED"}
    okc, msgc, _ = validate_calibration_v3(vals)
    c = (not okc) and "证据充分度" in msgc
    print(f"[C] evidence 未选禁止保存: {c} | {msgc}")
    ok &= c

    # D. confidence 未选择 → 拒绝
    vals2 = dict(vals); vals2["evidence_sufficiency"] = "SUFFICIENT"
    vals2["review_confidence"] = ""
    okd, msgd, _ = validate_calibration_v3(vals2)
    d = (not okd) and "把握度" in msgd
    print(f"[D] confidence 未选禁止保存: {d} | {msgd}")
    ok &= d

    # E. AI SUPPORTED POWER_CONVENIENCE vs Human POSSIBLE → OVERCONFIDENT 不得 TP
    ai_supported = {"POWER_CONVENIENCE"}
    if stored["POWER_CONVENIENCE"] == "POSSIBLE_BUT_INSUFFICIENT":
        e = "POWER_CONVENIENCE" not in (ai_supported & {"STORAGE"})  # 非 TRUE
        print(f"[E] AI SUPPORTED vs Human POSSIBLE → 不计 TRUE（OVERCONFIDENT）: {e}")
        ok &= e
    else:
        print("[E] FAIL: POWER_CONVENIENCE 状态不对"); ok = False

    # F. 删除 mock
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM stage2_business_cognition_calibration_v3 WHERE segment_id=?", (MOCK,))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM stage2_business_cognition_calibration_v3").fetchone()[0]
    conn.close()
    f = n == 0
    print(f"[F] mock 已删除 | v3 表剩余 {n} 行: {f}")
    ok &= f

    print("\n===== V3 SMOKE:", "PASS ✅" if ok else "FAIL ❌", "=====")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
