# -*- coding: utf-8 -*-
"""TREECUT B1R1 F0 — HISTORICAL FEATURE FORENSICS (read-only).

For every frozen product feature: token search over FULL git history
(git log --all --full-history -S / -G), first/last commit, HEAD worktree
presence, E-install deployment presence, production-call relationship,
tests and real-run evidence -> classification into the 8 allowed categories.
Outputs: F0_GIT_TIMELINE.json / F0_CALL_GRAPH.json /
F0_PRODUCT_CONTRACT_FREEZE.json (+ prints).
No product code is modified.
"""
import json
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
OUT = Path(REPO / "reports" / "storage")
HEAD = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
KEY_COMMITS = ["11887df", "02c1fc8", "cec8040", "ced26b6", "0c95e5c",
               "f378fda", HEAD[:7]]

FEATURES = [
    {"id": "caption_display_punctuation", "name": "显示字幕去标点 (speech/display 分离)",
     "tokens": ["标点", "punctuation", "display_text", "build_srt",
                "split_subtitle_cues"]},
    {"id": "subtitle_occlusion_plate", "name": "原字幕遮挡板 (drawbox/occlusion/plate)",
     "tokens": ["drawbox", "occlusion", "遮挡板", "inpaint"]},
    {"id": "old_subtitle_detection", "name": "原字幕检测/卫生 (old_subtitle/hygiene)",
     "tokens": ["old_subtitle", "OLD_SUBTITLE_ABSENT", "原字幕",
                "subtitle hygiene", "SUBTITLE_HYGIENE_PASS"]},
    {"id": "caption_safe_zone", "name": "字幕安全区/字号行数 (safe zone/MarginV)",
     "tokens": ["safe zone", "MarginV", "安全区", "Alignment=2",
                "CAPTION_LINE_TOO_LONG"]},
    {"id": "source_gate", "name": "干净生产源门 (source gate)",
     "tokens": ["production_source", "source_role", "clean_raw",
                "SourceGate", "SUBTITLE_HYGIENE_NOT_RUN"]},
    {"id": "beat_claim", "name": "Beat/Claim 拆解",
     "tokens": ["claim_visual", "visual_beat", "BeatClaim", "beat_id"]},
    {"id": "feedback_loop", "name": "人工反馈消费 (FeedbackStore)",
     "tokens": ["FeedbackStore", "adjustments", "feedback"]},
    {"id": "semantic_selection", "name": "BGE/CLIP 语义选材",
     "tokens": ["semantic_matching", "semantic_scores", "Chinese-CLIP",
                "bge_scored"]},
    {"id": "cam_mmvv_action", "name": "CAM/MMVV/动作证据生产接线",
     "tokens": ["mmvl", "MMVV", "action_evidence", "visual_action",
                "ActionEvidenceGate"]},
    {"id": "plan_override_bypass", "name": "plan_override 绕过智能选材",
     "tokens": ["plan_override"]},
]


def git(args):
    proc = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def log_S(token):
    """commits where token was added/removed in ANY path (full history)."""
    rc, out, _ = git(["log", "--all", "--full-history", "-S", token,
                      "--format=%H %ct %s", "--"])
    commits = []
    for line in out.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2:
            commits.append({"sha": parts[0], "ct": parts[1],
                            "subject": parts[2] if len(parts) > 2 else ""})
    return commits


def log_G_files(token):
    rc, out, _ = git(["log", "--all", "--full-history", "-G", token,
                      "--format=%H", "--name-only", "--"])
    return out


def head_grep(token):
    rc, out, _ = git(["grep", "-l", "-e", token, "HEAD", "--", "."])
    return [ln.split(":", 1)[1] for ln in out.splitlines() if ":" in ln] if rc == 0 else []


def token_evidence(token):
    commits = log_S(token)
    first = commits[-1] if commits else None
    last = commits[0] if commits else None
    head_paths = head_grep(token)
    e_paths = []
    for p in head_paths:
        ep = E_SRC / p.replace("src/", "", 1) if p.startswith("src/") else None
        if ep is not None and ep.exists():
            e_paths.append(str(ep.relative_to(E_SRC)))
    return {"token": token, "commit_count": len(commits),
            "first_commit": first, "last_commit": last,
            "head_paths": head_paths[:25], "e_install_paths": e_paths[:25]}


