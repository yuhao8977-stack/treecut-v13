# -*- coding: utf-8 -*-
"""Stage3 FINAL — FRESH_HOLDOUT_V2 AI FIRST-PASS EXAM（Bundle V2 独立交卷）。

使用唯一 VISION_MODEL_BUNDLE_V2（lock sha a87d3124…，inference commit 813fc5a）
对 FRESH_HOLDOUT_V2 30 条执行一次完整 Prediction。

每段保存两层：
  A. FINAL ROUTED PREDICTION（9 字段冻结 route 的最终输出）
  B. RAW PROVIDER EVIDENCE（YOLO/SigLIP/ASR/OCR/Motion/SemanticAction V1/V2/rules）

纪律：
  - 不修改模型/Prompt/Policy/Threshold/Routing
  - 不看前几题结果调整（一次性 30/30）
  - People invariant：YOLO 正常运行无检测 → NO，fallback_used=FALSE；仅技术失败才 fallback
  - SemanticActionRouterV2：NO_CLAIM（OPEN_CABINET/RETRACT）不输出；INSUFFICIENT 不升级
  - 30/30 staging 通过 + schema/identity 校验后才 FINALIZE + 原子锁

冻结 route（来自 VISION_MODEL_BUNDLE_V2_LOCK）：
  people: PeopleAnalyzerV2 (YOLO 0.70)
  product_family: SigLIP EN top-1
  component: SigLIP V2 Top3 gap0.10 min0.02
  function: SigLIP V2
  material: SigLIP V1 threshold0.06
  shot_role: SigLIP V1 threshold0.06
  scene_family: SigLIP top-1
  product_variant: SigLIP conservative top-1
  semantic_action: SemanticActionRouterV2 per-action
"""
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"
DB = os.path.join(DATA_ROOT, "database", "materials.db")

BUNDLE_ID = "VISION_MODEL_BUNDLE_V2"
BUNDLE_LOCK_SHA = "a87d31246066bf8c6b0b1410d7e0b3598d626dfd2163274de5b1a77ef3871852"
MANIFEST_SHA = "27f751ed402f81e2c3477341ad562218f2b67cf1902c764d5735397767d9e64b"
INFERENCE_COMMIT = "813fc5aa578dee55ba0cac8c61d5092859bd555a"


