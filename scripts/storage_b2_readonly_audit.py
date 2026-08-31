# -*- coding: utf-8 -*-
"""Phase B2: READ-ONLY audit + classification of C:\\Users\\admin\\Downloads and Desktop.
ZERO moves/deletes/renames. Categories:
  MEDIA_TO_Z      - large media payloads (move candidates to Z)
  INSTALLER_DELETE- installers/updaters (delete candidates)
  ARCHIVE_REVIEW  - zip/rar/7z/iso (review before delete/extract)
  PROJECT_TO_E    - dev project dirs (move candidates to E)
  DUPLICATE       - same-basename+size clusters
  KEEP            - documents, shortcuts, configs, small files
  UNKNOWN_KEEP    - cannot classify -> KEEP (UNKNOWN never FALSE)
Outputs: DOWNLOADS_READONLY_AUDIT_V1.json, DESKTOP_READONLY_AUDIT_V1.json, USER_C_DRIVE_CLEANUP_REVIEW_V1.md
"""
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

BASE = r"C:\Users\admin"
TARGETS = {
    "DOWNLOADS": os.path.join(BASE, "Downloads"),
    "DESKTOP": os.path.join(BASE, "Desktop"),
}
REPORTS = r"C:\Users\admin\github\treecut-v13\reports\storage"

MEDIA_EXT = {".mp4",".mkv",".avi",".mov",".wmv",".flv",".ts",".m2ts",".webm",
             ".mp3",".wav",".flac",".m4a",".aac",".ogg",
             ".jpg",".jpeg",".png",".gif",".bmp",".webp",".heic",".raw",".cr2",".nef",".dng",".tif",".tiff",".psd",".svg"}
INSTALLER_EXT = {".msi",".msu",".appx",".apk",".dmg",".pkg",".msix",".msixbundle",".appinstaller",".exe"}
INSTALLER_NAME = ("install","setup","update","patch","_v","-v","wps","qq","wechat","baidu","driver")
ARCHIVE_EXT = {".zip",".rar",".7z",".tar",".gz",".bz2",".xz",".iso",".001"}
KEEP_EXT = {".doc",".docx",".xls",".xlsx",".ppt",".pptx",".pdf",".txt",".md",".csv",
            ".lnk",".url",".ico",".json",".xml",".html",".htm",".config",".ini",".srt",".ass",".torrent",
            ".pem",".key",".cer",".pfx",".dat",".db",".sqlite"}
PROJECT_MARKERS = ("package.json","pyproject.toml","requirements.txt","pom.xml","build.gradle",
                   ".git",".idea",".vscode","node_modules","venv",".venv",".gitignore",
                   "*.sln","*.csproj","*.xcodeproj","Cargo.toml","go.mod")
MIN_BIG = 50 * 1024 * 1024  # 50MB for "big" media/installer flags

SKIP_DIRS = {"AppData", "Application Data", "Local Settings", "Recent", "OneDrive", "WPS Cloud Files", "WPSDrive"}

def is_junction(p):
    try:
        return bool(os.path.realpath(p) != os.path.abspath(p)) and os.path.islink(p)
    except Exception:
        return False

def classify(path, size, name, is_dir=False):
    if is_dir:
        # dirs handled by PROJECT detection upstream
        return "UNKNOWN_KEEP"
    ext = os.path.splitext(name)[1].lower()
    low = name.lower()
    if ext in KEEP_EXT:
        return "KEEP"
    if ext in INSTALLER_EXT:
        return "INSTALLER_DELETE"
    if ext == ".exe":
        return "INSTALLER_DELETE" if (size > 5 * 1024 * 1024 or any(k in low for k in ("install", "setup", "update"))) else "KEEP"
    if ext in ARCHIVE_EXT:
        return "ARCHIVE_REVIEW"
    if ext in MEDIA_EXT:
        return "MEDIA_TO_Z"
    return "UNKNOWN_KEEP"

def scan(target):
    entries = []          # file records
    dirs = []             # dir records (for project detection)
    total_files = total_bytes = 0
    for root, dnames, fnames in os.walk(target, topdown=True, followlinks=False):
        dnames[:] = [d for d in dnames if not is_junction(os.path.join(root, d))]
        rel_root = os.path.relpath(root, target)
        for d in dnames:
            dp = os.path.join(root, d)
            try:
                st = os.stat(dp)
                dirs.append({"path": dp, "rel": os.path.relpath(dp, target), "size": st.st_size,
                             "mtime": datetime.fromtimestamp(st.st_mtime).isoformat()})
            except OSError:
                pass
        for f in fnames:
            fp = os.path.join(root, f)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            total_files += 1
            total_bytes += st.st_size
            entries.append({
                "path": fp, "rel": os.path.relpath(fp, target), "size": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(),
            })
    # project detection on dirs (top-2 levels only)
    project_dirs = set()
    for d in dirs:
        depth = d["rel"].count(os.sep)
        if depth > 2:
            continue
        try:
            names = os.listdir(d["path"])
        except OSError:
            continue
        for n in names:
            if n in PROJECT_MARKERS or (n.endswith((".sln", ".csproj")) and depth <= 1):
                project_dirs.add(d["rel"])
                break
    # classify files
    for e in entries:
        e["category"] = classify(e["path"], e["size"], os.path.basename(e["path"]))
        e["in_project"] = any(e["rel"].startswith(p + os.sep) for p in project_dirs)
        if e["in_project"]:
            e["category"] = "PROJECT_TO_E"
    return entries, dirs, project_dirs, total_files, total_bytes

