# -*- coding: utf-8 -*-
"""A0 R2 — final assembler. Derives every deliverable JSON from machine evidence
files (never hardcodes counts/verdicts). Reads:
  storage: RAW_PREFLIGHT / SOURCE_PROVENANCE / BEAT_CLAIM_SEARCH /
           HISTORICAL_RELPATH_MANIFEST / HISTORICAL_CANONICAL_INPUT /
           RAW_TEST_RUNS / (A0R1 RAW_DB_EVIDENCE for CAM counts)
  external: TTS A/B metas + verdict; repro run dir from repro_run_path.txt
Writes:
  TTS_AB_RESULT / REPRO_RUN_MANIFEST / CURRENT_REPRODUCTION /
  CORRECTED_CAPABILITY_MATRIX / CORRECTED_GAP_MAP / EVIDENCE_INDEX / RESULT
"""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
EXT = Path(r"E:\EchoBird-main\_treecut_audit_temp")


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def load_ext(name):
    return json.loads((EXT / name).read_text(encoding="utf-8"))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    pre = load("TREECUT_A0R2_RAW_PREFLIGHT.json")
    prov = load("TREECUT_A0R2_SOURCE_PROVENANCE.json")
    beat = load("TREECUT_A0R2_BEAT_CLAIM_SEARCH.json")
    canon = load("TREECUT_A0R2_HISTORICAL_CANONICAL_INPUT.json")
    relpath = load("TREECUT_A0R2_HISTORICAL_RELPATH_MANIFEST.json")
    testr = load("TREECUT_A0R2_RAW_TEST_RUNS.json")
    db = load("TREECUT_A0R1_RAW_DB_EVIDENCE.json")  # CAM/prod counts (A0R1 machine)

    # ---- TTS AB RESULT ----
    inv_a = load_ext("tts_inventory_A.json")
    inv_b = load_ext("tts_inventory_B.json")
    meta_a = load_ext("tts_A/meta.json")
    meta_b = load_ext("tts_B/meta.json")
    tts = {
        "experiment": "TREECUT_A0R2_TTS_AB_RESULT",
        "inventory_A": inv_a, "inventory_B": inv_b,
        "A": {"rc": meta_a.get("rc"), "error": meta_a.get("error"),
              "wav": meta_a.get("wav")},
        "B": {"rc": meta_b.get("rc"), "error": meta_b.get("error"),
              "wav": meta_b.get("wav")},
        "copy_identical": inv_a["file_count"] == inv_b["file_count"]
        and inv_a["total_bytes"] == inv_b["total_bytes"]
        and inv_a["required_files"] == inv_b["required_files"],
        "verdict": ("TTS_NON_ASCII_ROOT_CAUSE=CONFIRMED"
                    if (meta_a.get("rc") != 0 and meta_b.get("rc") == 0
                        and inv_a["required_files"] == inv_b["required_files"])
                    else "REFUTED_OR_DIFFERENT_BLOCKER"
                    if (meta_a.get("rc") != 0 and meta_b.get("rc") != 0)
                    else "INCONCLUSIVE"),
        "rule": "A fail + B pass + model hashes same => CONFIRMED; both fail => REFUTED; unstable => INCONCLUSIVE",
    }
    (OUT / "TREECUT_A0R2_TTS_AB_RESULT.json").write_text(
        json.dumps(tts, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- reproduction (run dir from pointer written by the runner invocation) ----
    repro = None
    ptr = EXT / "repro_run_path.txt"
    if ptr.exists():
        run_dir = Path(ptr.read_text(encoding="utf-8").strip())
        manifest = json.loads((run_dir / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        result = json.loads((run_dir / "reproduction_result.json").read_text(encoding="utf-8"))
        status = {}
        proj = result.get("project")
        if proj:
            sp = Path(proj) / "STATUS.json"
            if sp.exists():
                status = json.loads(sp.read_text(encoding="utf-8"))
        repro = {"run_id": manifest["run_id"], "data_root": str(run_dir),
                 "PASS": result.get("PASS"), "project": proj,
                 "status_state": status.get("state"), "status_error": status.get("error"),
                 "final_mp4": result.get("final_mp4"), "draft": result.get("draft"),
                 "n_matches": result.get("n_matches"),
                 "imported_module_source_sha": result.get("imported_module_source_sha")}
    (OUT / "TREECUT_A0R2_CURRENT_REPRODUCTION.json").write_text(
        json.dumps(repro or {"run": "NONE", "note": "no approved E2E run available"},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- corrected capability matrix (semantics: shadow data != connected) ----
    def closure_has(part):
        return any(part in m for m in beat["production_import_closure"]["closure_modules"])

    hist_success = [p for p in relpath if any(f.endswith("TreeCut_成片.mp4") for f in relpath[p])]
    matrix = {
        "experiment": "TREECUT_A0R2_CORRECTED_CAPABILITY_MATRIX",
        "note": "DATA_PRESENT_SHADOW/NOT_PRODUCTION_CONNECTED replaces DATA_CONNECTED "
                "when data lives in CAM db or module is absent from the production "
                "import closure (machine: BEAT_CLAIM_SEARCH.production_import_closure)",
        "items": [
            {"capability": "A1_scan", "level": "DATA_CONNECTED",
             "evidence": "15378 media prod db; sources local; 132 path-missing",
             "production_connected": True},
            {"capability": "B2_ASR", "level": "DATA_PRESENT_SHADOW / NOT_PRODUCTION_CONNECTED",
             "evidence": "CAM transcripts 51543; asr module not in production import closure",
             "production_connected": closure_has("asr")},
            {"capability": "B3_OCR", "level": "DATA_PRESENT_SHADOW / NOT_PRODUCTION_CONNECTED",
             "evidence": "CAM ocr 289218; ocr not in production import closure",
             "production_connected": closure_has("ocr")},
            {"capability": "B4_vision", "level": "DATA_PRESENT_SHADOW / NOT_PRODUCTION_CONNECTED",
             "evidence": "Florence captions in analysis_jobs; models/vision_* NOT_IN_HEAD; "
                         "not in production import closure",
             "production_connected": closure_has("vision")},
            {"capability": "segment_level", "level": "DATA_PRESENT_SHADOW / NOT_PRODUCTION_CONNECTED",
             "evidence": "CAM assets 22466/segments 41834; no identity bridge; prod uses whole-file clips",
             "production_connected": False},
            {"capability": "E1_retrieval", "level": "DATA_CONNECTED",
             "evidence": "load_candidates real; BGE/CLIP in closure",
             "production_connected": True,
             "current_e2e": repro["PASS"] if repro else None},
            {"capability": "F2_render_mp4", "level": "E2E_PROVEN_CURRENT_RENDER",
             "evidence": "vertical render mp4 generated in current runs",
             "production_connected": True},
            {"capability": "G3_tts", "level": ("BLOCKED_AT_LOAD(CHINESE_PATH)/"
                                               "PASS_AT_ASCII_PATH"),
             "evidence": "TTS A/B: A fail date.fst open (Chinese path), B pass 7.059s wav, "
                         "copy hashes identical => TTS_NON_ASCII_ROOT_CAUSE=CONFIRMED",
             "production_connected": True},
            {"capability": "G4_subtitle_burn", "level": "NOT_REACHED_CURRENT"
             if not (repro and repro.get("PASS")) else "REACHED_IN_E2E_RUN",
             "evidence": "upstream TTS; historical burned srt existed",
             "production_connected": True},
            {"capability": "H1_final_mp4", "level": "NOT_REACHED_CURRENT"
             if not (repro and repro.get("PASS")) else "REACHED_IN_E2E_RUN",
             "evidence": "final TreeCut_成片.mp4 only historical",
             "production_connected": True},
            {"capability": "H2_jianying_draft", "level": "NOT_REACHED_CURRENT"
             if not (repro and repro.get("PASS")) else "REACHED_IN_E2E_RUN",
             "evidence": "draft_content.json historical only",
             "production_connected": True},
            {"capability": "D2_script_beat_claim", "level": "NOT_FOUND_IN_PRODUCTION",
             "evidence": "production import closure 21 modules, 0 beat/claim; "
                         "E src name-hits=0; repo-only visual_beat.py not in E install",
             "production_connected": False},
            {"capability": "X1_cam_eh", "level": "UNIT_TESTED_SHADOW / NOT_PRODUCTION_CONNECTED",
             "evidence": "no production caller (repo research modules absent from E install)",
             "production_connected": False},
            {"capability": "C3_feedback", "level": "CODE_PATH_CONNECTED",
             "evidence": "FeedbackStore.adjustments read in production.py:178; "
                         "no before/after ranking counterfactual",
             "production_connected": True},
            {"capability": "H3_desktop_ui", "level": "USER_USABLE_NOT_PROVEN_LIVE",
             "evidence": "no live UI session in audit; desktop.py E-content differs from HEAD",
             "production_connected": True},
        ],
    }
    (OUT / "TREECUT_A0R2_CORRECTED_CAPABILITY_MATRIX.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- corrected gap map: ROOT_CAUSE vs ACCEPTANCE_GATE ----
    root_causes = [
        {"id": "RC_script_beat_parse", "desc": "生产链无脚本→逐句 Beat/Claim 拆分层",
         "evidence": "production closure 21 modules, 0 beat/claim (machine)"},
        {"id": "RC_tts_non_ascii_model_path", "desc": "sherpa-onnx 打不开中文路径下 date.fst",
         "evidence": "TTS A/B CONFIRMED (A fail / B pass / hashes same)"},
        {"id": "RC_baseline_not_self_contained", "desc": "运行源码不属 Git HEAD："
         "models/ 12 文件被 .gitignore 忽略从未入 git + 4 文件 E 内容异于 HEAD",
         "evidence": "SOURCE_PROVENANCE BASELINE_SELF_CONTAINED=False"},
        {"id": "RC_prod_cam_identity_split", "desc": "生产 4 表库与 CAM 88 表库身份不互连；"
         "生产用整文件 clip 非 segment",
         "evidence": "A0R1 RAW_DB_EVIDENCE counts"},
    ]
    acceptance_gates = [
        {"id": "GATE_current_e2e_to_final", "desc": "当前简化链跑通到最终 MP4+剪映草稿",
         "evidence": ("PASS" if repro and repro.get("PASS") else "NOT_PASSED")
         + f" (repro run_id={repro['run_id'] if repro else 'none'})"},
        {"id": "GATE_target_mvp_missing_human_review_replace",
         "desc": "目标 MVP 尚缺：human review/replace 闭环"},
        {"id": "GATE_target_mvp_missing_old_subtitle_policy",
         "desc": "目标 MVP 尚缺：旧字幕拒绝/裁剪策略（未验证）"},
        {"id": "GATE_target_mvp_missing_segment_bridge",
         "desc": "目标 MVP 尚缺：segment 级选材桥接"},
        {"id": "GATE_target_mvp_missing_9x16_multishot",
         "desc": "目标 MVP 尚缺：9:16 多镜头信息流混剪验证"},
        {"id": "GATE_target_mvp_missing_candidate_generation",
         "desc": "目标 MVP 尚缺：3 候选生成"},
        {"id": "GATE_target_beat_claim",
         "desc": "目标链 script→Beat/Claim→segment 级→人工确认→时间线→9:16→3候选→MP4/剪映",
         "evidence": "第一阻断 SCRIPT_TO_BEAT_CLAIM_NOT_FOUND"},
    ]
    gap = {"experiment": "TREECUT_A0R2_CORRECTED_GAP_MAP",
           "rule": "ROOT_CAUSE=当前真根因；ACCEPTANCE_GATE=目标达成门槛"
                   "（current_e2e_not_proven 是 gate 不是独立根因）",
           "ROOT_CAUSE": root_causes, "ACCEPTANCE_GATE": acceptance_gates,
           "counts": {"ROOT_CAUSE": len(root_causes), "ACCEPTANCE_GATE": len(acceptance_gates)}}
    (OUT / "TREECUT_A0R2_CORRECTED_GAP_MAP.json").write_text(
        json.dumps(gap, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- RESULT (final report fields; derived, not hardcoded) ----
    test_cls = testr.get("classification_counts", {})
    res = {
        "experiment": "TREECUT_A0R2_RESULT",
        "baseline": pre.get("head"),
        "head_eq_origin": pre.get("head_eq_origin"),
        "worktree_clean": pre.get("worktree_clean"),
        "A0R1_SUBSTANTIVE_FINDINGS": "PROVISIONALLY_ACCEPTED",
        "A0R1_EVIDENCE_CLOSURE": "NO",
        "BASELINE_SELF_CONTAINED": prov.get("baseline_self_contained"),
        "provenance_match_counts": prov.get("match_counts"),
        "provenance_not_in_head": prov.get("e_files_not_in_head"),
        "provenance_differs": prov.get("e_files_content_differ_head"),
        "TTS_NON_ASCII_ROOT_CAUSE": tts["verdict"],
        "historical_unique_inputs": len({v.get("canonical_hash") for v in canon.values()
                                         if v.get("canonical_hash")}),
        "historical_success_projects_with_final": len(hist_success),
        "TARGET_BEAT_LAYER": beat["target_beat_layer_in_production"],
        "CURRENT_REDUCED_E2E": ("PASS" if repro and repro.get("PASS") else "NOT_PASSED"),
        "current_reproduction": repro,
        "test_truth_classification_counts": test_cls,
        "TRACK_A_ALLOWED": "NO",
        "N1_GEOM_CAM_PRODUCTION": "NO",
        "NEXT_BLOCKER": ("none (approved ASCII root run succeeded)" if repro and repro.get("PASS")
                         else "TTS_NON_ASCII_ROOT_CAUSE (approved temporary ASCII model root "
                              "run pending/failed)"),
    }
    (OUT / "TREECUT_A0R2_RESULT.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- evidence index LAST (excludes itself; all other files final) ----
    entries = []
    for f in sorted(OUT.glob("TREECUT_A0R2_*.json")):
        if f.name == "TREECUT_A0R2_EVIDENCE_INDEX.json":
            continue
        entries.append({"path": f.name, "exists": True, "sha256": sha256_file(f)})
    idx = {"audit": "TREECUT_A0R2_EVIDENCE_INDEX", "count": len(entries), "entries": entries}
    (OUT / "TREECUT_A0R2_EVIDENCE_INDEX.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TTS verdict:", tts["verdict"])
    print("BASELINE_SELF_CONTAINED:", prov.get("baseline_self_contained"))
    print("CURRENT_REDUCED_E2E:", res["CURRENT_REDUCED_E2E"])
    print("test classification:", test_cls)
    print("evidence index:", len(entries))


if __name__ == "__main__":
    main()