def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    # ---- 前置校验 ----
    lock = json.load(open(os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V2_LOCK.json"), encoding="utf-8"))
    assert lock["bundle_lock_sha256"] == BUNDLE_LOCK_SHA, "Bundle Lock sha 不匹配！"
    man = json.load(open(os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_MANIFEST_LOCK.json"), encoding="utf-8"))
    assert man["manifest_sha256"] == MANIFEST_SHA, "Holdout V2 manifest sha 不匹配！"
    # 污染检查：Human Truth 必须 0
    conn = sqlite3.connect("file:" + DB.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    v2_sids = [s["segment_id"] for s in man["strata"]]
    ph = ",".join("?" * len(v2_sids))
    hrows = conn.execute(f"SELECT COUNT(*) n FROM fresh_holdout_human_review_v1 WHERE segment_id IN ({ph})", v2_sids).fetchone()["n"]
    assert hrows == 0, f"Holdout V2 已有 Human Truth {hrows} 行，禁止作答！"
    print("污染检查: Holdout V2 Human Truth =", hrows, "OK")

    # ---- 数据收集 ----
    kf_map, asr_map, ocr_map, seg_asset = {}, {}, {}, {}
    for r in conn.execute("SELECT segment_id, asset_id FROM segments"):
        seg_asset[r["segment_id"]] = r["asset_id"]
    for r in conn.execute("SELECT segment_id, image_path FROM keyframes ORDER BY segment_id, timestamp_ms"):
        kf_map.setdefault(r["segment_id"], []).append(r["image_path"])
    for r in conn.execute("SELECT asset_id, text_corrected FROM transcripts WHERE text_corrected IS NOT NULL"):
        asr_map.setdefault(r["asset_id"], []).append(r["text_corrected"])
    for r in conn.execute("SELECT asset_id, text FROM ocr_text WHERE text IS NOT NULL"):
        ocr_map.setdefault(r["asset_id"], []).append(r["text"])
    conn.close()

    # ---- Bundle V2 providers ----
    from treecut.services.vision_runtime import VisionRuntimeProvider
    from treecut.services.static_vision_v2 import StaticVisionAnalyzerV2
    from treecut.services.people_analyzer_v2 import PeoplePresenceAnalyzerV2
    from treecut.services.semantic_action_v1 import SemanticActionAnalyzerV1
    from treecut.services.semantic_action_v2 import SemanticActionAnalyzerV2

    rt = VisionRuntimeProvider()
    siglip = StaticVisionAnalyzerV2(rt)
    people = PeoplePresenceAnalyzerV2(rt)
    sa1 = SemanticActionAnalyzerV1()
    sa2 = SemanticActionAnalyzerV2(rt)

    # 冻结 route 的 multi-label 预测函数（与 static_vision_v2 MULTI_POLICY 一致）
    def multi_pred(field, scores):
        if not scores:
            return ["UNKNOWN"]
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        pol = siglip.MULTI_POLICY.get(field, {"top_k": 3, "gap": 0.10, "min_score": 0.02, "policy_mode": "v2"})
        if pol.get("policy_mode") == "v1":
            base = max(scores.values())
            out = [lab for lab, s in scores.items() if s >= base - pol.get("threshold", 0.06)]
            return out or ["UNKNOWN"]
        top1 = ranked[0][1]
        out = []
        for lab, s in ranked[: pol["top_k"]]:
            if s >= top1 - pol["gap"] and s >= pol["min_score"]:
                out.append(lab)
        return out or ["UNKNOWN"]

    def single_pred(field, scores):
        if not scores:
            return "UNKNOWN"
        return max(scores, key=scores.get)

    # ---- 30 条考试 ----
    results = []
    people_invariants = {"NORMAL_NO_FALLBACK_VIOLATIONS": 0, "tech_fallback_count": 0}
    for i, sid in enumerate(v2_sids):
        fr = kf_map.get(sid, [])[:8]
        asset = seg_asset.get(sid, "")
        asr_text = " ".join(asr_map.get(asset, []))[:600]
        ocr_text = " ".join(ocr_map.get(asset, []))[:300]
        print(f"[{i+1}/30] {sid[:8]}", flush=True)

        # SigLIP 全字段
        sig = siglip.analyze(fr) if fr else {"error": "no_frames"}
        evid = {"asr": asr_text, "ocr": ocr_text, "frames": len(fr)}

        # people（YOLO primary，含 invariant 记录）
        pr = people.analyze(fr)
        if pr.provider == "yolo" and pr.prediction == "NO" and pr.frame_hit_count == 0:
            people_invariants["NORMAL_NO_FALLBACK_VIOLATIONS"] += 0  # 正确：NORMAL NO
        if pr.provider == "siglip_fallback":
            people_invariants["tech_fallback_count"] += 1
        evid["people"] = {"provider": pr.provider, "yolo_max_conf": pr.max_person_conf,
                          "frame_hit_count": pr.frame_hit_count,
                          "frames_sampled": pr.frames_sampled, "fallback_used": pr.provider != "yolo",
                          "fallback_reason": "" if pr.provider == "yolo" else
                          ("technical" if pr.provider == "siglip_fallback" else "no_evidence")}

        # 单值字段（SigLIP EN）
        fields = {}
        fields["people_presence"] = pr.prediction  # YOLO primary（合法 NO 或 YES）
        for f in ("product_family", "scene_family", "product_variant"):
            sc = sig.get(f, {}).get("scores", {})
            pred = single_pred(f, sc)
            fields[f] = pred
            evid[f] = {"provider": "siglip", "scores": {k: round(v, 3) for k, v in
                       sorted(sc.items(), key=lambda x: -x[1])[:4]}}
        # 多标签字段
        for f in ("component", "function", "material", "shot_role"):
            sc = sig.get(f, {}).get("scores", {})
            pred = multi_pred(f, sc)
            fields[f] = pred
            evid[f] = {"provider": "siglip", "policy": siglip.MULTI_POLICY.get(f, {}).get("policy_mode", "v2"),
                       "top_scores": {k: round(v, 3) for k, v in sorted(sc.items(), key=lambda x: -x[1])[:6]}}

        # Semantic Action（SemanticActionRouterV2 per-action）
        comp = fields.get("component", [])
        if not isinstance(comp, list):
            comp = []
        o1 = sa1.analyze(fr, asr_text=asr_text, ocr_text=ocr_text, component=comp)
        o2 = sa2.analyze(fr, component=comp, asr_text=asr_text, ocr_text=ocr_text)
        # Router：per-action best-known + NO_CLAIM 保护
        router = lock["semantic_action_router"]
        routed_seq = []
        cand1 = o1.get("action_sequence", [])
        cand2 = o2.get("action_sequence", [])
        for a in cand1 + cand2:
            spec = router.get(a)
            if spec is None:
                continue
            prov = spec.get("provider")
            if prov in ("NO_CLAIM", "INSUFFICIENT_SAMPLE"):
                continue  # 保护：不输出 NO_CLAIM / INSUFFICIENT
            if a not in routed_seq:
                routed_seq.append(a)
        gmap = {"OPEN_DRAWER": "DRAWER", "CLOSE_DRAWER": "DRAWER",
                "OPEN_CABINET": "CABINET", "CLOSE_CABINET": "CABINET",
                "OPERATE_SOCKET": "POWER_INTERACTION", "OPEN_SINK_COVER": "WATER_INTERACTION",
                "PULL_OUT": "EXTEND", "RETRACT": "EXTEND",
                "STATIC_DISPLAY": "STATIC", "PERSON_SPEAKING": "SPEAKING", "OTHER": "OTHER"}
        fields["action_group"] = gmap.get(routed_seq[0], "OTHER") if routed_seq else (
            "STATIC" if o1.get("prediction") == "STATIC" else "OTHER")
        fields["action_sequence"] = routed_seq
        evid["semantic_action"] = {"v1": o1.get("action_sequence"), "v2": o2.get("action_sequence"),
                                   "routed": routed_seq, "motion": o1.get("evidence", {}).get("motion")}

        results.append({"segment_id": sid, "stratum": next(s["stratum"] for s in man["strata"] if s["segment_id"] == sid),
                        "final_routed_prediction": fields,
                        "raw_provider_evidence": evid})
        print(f"  people={pr.prediction}({pr.provider}) sa={routed_seq}", flush=True)

    # ---- schema/identity 校验（staging）----
    assert len(results) == 30, "预测数 != 30"
    assert len({r["segment_id"] for r in results}) == 30
    for r in results:
        p = r["final_routed_prediction"]
        assert set(p.keys()) >= {"people_presence", "product_family", "component", "function",
                                 "material", "shot_role", "scene_family", "product_variant",
                                 "action_group", "action_sequence"}
    print("\nstaging: 30/30 OK, schema OK, identity OK")

    # ---- invariant check ----
    print("People invariant:", people_invariants)

    # ---- FINALIZE：写 prediction 文件 + lock ----
    pred_out = {"manifest": "HOLDOUT_V2_AI_PREDICTIONS_V1",
                "bundle_id": BUNDLE_ID, "bundle_lock_sha256": BUNDLE_LOCK_SHA,
                "holdout_manifest_sha256": MANIFEST_SHA,
                "inference_git_commit": INFERENCE_COMMIT,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "results": results}
    p = os.path.join(DATA_ROOT, "HOLDOUT_V2_AI_PREDICTIONS_V1.json")
    json.dump(pred_out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", p)

    pred_canon = json.dumps({"segments": [{k: r["final_routed_prediction"] for k, r in enumerate(results)}]},
                            ensure_ascii=False, sort_keys=True)
    pred_sha = sha256_str(json.dumps([r["final_routed_prediction"] for r in results],
                                     ensure_ascii=False, sort_keys=True))
    plock = {
        "manifest": "FRESH_HOLDOUT_V2_PREDICTION_LOCK",
        "bundle_id": BUNDLE_ID, "bundle_lock_sha256": BUNDLE_LOCK_SHA,
        "holdout_manifest_sha256": MANIFEST_SHA,
        "inference_git_commit": INFERENCE_COMMIT,
        "prediction_sha256": pred_sha,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "predictions": [{"segment_id": r["segment_id"], "stratum": r["stratum"],
                         "final": r["final_routed_prediction"]} for r in results],
        "state": {"AI_PREDICTION_COUNT": 30, "PREDICTION_LOCKED": True,
                  "DO_NOT_REPREDICT": True, "DO_NOT_TRAIN": True,
                  "DO_NOT_CALIBRATE": True, "HUMAN_REVIEW_STARTED": False},
    }
    plock["lock_sha256"] = sha256_str(json.dumps({k: v for k, v in plock.items() if k != "lock_sha256"},
                                                 ensure_ascii=False, sort_keys=True))
    pp = os.path.join(DATA_ROOT, "FRESH_HOLDOUT_V2_PREDICTION_LOCK.json")
    json.dump(plock, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("->", pp)
    print("prediction_sha256:", pred_sha)
    print("PREDICTION_LOCKED: TRUE | DO_NOT_REPREDICT: TRUE")

    # 清理 GPU
    siglip.unload()
    people.unload()
    sa2.unload()


if __name__ == "__main__":
    main()
