# -*- coding: utf-8 -*-
"""A0 R2 — BEAT/CLAIM reproducible machine search.

Answers TARGET_BEAT_LAYER with evidence, not assertion:
  1) filename/content search for beat/claim in E-install RUNNING src
     and in the repo worktree src (development superset).
  2) production call graph: AST import closure from E application/production.py
     (the only formal orchestration path) -> list of treecut modules reachable;
     flag whether any reachable module is a beat/claim layer.
"""
import ast
import json
import re
from pathlib import Path

E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
REPO_SRC = Path(r"C:\Users\admin\github\treecut-v13\src")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
NAME_RE = re.compile(r"(beat|claim)", re.IGNORECASE)
CONTENT_RE = re.compile(r"(beat|claim|逐句|拆分层)", re.IGNORECASE)


def scan(root: Path) -> dict:
    hits_name, hits_content = [], []
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(root).as_posix()
        if NAME_RE.search(p.name):
            hits_name.append(rel)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if CONTENT_RE.search(line):
                hits_content.append(f"{rel}:{i}")
                break  # one hit per file is enough for presence evidence
    return {"module_name_hits": hits_name, "content_hit_files": hits_content}


def import_closure(root: Path, entry_rel: str) -> dict:
    """AST import closure from entry module over treecut.* packages."""
    seen, queue = set(), [entry_rel]
    edges = []
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
                base = node.module if node.level == 0 else None
                if base:
                    names = [base]
            for n in names:
                if n.startswith("treecut") or n == "treecut":
                    mod_rel = n.replace(".", "/") + ".py"
                    if mod_rel not in seen:
                        queue.append(mod_rel)
                        edges.append((rel, n))
    beat_reachable = [r for r in seen if NAME_RE.search(r)]
    return {"entry": entry_rel, "closure_module_count": len(seen),
            "closure_modules": sorted(seen),
            "beat_or_claim_modules_in_closure": beat_reachable}


def main():
    e_scan = scan(E_SRC)
    r_scan = scan(REPO_SRC)
    closure = import_closure(E_SRC, "treecut/application/production.py")
    search = {
        "experiment": "TREECUT_A0R2_BEAT_CLAIM_SEARCH",
        "E_running_src": e_scan,
        "repo_worktree_src": r_scan,
        "production_import_closure": closure,
        "target_beat_layer_in_production": "FOUND" if closure["beat_or_claim_modules_in_closure"]
        else "NOT_FOUND",
        "note": "production.py is the only formal orchestration path (desktop/CLI/API); "
                "closure = all treecut.* modules statically reachable from its imports",
    }
    (OUT / "TREECUT_A0R2_BEAT_CLAIM_SEARCH.json").write_text(
        json.dumps(search, ensure_ascii=False, indent=1), encoding="utf-8")
    print("E scan name hits:", len(e_scan["module_name_hits"]),
          "content hits:", len(e_scan["content_hit_files"]))
    print("repo scan name hits:", len(r_scan["module_name_hits"]),
          "content hits:", len(r_scan["content_hit_files"]))
    print("production closure modules:", closure["closure_module_count"],
          "| beat/claim in closure:", closure["beat_or_claim_modules_in_closure"])


if __name__ == "__main__":
    main()
