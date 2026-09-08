# -*- coding: utf-8 -*-
"""A0 R1 — historical artifact forensics (2026-08-06 projects). Read-only."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

OUT = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
BASE = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\output\projects")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,r_frame_rate,duration:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"error": r.stderr[:120]}


def main():
    manifest = {}
    for proj in sorted(BASE.iterdir()):
        if not proj.is_dir():
            continue
        files = {}
        for f in sorted(proj.rglob("*")):
            if f.is_file():
                rec = {"exists": True, "size": f.stat().st_size,
                       "sha256": sha(f), "path": str(f)}
                if f.suffix.lower() == ".mp4":
                    rec["ffprobe"] = probe(f)
                files[f.name] = rec
        status = {}
        sp = proj / "STATUS.json"
        if sp.exists():
            status = json.loads(sp.read_text(encoding="utf-8"))
        # draft content summary
        draft = None
        dp = proj / "TreeCut_剪映草稿" / "draft_content.json"
        if dp.exists():
            dc = json.loads(dp.read_text(encoding="utf-8"))
            draft = {"duration": dc.get("duration"),
                     "has_tracks": "tracks" in dc,
                     "n_materials": len(dc.get("materials", [])) if "materials" in dc else None,
                     "canvas": dc.get("canvas_config")}
        report = {}
        rp = proj / "production_report.json"
        if rp.exists():
            r = json.loads(rp.read_text(encoding="utf-8"))
            report = {"request_selling": r.get("request", {}).get("selling_points"),
                      "request_narration": (r.get("request", {}).get("narration") or "")[:60],
                      "n_matches": len(r.get("matches", [])),
                      "match_media_ids": [m.get("media_id") for m in r.get("matches", [])],
                      "plan_segments": len(r.get("plan", {}).get("segments", [])),
                      "plan_duration": r.get("plan", {}).get("planned_duration"),
                      "quality_passed": r.get("quality", {}).get("passed"),
                      "final_mp4": r.get("final_mp4"), "draft": r.get("jianying_draft")}
        manifest[proj.name] = {"status": status.get("state"),
                               "error": status.get("error", ""),
                               "report": report, "draft_summary": draft,
                               "files": files}
    (OUT / "TREECUT_A0R1_HISTORICAL_ARTIFACT_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    # concise
    for proj, m in manifest.items():
        print(proj, "| status:", m["status"])
        rep = m.get("report") or {}
        print("  matches:", rep.get("n_matches"), "| media:", rep.get("match_media_ids"),
              "| plan segs:", rep.get("plan_segments"), "dur:", rep.get("plan_duration"),
              "| qa:", rep.get("quality_passed"))
        print("  narration:", (rep.get("request_narration") or "")[:50])
        print("  draft:", m.get("draft_summary"))


if __name__ == "__main__":
    main()
