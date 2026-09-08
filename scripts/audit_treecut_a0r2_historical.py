# -*- coding: utf-8 -*-
"""A0 R2 — HISTORICAL relpath-keyed manifest + canonical input hash.

For the 4 historical 2026-08-06 projects under the production output dir:
  * every file keyed by PROJECT-RELATIVE path (avoids same-name overwrite)
    with exists / size / sha256 / (ffprobe for mp4)
  * canonical input hash per project = sha256(full selling + full narration +
    sorted media ids + plan duration + canvas) parsed from the project's own
    production_report.json / draft_content.json files on disk.
Unique-input determination = compare canonical hashes (not narration prefixes).
"""
import hashlib
import json
from pathlib import Path

OUT_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\output\projects")
OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
FFPROBE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\tools\win32\ffprobe.exe")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe(p: Path) -> dict:
    import subprocess
    try:
        proc = subprocess.run([str(FFPROBE), "-v", "quiet", "-print_format", "json",
                               "-show_format", "-show_streams", str(p)],
                              capture_output=True, timeout=60)
        return json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main():
    projects = sorted(p for p in OUT_ROOT.iterdir() if p.is_dir() and p.name.startswith("20260806"))
    manifest = {}
    for proj in projects:
        rel = {}
        for f in sorted(p for p in proj.rglob("*") if p.is_file()):
            relp = f.relative_to(OUT_ROOT).as_posix()  # project-relative key
            entry = {"exists": True, "size": f.stat().st_size, "sha256": sha256_file(f)}
            if f.suffix.lower() in (".mp4", ".wav"):
                entry["ffprobe"] = ffprobe(f)
            rel[relp] = entry
        manifest[proj.name] = rel
    (OUT / "TREECUT_A0R2_HISTORICAL_RELPATH_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # canonical input hash from each project's own production_report.json
    canonical = {}
    for proj in projects:
        rep = proj / "production_report.json"
        if not rep.exists():
            canonical[proj.name] = {"status": "no_report"}
            continue
        data = json.loads(rep.read_text(encoding="utf-8"))
        req = data.get("request", {})
        matches = [m.get("media_id") if isinstance(m, dict) else m
                   for m in data.get("matches", [])]
        plan = data.get("plan", {})
        can = {
            "selling": str(req.get("selling_points", "")),
            "narration": str(req.get("narration", "")),
            "media_ids_sorted": sorted(str(x) for x in matches if x is not None),
            "plan_duration": plan.get("planned_duration"),
            "n_matches": len(matches),
            "preset": req.get("output_preset"),
            "style": req.get("style"),
            "target_duration": req.get("target_duration"),
        }
        h = hashlib.sha256(json.dumps(can, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        canonical[proj.name] = {"canonical": can, "canonical_hash": h}
    (OUT / "TREECUT_A0R2_HISTORICAL_CANONICAL_INPUT.json").write_text(
        json.dumps(canonical, ensure_ascii=False, indent=1), encoding="utf-8")
    hashes = {k: v.get("canonical_hash") for k, v in canonical.items()
              if "canonical_hash" in v}
    unique = sorted(set(x for x in hashes.values() if x))
    print("projects:", len(projects), "| canonical hashes:", hashes)
    print("unique input count:", len(unique))


if __name__ == "__main__":
    main()
