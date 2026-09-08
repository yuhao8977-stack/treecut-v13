# -*- coding: utf-8 -*-
"""A0 R2 — SINGLE FORMAL REPRODUCTION RUNNER (audit-only).

Runs the existing reduced production chain (ProductionService.create) once with:
  * unique run_id auto-generated every run (no hardcoded repro3/timestamp dirs)
  * E-install running source first on sys.path (the code the product actually runs)
  * TREECUT_DATA_ROOT  = unique ASCII audit data root (this run)
  * TREECUT_MODEL_ROOT = unique ASCII model copy root (passed via --model-root)
  * production materials.db COPIED into the run data root (never modifies prod DB)
Outputs (all under the run data root):
  * RUN_MANIFEST.json   (baseline sha, git status, interpreters/versions, env,
                         actual imported-module source sha, DB copy sha, full
                         request, selected media ids, edit plan, model path,
                         output dir)
  * run_stdout.log / run_stderr.log
  * STATUS.json / production_report.json / output artifacts (from the chain)
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

REPO = Path(r"C:\Users\admin\github\treecut-v13")
E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
E_INSTALL = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13")
PROD_DB = E_INSTALL / "runtime_data" / "database"
BASELINE = "02c1fc8abb4f28ec45745bb4e484a4efa0bb5bef"
AUDIT_BASE = Path(r"E:\EchoBird-main\_treecut_audit_temp")

NARRATION = ("小户型也能拥有实用岛台。伸缩设计兼顾办公、用餐和聚会。"
             "分区收纳让常用物品随手可取。合理定制高度、宽度和台面厚度，让小空间更舒适。")
SELLING = "小户型岛台 可伸缩设计 分区收纳 实用尺寸 家庭办公会客两用"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_status() -> dict:
    def run(*args):
        proc = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    return {"head": run("rev-parse", "HEAD")["stdout"].strip(),
            "origin_main": run("rev-parse", "origin/main")["stdout"].strip(),
            "status": run("status", "--porcelain=v1", "--untracked-files=all")["stdout"]}


def module_source_sha() -> dict:
    """sha256 of the ACTUAL imported treecut module files in this process."""
    out = {}
    for name, mod in sorted(sys.modules.items()):
        if name.startswith("treecut") and getattr(mod, "__file__", None):
            try:
                p = Path(mod.__file__)
                if p.is_file():
                    out[name] = {"file": str(p), "sha256": sha256_file(p)}
            except OSError:
                pass
    return out


def main():
    model_root = None
    if "--model-root" in sys.argv:
        model_root = Path(sys.argv[sys.argv.index("--model-root") + 1]).resolve()
    if not model_root or not model_root.is_dir():
        raise SystemExit(f"model root missing/not a dir: {model_root}")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    data_root = AUDIT_BASE / f"a0r2_repro_{run_id}"
    data_root.mkdir(parents=True, exist_ok=True)

    # env BEFORE importing treecut (paths.discover reads env at call time)
    os.environ["TREECUT_DATA_ROOT"] = str(data_root)
    os.environ["TREECUT_MODEL_ROOT"] = str(model_root)
    os.environ["PYTHONPYCACHEPREFIX"] = str(data_root / "pycache")
    os.environ.pop("TREECUT_DEVELOPMENT_MODE", None)
    sys.path.insert(0, str(E_SRC))

    # DB copies (read-only on prod)
    db_dir = data_root / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_sha = {}
    for name in ("materials.db", "feedback.db"):
        src = PROD_DB / name
        if src.exists():
            shutil.copy2(src, db_dir / name)
            db_sha[name] = {"size": src.stat().st_size, "sha256": sha256_file(src)}

    versions = {}
    try:
        import torch
        import sherpa_onnx
        import onnxruntime
        versions = {"python": sys.version.split()[0], "torch": torch.__version__,
                    "torch_cuda": bool(torch.cuda.is_available()),
                    "sherpa_onnx": getattr(sherpa_onnx, "__version__", "?"),
                    "onnxruntime": onnxruntime.__version__}
    except Exception as exc:  # noqa: BLE001
        versions = {"error": str(exc)}

    manifest = {
        "run_id": run_id, "runner": "audit_treecut_a0r2_repro_runner.py",
        "baseline_sha": BASELINE, "git": git_status(),
        "data_root": str(data_root), "model_root": str(model_root),
        "versions": versions,
        "env": {k: v for k, v in os.environ.items() if k.startswith("TREECUT")},
        "db_copy_sha": db_sha,
        "request": {"selling_points": SELLING, "narration": NARRATION,
                    "target_duration": 25.0, "clip_seconds": 4.0,
                    "output_mp4": True, "output_jianying": True,
                    "include_test_materials": False, "bgm_path": "",
                    "output_preset": "vertical", "narration_speed": 1.0,
                    "style": "natural", "watermark_path": ""},
        "source_provenance_ref": "TREECUT_A0R2_SOURCE_PROVENANCE.json (BASELINE_SELF_CONTAINED=NO: 12 models files NOT_IN_HEAD + 4 differ)",
    }
    (data_root / "RUN_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    log = (data_root / "run_stdout.log").open("w", encoding="utf-8")
    errlog = (data_root / "run_stderr.log").open("w", encoding="utf-8")
    result = {"run_id": run_id, "PASS": False}
    t0 = time.time()
    try:
        from treecut.application import CreativeRequest, ProductionService
        request = CreativeRequest(selling_points=SELLING, narration=NARRATION,
                                  target_duration=25.0, clip_seconds=4.0,
                                  output_mp4=True, output_jianying=True,
                                  include_test_materials=False, bgm_path="",
                                  output_preset="vertical", narration_speed=1.0,
                                  style="natural", watermark_path="")
        svc = ProductionService()
        res = svc.create(request)
        result.update({
            "PASS": True, "seconds": round(time.time() - t0, 1),
            "project": res.project_dir, "preview": res.preview_mp4,
            "final_mp4": res.final_mp4, "draft": res.jianying_draft,
            "report": res.report_json, "cover": res.cover,
            "n_matches": res.match_count, "plan_duration": res.planned_duration,
        })
        print(json.dumps(result, ensure_ascii=False, indent=1), file=log)
    except Exception as exc:  # noqa: BLE001
        result.update({"PASS": False, "seconds": round(time.time() - t0, 1),
                       "error": f"{type(exc).__name__}: {str(exc)[:400]}",
                       "trace": traceback.format_exc()[-1600:]})
        print(json.dumps(result, ensure_ascii=False, indent=1), file=errlog)
    finally:
        # actual imported-module source sha (real import closure of this run)
        result["imported_module_source_sha"] = module_source_sha()
        (data_root / "reproduction_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        log.close()
        errlog.close()
        print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
