# -*- coding: utf-8 -*-
"""Stage3 FINAL CONSOLIDATION — Bundle V2 + Fresh Holdout V2 回归测试。"""
import json
import os
import sys

DATA_ROOT = os.environ.get(
    "TREECUT_DATA_ROOT",
    r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")


def test_bundle_v2_lock_complete():
    lock = json.load(open(os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V2_LOCK.json"),
                          encoding="utf-8"))
    assert lock["bundle_id"] == "VISION_MODEL_BUNDLE_V2"
    assert len(lock["bundle_lock_sha256"]) == 64
    assert len(lock["stage3_dev_snapshot_hash"]) == 64
    assert len(lock["git_code_commit"]) == 40
    # 9 字段
    assert len(lock["fields"]) == 9
    for f, v in lock["fields"].items():
        assert v["status"] in ("READY", "READY_CANDIDATE", "READY/LIMITED_READY",
                               "LIMITED", "EXPERIMENTAL", "EXPERIMENTAL/FALLBACK")
    # People 路由纪律
    pp = lock["fields"]["people_presence"]
    assert pp["threshold"] == 0.70
    assert "合法 NO" in pp["fallback_rule"]
    assert "技术失败" in pp["fallback_rule"]


def test_bundle_v2_snapshot():
    snap = json.load(open(os.path.join(DATA_ROOT, "STAGE3_FINAL_DEV_SNAPSHOT.json"),
                          encoding="utf-8"))
    assert snap["total_dev_segments"] == 411
    assert len(snap["snapshot_sha256"]) == 64
    assert snap["datasets"]["stage3_v31"]["human_truth_sha256"].startswith("a6cc7f30")
    assert snap["datasets"]["mini18"]["human_truth_sha256"].startswith("9838bf58")


def test_semantic_action_router_no_claim():
    lock = json.load(open(os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V2_LOCK.json"),
                          encoding="utf-8"))
    router = lock["semantic_action_router"]
    assert router["OPEN_CABINET"]["provider"] == "NO_CLAIM"
    assert router["RETRACT"]["provider"] == "NO_CLAIM"
    assert router["OPERATE_SOCKET"]["provider"] == "INSUFFICIENT_SAMPLE"
    assert router["OPEN_SINK_COVER"]["provider"] == "INSUFFICIENT_SAMPLE"


def test_holdout_v2_manifest_30():
    m = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"),
                       encoding="utf-8"))
    strata = m["strata"]
    assert len(strata) == 30
    assert len({s["segment_id"] for s in strata}) == 30
    assert len({s["asset_id"] for s in strata}) == 30
    assert m["strata_counts"] == {"RANDOM": 10, "HARD": 10, "GAP": 10}
    assert len(m["manifest_sha256"]) == 64
    assert m["guard"] == "DO_NOT_TRAIN; DO_NOT_CALIBRATE; DO_NOT_PREDICT（V2 AI 未作答）"


def test_holdout_v2_isolated_from_dev():
    m = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"),
                       encoding="utf-8"))
    v2_sids = {s["segment_id"] for s in m["strata"]}
    v2_assets = {s["asset_id"] for s in m["strata"]}
    # 与 Cal333 + Stage3 + Mini + HoldoutV1 无 segment/asset 交集
    import sqlite3
    conn = sqlite3.connect("file:" + os.path.join(
        DATA_ROOT, "database", "materials.db").replace("\\", "/") + "?mode=ro", uri=True)
    seen = {r[0] for r in conn.execute("SELECT segment_id FROM canonical_human_truth")}
    seen_asset = {r[0] for r in conn.execute(
        "SELECT DISTINCT asset_id FROM segments WHERE segment_id IN (SELECT segment_id FROM canonical_human_truth)")}
    conn.close()
    for f in ("TARGETED_REVIEW_STAGE3_V3_1.json", "TARGETED_REVIEW_STAGE3_MINI_V1.json"):
        d = json.load(open(os.path.join(DATA_ROOT, f), encoding="utf-8"))
        seen |= {s["segment_id"] for s in d["segments"]}
        seen_asset |= {s["asset_id"] for s in d["segments"]}
    h1 = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"),
                        encoding="utf-8"))
    seen |= {s["segment_id"] for s in h1["strata"]}
    seen_asset |= {s["asset_id"] for s in h1["strata"]}
    assert not (v2_sids & seen), "Holdout V2 与已见 segment 重叠!"
    assert not (v2_assets & seen_asset), "Holdout V2 与已见 asset 重叠!"


