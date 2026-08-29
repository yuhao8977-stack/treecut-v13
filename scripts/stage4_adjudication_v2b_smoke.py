# -*- coding: utf-8 -*-
"""Adjudication V2b Smoke Test（Gate §12）：
  CLEARLY_SUPPORTED={STORAGE}, POSSIBLE={CUSTOMIZATION}
  → Human supported truth = {STORAGE}
  → AI SUPPORTED STORAGE → TP；CUSTOMIZATION 不得作为 SUPPORTED TP
完成后删除 mock。
"""
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
MOCK = "MOCK-ADJUDICATION-V2B-0004"

sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")
from treecut.services.annotation_governance import AnnotationService  # noqa: E402


def main():
    svc = AnnotationService(DB)
    ok = True

    # 保存 V2b：明确支持 STORAGE，可能相关 CUSTOMIZATION
    svc.save_business_cognition_adjudication_v2b(
        MOCK, clearly_needs=["STORAGE"], possible_needs=["CUSTOMIZATION"],
        clearly_values=[], possible_values=[],
        needs_field_unknown=False, values_field_unknown=False,
        evidence_sufficiency="SUFFICIENT", conflict_observed="NO",
        review_confidence="HIGH", review_duration_seconds=30.0,
        review_status="REVIEWED", comment="smoke", operator="SMOKE")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM stage2_business_cognition_adjudication_v2b "
                       "WHERE segment_id=?", (MOCK,)).fetchone()
    conn.close()
    assert row is not None, "mock 未保存"
    import json as _json
    clearly = set(_json.loads(row["clearly_supported_needs"] or "[]"))
    possible = set(_json.loads(row["possible_needs"] or "[]"))

    # Gate §12 语义验证
    human_supported_truth = clearly  # 只有 CLEARLY 计 Human positive
    print(f"[mock] clearly={sorted(clearly)} possible={sorted(possible)}")
    print(f"[mock] human_supported_truth={sorted(human_supported_truth)}")
    ok &= human_supported_truth == {"STORAGE"}
    ok &= possible == {"CUSTOMIZATION"}

    # AI SUPPORTED: STORAGE → TP；CUSTOMIZATION → 不得 TP
    ai_supported = {"STORAGE", "CUSTOMIZATION"}  # 模拟 AI 两标签都 SUPPORTED
    tp = len(ai_supported & human_supported_truth)
    c_tp = "CUSTOMIZATION" in (ai_supported & human_supported_truth)
    print(f"[mock] TP={tp}（STORAGE）| CUSTOMIZATION 计入 TP? {c_tp} → 期望 False")
    ok &= (tp == 1 and not c_tp)

    # 清理
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM stage2_business_cognition_adjudication_v2b WHERE segment_id=?", (MOCK,))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM stage2_business_cognition_adjudication_v2b").fetchone()[0]
    conn.close()
    print(f"[mock] 已删除 | v2b 表剩余 {n} 行（应为 0）")
    ok &= (n == 0)

    print("\n===== V2b SMOKE:", "PASS ✅" if ok else "FAIL ❌", "=====")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
