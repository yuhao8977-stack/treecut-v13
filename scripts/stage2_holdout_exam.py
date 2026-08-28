# -*- coding: utf-8 -*-
"""Stage 2 — FRESH_HOLDOUT_V1 AI FIRST-PASS EXAM + PREDICTION LOCK。

流程：
1. 污染检查（30 条 human truth=0；不属于 300/60/333）
2. 唯一冻结 Bundle V1_1（SigLIP en-prompt + FIELD_ROUTING_V1）作答 30 条
3. STAGING 写临时 → 30/30 校验 → FINALIZE → HOLDOUT_AI_PREDICTIONS_V1.json
4. prediction_sha256 → FRESH_HOLDOUT_V1_PREDICTION_LOCK.json（PREDICTION_LOCKED=True）
5. 更新 manifest lock 状态（INITIAL_PREDICTION_ALLOWED=False, DO_NOT_REPREDICT=True）
禁止：评分、修改模型/prompt/routing、自动人工审核。
"""
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = os.environ.get("TREECUT_DATA_ROOT", r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = os.path.join(DATA_ROOT, "database", "materials.db")
sys.path.insert(0, r"C:\Users\admin\github\treecut-v13\src")

BUNDLE_ID = "VISION_MODEL_BUNDLE_V1_1"
BUNDLE_LOCK = "6c2ce081b9d2a1be"
MANIFEST_LOCK = "31ae951d99f0e792"
INFERENCE_GIT = "af872dd80adf"
EVAL_GIT = "0c725f3"

from treecut.services.vision_runtime import VisionRuntimeProvider
from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2


def main():
    hold = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_CANDIDATES.json"), encoding="utf-8"))
    segs = hold["segments"]
    assert len(segs) == 30

    # ---- 1. 污染检查 ----
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    known = {r[0] for r in conn.execute(
        "SELECT target_id FROM human_annotations UNION SELECT segment_id FROM human_annotation_v2"
        " UNION SELECT segment_id FROM human_annotation_v3"
        " UNION SELECT segment_id FROM targeted_human_review_v1"
        " UNION SELECT segment_id FROM canonical_human_truth")}
    sid_set = {s["segment_id"] for s in segs}
    assert not (sid_set & known), "Holdout 与已标注/canonical 重叠！"
    print(f"[1] 污染检查 OK: 30 条 ∩ 已标注/Calibration = 0 (known={len(known)})", flush=True)

    # ---- 2. 冻结 Bundle 作答 ----
    rt = VisionRuntimeProvider()
    an = StaticVisionAnalyzerV2(rt)  # SigLIP en-prompt（Bundle V1_1 冻结）
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    staging = []
    for i, s in enumerate(segs):
        sid = s["segment_id"]
        with sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True) as c:
            c.row_factory = sqlite3.Row
            frames = [r["image_path"] for r in c.execute(
                "SELECT image_path FROM keyframes WHERE segment_id=? ORDER BY timestamp_ms LIMIT 5", (sid,))]
        try:
            r2 = an.analyze(frames) if frames else {"error": "no_frames"}
        except Exception as e:
            r2 = {"error": str(e)[:200]}
        # FIELD_ROUTING_V1 执行
        row = {"holdout_id": f"FHV1_{i+1:02d}", "segment_id": sid, "asset_id": s["asset_id"],
               "stratum": {"coverage_gap": "GAP", "low_evidence": "HARD", "random_audit": "RANDOM"}.get(
                   s["selection_reason"], s["selection_reason"]),
               "bundle_id": BUNDLE_ID, "bundle_lock_sha256": BUNDLE_LOCK,
               "holdout_manifest_sha256": MANIFEST_LOCK,
               "inference_git_commit": INFERENCE_GIT, "evaluation_git_commit": EVAL_GIT,
               "dictionary_version": "ANNOTATION_DICTIONARY_V2_1",
               "field_routing_version": "FIELD_ROUTING_V1", "prompt_version": "en-v1",
               "prediction_started_at": started,
               "prediction_completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        if "error" in r2:
            row["fields"] = {"error": r2["error"]}
            row["status"] = "FAILED"
        else:
            # 路由：product_family=SigLIP；people=legacy(无样本→UNKNOWN+记录SigLIP)；variant=UNKNOWN gate
            fields = {
                "scene_family": {"final": r2["scene_family"]["prediction"], "provider": "SIGLIP",
                                 "status": "EXPERIMENTAL", "raw_score": r2["scene_family"]["model_score"]},
                "scene_subtype": {"final": "UNKNOWN", "provider": "ROUTING_GATE", "status": "EXPERIMENTAL"},
                "product_family": {"final": r2["product_family"]["prediction"], "provider": "SIGLIP",
                                   "status": "READY_FOR_HOLDOUT", "raw_score": r2["product_family"]["model_score"]},
                "product_variant": {"final": "UNKNOWN", "provider": "UNKNOWN_GATE", "status": "FALLBACK"},
                "material": {"final": r2["material"]["prediction"], "provider": "SIGLIP",
                             "status": "EXPERIMENTAL", "raw_score": r2["material"]["model_score"]},
                "component": {"final": r2["component"]["prediction"], "provider": "SIGLIP",
                              "status": "EXPERIMENTAL", "raw_score": r2["component"]["model_score"]},
                "function": {"final": r2["function"]["prediction"], "provider": "SIGLIP",
                             "status": "EXPERIMENTAL", "raw_score": r2["function"]["model_score"]},
                "shot_scale": {"final": r2["shot_scale"]["prediction"], "provider": "SIGLIP",
                               "status": "EXPERIMENTAL", "raw_score": r2["shot_scale"]["model_score"]},
                "shot_role": {"final": r2["shot_role"]["prediction"], "provider": "SIGLIP",
                              "status": "EXPERIMENTAL", "raw_score": r2["shot_role"]["model_score"]},
                "people_presence": {"final": "UNKNOWN", "provider": "LEGACY_FALLBACK",
                                    "status": "FALLBACK", "siglip_hint": r2["people_presence"]["prediction"]},
                "action_group": {"final": "UNKNOWN", "provider": "MOTION_EVIDENCE_ONLY", "status": "EXPERIMENTAL"},
                "action_sequence": {"final": [], "provider": "NONE", "status": "EXPERIMENTAL"},
            }
            row["fields"] = fields
            row["status"] = "OK"
        staging.append(row)
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/30] {time.time():.0f}", flush=True)
    an.unload()

    # ---- 3. STAGING → 完整性校验 → FINALIZE ----
    failed = [r for r in staging if r["status"] == "FAILED"]
    assert not failed, f"存在失败预测: {failed}"
    assert len(staging) == 30
    assert len({r["segment_id"] for r in staging}) == 30
    assert all(r["bundle_lock_sha256"] == BUNDLE_LOCK for r in staging)
    assert all(r["holdout_manifest_sha256"] == MANIFEST_LOCK for r in staging)

    predictions = {"manifest_version": "HOLDOUT_AI_PREDICTIONS_V1",
                   "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "bundle_id": BUNDLE_ID, "bundle_lock_sha256": BUNDLE_LOCK,
                   "holdout_manifest_sha256": MANIFEST_LOCK,
                   "inference_git_commit": INFERENCE_GIT, "evaluation_git_commit": EVAL_GIT,
                   "count": 30, "segments": staging}
    pp = os.path.join(DATA_ROOT, "HOLDOUT_AI_PREDICTIONS_V1.json")
    json.dump(predictions, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 4. Prediction hash（固定 segment_id 排序序列化）----
    canon = sorted(staging, key=lambda r: r["segment_id"])
    payload = json.dumps({"bundle_lock": BUNDLE_LOCK, "manifest_lock": MANIFEST_LOCK,
                          "dictionary": "ANNOTATION_DICTIONARY_V2_1",
                          "routing": "FIELD_ROUTING_V1",
                          "predictions": [{r["segment_id"]: r["fields"]} for r in canon]},
                         ensure_ascii=False, sort_keys=True)
    pred_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
    lock = {
        "manifest_version": "FRESH_HOLDOUT_V1_PREDICTION_LOCK",
        "locked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "bundle_id": BUNDLE_ID, "bundle_lock_sha256": BUNDLE_LOCK,
        "holdout_manifest_sha256": MANIFEST_LOCK,
        "prediction_sha256": pred_hash,
        "ai_prediction_count": 30,
        "state": {"INITIAL_PREDICTION_ALLOWED": False, "PREDICTION_LOCKED": True,
                  "DO_NOT_REPREDICT": True, "DO_NOT_TRAIN": True,
                  "DO_NOT_CALIBRATE": True, "HUMAN_REVIEW_STARTED": False},
    }
    lp = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_PREDICTION_LOCK.json")
    json.dump(lock, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- 5. 更新 manifest lock 状态 ----
    hl = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), encoding="utf-8"))
    hl["state"] = {"INITIAL_PREDICTION_ALLOWED": False, "PREDICTION_LOCKED": True,
                   "DO_NOT_REPREDICT": True}
    json.dump(hl, open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V1_MANIFEST_LOCK.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"[3] FINALIZE OK: 30/30")
    print(f"[4] prediction_sha256 = {pred_hash}")
    print(f"[5] LOCK: PREDICTION_LOCKED=True, DO_NOT_REPREDICT=True")
    conn.close()


if __name__ == "__main__":
    main()