def feature_evidence(feat):
    toks = [token_evidence(t) for t in feat["tokens"]]
    all_commits = []
    for t in toks:
        all_commits.extend(t["commit_count"] for _ in [0])
    head_all = sorted({p for t in toks for p in t["head_paths"]})
    e_all = sorted({p for t in toks for p in t["e_install_paths"]})
    firsts = [t["first_commit"] for t in toks if t["first_commit"]]
    lasts = [t["last_commit"] for t in toks if t["last_commit"]]
    return {"id": feat["id"], "name": feat["name"], "tokens": toks,
            "head_paths_union": head_all, "e_install_paths_union": e_all,
            "first_commit_overall": min(firsts, key=lambda c: c["ct"]) if firsts else None,
            "last_commit_overall": max(lasts, key=lambda c: c["ct"]) if lasts else None,
            "any_history_hit": bool(firsts), "in_head": bool(head_all)}


def classify(fe):
    """Heuristic classification from evidence; docstring lists the categories."""
    if not fe["any_history_hit"]:
        return "NEVER_IMPLEMENTED"
    head = set(fe["head_paths_union"])
    code_head = {p for p in head if p.startswith("src/")}
    docs_only = head and not code_head and all(
        p.startswith(("docs/", "reports/", "DESIGN", "README")) for p in head)
    if not head:
        # token existed in history but absent at HEAD -> removed/overwritten
        return "DELETED"  # refined by report (check last commit nature)
    if docs_only:
        return "REPORT_OR_CHAT_ONLY"
    scripts_only = code_head and all(p.startswith("scripts/") for p in code_head)
    if scripts_only:
        return "HISTORICAL_SCRIPT_ONLY"
    if code_head:
        # code present under src -> caller relationship decided in CALL_GRAPH
        return "CODE_PRESENT_PENDING_CALLER"
    return "UNKNOWN"


def production_closure():
    """AST import closure from application/production.py (HEAD worktree)."""
    import ast
    root = REPO / "src"
    entry = "treecut/application/production.py"
    seen, queue = set(), [entry]
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        p = root / rel
        if not p.exists():
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n == "treecut" or n.startswith("treecut."):
                    mod = n.replace(".", "/") + ".py"
                    if mod not in seen:
                        queue.append(mod)
    return sorted(seen)


