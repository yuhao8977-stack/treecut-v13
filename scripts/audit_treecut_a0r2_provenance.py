# -*- coding: utf-8 -*-
"""A0 R2 — SOURCE_PROVENANCE v2 (git-native comparison).
For every .py under the E-install running src (treecut package, non-pyc):
  - git ls-files --error-unmatch <path>            tracked?
  - git rev-parse HEAD:<path>                      head blob sha
  - content comparison: HEAD blob bytes vs E file bytes with CRLF->LF
    normalization (repo core.autocrlf=true: git commits LF; raw byte compare
    would be a false positive for CRLF checkouts). Raw byte equality of
    repo-worktree vs E-install is also recorded.
Exit codes/stdout/stderr of every git command recorded. Nothing hardcoded."""
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
OUT = Path(REPO / "reports" / "storage")
GITIGNORE_LINE = "models/"  # repo .gitignore pattern ignoring src/treecut/models/


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(args):
    proc = subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"cmd": "git " + " ".join(args), "exit_code": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


def main():
    e_files = sorted(p for p in (E_SRC / "treecut").rglob("*.py")
                     if "__pycache__" not in p.parts)
    rows = []
    for e in e_files:
        rel_e = e.relative_to(E_SRC)           # treecut\models\tts_local.py
        git_path = (Path("src") / rel_e).as_posix()
        row = {"e_relpath": rel_e.as_posix(), "git_path": git_path}
        ls = run_git(["ls-files", "--error-unmatch", "--", git_path])
        row["ls_files"] = ls
        row["tracked"] = ls["exit_code"] == 0
        e_raw = e.read_bytes()
        e_norm = e_raw.replace(b"\r\n", b"\n")
        row["sha_e_raw"] = sha256_bytes(e_raw)
        row["sha_e_norm"] = sha256_bytes(e_norm)
        # repo worktree raw bytes (exists on disk even for gitignored files)
        w = REPO / (Path("src") / rel_e)
        if w.exists():
            w_raw = w.read_bytes()
            row["worktree_exists_on_disk"] = True
            row["sha_wt_raw"] = sha256_bytes(w_raw)
            row["wt_raw_eq_e_raw"] = w_raw == e_raw
            row["wt_norm_eq_e_norm"] = w_raw.replace(b"\r\n", b"\n") == e_norm
        else:
            row["worktree_exists_on_disk"] = False
            row["wt_raw_eq_e_raw"] = False
            row["wt_norm_eq_e_norm"] = False
        if row["tracked"]:
            rev = run_git(["rev-parse", f"HEAD:{git_path}"])
            row["rev_parse"] = rev
            row["head_blob_sha"] = rev["stdout"].strip() if rev["exit_code"] == 0 else None
            blob = subprocess.run(["git", "-C", str(REPO), "cat-file", "blob",
                                   f"HEAD:{git_path}"], capture_output=True)
            row["sha_head_blob_raw"] = sha256_bytes(blob.stdout)
            row["cat_file_exit"] = blob.returncode
            row["e_content_eq_head"] = blob.stdout == e_norm
        else:
            row["rev_parse"] = None
            row["head_blob_sha"] = None
            row["e_content_eq_head"] = False
        if not row["tracked"]:
            row["match"] = "NOT_IN_HEAD"
        elif row["e_content_eq_head"]:
            row["match"] = "E_CONTENT_EQ_HEAD"
        else:
            row["match"] = "E_CONTENT_DIFFERS_HEAD"
        rows.append(row)

    not_in_head = [r["e_relpath"] for r in rows if r["match"] == "NOT_IN_HEAD"]
    differs = [r["e_relpath"] for r in rows if r["match"] == "E_CONTENT_DIFFERS_HEAD"]
    self_contained = len(not_in_head) == 0 and len(differs) == 0
    provenance = {
        "experiment": "TREECUT_A0R2_SOURCE_PROVENANCE",
        "baseline": "02c1fc8abb4f28ec45745bb4e484a4efa0bb5bef",
        "method": "git-native: E bytes CRLF->LF normalized vs HEAD blob; gitignored/untracked => NOT_IN_HEAD; raw byte worktree-vs-E also recorded",
        "repo_core_autocrlf": "true",
        "gitignore_models_pattern": GITIGNORE_LINE,
        "e_src_py_count": len(rows),
        "match_counts": {m: sum(1 for r in rows if r["match"] == m) for m in
                         sorted({r["match"] for r in rows})},
        "e_files_not_in_head": not_in_head,
        "e_files_content_differ_head": differs,
        "baseline_self_contained": self_contained,
        "explicit_check": {f: next((r for r in rows
                                    if r["git_path"] == f"src/treecut/{m}"), None)
                           for f, m in [("tts_local.py", "models/tts_local.py"),
                                        ("vision_florence.py", "models/vision_florence.py"),
                                        ("cache.py", "models/cache.py")]},
        "files": rows,
    }
    (OUT / "TREECUT_A0R2_SOURCE_PROVENANCE.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=1), encoding="utf-8")
    print("files:", len(rows), "| counts:", provenance["match_counts"],
          "| BASELINE_SELF_CONTAINED:", self_contained)
    print("NOT_IN_HEAD:", len(not_in_head), "| DIFFERS:", len(differs))


if __name__ == "__main__":
    main()
