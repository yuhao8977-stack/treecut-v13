# -*- coding: utf-8 -*-
"""TREECUT B0 — A0R2 ERRATA + COMPACT EVIDENCE archive.

Records errata against A0R2 (never rewrites the A0R2 history files) and builds a
compact evidence JSON: original RUN_MANIFEST / reproduction_result /
production_report key fields / output manifest(size+sha256+ffprobe summary) /
TTS A-B raw meta / pytest JUnit file sha256 + real exit codes.
No MP4 / models / DB / big files are embedded.
"""
import hashlib
import json
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
EXT = Path(r"E:\EchoBird-main\_treecut_audit_temp")
RUN = EXT / "a0r2_repro_20260908_184606_986514"
PROJ = RUN / "output" / "projects" / "20260908_184619_988409"
FFPROBE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffprobe.exe")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_summary(p: Path) -> dict:
    import subprocess
    try:
        proc = subprocess.run([str(FFPROBE), "-v", "quiet", "-print_format", "json",
                               "-show_format", "-show_streams", str(p)],
                              capture_output=True, timeout=60)
        d = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        return {"streams": [{"codec_type": s.get("codec_type"),
                             "width": s.get("width"), "height": s.get("height"),
                             "r_frame_rate": s.get("r_frame_rate"),
                             "duration": s.get("duration")} for s in d.get("streams", [])],
                "format_duration": (d.get("format") or {}).get("duration")}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main():
    # ---- errata ----
    preflight_ff = (EXT / "preflight_20260908_183213" / "ffmpeg.txt").read_text(
        encoding="utf-8-sig", errors="replace")
    ff_version = "8.0.1" if "8.0.1" in preflight_ff else (
        "8.1.1" if "8.1.1" in preflight_ff else "UNKNOWN")
    errata = {
        "experiment": "TREECUT_B0_A0R2_ERRATA_AND_DECISION",
        "note": "errata to A0 R2 report; historical A0R2 files NOT rewritten",
        "adjudications": {"A0R2_CORE_FINDINGS": "ACCEPTED_FOR_DECISION",
                          "MASTER_AUDIT_PHASE": "COMPLETE",
                          "PERMANENT_ASCII_MODEL_ROOT": "APPROVED",
                          "TRACK_A_ALLOWED": "NO",
                          "N1_GEOM_CAM_PRODUCTION": "NO",
                          "CLIP_DEFECT": "OPEN_UNCHANGED (first product defect after B0)"},
        "errata": [
            {"id": "E1_ffmpeg_version", "report_said": "8.1.1", "correct": ff_version,
             "evidence": "RAW_PREFLIGHT ffmpeg.txt first line: "
                         + (preflight_ff.splitlines()[1] if len(preflight_ff.splitlines()) > 1
                            else preflight_ff)},
            {"id": "E2_tts_hash_claim", "issue": "A0R2 said '20 files hashes identical'; "
             "evidence only proves key required-file hashes (date.fst/model.onnx/tokens/"
             "lexicon/model.int8) + total count/bytes equal",
             "correct_statement": "copy identical at file_count=20, total_bytes=191246256, "
                                  "and 5 required-file sha256 equal (not all 20 files)"},
            {"id": "E3_h1_h2_levels", "issue": "capability matrix H1/H2 evidence still said "
             "'historical only' while current ASCII-root E2E reached final MP4 + Jianying "
             "draft; corrected level REACHED_IN_E2E_RUN (see CORRECTED_CAPABILITY_MATRIX)"},
            {"id": "E4_next_blocker", "issue": "RESULT NEXT_BLOCKER='none' was wrong",
             "correct": "NEXT_BLOCKER=B0_SOURCE_OF_TRUTH_RECONCILIATION (git baseline not "
                        "self-contained at A0R2 close)"},
            {"id": "E5_e2e_quality_scope", "issue": "Chinese-CLIP reranker errored "
             "(clip_scored=0, BGE 3260 fallback) => A0R2 E2E proves the technical chain "
             "runs, NOT material-selection quality"},
        ],
    }
    (OUT / "TREECUT_B0_A0R2_ERRATA_AND_DECISION.json").write_text(
        json.dumps(errata, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- compact evidence ----
    run_manifest = json.loads((RUN / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
    repro_result = json.loads((RUN / "reproduction_result.json").read_text(encoding="utf-8"))
    report = json.loads((PROJ / "production_report.json").read_text(encoding="utf-8"))
    status = json.loads((PROJ / "STATUS.json").read_text(encoding="utf-8"))
    output_files = {}
    for f in sorted(PROJ.rglob("*")):
        if f.is_file():
            rel = f.relative_to(PROJ).as_posix()
            entry = {"size": f.stat().st_size, "sha256": sha256_file(f)}
            if f.suffix.lower() in (".mp4", ".wav"):
                entry["ffprobe"] = ffprobe_summary(f)
            output_files[rel] = entry
    tts_a = json.loads((EXT / "tts_A" / "meta.json").read_text(encoding="utf-8"))
    tts_b = json.loads((EXT / "tts_B" / "meta.json").read_text(encoding="utf-8"))
    inv_a = json.loads((EXT / "tts_inventory_A.json").read_text(encoding="utf-8"))
    inv_b = json.loads((EXT / "tts_inventory_B.json").read_text(encoding="utf-8"))
    junit = {}
    for stem in ("system_full", "runtime_full", "reorder_first",
                 "iso_test_source_audit_r11", "iso_test_stage3_mini_v2",
                 "iso_test_stage3_model_dev"):
        jx = EXT / "tests" / f"{stem}_junit.xml"
        lg = EXT / "tests" / f"{stem}_raw.log"
        if jx.exists():
            entry = {"sha256": sha256_file(jx)}
            if lg.exists():
                tail = [ln for ln in lg.read_text(encoding="utf-8",
                                                  errors="replace").splitlines()
                        if ln.startswith("# exit_code=")]
                entry["exit_code_line"] = tail[-1] if tail else ""
            junit[stem] = entry
    compact = {
        "experiment": "TREECUT_B0_COMPACT_EVIDENCE",
        "run_manifest": run_manifest,
        "reproduction_result": {k: v for k, v in repro_result.items()
                                if k != "imported_module_source_sha"},
        "imported_module_sha_count": len(repro_result.get("imported_module_source_sha", {})),
        "status": status,
        "production_report_key_fields": {
            "quality_passed": report.get("quality", {}).get("passed"),
            "critical_failed": [c for c in report.get("quality", {}).get("checks", [])
                                if c.get("critical") and not c.get("passed")],
            "semantic": report.get("semantic_models"),
            "matches": [m.get("media_id") for m in report.get("matches", [])],
            "plan": {"segments": len(report.get("plan", {}).get("segments", [])),
                     "planned_duration": report.get("plan", {}).get("planned_duration")},
        },
        "output_manifest": output_files,
        "tts_ab_raw": {"A_meta": tts_a, "B_meta": tts_b,
                       "inventory_A": inv_a, "inventory_B": inv_b},
        "pytest_junit_sha256_and_exit": junit,
        "no_large_files_embedded": True,
    }
    (OUT / "TREECUT_B0_COMPACT_EVIDENCE.json").write_text(
        json.dumps(compact, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ffmpeg actual:", ff_version)
    print("output files:", len(output_files), "| junit files:", len(junit))
    print("report quality passed:", report.get("quality", {}).get("passed"))


if __name__ == "__main__":
    main()