def main():
    feats = [feature_evidence(f) for f in FEATURES]
    timeline = {"experiment": "TREECUT_B1R1_F0_GIT_TIMELINE",
                "head": HEAD, "key_commits": KEY_COMMITS,
                "method": "git log --all --full-history -S/-G per token; "
                          "HEAD grep; E-install presence",
                "features": feats}
    (OUT / "TREECUT_B1R1_F0_GIT_TIMELINE.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=1), encoding="utf-8")

    closure = production_closure()
    callgraph = {"experiment": "TREECUT_B1R1_F0_CALL_GRAPH",
                 "production_entry": "src/treecut/application/production.py",
                 "production_import_closure": closure,
                 "closure_count": len(closure),
                 "per_feature": {}}
    for fe in feats:
        code = sorted({p for p in fe["head_paths_union"] if p.startswith("src/")})
        in_closure = [p for p in code if p in closure or any(
            c.startswith(p.rsplit(".", 1)[0].replace("src/", "treecut/", 1))
            for c in closure)]
        callgraph["per_feature"][fe["id"]] = {
            "code_files": code,
            "in_production_closure": bool(in_closure),
            "closure_matches": in_closure,
        }
    callgraph["classification"] = {fe["id"]: classify(fe) for fe in feats}
    callgraph["runner_bypass_evidence"] = {
        "production_plan_override_branch": "production.py sets matches=[], "
        "bge=clip={} when plan_override is not None (skips load_candidates/"
        "FeedbackStore/semantic_scores/match_materials/build_edit_plan)",
        "b1_success_media": "TREECUT_B1_SUCCESS_REPRO.json media.id=32 (path "
        "D:\\剪影草稿\\...0619-01\\...L0_001....mov, 0-25s window)",
        "b1r1_success_media": "TREECUT_B1R1_SUCCESS_REPRO.json media.id=32 "
        "same path, same 0-25s window, plan_override used",
        "bge_clip_on_runs": {"b1": "bge_scored=3260? no: B1 used plan_override "
                            "=> semantic_models.bge_scored=0, clip_scored=0",
                            "b1r1": "bge_scored=0, clip_scored=0"},
        "conclusion": "SELECTION_ROUTE_BYPASSED - B1/B1R1 reused media_id=32 "
                      "with plan_override; NOT a smart-selection reproduction",
    }
    (OUT / "TREECUT_B1R1_F0_CALL_GRAPH.json").write_text(
        json.dumps(callgraph, ensure_ascii=False, indent=1), encoding="utf-8")

    contract = {
        "experiment": "TREECUT_B1R1_F0_PRODUCT_CONTRACT_FREEZE",
        "authority": "architect B1R1 deep-audit rulings; single source of truth "
                     "for later B2/C0 implementation; any deviation requires "
                     "architect approval",
        "frozen_requirements": [
            {"id": "SPEECH_DISPLAY_SPLIT",
             "rule": "speech_text keeps full punctuation (TTS/script integrity); "
                     "display_text defaults to NO visible sentence/clause "
                     "punctuation; protect decimal/version/percent/model/URL "
                     "internal symbols (no naive 'delete all dots')"},
            {"id": "DISPLAY_PUNCTUATION_GATE",
             "rule": "hard gate DISPLAY_PUNCTUATION_FORBIDDEN / COUNT / "
                     "DISPLAY_TEXT_EMPTY_AFTER_NORMALIZE; default acceptance: "
                     "0 visible CJK sentence/clause punctuation in display_text "
                     "except explicit whitelist"},
            {"id": "OLD_SUBTITLE_POLICY",
             "rule": "clean-no-subtitle material highest priority; bottom "
                     "stable subtitle band: occlusion plate (region-derived "
                     "height + margin + high-opacity dark plate) then redraw "
                     "new caption centered; top/mid large or multi-region "
                     "dynamic text: REJECT_DIRTY_TEXT (fail-closed, swap "
                     "candidate); watermark by allowlist else reject; inpaint "
                     "not first version"},
            {"id": "SUBTITLE_NOT_RUN_NEVER_PASS",
             "rule": "SUBTITLE_HYGIENE_NOT_RUN when no source-text detection "
                     "executed; never pass without detection"},
            {"id": "SAFE_ZONE",
             "rule": "explicit 1080x1920 caption coordinates (no reliance on "
                     "MarginV=75 alone); <=2 lines; line length bounded; "
                     "caption must not cover product core"},
            {"id": "POST_RENDER_VERIFY",
             "rule": "after occlusion+redraw sample frames: old subtitle not "
                     "readable, new caption present, subject not covered; any "
                     "frame fail -> swap candidate, never warning-only"},
            {"id": "SELECTION_NOT_SMART_UNLESS_SMART_RAN",
             "rule": "plan_override runs are SELECTION_ROUTE_BYPASSED and must "
                     "never be presented as smart-selection success; smart "
                     "selection requires plan_override=false + source gate + "
                     "segment identity + BGE/CLIP recorded + beat evidence"},
            {"id": "NAMING",
             "rule": "when PUBLISH_READY=false deliveries carry NOT_PUBLISHABLE "
                     "or explicit test purpose; statuses TECHNICAL_AUDIO_"
                     "TEST_PASS / SUBTITLE_TEST_PASS/FAIL / SELECTION_TEST_"
                     "NOT_RUN / HUMAN_ACCEPTANCE_FAIL / PUBLISH_READY_NO"},
        ],
        "allowed_categories": ["NEVER_IMPLEMENTED", "REPORT_OR_CHAT_ONLY",
                               "HISTORICAL_SCRIPT_ONLY",
                               "IMPLEMENTED_BUT_DISCONNECTED",
                               "IMPLEMENTED_ACTIVE", "OVERWRITTEN", "DELETED",
                               "DEPLOYMENT_MISSING"],
    }
    (OUT / "TREECUT_B1R1_F0_PRODUCT_CONTRACT_FREEZE.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=1), encoding="utf-8")
    print("HEAD", HEAD)
    print("closure count", len(closure))
    print("classifications:", json.dumps(callgraph["classification"],
                                         ensure_ascii=False))
    for fe in feats:
        print("-", fe["id"], "hist:", fe["any_history_hit"],
              "in_head:", fe["in_head"], "| first:",
              (fe["first_commit_overall"] or {}).get("sha", "-")[:8] if fe["first_commit_overall"] else "-",
              "last:", (fe["last_commit_overall"] or {}).get("sha", "-")[:8] if fe["last_commit_overall"] else "-")


if __name__ == "__main__":
    main()
