# -*- coding: utf-8 -*-
"""Stage3 FINAL CONSOLIDATION — STEP 1-16：DEV Snapshot + 9 字段 Routing + Bundle V2 Lock。

生成：
  STAGE3_FINAL_DEV_SNAPSHOT.json（数据身份冻结，含全部 hash）
  VISION_MODEL_BUNDLE_V2_LOCK.json（64 位 sha256）
  VISION_MODEL_BUNDLE_V2.md（人工可读）
"""
import hashlib
import json
import os
import sys
from datetime import datetime

sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DATA_ROOT = r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    # ---- 数据身份（STEP 1）----
    cal = json.load(open(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"), encoding="utf-8"))
    cal_sha = sha256_file(os.path.join(DATA_ROOT, "CALIBRATION_CORPUS_V2_MANIFEST.json"))
    v31_lock = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_V3_1_HUMAN_LOCK.json"), encoding="utf-8"))
    mini_lock = json.load(open(os.path.join(DATA_ROOT, "TARGETED_REVIEW_STAGE3_MINI_V1_HUMAN_LOCK.json"), encoding="utf-8"))
    qa_lock_p = os.path.join(DATA_ROOT, "STAGE3_ACTION_QA_ADJUDICATION_LOCK.json")
    qa_sha = sha256_file(qa_lock_p) if os.path.exists(qa_lock_p) else None

    snapshot = {
        "manifest": "STAGE3_FINAL_DEV_SNAPSHOT",
        "frozen_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dictionary_version": "ANNOTATION_DICTIONARY_V2_1",
        "datasets": {
            "calibration333": {"manifest": "CALIBRATION_CORPUS_V2_MANIFEST.json",
                               "count": len(cal["segments"]),
                               "manifest_sha256": cal_sha},
            "stage3_v31": {"lock": "TARGETED_REVIEW_STAGE3_V3_1_HUMAN_LOCK.json",
                           "count": v31_lock["count"],
                           "human_truth_sha256": v31_lock["human_truth_sha256"]},
            "mini18": {"lock": "TARGETED_REVIEW_STAGE3_MINI_V1_HUMAN_LOCK.json",
                       "count": mini_lock["count"],
                       "human_truth_sha256": mini_lock["human_truth_sha256"]},
            "qa_adjudication": {"lock": "STAGE3_ACTION_QA_ADJUDICATION_LOCK.json",
                                "sha256": qa_sha},
        },
        "total_dev_segments": len(cal["segments"]) + v31_lock["count"] + mini_lock["count"],
        "guard": "Bundle V2 模型选择必须可追溯到此 Snapshot；Fresh Holdout V1 不在此内",
    }
    snapshot_sha = sha256_str(json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
    snapshot["snapshot_sha256"] = snapshot_sha
    sp = os.path.join(DATA_ROOT, "STAGE3_FINAL_DEV_SNAPSHOT.json")
    json.dump(snapshot, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("STEP1: snapshot ->", sp, "| sha:", snapshot_sha, "| total:", snapshot["total_dev_segments"])

    # ---- 9 字段 Routing（STEP 2-13）----
    from treecut.services.people_analyzer_v2 import DEFAULT_THRESHOLD
    import treecut.services.static_vision_v2 as sv2

    fields = {
        "people_presence": {
            "primary_provider": "PeoplePresenceAnalyzerV2",
            "model": "YOLOv8n(COCO person=0)", "model_identity": "yolov8n.pt",
            "threshold": DEFAULT_THRESHOLD,
            "fallback_provider": "SigLIP ONLY on technical failure",
            "fallback_rule": ("YOLO 正常运行：无 person 检测 = 合法 NO，不 fallback；"
                              "仅 YOLO runtime/frame/detector 技术失败才 SigLIP fallback 或 UNKNOWN"),
            "support": "YES 305 / NO 114（Cal333+Stage3）",
            "dev_metric": "combined F1 94.2 / bacc 86.4（threshold 0.70 冻结）",
            "status": "READY",
            "known_limitations": "FP 3 条 hard-case（conf>=0.70 仍误判）；无身份属性输出",
        },
        "product_family": {
            "primary_provider": "StaticVisionAnalyzerV2", "model": "SigLIP base-patch16-224",
            "prompt_version": "EN prompts（Stage2 修正）", "policy_version": "single top-1",
            "support": "ISLAND 主导", "dev_metric": "Cal333 52.7% / Stage3 72.7%",
            "status": "READY/LIMITED_READY",
            "known_limitations": "V1_1 Holdout 锚点 51.7% 只作回归参考；禁改 product prompt",
        },
        "component": {
            "primary_provider": "StaticVisionAnalyzerV2", "model": "SigLIP",
            "policy_version": "V2（Top3+gap0.10+min0.02）",
            "support": "DRAWER 79 / TRACK_SOCKET 87 / COUNTERTOP 49",
            "dev_metric": "Cal+Stage3 microF1 35.9 / macroF1 53.2",
            "status": "READY_CANDIDATE",
            "known_limitations": "F1 中等；多标签压缩有效",
        },
        "function": {
            "primary_provider": "StaticVisionAnalyzerV2", "model": "SigLIP",
            "policy_version": "V2（Top3+gap0.10+min0.02）",
            "support": "STORAGE/EXTENDABLE/POWER/DINING/OFFICE",
            "dev_metric": "Cal+Stage3 microF1 33.2 / macroF1 52.6",
            "status": "READY_CANDIDATE",
            "known_limitations": "同上",
        },
        "scene_family": {
            "primary_provider": "StaticVisionAnalyzerV2", "model": "SigLIP",
            "policy_version": "single top-1",
            "support": "FACTORY 398 / CUSTOMER_HOME 2 / SHOWROOM 1",
            "dev_metric": "FACTORY 极度偏科",
            "status": "LIMITED",
            "known_limitations": "CUSTOMER_HOME/SHOWROOM/INSTALLATION_SITE 数据不足；不当作生产级",
        },
        "material": {
            "primary_provider": "StaticVisionAnalyzerV2", "model": "SigLIP",
            "policy_version": "V1（threshold 0.06）—— V2 已证退化",
            "support": "岩板 403 / 实木 1",
            "dev_metric": "Cal+Stage3 F1 22.2（MIXED/弱）",
            "status": "EXPERIMENTAL/FALLBACK",
            "known_limitations": "SOLID_WOOD/奢石/大理石/不锈钢/玻璃 INSUFFICIENT/LIBRARY_GAP；岩板仅靠分布支持",
        },
        "shot_role": {
            "primary_provider": "StaticVisionAnalyzerV2", "model": "SigLIP",
            "policy_version": "V1（threshold 0.06）—— V3 压缩未达门槛",
            "support": "丰富",
            "dev_metric": "F1 36.9 / pred_avg 7.0",
            "status": "EXPERIMENTAL",
            "known_limitations": "KNOWN_OVERPREDICTION_RISK（pred_avg 7.0 vs human 2.3）；不再 Stage3 调 threshold",
        },
        "product_variant": {
            "primary_provider": "StaticVisionAnalyzerV2", "model": "SigLIP",
            "policy_version": "conservative top-1",
            "support": "EXTENDABLE 199+/STANDARD 10",
            "dev_metric": "EXTENDABLE 有证据",
            "status": "LIMITED",
            "known_limitations": "FLOATING/FLOOR LIBRARY_GAP；低证据 UNKNOWN 优先，禁凭空猜",
        },
        "semantic_action": {
            "primary_provider": "SemanticActionRouterV2（per-action best-known）",
            "model": "SemanticActionAnalyzerV1/V2 组合",
            "router_version": "semantic-action-router-v2",
            "support": "见 per-action map",
            "dev_metric": "见 per-action map",
            "status": "EXPERIMENTAL",
            "known_limitations": "state-change 细粒度未解决；不阻塞 Bundle V2",
        },
    }

    # SemanticActionRouterV2 per-action provider map（STEP 11）
    action_router = {
        "OPEN_DRAWER": {"provider": "V1_RULE", "f1": 30.8, "note": "V1 优于 V2（P100）"},
        "PULL_OUT": {"provider": "V1_RULE_SIMPLE", "f1": 25.4, "note": "V1/V2 相近，用简单稳定路线"},
        "CLOSE_DRAWER": {"provider": "V2_STATE_EXPERIMENTAL", "f1": 11.1, "note": "V2 提供非零能力"},
        "CLOSE_CABINET": {"provider": "V2_STATE_EXPERIMENTAL", "f1": 16.0, "note": "V2 真实增益"},
        "OPEN_CABINET": {"provider": "NO_CLAIM", "f1": 0.0, "note": "不得声称已有能力"},
        "RETRACT": {"provider": "NO_CLAIM", "f1": 0.0, "note": "不得声称已有能力"},
        "OPERATE_SOCKET": {"provider": "INSUFFICIENT_SAMPLE", "f1": None, "support": 2},
        "OPEN_SINK_COVER": {"provider": "INSUFFICIENT_SAMPLE", "f1": None, "support": 4},
        "PERSON_SPEAKING": {"provider": "MOTION_BASELINE", "f1": None, "note": "motion evidence 仅"},
        "STATIC_DISPLAY": {"provider": "MOTION_BASELINE", "f1": None},
        "OTHER": {"provider": "DEFAULT", "f1": 33.1},
    }
    fields["semantic_action"]["action_router"] = action_router

    # ---- Bundle V2 Lock（STEP 14-16 + PROVENANCE FIX）----
    # Git 证据：People NORMAL_YOLO_NO 修复（ran/合法NO）仅在 813fc5a 存在；
    # c4ff7e5 仍为旧 fallback 逻辑（if hits: → SigLIP fallback）。
    # 情况 B → inference_git_commit 必须 = 813fc5a。
    INFERENCE_COMMIT = "813fc5a"  # 含最终 People 路由修复的 Inference 代码
    # 查完整 hash
    import subprocess
    try:
        full = subprocess.run(["git", "-C", r"C:\Users\admin\github\treecut-v13",
                               "rev-parse", INFERENCE_COMMIT],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        full = INFERENCE_COMMIT
    git_commit = full or INFERENCE_COMMIT
    packaging_commit = "813fc5a"  # Final Consolidation 冻结/打包提交
    # 若 packaging 与 inference 相同，记录差异说明
    provenance_note = ("inference_git_commit 与 packaging_commit 均指向 813fc5a："
                       "People YOLO NO 修复、SemanticActionRouterV2、Bundle Lock 全部在该提交冻结；"
                       "旧 Lock（01b7afa9）记录 c4ff7e5 为 provenance 错误（该提交仍是旧 fallback 逻辑），"
                       "已 SUPERSEDED_PROVENANCE_LOCK")
    lock = {
        "bundle_id": "VISION_MODEL_BUNDLE_V2",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "git_code_commit": git_commit,
        "inference_git_commit": git_commit,
        "packaging_commit": packaging_commit,
        "evaluation_commit": packaging_commit,
        "provenance_note": provenance_note,
        "supersedes": "VISION_MODEL_BUNDLE_V2_LOCK（旧 sha 01b7afa9... 标 SUPERSEDED_PROVENANCE_LOCK，未删除）",
        "stage3_dev_snapshot_hash": snapshot_sha,
        "dictionary_version": "ANNOTATION_DICTIONARY_V2_1",
        "stage3_status": "COMPLETE",
        "fields": fields,
        "semantic_action_router": action_router,
        "known_limitations_summary": {
            "scene": "FACTORY 偏科，长尾 LIBRARY_GAP",
            "material": "V1 fallback；实木/奢石/大理石/不锈钢/玻璃 INSUFFICIENT",
            "shot_role": "overprediction",
            "variant": "FLOATING/FLOOR LIBRARY_GAP",
            "semantic_action": "state-change 未解决；6 关键动作无 F1>=30",
        },
        "bundle_definition": "截至 Stage3 结束每字段 best-known frozen route 的不可变组合；"
                             "不要求所有字段 READY；LIMITED/EXPERIMENTAL/FALLBACK 允许共存",
    }
    canon = json.dumps(lock, ensure_ascii=False, sort_keys=True)
    lock["bundle_lock_sha256"] = sha256_str(canon)
    lp = os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V2_LOCK.json")
    json.dump(lock, open(lp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("STEP15: lock ->", lp)
    print("STEP16: bundle_lock_sha256 =", lock["bundle_lock_sha256"])

    # 人工可读 md
    md = ["# VISION_MODEL_BUNDLE_V2", "",
          f"> bundle_id: VISION_MODEL_BUNDLE_V2 · created: {lock['created_at']} · git: {git_commit}",
          f"> bundle_lock_sha256: `{lock['bundle_lock_sha256']}`",
          f"> stage3_dev_snapshot_hash: `{snapshot_sha}`", "",
          "## 9 字段状态", "", "| 字段 | 状态 | Primary | Fallback | Policy | DEV metric |", "|---|---|---|---|---|---|"]
    for name, f in fields.items():
        md.append(f"| {name} | {f['status']} | {f['primary_provider']} | {f.get('fallback_provider','—')} "
                  f"| {f.get('policy_version','—')} | {f.get('dev_metric','—')} |")
    md += ["", "## SemanticActionRouterV2 per-action", ""]
    for a, r in action_router.items():
        md.append(f"- {a}: {r['provider']}（{r.get('note','')}）")
    md += ["", "## 冻结纪律",
           "- Bundle V2 = 每字段 best-known frozen route 不可变组合；LIMITED/EXPERIMENTAL 允许",
           "- Fresh Holdout V1 仅 KNOWN BENCHMARK 参考，不用于 V2 选择",
           "- 冻结后建立 FRESH_HOLDOUT_V2；禁止先看 V2 题再改 Bundle"]
    mdp = os.path.join(DATA_ROOT, "VISION_MODEL_BUNDLE_V2.md")
    open(mdp, "w", encoding="utf-8").write("\n".join(md))
    print("->", mdp)

    # docs 副本
    import shutil
    shutil.copy(mdp, r"C:\Users\admin\github\treecut-v13\docs\VISION_MODEL_BUNDLE_V2.md")
    print("-> docs/VISION_MODEL_BUNDLE_V2.md")


if __name__ == "__main__":
    main()
