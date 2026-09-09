# -*- coding: utf-8 -*-
"""TREECUT B0 — SOURCE PROVENANCE rerun after E-install full-tree sync.

Same git-native method as A0R2 (E bytes CRLF->LF normalized vs HEAD blob;
gitignored/untracked => NOT_IN_HEAD) but writes TREECUT_B0_* evidence so the
A0R2 historical file is never rewritten. Expectation after sync:
  every E .py == HEAD blob  => BASELINE_SELF_CONTAINED=YES
"""
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\admin\github\treecut-v13")
E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
OUT = Path(REPO / "reports" / "storage")


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
    rows, not_in_head, differs = [], [], []
    for e in e_files:
        rel_e = e.relative_to(E_SRC)
        git_path = (Path("src") / rel_e).as_posix()
        ls = run_git(["ls-files", "--error-unmatch", "--", git_path])
        tracked = ls["exit_code"] == 0
        e_norm = e.read_bytes().replace(b"\r\n", b"\n")
        row = {"e_relpath": rel_e.as_posix(), "git_path": git_path,
               "tracked": tracked, "ls_files": ls,
               "sha_e_norm": sha256_bytes(e_norm)}
        if tracked:
            rev = run_git(["rev-parse", f"HEAD:{git_path}"])
            row["rev_parse"] = rev
            row["head_blob_sha"] = rev["stdout"].strip() if rev["exit_code"] == 0 else None
            blob = subprocess.run(["git", "-C", str(REPO), "cat-file", "blob",
                                   f"HEAD:{git_path}"], capture_output=True)
            row["sha_head_blob_raw"] = sha256_bytes(blob.stdout)
            row["e_content_eq_head"] = blob.stdout == e_norm
            row["match"] = ("E_CONTENT_EQ_HEAD" if row["e_content_eq_head"]
                            else "E_CONTENT_DIFFERS_HEAD")
            if not row["e_content_eq_head"]:
                differs.append(rel_e.as_posix())
        else:
            row["match"] = "NOT_IN_HEAD"
            not_in_head.append(rel_e.as_posix())
        rows.append(row)
    self_contained = len(not_in_head) == 0 and len(differs) == 0
    data = {
        "experiment": "TREECUT_B0_SOURCE_PROVENANCE",
        "after_e_full_sync": True,
        "e_src_py_count": len(rows),
        "match_counts": {m: sum(1 for r in rows if r["match"] == m) for m in
                         sorted({r["match"] for r in rows})},
        "e_files_not_in_head": not_in_head,
        "e_files_content_differ_head": differs,
        "baseline_self_contained": self_contained,
        "files": rows,
    }
    (OUT / "TREECUT_B0_SOURCE_PROVENANCE.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("E src py:", len(rows), "| counts:", data["match_counts"],
          "| BASELINE_SELF_CONTAINED:", self_contained)


if __name__ == "__main__":
    main()
