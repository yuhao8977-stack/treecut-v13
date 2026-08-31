# -*- coding: utf-8 -*-
"""Phase A — 生成存储架构/仓库重复/模型缓存/清理计划/验证模板 JSON + 审计 md。"""
from __future__ import annotations

import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "storage"
OUT.mkdir(parents=True, exist_ok=True)
NOW = time.strftime("%Y-%m-%d %H:%M:%S")

audit = json.loads((OUT / "C_DRIVE_STORAGE_AUDIT_V1.json").read_text(encoding="utf-8"))

# ---------- 1. STORAGE_ARCHITECTURE_V1.json ----------
arch = {
    "generated_at": NOW, "version": "V1",
    "layers": {
        "C": {"role": "系统 + 用户配置 + 必要小文件", "free_gb": audit["disks"]["C"]["free_gb"]},
        "E": {"role": "TreeCut 程序 + 运行数据（DB/browser_profile/checkpoint/inbox/logs/temp/staging）",
              "root": "E:\\TreeCut\\", "free_gb": audit["disks"]["E"]["free_gb"]},
        "G": {"role": "AI 模型 + 大型可复用缓存（models/huggingface_cache/modelscope_cache/ollama）",
              "root": "G:\\AI\\", "free_gb": audit["disks"]["G"]["free_gb"]},
        "Z": {"role": "大型媒体（视频/图片/cover/导出/归档）",
              "root": "Z:\\TreeCut_Media\\", "free_gb": audit["disks"]["Z"]["free_gb"]},
    },
    "constraints": [
        "Z 仅放 media，不放 SQLite/Profile/LevelDB/Git working tree（网络/IO 延迟）",
        "媒体先写 E:\\TreeCut\\runtime\\staging\\*.part → 验证 PASS → 原子移至 Z",
        "MEDIA_ROOT 不可用 → MEDIA_STORAGE_UNAVAILABLE，STOP，绝不 fallback C",
        "C free < 80GB → WARNING；< 50GB → CRITICAL（禁媒体/缓存写 C）",
    ],
    "env_vars": {
        "TREECUT_REPO_ROOT": "E:\\TreeCut\\repo\\treecut-v13",
        "TREECUT_DATA_ROOT": "E:\\TreeCut\\runtime",
        "TREECUT_MEDIA_ROOT": "Z:\\TreeCut_Media",
        "TREECUT_MODEL_ROOT": "G:\\AI",
        "TREECUT_TEMP_ROOT": "E:\\TreeCut\\runtime\\temp",
        "HF_HOME": "G:\\AI\\huggingface_cache",
        "OLLAMA_MODELS": "G:\\AI\\ollama",
    },
    "media_tree": {
        "Z:\\TreeCut_Media\\": ["B003", "B007", "B008", "B010", "UNASSIGNED_LEGACY"],
        "B007": ["covers", "published_media", "creator_exports", "raw_media", "archive"],
    },
}
(OUT / "STORAGE_ARCHITECTURE_V1.json").write_text(
    json.dumps(arch, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- 2. TREECUT_REPO_DUPLICATE_AUDIT_V1.json ----------
repo_audit = {
    "generated_at": NOW,
    "canonical_dev_repo": {
        "path": r"C:\Users\admin\github\treecut-v13", "is_git": True,
        "head": "e5c4f65", "dirty": False, "size_gb": 0.07,
        "verdict": "CURRENT_CANONICAL（唯一 git 仓库）"},
    "e_candidates": [
        {"path": r"E:\树剪整理\01_主程序源码", "is_git": False, "size_gb": None,
         "content": "树剪软件相关文件（旧源码转储）",
         "verdict": "LEGACY_SOURCE_DUMP / NEEDS_REVIEW（无 git，需人工确认是否含独有工作）"},
        {"path": r"E:\树剪整理\02_安装程序\TreeCut_v13", "is_git": False,
         "size_gb": None, "content": "安装版产物（src+runtime+models+runtime_data）",
         "verdict": "INSTALLED_PRODUCT（非 git；其 runtime_data 即当前运行数据，MUST_PRESERVE）"},
    ],
    "migration_policy": [
        "以 C 仓库为源，E:\\TreeCut\\repo\\treecut-v13 为唯一 canonical（clone/复制+checkout 同 commit）",
        "E 旧源码/安装版：本轮不删除；待 canonical E 验证通过后再分类清理",
        "禁止文件覆盖式合并",
    ],
}
(OUT / "TREECUT_REPO_DUPLICATE_AUDIT_V1.json").write_text(
    json.dumps(repo_audit, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- 3. TREECUT_MODEL_CACHE_AUDIT_V1.json ----------
model_audit = {
    "generated_at": NOW,
    "caches": {
        ".cache/huggingface": {"path": r"C:\Users\admin\.cache\huggingface",
                               "size_gb": audit["model_caches"][".cache"]["size_gb"],
                               "note": "HF 缓存含硬链接（blobs+snapshots 共享磁盘），实测占用小于表观值；含 faster-whisper-large-v3/bge-m3/vit_clip/florence 等",
                               "can_redirect": True, "redirect": "HF_HOME=G:\\AI\\huggingface_cache",
                               "action": "Phase B：设 HF_HOME + 迁移现有 hub 目录后验证"},
        ".ollama": {"path": r"C:\Users\admin\.ollama", "size_gb": 5.56,
                    "can_redirect": True, "redirect": "OLLAMA_MODELS=G:\\AI\\ollama",
                    "action": "Phase B：设 OLLAMA_MODELS + 迁移 models 后验证"},
        "dsh_models": {"path": r"C:\Users\admin\dsh_models", "size_gb": 1.89,
                       "can_redirect": True, "redirect": "G:\\AI\\dsh_models",
                       "action": "Phase B：确认消费方支持后迁移"},
        ".modelscope": {"path": r"C:\Users\admin\.modelscope", "size_gb": 0.00,
                        "can_redirect": True, "redirect": "MODELSCOPE_CACHE=G:\\AI\\modelscope_cache"},
    },
    "rule": "不得直接剪切未知 AI 运行目录；须经支持的环境变量/配置重定向并验证。",
}
(OUT / "TREECUT_MODEL_CACHE_AUDIT_V1.json").write_text(
    json.dumps(model_audit, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- 4. C_DRIVE_CLEANUP_PLAN_V1.json（PENDING，不执行） ----------
cleanup = {
    "generated_at": NOW, "status": "PENDING_APPROVAL",
    "note": "仅规划，未执行任何删除。DELETE 须在 Phase B 迁移验证全部 PASS 且用户批准后独立执行。",
    "candidates": [
        {"path": r"C:\Users\admin\AppData\Local\Temp", "size_gb": 17.48,
         "category": "TEMP", "delete_safe": "审查后（仅过期/无用临时文件）",
         "est_release_gb": "10-15（需审查）"},
        {"path": r"C:\Users\admin\.cache\huggingface", "size_gb": 14.93,
         "category": "MODEL_CACHE", "delete_safe": "迁移到 G 并验证后可清（HF blobs 硬链接按实占算约 8-10）",
         "est_release_gb": "8-10"},
        {"path": r"C:\Users\admin\.ollama", "size_gb": 5.56,
         "category": "MODEL_CACHE", "delete_safe": "迁移到 G 并验证后可清", "est_release_gb": "5.5"},
        {"path": r"C:\Users\admin\dsh_models", "size_gb": 1.89,
         "category": "MODEL_CACHE", "delete_safe": "确认消费方后迁 G", "est_release_gb": "1.9"},
        {"path": r"C:\Users\admin\Downloads", "size_gb": 21.33,
         "category": "USER_FILES", "delete_safe": "需用户人工审查", "est_release_gb": "用户决定"},
        {"path": r"C:\Users\admin\Desktop", "size_gb": 7.50,
         "category": "USER_FILES", "delete_safe": "需用户人工审查", "est_release_gb": "用户决定"},
        {"path": r"C:\Users\admin\github\treecut-v13", "size_gb": 0.07,
         "category": "REPO", "delete_safe": "canonical E 验证通过后保留备份一段时间再清", "est_release_gb": "0.07"},
    ],
    "est_total_release_gb": "26-33（不含用户文件审查项）→ C 可回到约 70-80GB；含用户文件审查可达 100GB+",
}
(OUT / "C_DRIVE_CLEANUP_PLAN_V1.json").write_text(
    json.dumps(cleanup, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- 5. 迁移验证模板（PENDING） ----------
for name, scope in [
    ("TREECUT_RUNTIME_MIGRATION_VALIDATION_V1.json", "runtime data → E"),
    ("TREECUT_MEDIA_ROOT_VALIDATION_V1.json", "media root → Z"),
    ("TREECUT_BROWSER_PROFILE_MIGRATION_V1.json", "B007 profile → E"),
]:
    (OUT / name).write_text(json.dumps(
        {"status": "PENDING_PHASE_B", "scope": scope,
         "checks": ["目录可写", "字节数一致", "登录持久化（profile）", "DB integrity（runtime）",
                    "读写验证（media）"], "result": None}, ensure_ascii=False, indent=1),
        encoding="utf-8")

# ---------- 6. C_DRIVE_STORAGE_AUDIT_V1.md ----------
md = ["# C 盘存储审计 V1", "", f"生成时间：{NOW}", "",
      "## 磁盘可用空间", "", "| 盘 | 可用 GB | 总 GB | 用途建议 |",
      "|---|--------:|-----:|----------|"]
roles = {"C": "系统/配置", "D": "普通软件", "E": "TreeCut 程序+运行数据",
         "G": "AI 模型/缓存", "Z": "大型媒体"}
for d, info in audit["disks"].items():
    md.append(f"| {d} | {info['free_gb']} | {info['total_gb']} | {roles.get(d,'')} |")
md += ["", "## C:\\Users\\admin 主要目录", "", "| 目录 | 大小 GB | 分类 |",
       "|------|-------:|------|"]
cats = {"Downloads": "用户文件-需审查", "AppData_Local_Temp": "临时-可清(审查)",
        ".cache": "模型缓存-可迁G", "Desktop": "用户文件-需审查",
        ".ollama": "模型-可迁G", "dsh_models": "模型-可迁G",
        "deepseek-harness": "Harness 程序数据", ".dsh": "Harness 数据",
        "github": "开发仓库(仅0.07GB)", "harness_workspace": "工作区",
        ".treecut": "TreeCut 用户数据(≈0)", ".modelscope": "模型缓存(≈0)"}
for d in audit["top_dirs"]:
    md.append(f"| {d['name']} | {d['size_gb']:.2f} | {cats.get(d['name'],'')} |")
md += ["", "## Top 大文件（>50MB，取前 19）", "", "| 大小 GB | 路径 |"]
for f in audit["top_files"][:19]:
    md.append(f"| {f['size_bytes']/2**30:.2f} | `{f['path']}` |")
md += ["", "## 结论", "",
       "- TreeCut 本身在 C 盘仅占 ~0.07GB（仓库）；运行数据（DB/profile/快照）实际已在 E 盘",
       "- C 盘压力主源：Downloads 21GB、Temp 17.5GB、.cache 15GB、Desktop 7.5GB、.ollama 5.6GB、dsh_models 1.9GB",
       "- 可预测回收（不含用户文件审查项）：Temp 清理 + 模型缓存迁 G ≈ 26-33GB → C 回到 ~70-80GB",
       "- 全部为规划；删除须 Phase B 验证 + 用户批准后执行"]
(OUT / "C_DRIVE_STORAGE_AUDIT_V1.md").write_text("\n".join(md), encoding="utf-8")

print("Phase A outputs written to", OUT)
for f in sorted(OUT.iterdir()):
    print("  ", f.name)
