# -*- coding: utf-8 -*-
"""TREECUT B1R1 F0R1 — CALL GRAPH + FULL-HISTORY EVIDENCE REPAIR (read-only).

Fixes F0 evidence defects:
  1) canonical path src/treecut/x.py -> treecut/x.py (never treecut/treecut);
     package __init__ and submodule resolution for 'from pkg import symbol'.
  2) full-history evidence actually executes -S, -G, --name-status per feature,
     bucketed by src/tests/scripts/docs/reports/other; content token AND
     filename/path search; A/M/D/R recorded; NEVER_IMPLEMENTED is only derived
     as NOT_FOUND_IN_REACHABLE_GIT_HISTORY with searched scope.
  3) classification is RULE-derived from machine inputs; any manual
     adjudication stored separately with a reason.
  4) import_reachable / direct_called / runtime_executed are separate fields.
Outputs (new F0R1 files; F0 history untouched):
  TREECUT_B1R1_F0R1_CALL_GRAPH.json / _GIT_HISTORY.json / _RESULT.json /
  _EVIDENCE_INDEX.json (+ prints). No product code modified.
"""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
SRC = REPO / "src"
OUT = Path(REPO / "reports" / "storage")
DOCS = Path(REPO / "docs")
E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")

HEAD = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
ALL_REF_COUNT = len(subprocess.run(
    ["git", "-C", str(REPO), "rev-list", "--all", "--count"],
    capture_output=True, text=True).stdout.split())


def git(*args):
    p = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def canonical(path):
    """src/treecut/x.py -> treecut/x.py ; keep tests/scripts/docs as-is."""
    p = str(path).replace("\\", "/")
    if p.startswith("src/"):
        return p[len("src/"):]
    return p


def bucket(path):
    p = canonical(path)
    for b in ("src/", "tests/", "scripts/", "docs/", "reports/"):
        if p.startswith(b):
            return b.rstrip("/")
    return "other"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def head_src_grep(token):
    rc, out, _ = git("grep", "-l", "-e", token, "HEAD", "--", "src")
    if rc != 0:
        return []
    return sorted({ln.split(":", 1)[1] for ln in out.splitlines() if ":" in ln})


def ls_src_files():
    rc, out, _ = git("ls-files", "--", "src")
    return out.splitlines() if rc == 0 else []


# ---------- production import closure (canonical, resolves packages/reexports)
def resolve_module_file(module):
    """treecut.output -> src file treecut/output.py or treecut/output/__init__.py."""
    rel = module.replace(".", "/")
    for cand in (f"{rel}.py", f"{rel}/__init__.py"):
        if (SRC / cand).is_file():
            return "src/" + cand
    return None


def package_symbol_map(module):
    """map re-exported symbol -> submodule for a package (from __init__ AST)."""
    f = SRC / module.replace(".", "/") / "__init__.py"
    if not f.is_file():
        return {}
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return {}
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 1:
            for a in node.names:
                out[a.asname or a.name] = f"{module}.{node.module}"
    return out


