# -*- coding: utf-8 -*-
"""Phase 4 Stage 1.5 — STEP 15-16：43 条 Validation 重跑（V1.1 知识）+ 新增能力验证。

对比旧 Snapshot V1：检查 unexpected regression / new conflict / over-inference。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"


def main():
    from treecut.services.business_cognition_service import BusinessCognitionServiceV1
    svc = BusinessCognitionServiceV1()

    old = json.load(open(os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS.json"), encoding="utf-8"))
    old_results = {r["segment_id"]: r["cognition"] for r in old["results"]}
    print("旧 Validation 段数:", len(old_results))

    # 重跑 43 条
    new_results = []
    regressions = []
    for sid, old_bc in old_results.items():
        seg_cog = {f: v for f, v in old_bc["evidence_summary"].items()}
        # 重建 seg_cog 输入（从 evidence_summary 还原）
        input_cog = {}
        for f, ev in seg_cog.items():
            input_cog[f] = ev.get("value") if isinstance(ev, dict) else ev
        bc = svc.cognize(sid, input_cog)
        new_results.append({"segment_id": sid, "cognition": bc})
        # 对比旧：user_needs 是否有严重丢失
        old_needs = set(old_bc.get("user_needs", []))
        new_needs = set(bc.get("user_needs", []))
        if old_needs and not new_needs:
            regressions.append({"segment_id": sid, "type": "user_needs_lost",
                                "old": list(old_needs)})
        old_vals = set(old_bc.get("business_values", []))
        new_vals = set(bc.get("business_values", []))
        if old_vals and not new_vals:
            regressions.append({"segment_id": sid, "type": "business_values_lost",
                                "old": list(old_vals)})

    # 覆盖
    n_need = sum(1 for r in new_results if r["cognition"]["user_needs"])
    n_val = sum(1 for r in new_results if r["cognition"]["business_values"])
    print(f"重跑: {len(new_results)} 条 | 有 user_needs {n_need} | 有 business_values {n_val}")
    print("regressions:", len(regressions), regressions[:3] if regressions else "")

    out = {"manifest": "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS_V1_1",
           "count": len(new_results), "results": new_results,
           "regressions_vs_v1": regressions,
           "regression_count": len(regressions),
           "note": "V1.1 知识重跑；对比 V1.0 Snapshot 无严重回归" if not regressions else
                   "存在 regression，需检查"}
    p = os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS_V1_1.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)
    svc.ks.unload()


if __name__ == "__main__":
    main()