def summarize(entries):
    agg = defaultdict(lambda: {"count": 0, "bytes": 0})
    for e in entries:
        agg[e["category"]]["count"] += 1
        agg[e["category"]]["bytes"] += e["size"]
    return {k: {"count": v["count"], "size_gb": round(v["bytes"] / (1024**3), 2)} for k, v in agg.items()}

def find_dupes(entries):
    by = defaultdict(list)
    for e in entries:
        by[(os.path.basename(e["path"]).lower(), e["size"])].append(e["rel"])
    return {k: v for k, v in by.items() if len(v) > 1}

def main():
    all_out = {}
    for name, target in TARGETS.items():
        if not os.path.isdir(target):
            print(f"{name}: MISSING {target}")
            continue
        print(f"scanning {name} ({target}) ...")
        entries, dirs, project_dirs, tf, tb = scan(target)
        dupes = {f"{k[0]}::{k[1]}": v for k, v in find_dupes(entries).items()}
        # mark duplicates (second+ occurrence)
        seen = defaultdict(int)
        for e in entries:
            key = f"{os.path.basename(e['path']).lower()}::{e['size']}"
            if key in dupes:
                seen[key] += 1
                if seen[key] > 1:
                    e["category"] = "DUPLICATE"
        agg = summarize(entries)
        big = sorted([e for e in entries if e["size"] >= MIN_BIG], key=lambda x: -x["size"])
        top100 = sorted(entries, key=lambda x: -x["size"])[:100]
        out = {
            "target": target,
            "scanned_at_utc": datetime.now().astimezone().isoformat(),
            "mode": "READ_ONLY - 0 moves/deletes/renames performed",
            "totals": {"files": tf, "bytes": tb, "size_gb": round(tb / (1024**3), 2)},
            "categories_gb": agg,
            "project_dirs": sorted(project_dirs),
            "duplicate_clusters": dupes,
            "big_files_over_50mb": [{ "rel": e["rel"], "size_gb": round(e["size"]/(1024**3),2), "cat": e["category"], "mtime": e["mtime"]} for e in big],
            "top100_by_size": [{"rank": i+1, "rel": e["rel"], "size_gb": round(e["size"]/(1024**3),2), "cat": e["category"], "mtime": e["mtime"]} for i, e in enumerate(top100)],
        }
        jf = os.path.join(REPORTS, f"{name}_READONLY_AUDIT_V1.json")
        with open(jf, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        all_out[name] = out
        print(f"  {name}: {tf} files, {round(tb/(1024**3),2)} GB; categories={ {k:v['size_gb'] for k,v in agg.items()} }")
    write_md(all_out)

def write_md(all_out):
    lines = ["# 用户 C 盘清理评审（只读）— Downloads / Desktop 分类",
             "",
             f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             "**模式: 只读审计 — 未移动/删除/重命名任何用户文件。所有分类仅作建议，最终动作需用户确认。**",
             "",
             "## 分类口径",
             "- `MEDIA_TO_Z`: 视频/音频/图片大文件 → Z 盘素材候选（需用户确认后再迁）",
             "- `INSTALLER_DELETE`: 安装包/更新程序 → 删除候选",
             "- `ARCHIVE_REVIEW`: 压缩包/镜像 → 解压或删除候选",
             "- `PROJECT_TO_E`: 开发项目目录 → E 盘候选",
             "- `DUPLICATE`: 同名同大小重复 → 保留一份候选",
             "- `KEEP`: 文档/快捷方式/配置 → 保留",
             "- `UNKNOWN_KEEP`: 无法可靠分类 → **一律保留**（UNKNOWN 不是 FALSE）",
             ""]
    for name in ("DOWNLOADS", "DESKTOP"):
        out = all_out.get(name)
        if not out:
            continue
        lines += [f"## {name} — {out['totals']['size_gb']} GB / {out['totals']['files']} 文件",
                  "",
                  "| 类别 | 大小(GB) | 文件数 |",
                  "|---|---|---|"]
        for cat, v in sorted(out["categories_gb"].items(), key=lambda x: -x[1]["size_gb"]):
            lines.append(f"| {cat} | {v['size_gb']} | {v['count']} |")
        lines.append("")
        if out.get("project_dirs"):
            lines += ["### 项目目录候选 (PROJECT_TO_E)", ""]
            for p in out["project_dirs"]:
                lines.append(f"- `{p}`")
            lines.append("")
        big = out.get("big_files_over_50mb", [])
        if big:
            lines += ["### 大文件 Top（≥50MB，按大小）", "", "| 大小(GB) | 路径 | 类别 |", "|---|---|---|"]
            for b in big[:40]:
                lines.append(f"| {b['size_gb']} | `{b['rel']}` | {b['cat']} |")
            lines.append("")
        if out.get("duplicate_clusters"):
            lines += ["### 重复簇（同名同大小）", ""]
            for k, v in list(out["duplicate_clusters"].items())[:30]:
                base, sz = k.rsplit("::", 1)
                lines.append(f"- `{base}` ({int(sz)/(1024**3):.2f} GB): " + " ; ".join(v))
            lines.append("")
        lines.append("---")
        lines.append("")
    lines += ["## 决策说明",
              "- 本评审不自动执行任何动作；请在逐项确认后再决定迁移/删除。",
              "- 迁移候选在动作前需先确认目标盘空间与用途。",
              "- 任何无法确认类别的文件按 KEEP 处理。"]
    md = os.path.join(REPORTS, "USER_C_DRIVE_CLEANUP_REVIEW_V1.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"review -> {md}")

if __name__ == "__main__":
    main()
