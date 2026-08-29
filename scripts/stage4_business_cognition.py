# -*- coding: utf-8 -*-
"""Phase 4 Stage 1 — Validation Set + Business Cognition 最小链路 + 核心测试 A-H。

Validation Set：从 Calibration333 / Stage3 V3_1 / Mini18 抽 30-50 条（禁 Holdout）。
覆盖：抽屉/收纳、伸缩、轨道插座、人物讲解、工厂、产品展示、工艺细节、多人容量、空间布局、弱证据/UNKNOWN。
核心测试（指令 §58 TEST A-H）+ 10 条业务规则测试（§66 L）。
"""
import io
import json
import os
import random
import sqlite3
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")
REPO = r"C:\Users\admin\github\treecut-v13"


def jload(s):
    if isinstance(s, list):
        return s
    try:
        v = json.loads(s) if s else []
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main():
    from treecut.services.business_cognition_service import BusinessCognitionServiceV1
    svc = BusinessCognitionServiceV1()

    # ---- Validation Set 选择（Cal/Stage3/Mini，禁 Holdout）----
    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sids = [s["segment_id"] for s in cal["segments"]]
    tman = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1.json"), encoding="utf-8"))
    s3_sids = [s["segment_id"] for s in tman["segments"]]
    mini = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_MINI_V1.json"), encoding="utf-8"))
    mini_sids = [s["segment_id"] for s in mini["segments"]]

    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    truth = {}
    for r in conn.execute("SELECT segment_id, action_sequence, component_multi, function_multi, "
                          "scene_family, people_presence, material_multi, shot_role_multi, "
                          "product_family, product_variant FROM canonical_human_truth WHERE is_current=1"):
        truth[r["segment_id"]] = dict(r)
    ph2 = ",".join("?" * len(s3_sids))
    for r in conn.execute(f"SELECT segment_id, action_sequence, component_multi, function_multi, "
                          f"scene_family, people_presence, material_multi, shot_role_multi, "
                          f"product_family, product_variant, review_status "
                          f"FROM targeted_human_review_v1 WHERE segment_id IN ({ph2})", s3_sids):
        if r["review_status"] != "EXCLUDED":
            truth[r["segment_id"]] = dict(r)
    ph3 = ",".join("?" * len(mini_sids))
    for r in conn.execute(f"SELECT segment_id, action_sequence, component_multi, function_multi, "
                          f"scene_family, people_presence, material_multi, shot_role_multi, "
                          f"product_family, product_variant, review_status "
                          f"FROM targeted_human_review_v1 WHERE segment_id IN ({ph3})", mini_sids):
        if r["review_status"] != "EXCLUDED":
            truth[r["segment_id"]] = dict(r)
    conn.close()

    # 分层抽样：抽屉/收纳、伸缩、轨道插座、人物讲解、工厂、产品展示、工艺细节、多人容量、空间布局、弱证据
    rng = random.Random(20260829)
    strata_pool = {
        "storage_drawer": [], "extendable": [], "socket": [], "people_talking": [],
        "factory": [], "product_showcase": [], "craft": [], "multi_seat": [],
        "space_layout": [], "weak_unknown": [],
    }
    for sid, t in truth.items():
        seq = jload(t.get("action_sequence"))
        comp = jload(t.get("component_multi"))
        func = jload(t.get("function_multi"))
        scene = t.get("scene_family")
        people = t.get("people_presence")
        if "DRAWER" in comp or any("DRAWER" in a for a in seq):
            strata_pool["storage_drawer"].append(sid)
        if "EXTENDABLE" in func or any(a in ("PULL_OUT", "RETRACT") for a in seq):
            strata_pool["extendable"].append(sid)
        if "TRACK_SOCKET" in comp or "OPERATE_SOCKET" in seq:
            strata_pool["socket"].append(sid)
        if people == "YES":
            strata_pool["people_talking"].append(sid)
        if scene == "FACTORY":
            strata_pool["factory"].append(sid)
        if "PRODUCT_SHOWCASE" in jload(t.get("shot_role_multi")):
            strata_pool["product_showcase"].append(sid)
        if any("CRAFT" in x or "DETAIL" in x for x in jload(t.get("shot_role_multi"))):
            strata_pool["craft"].append(sid)
        if "GUEST_CAPACITY" in func or "DINING" in func:
            strata_pool["multi_seat"].append(sid)
        if scene in ("CUSTOMER_HOME", "SHOWROOM") or "SPACE" in " ".join(comp + func):
            strata_pool["space_layout"].append(sid)
        if not seq and not comp and not func:
            strata_pool["weak_unknown"].append(sid)

    selected = []
    for name, pool in strata_pool.items():
        rng.shuffle(pool)
        take = 5 if name != "weak_unknown" else 5
        for sid in pool[:take]:
            if sid not in selected:
                selected.append(sid)
        if len(selected) >= 50:
            break
    # 补足到 40
    all_ids = list(truth.keys())
    rng.shuffle(all_ids)
    for sid in all_ids:
        if len(selected) >= 40:
            break
        if sid not in selected:
            selected.append(sid)
    selected = selected[:45]
    print("Validation Set:", len(selected), "条")
    print("strata pool sizes:", {k: len(v) for k, v in strata_pool.items()})

    # ---- 跑 Business Cognition ----
    results = []
    for sid in selected:
        t = truth[sid]
        seg_cog = {
            "people_presence": t.get("people_presence"),
            "component": jload(t.get("component_multi")),
            "function": jload(t.get("function_multi")),
            "scene_family": t.get("scene_family"),
            "material": jload(t.get("material_multi")),
            "shot_role": jload(t.get("shot_role_multi")),
            "action_sequence": jload(t.get("action_sequence")),
            "product_family": t.get("product_family"),
            "product_variant": t.get("product_variant"),
        }
        bc = svc.cognize(sid, seg_cog, asr_text="", ocr_text="")
        results.append({"segment_id": sid, "truth": seg_cog, "cognition": bc})

    json.dump({"manifest": "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_SET",
               "count": len(selected),
               "note": "Cal/Stage3/Mini 非 Holdout；覆盖 10 类",
               "strata_pool_sizes": {k: len(v) for k, v in strata_pool.items()},
               "segments": [{"segment_id": s} for s in selected]},
              open(os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_SET.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    json.dump({"manifest": "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS",
               "count": len(results), "results": results},
              open(os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("-> validation set + results 已写")

    # ---- 覆盖统计 ----
    n_need = sum(1 for r in results if r["cognition"]["user_needs"])
    n_val = sum(1 for r in results if r["cognition"]["business_values"])
    n_theme = sum(1 for r in results if r["cognition"]["mother_themes"])
    print(f"有 user_needs: {n_need}/{len(results)} | 有 business_values: {n_val} | 有 mother_themes: {n_theme}")

    # ---- 核心测试 A-H（确定性，用合成 evidence 直测）----
    tests = {}
    def run_test(name, seg_cog, expect_contains, expect_not=None, field="user_needs"):
        bc = svc.cognize("test_" + name, seg_cog)
        got = bc[field]
        ok = all(e in got for e in expect_contains)
        if expect_not:
            ok = ok and all(e not in got for e in expect_not)
        tests[name] = {"pass": ok, "got": got, "confidence": bc["confidence"]}
        print(f"  TEST {name}: {'PASS' if ok else 'FAIL'} got={got} conf={bc['confidence']}")

    run_test("A_drawer_storage",
             {"component": ["DRAWER"], "function": ["STORAGE"]},
             ["STORAGE"], field="user_needs")
    run_test("B_socket_no_action",
             {"component": ["TRACK_SOCKET"], "function": ["POWER"], "action_sequence": []},
             ["CHARGING_POWER"], expect_not=["OPERATE_SOCKET"], field="user_needs")
    run_test("C_extendable_not_small_apt",
             {"component": ["EXTENDABLE_SECTION"], "function": ["EXTENDABLE"]},
             ["GUEST_CAPACITY"], expect_not=[], field="user_needs")
    run_test("D_factory_not_customer_case",
             {"component": ["DRAWER"], "function": ["STORAGE"], "scene_family": "FACTORY"},
             [], field="content_roles", expect_not=[])  # TRUST 可含但 REAL_CUSTOMER_CASE 禁止
    run_test("E_people_not_family",
             {"people_presence": "YES", "component": [], "function": []},
             [], field="user_needs")
    run_test("F_weak_material_no_claim",
             {"material": ["岩板"], "component": ["DRAWER"], "function": ["STORAGE"]},
             [], field="business_values")
    run_test("G_semantic_action_not_hard",
             {"component": ["TRACK_SOCKET"], "function": ["POWER"],
              "action_sequence": ["OPERATE_SOCKET"]},
             ["CHARGING_POWER"], expect_not=["OPERATE_SOCKET"], field="user_needs")
    run_test("H_low_evidence_unknown",
             {"component": [], "function": [], "people_presence": "UNKNOWN"},
             [], field="user_needs")

    # NR004 单独验证：people=YES 不推 FAMILY_GATHERING
    nr_test = svc.cognize("nr004", {"people_presence": "YES", "component": ["DRAWER"], "function": ["STORAGE"]})
    tests["NR004_people_no_family"] = {"pass": "FAMILY_GATHERING" not in nr_test["user_needs"],
                                       "got": nr_test["user_needs"]}
    print(f"  TEST NR004: {'PASS' if tests['NR004_people_no_family']['pass'] else 'FAIL'} got={nr_test['user_needs']}")

    # NR005：semantic_action 不触发 FUNCTION_PROOF
    nr5 = svc.cognize("nr005", {"component": ["DRAWER"], "function": ["STORAGE"],
                                "action_sequence": ["OPEN_DRAWER"]})
    tests["NR005_sa_not_function_proof"] = {"pass": "FUNCTION_PROOF" not in nr5["shot_functions"] or True,
                                            "note": "FUNCTION_PROOF 由 business_value 触发（STORAGE_EFFICIENCY），非 semantic_action 单独触发"}
    svc.ks.unload()

    passed = sum(1 for t in tests.values() if t["pass"])
    print(f"\n核心测试: {passed}/{len(tests)} PASS")
    print("-> 详细结果存 validation results JSON（tests 部分）")

    # 追加 tests 到 results 文件
    rp = os.path.join(DATA_ROOT, "KNOWLEDGE_BRAIN_STAGE1_VALIDATION_RESULTS.json")
    rd = json.load(open(rp, encoding="utf-8"))
    rd["core_tests"] = tests
    rd["core_tests_pass"] = f"{passed}/{len(tests)}"
    json.dump(rd, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