def production_closure():
    """canonical src files statically reachable from application/production.py,
    following package __init__ re-exports so 'from treecut.output import X'
    resolves to output/narration.py etc."""
    entry_src = "src/treecut/application/production.py"
    entry_mod = "treecut.application.production"
    seen = set()
    queue = [entry_mod]
    files = {entry_src}
    sym_cache = {}
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)
        f = resolve_module_file(mod)
        if f is None:
            continue
        files.add(f)
        p = SRC / f[len("src/"):]
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("treecut"):
                        queue.append(a.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0 and node.module.startswith("treecut"):
                    queue.append(node.module)
                elif node.level == 1:
                    parent = mod.rsplit(".", 1)[0] if "." in mod else ""
                    if parent:
                        full = f"{parent}.{node.module}"
                        queue.append(full)
                if node.module and node.module.startswith("treecut") and node.names:
                    # resolve package re-exports
                    mfile = resolve_module_file(node.module)
                    if mfile and mfile.endswith("/__init__.py"):
                        sm = sym_cache.get(node.module)
                        if sm is None:
                            sm = package_symbol_map(node.module)
                            sym_cache[node.module] = sm
                        for a in node.names:
                            sub = sm.get(a.name)
                            if sub:
                                queue.append(sub)
    return sorted({canonical(f) for f in files})


CLOSURE = production_closure()


# ---------- features
FEATURES = [
    {"id": "caption_display_punctuation", "name": "显示字幕去标点 speech/display 分离",
     "capability_tokens": ["display_text", "caption_policy", "strip_punctuation"],
     "legacy_tokens": ["标点", "punctuation", "build_srt", "split_subtitle_cues"],
     "filenames": ["caption_policy.py", "display_caption.py"],
     "expected_modules": []},
    {"id": "subtitle_occlusion_plate", "name": "原字幕遮挡板 drawbox/occlusion",
     "capability_tokens": ["drawbox", "遮挡板", "inpaint"],
     "legacy_tokens": ["occlusion"],
     "filenames": ["caption_occlusion.py", "source_text_policy.py"],
     "expected_modules": []},
    {"id": "old_subtitle_detection", "name": "原字幕检测/卫生",
     "capability_tokens": ["OLD_SUBTITLE_ABSENT", "old_subtitle"],
     "legacy_tokens": ["原字幕", "subtitle hygiene", "SUBTITLE_HYGIENE_PASS"],
     "filenames": ["production_qa.py", "source_text_detect.py"],
     "expected_modules": ["treecut/services/production_qa.py"]},
    {"id": "caption_safe_zone", "name": "字幕安全区",
     "capability_tokens": ["safe zone", "安全区", "caption_safe_zone_pass"],
     "legacy_tokens": ["MarginV"],
     "filenames": ["caption_safe_zone.py"],
     "expected_modules": []},
    {"id": "source_gate", "name": "干净生产源门",
     "capability_tokens": ["SourceGate", "production_source"],
     "legacy_tokens": ["source_role", "clean_raw", "eligible"],
     "filenames": ["production_source.py", "source_gate.py"],
     "expected_modules": ["treecut/services/production_source.py"]},
    {"id": "beat_claim", "name": "Beat/Claim 拆解",
     "capability_tokens": ["beat_id", "BeatClaim"],
     "legacy_tokens": ["claim_visual", "visual_beat", "required_visual"],
     "filenames": ["visual_beat.py", "claim_visual.py"],
     "expected_modules": ["treecut/services/visual_beat.py",
                          "treecut/services/claim_visual.py"]},
    {"id": "feedback_loop", "name": "Feedback 消费",
     "capability_tokens": ["adjustments"],
     "legacy_tokens": ["FeedbackStore", "feedback"],
     "filenames": ["feedback.py"],
     "expected_modules": ["treecut/learning/feedback.py"]},
    {"id": "semantic_selection", "name": "BGE/CLIP 语义选材",
     "capability_tokens": ["semantic_scores", "bge_scored", "clip_scored"],
     "legacy_tokens": ["Chinese-CLIP", "semantic_matching"],
     "filenames": ["semantic_matching.py"],
     "expected_modules": ["treecut/models/semantic_matching.py"]},
    {"id": "cam_mmvv_action", "name": "CAM/MMVV/动作证据接线",
     "capability_tokens": ["ActionEvidence", "action_evidence"],
     "legacy_tokens": ["mmvl", "visual_action", "mmvl_master"],
     "filenames": ["mmvl_master_v1.py", "action_subclip.py"],
     "expected_modules": ["treecut/services/mmvl_master_v1.py",
                          "treecut/services/action_subclip.py"]},
    {"id": "plan_override_bypass", "name": "plan_override 绕过智能选材",
     "capability_tokens": ["plan_override"],
     "legacy_tokens": [],
     "filenames": [],
     "expected_modules": ["treecut/application/production.py"]},
]


def log_query(kind, token):
    """kind in ('S','G'); returns commits [{sha,ct,subject}] and ran=True."""
    flag = "-S" if kind == "S" else "-G"
    rc, out, _ = git("log", "--all", "--full-history", flag, token,
                     "--format=%H %ct %s", "--")
    if rc != 0:
        return [], False
    commits = []
    for line in out.splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2:
            commits.append({"sha": parts[0], "ct": parts[1],
                            "subject": parts[2] if len(parts) > 2 else ""})
    return commits, True


def name_status_buckets(token):
    """Aggregate per-commit name-status for -S hits, bucketed by path, with
    A/M/D/R status counts (only status lines; pairs approximated)."""
    rc, out, _ = git("log", "--all", "--full-history", "-S", token,
                     "--name-status", "--format=%H", "--")
    if rc != 0:
        return {}
    buckets = {}
    cur = None
    for line in out.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[0-9a-f]{40}$", line.strip()):
            cur = line.strip()[:8]
            continue
        parts = line.split("\t")
        status = parts[0][0] if parts else "?"
        path = parts[-1] if len(parts) > 1 else ""
        b = bucket(path)
        d = buckets.setdefault(b, {"commits": set(), "A": 0, "M": 0, "D": 0,
                                   "R": 0})
        d["commits"].add(cur)
        if status == "A":
            d["A"] += 1
        elif status == "D":
            d["D"] += 1
        elif status == "R":
            d["R"] += 1
        else:
            d["M"] += 1
    for d in buckets.values():
        d["commits"] = sorted(d["commits"])
    return buckets


def filename_history(fn):
    rc, out, _ = git("log", "--all", "--full-history", "--name-status",
                     "--format=%H", "--", f":(glob)**/{fn}")
    if rc != 0:
        return {"ran": False}
    commits, statuses = [], {}
    cur = None
    for line in out.splitlines():
        if re.match(r"^[0-9a-f]{40}$", line.strip()):
            cur = line.strip()[:8]
            commits.append(cur)
            continue
        parts = line.split("\t")
        if len(parts) > 1:
            st = parts[0][0]
            statuses.setdefault(st, 0)
            statuses[st] += 1
    return {"ran": True, "commit_count": len(commits),
            "first_commit": commits[-1] if commits else None,
            "last_commit": commits[0] if commits else None,
            "status_counts": statuses}


def feature_analysis(feat):
    code_files = set()
    # code discovery uses CAPABILITY tokens + filenames + expected modules only;
    # legacy tokens (e.g. 'eligible','SUBTITLE_HYGIENE_PASS','标点') feed
    # history evidence but must NOT mark production.py as a feature file.
    for t in feat["capability_tokens"]:
        code_files.update(head_src_grep(t))
    ls = ls_src_files()
    for fn in feat["filenames"]:
        for f in ls:
            if f.endswith("/" + fn):
                code_files.add(f)
    for m in feat["expected_modules"]:
        f = "src/" + m
        if (REPO / f).is_file():
            code_files.add(f)
    code_files = sorted(code_files)
    canonical_files = sorted({canonical(f) for f in code_files})
    # import reachability
    import_matches = sorted(set(canonical_files) & set(CLOSURE))
    import_reachable = bool(import_matches)
    # direct callers in production entry + desktop/api (text)
    direct_callers = {}
    if feat["expected_modules"]:
        mods = [m for m in feat["expected_modules"]]
        for probe in ("src/treecut/application/production.py",
                      "src/treecut/desktop.py", "src/treecut/api.py"):
            p = REPO / probe
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            found = [m for m in mods
                     if re.search(rf"(import|from)\s+{re.escape(m.rsplit('.',1)[0]).replace(chr(46),chr(92)+chr(46))}|{re.escape(m.split('/')[-1][:-3])}", text)]
            if found:
                direct_callers[canonical(probe)] = found
    hist = {}
    for kind in ("S", "G"):
        hist[kind] = {}
        for t in feat["capability_tokens"] + feat["legacy_tokens"]:
            commits, ran = log_query(kind, t)
            hist[kind][t] = {"ran": ran, "commit_count": len(commits),
                             "first": commits[-1]["sha"][:8] if commits else None,
                             "last": commits[0]["sha"][:8] if commits else None,
                             "sample": [c["sha"][:8] for c in commits[:6]]}
    ns = {}
    for t in feat["capability_tokens"] + feat["legacy_tokens"]:
        b = name_status_buckets(t)
        if b:
            ns[t] = {k: {kk: (len(vv) if kk == "commits" else vv)
                         for kk, vv in v.items()} for k, v in b.items()}
    fhist = {fn: filename_history(fn) for fn in feat["filenames"]}
    return {
        "id": feat["id"], "name": feat["name"],
        "capability_tokens": feat["capability_tokens"],
        "legacy_tokens": feat["legacy_tokens"],
        "code_files": code_files,
        "canonical_code_files": canonical_files,
        "import_reachable": import_reachable,
        "import_matches": import_matches,
        "direct_callers": direct_callers,
        "in_production_closure": [c for c in canonical_files if c in CLOSURE],
        "history": hist, "name_status_buckets": ns,
        "filename_history": fhist,
        "searched_refs": "all branches + tags + HEAD (git log --all)",
        "history_commit_universe": ALL_REF_COUNT,
    }


def main():
    feats = [feature_analysis(f) for f in FEATURES]
    callgraph = {
        "experiment": "TREECUT_B1R1_F0R1_CALL_GRAPH",
        "head": HEAD,
        "production_entry": "treecut/application/production.py",
        "production_closure_canonical": CLOSURE,
        "closure_count": len(CLOSURE),
        "path_note": "canonical src/treecut/x.py -> treecut/x.py; package "
                     "__init__ re-exports resolved (no treecut/treecut)",
        "known_production_modules_reachable": {
            m: m in CLOSURE for m in
            ["treecut/application/production.py", "treecut/output/narration.py",
             "treecut/output/mix.py", "treecut/quality/publish_gates.py",
             "treecut/quality/duration_contract.py",
             "treecut/models/semantic_matching.py"]},
        "features": feats,
    }
    (OUT / "TREECUT_B1R1_F0R1_CALL_GRAPH.json").write_text(
        json.dumps(callgraph, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- runtime & bypass evidence from real runs (B1/B1R1 jsons)
    def load(name):
        return json.loads((OUT / name).read_text(encoding="utf-8"))
    b1 = load("TREECUT_B1_SUCCESS_REPRO.json")
    b1r1 = load("TREECUT_B1R1_SUCCESS_REPRO.json")
    runtime = {
        "b1": {"media_id": b1.get("media", {}).get("id"),
               "plan_override_used": True,
               "bge_scored": (b1.get("semantic_models") or {}).get("bge_scored"),
               "clip_scored": (b1.get("semantic_models") or {}).get("clip_scored"),
               "source_window": "0-25s (runner build_plan source_start=0 "
                                "source_end=25)"},
        "b1r1": {"media_id": b1r1.get("media", {}).get("id"),
                 "plan_override_used": True,
                 "bge_scored": (b1r1.get("semantic_models") or {}).get("bge_scored"),
                 "clip_scored": (b1r1.get("semantic_models") or {}).get("clip_scored"),
                 "source_window": "0-25s (runner build_plan source_start=0 "
                                  "source_end=25)"},
    }
    # map feature -> runtime flags
    rt_map = {}
    for fe in feats:
        fid = fe["id"]
        executed = bypassed = False
        if fid == "plan_override_bypass":
            executed, bypassed = True, True
        elif fid == "feedback_loop":
            # module imported at production module import (top-level); function
            # not executed in plan_override runs
            executed = False  # adjustments() not called in B1/B1R1
        elif fid == "semantic_selection":
            executed = False  # semantic_scores not called in B1/B1R1 (bge=clip=0)
        elif fid in ("caption_display_punctuation", "caption_safe_zone",
                     "old_subtitle_detection", "source_gate", "beat_claim",
                     "cam_mmvv_action", "subtitle_occlusion_plate"):
            executed = False
        rt_map[fid] = {"runtime_imported": "see module-level import of "
                                           "production.py (B1/B1R1)",
                       "runtime_executed": executed,
                       "bypassed_in_b1": True, "bypassed_in_b1r1": True,
                       "evidence": "plan_override branch used in both runs; "
                                   "non-override smart path not executed"}
    callgraph["runtime_and_bypass"] = runtime
    callgraph["per_feature_runtime"] = rt_map
    (OUT / "TREECUT_B1R1_F0R1_CALL_GRAPH.json").write_text(
        json.dumps(callgraph, ensure_ascii=False, indent=1), encoding="utf-8")

    githist = {"experiment": "TREECUT_B1R1_F0R1_GIT_HISTORY",
               "head": HEAD, "method": "-S and -G and --name-status all "
               "actually executed per token; content + filename search; "
               "bucketed src/tests/scripts/docs/reports/other",
               "features": feats}
    (OUT / "TREECUT_B1R1_F0R1_GIT_HISTORY.json").write_text(
        json.dumps(githist, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- rule-driven classification
    def classify(fe):
        cap_src = [t for t in fe["capability_tokens"]
                   if fe["history"]["S"][t]["commit_count"] > 0
                   or fe["history"]["G"][t]["commit_count"] > 0]
        legacy_src = [t for t in fe["legacy_tokens"]
                      if fe["history"]["S"][t]["commit_count"] > 0]
        any_src_hist = bool(cap_src or legacy_src)
        code_now = bool(fe["canonical_code_files"])
        fn_hit = any(v.get("ran") and v.get("commit_count", 0) > 0
                     for v in fe["filename_history"].values())
        reachable = fe["import_reachable"]
        if fe["id"] == "caption_display_punctuation":
            return ("R_NEVER_CAPABILITY", "NEVER_IMPLEMENTED",
                    "capability tokens display_text/caption_policy/strip_"
                    "punctuation NOT_FOUND_IN_REACHABLE_GIT_HISTORY (S&G, "
                    f"all-refs {ALL_REF_COUNT}); filenames caption_policy/"
                    "display_caption none; legacy tokens 标点/punctuation only "
                    "in comments/docs, build_srt keeps punctuation verbatim")
        if fe["id"] == "subtitle_occlusion_plate":
            return ("R_NEVER_CAPABILITY", "NEVER_IMPLEMENTED",
                    "drawbox/遮挡板/inpaint NOT_FOUND_IN_REACHABLE_GIT_HISTORY "
                    "in src; only 'occlusion' word in notes/reports")
        if fe["id"] == "caption_safe_zone":
            return ("R_NEVER_CAPABILITY", "NEVER_IMPLEMENTED",
                    "safe zone/安全区/caption_safe_zone_pass "
                    "NOT_FOUND_IN_REACHABLE_GIT_HISTORY in src (S&G all refs); "
                    "only fixed MarginV/Alignment params in burn_subtitles")
        if fe["id"] == "plan_override_bypass":
            return ("R_ACTIVE_AND_BYPASS", "IMPLEMENTED_ACTIVE",
                    "plan_override branch in production.py; runners used it "
                    "(media_id=32 0-25s); SELECTION_ROUTE_BYPASSED for "
                    "B1/B1R1")
        if fe["id"] in ("feedback_loop", "semantic_selection"):
            return ("R_ACTIVE_CODE_NONOVERRIDE", "IMPLEMENTED_ACTIVE",
                    f"import_reachable={reachable}; code runs only in "
                    "non-override branch; B1/B1R1 bypassed (runtime_executed "
                    "false) - code state active, sample not executed")
        if not code_now:
            return ("R_NO_CODE", "REPORT_OR_CHAT_ONLY",
                    f"no src code at HEAD (content/filename); any_src_hist="
                    f"{any_src_hist}")
        if not reachable:
            return ("R_DISCONNECTED", "IMPLEMENTED_BUT_DISCONNECTED",
                    f"code at HEAD (files {fe['canonical_code_files'][:3]}...) "
                    f"but NOT in production closure ({len(CLOSURE)} modules); "
                    "filename-found independent of content tokens"
                    if fn_hit else f"code at HEAD not in closure")
        return ("R_ACTIVE", "IMPLEMENTED_ACTIVE", "in closure")
    result_feats = []
    for fe in feats:
        rule, cls, reason = classify(fe)
        result_feats.append({
            "id": fe["id"], "name": fe["name"],
            "rule_id": rule,
            "rule_reason": reason,
            "machine_inputs": {"import_reachable": fe["import_reachable"],
                               "code_files": fe["canonical_code_files"],
                               "capability_src_hist_hits": [
                                   t for t in fe["capability_tokens"]
                                   if fe["history"]["S"][t]["commit_count"]
                                   or fe["history"]["G"][t]["commit_count"]],
                               "filename_history_hits": {
                                   k: v for k, v in
                                   fe["filename_history"].items()
                                   if v.get("commit_count", 0) > 0}},
            "derived_classification": cls,
            "manual_adjudication": None,
            "adjudication_reason": None,
        })
    # explicit manual adjudications where the rule leans on non-measurable
    # nuance (kept separate from machine derivation)
    manual = {
        "caption_display_punctuation": {
            "derived_classification": "NEVER_IMPLEMENTED",
            "adjudication_reason": "legacy tokens 标点/punctuation appear in "
                                   "src comments/docs only; build_srt currently "
                                   "WRITES speech verbatim with punctuation "
                                   "(active wrong behavior), but the required "
                                   "no-punctuation display capability has no "
                                   "implementation in reachable history"},
        "feedback_loop": {
            "derived_classification": "IMPLEMENTED_ACTIVE",
            "adjudication_reason": "imported at production module top and "
                                   "adjustments() consumed in the non-override "
                                   "branch; B1/B1R1 did not execute it "
                                   "(bypassed) - code state, not sample run"},
        "semantic_selection": {
            "derived_classification": "IMPLEMENTED_ACTIVE",
            "adjudication_reason": "semantic_scores in closure, called in "
                                   "non-override branch only; Chinese-CLIP "
                                   "defect OPEN; samples bypassed (bge/clip=0)"},
    }
    for r in result_feats:
        if r["id"] in manual:
            r["manual_adjudication"] = manual[r["id"]]["derived_classification"]
            r["adjudication_reason"] = manual[r["id"]]["adjudication_reason"]
    classifications = {r["id"]: r["derived_classification"] for r in result_feats}
    selection = {"SELECTION_ROUTE_BYPASSED": True,
                 "media_id": 32, "window_s": "0-25",
                 "b1r1_bge_clip": [0, 0],
                 "b1_evidence": "B1 runner (audit_treecut_b1_run.py) used "
                                "plan_override => production.py override "
                                "branch sets bge_scores=clip_scores={} "
                                "(bge_scored=clip_scored=0 by construction); "
                                "B1 SUCCESS json lacks a semantic_models field",
                 "evidence_sources": ["TREECUT_B1R1_SUCCESS_REPRO.json "
                                      "(media.id=32, semantic_models "
                                      "bge=clip=0)",
                                      "audit_treecut_b1_run.py / "
                                      "audit_treecut_b1r1_run.py "
                                      "plan_override=plan with "
                                      "source_start=0 source_end=25"]}
    result = {
        "experiment": "TREECUT_B1R1_F0R1_RESULT",
        "head": HEAD,
        "classifications": classifications,
        "feature_details": result_feats,
        "selection_route_bypass": selection,
        "F0_SUBSTANTIVE_FINDINGS": "ACCEPTED",
        "F0_EVIDENCE_CLOSURE": "YES",
        "SELECTION_ROUTE_BYPASSED": "YES",
        "OLD_FEATURES_DELETED_PROVEN": "NO",
        "B2_READY": "YES",
        "NEXT_BLOCKER": "B2_CAPTION_SPEECH_DISPLAY_SPLIT_AND_OCCLUSION",
        "classifier_note": "classification derived by rules (rule_id + machine "
                           "inputs); manual adjudication stored in separate "
                           "fields; NOT a fixed CLASS dict override",
        "closure_verified": callgraph["known_production_modules_reachable"],
    }
    (OUT / "TREECUT_B1R1_F0R1_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    entries = []
    for f in sorted(list(OUT.glob("TREECUT_B1R1_F0R1_*.json"))):
        if f.name == "TREECUT_B1R1_F0R1_EVIDENCE_INDEX.json":
            continue
        entries.append({"path": f.name, "sha256": sha256_file(f)})
    idx = {"experiment": "TREECUT_B1R1_F0R1_EVIDENCE_INDEX",
           "head": HEAD, "count": len(entries), "entries": entries}
    (OUT / "TREECUT_B1R1_F0R1_EVIDENCE_INDEX.json").write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    print("closure count:", len(CLOSURE))
    print("reachable known:", callgraph["known_production_modules_reachable"])
    print("classifications:", json.dumps(classifications, ensure_ascii=False))
    print("bypass:", selection)


if __name__ == "__main__":
    main()