def test_holdout_v2_neardup_audit():
    nd = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_NEARDUP_AUDIT.json"),
                        encoding="utf-8"))
    assert nd["n_holdout_v2"] == 30
    assert nd["pass"] is True
    assert nd["vs_all_seen_dev_holdout1"].get("EXACT", 0) == 0
    assert nd["vs_all_seen_dev_holdout1"].get("NEAR", 0) == 0
    assert nd["internal"].get("EXACT", 0) == 0
    assert nd["internal"].get("NEAR", 0) == 0


def test_holdout_v2_manifest_unchanged():
    """STEP 2：Manifest 内容未变化（provenance 修复不得重新挑题）。"""
    m = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"),
                       encoding="utf-8"))
    assert m["manifest_sha256"] == "27f751ed402f81e2c3477341ad562218f2b67cf1902c764d5735397767d9e64b"
    assert len(m["strata"]) == 30


def test_bundle_v2_lock_provenance_fixed():
    """STEP 0/1：provenance 修复 —— inference commit = 813fc5a（含 People YOLO NO 修复）。"""
    lock = json.load(open(os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V2_LOCK.json"),
                          encoding="utf-8"))
    assert lock["inference_git_commit"].startswith("813fc5a")
    assert lock["packaging_commit"] == "813fc5a"
    assert lock["bundle_lock_sha256"] == "a87d31246066bf8c6b0b1410d7e0b3598d626dfd2163274de5b1a77ef3871852"
    assert len(lock["bundle_lock_sha256"]) == 64
    assert "supersedes" in lock


def test_holdout_v2_prediction_lock():
    """STEP 8-10：prediction lock 状态机。"""
    pl = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_PREDICTION_LOCK.json"),
                        encoding="utf-8"))
    assert len(pl["predictions"]) == 30
    assert pl["state"]["AI_PREDICTION_COUNT"] == 30
    assert pl["state"]["PREDICTION_LOCKED"] is True
    assert pl["state"]["DO_NOT_REPREDICT"] is True
    assert pl["state"]["DO_NOT_TRAIN"] is True
    assert pl["state"]["DO_NOT_CALIBRATE"] is True
    assert pl["state"]["HUMAN_REVIEW_STARTED"] is False
    assert len(pl["prediction_sha256"]) == 64
    assert pl["bundle_lock_sha256"] == "a87d31246066bf8c6b0b1410d7e0b3598d626dfd2163274de5b1a77ef3871852"


def test_holdout_v2_human_truth_zero():
    """STEP 3：AI 考试前 Human Truth 必须为 0。"""
    import sqlite3
    m = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"),
                       encoding="utf-8"))
    sids = [s["segment_id"] for s in m["strata"]]
    conn = sqlite3.connect("file:" + os.path.join(
        DATA_ROOT, "database", "materials.db").replace("\\", "/") + "?mode=ro", uri=True)
    ph = ",".join("?" * len(sids))
    n = conn.execute(f"SELECT COUNT(*) FROM fresh_holdout_human_review_v1 WHERE segment_id IN ({ph})",
                     sids).fetchone()[0]
    conn.close()
    assert n == 0


def test_people_invariant_no_fallback():
    """STEP 6：prediction 中 NORMAL NO 不 fallback。"""
    pred = json.load(open(os.path.join(DATA_ROOT, "HOLDOUT_V2_AI_PREDICTIONS_V1.json"),
                          encoding="utf-8"))
    violations = 0
    for r in pred["results"]:
        pe = r["raw_provider_evidence"].get("people", {})
        if pe.get("provider") == "yolo" and pe.get("fallback_used") is True:
            violations += 1
    assert violations == 0


def test_semantic_action_no_claim_protected():
    """STEP 7：NO_CLAIM（OPEN_CABINET/RETRACT）不得出现在 routed prediction。"""
    pred = json.load(open(os.path.join(DATA_ROOT, "HOLDOUT_V2_AI_PREDICTIONS_V1.json"),
                          encoding="utf-8"))
    for r in pred["results"]:
        seq = r["final_routed_prediction"].get("action_sequence", [])
        assert "OPEN_CABINET" not in seq
        assert "RETRACT" not in seq
        assert "OPERATE_SOCKET" not in seq
        assert "OPEN_SINK_COVER" not in seq
