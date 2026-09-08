# -*- coding: utf-8 -*-
"""A0 R1 — SOURCE EVIDENCE + CURRENT REPRODUCTION (live collection, no hardcode).

SOURCE: real sha256 of key source files + git blob existence.
REPRO: read actual repro3 project files from disk (mp4 exists, STATUS failed w/ error).
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
OUT = REPO / "reports" / "storage"
INSTALL = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13")
REPRO_PROJ = INSTALL / "runtime_data" / "temp" / "a0r1_repro3" / "output" / "projects" / "20260908_172116_125160"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a):
    return subprocess.run(["git", "-C", str(REPO)] + list(a),
                          capture_output=True, text=True).stdout.strip()


def main():
    # ===== SOURCE EVIDENCE (real) =====
    src_files = [
        "src/treecut/application/production.py",
        "src/treecut/workflow/matching.py",
        "src/treecut/workflow/planning.py",
        "src/treecut/output/mp4.py",
        "src/treecut/output/narration.py",
        "src/treecut/output/jianying.py",
        "src/treecut/output/inspection.py",
        "src/treecut/models/tts_local.py",
        "src/treecut/desktop.py",
        "src/treecut/api.py",
        "src/treecut/asr/engine.py",
        "src/treecut/ocr/engine.py",
        "src/treecut/models/vision_florence.py",
        "src/treecut/scanner/incremental.py",
        "src/treecut/application/jobs.py",
    ]
    src_ev = []
    for rel in src_files:
        p = REPO / rel
        blob = git("rev-parse", "HEAD:" + rel) if (p.exists()) else "NOT_IN_GIT"
        src_ev.append({"path": rel, "exists": p.exists(),
                       "sha256": sha(p) if p.exists() else None,
                       "git_blob_at_head": blob,
                       "bytes": p.stat().st_size if p.exists() else None})
    # caller scan: who imports production service / who calls tts (python scan)
    def grep_imports(term):
        hits = []
        for p in (REPO / "src").rglob("*.py"):
            try:
                if term in p.read_text(encoding="utf-8", errors="ignore"):
                    hits.append(os.path.relpath(p, REPO))
            except Exception:
                pass
        return hits
    src_ev.append({"caller_scan": {
        "imports_ProductionService": grep_imports("ProductionService"),
        "imports_FeedbackStore": grep_imports("FeedbackStore"),
        "imports_semantic_scores": grep_imports("semantic_scores")}})
    (OUT / "TREECUT_A0R1_SOURCE_EVIDENCE.json").write_text(
        json.dumps({"head": git("rev-parse", "HEAD"), "files": src_ev},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    # ===== CURRENT REPRODUCTION (read actual disk) =====
    mp4 = REPRO_PROJ / "01_高清画面底片.mp4"
    status_p = REPRO_PROJ / "STATUS.json"
    repro = {"reproduction_dir": str(REPRO_PROJ),
             "project_exists": REPRO_PROJ.exists()}
    if mp4.exists():
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_type,width,height,duration", "-of", "json", str(mp4)],
                           capture_output=True, text=True, timeout=60)
        repro["mp4"] = {"exists": True, "bytes": mp4.stat().st_size,
                        "sha256": sha(mp4), "ffprobe": r.stdout[:400]}
    else:
        repro["mp4"] = {"exists": False}
    if status_p.exists():
        st = json.loads(status_p.read_text(encoding="utf-8"))
        repro["status"] = st.get("state")
        repro["error"] = st.get("error", "")[:400]
    repro["classification"] = ("CURRENT_REDUCED_CHAIN_REACHED_RENDER_ONLY"
                               if repro.get("mp4", {}).get("exists")
                               else "NOT_REACHED_RENDER")
    repro["first_blocker"] = ("TTS_MODEL_LOAD_CHINESE_PATH" if repro.get("status") == "failed"
                              and "date.fst" in repro.get("error", "")
                              else repro.get("status"))
    (OUT / "TREECUT_A0R1_CURRENT_REPRODUCTION.json").write_text(
        json.dumps(repro, ensure_ascii=False, indent=1), encoding="utf-8")
    print("source evidence + current reproduction written")
    print("mp4 exists:", repro["mp4"]["exists"], "| status:", repro.get("status"))
    print("blocker:", repro.get("first_blocker"))


if __name__ == "__main__":
    main()
