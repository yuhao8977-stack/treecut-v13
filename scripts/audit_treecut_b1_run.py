# -*- coding: utf-8 -*-
"""TREECUT B1 — integration reproduction runner (runtime python + E install).

Modes:
  fail    STRICT_REJECT, 64-char narration (11.6s) + 25s target
          => MUST raise NARRATION_TOO_SHORT; no success artifacts allowed.
  success STRICT_REJECT, calibrated ~24.5s narration + 25s target via
          plan_override (bypasses the 3260-candidate semantic pass; B1 only
          proves the DURATION CONTRACT, not selection quality)
Writes evidence JSONs into reports/storage (no binaries).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

E_SRC = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
E_INSTALL = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13")
PROD_DB = E_INSTALL / "runtime_data" / "database" / "materials.db"
REPO_STORAGE = Path(r"C:\Users\admin\github\treecut-v13\reports\storage")
AUDIT = Path(r"E:\EchoBird-main\_treecut_audit_temp")
FFPROBE = E_INSTALL / "tools" / "win32" / "ffprobe.exe"
MODE = sys.argv[1] if len(sys.argv) > 1 else "fail"

sys.path.insert(0, str(E_SRC))
os.environ.pop("TREECUT_MODEL_ROOT", None)
os.environ.pop("TREECUT_DEVELOPMENT_MODE", None)

SHORT_NARRATION = ("小户型也能拥有实用岛台。伸缩设计兼顾办公、用餐和聚会。"
                   "分区收纳让常用物品随手可取。合理定制高度、宽度和台面厚度，让小空间更舒适。")

SENTENCES = [
    "小户型也能拥有实用岛台。",
    "平时收起来不占过道，需要时轻轻拉出，立刻多出一张工作台。",
    "它既能当办公桌，也能招待朋友用餐，一物三用不浪费。",
    "台面下方做了分区收纳，抽屉放文具，柜门里放餐具。",
    "常用物品放在顺手的高度，拿取不用弯腰。",
    "边角都做了圆润处理，家里有小孩也不用担心磕碰。",
    "台面宽度可以按户型定制，过道窄也能放得下。",
    "高度同样能调节，站着办公或坐着用餐都舒服。",
    "岩板表面耐刮耐热，泼了水一擦就干净。",
    "滑轮带锁，拉出后固定不晃动，使用更安心。",
    "入住半年，这台岛台让整个客厅显得更有条理。",
    "如果你家也想利用角落空间，这款设计值得参考。",
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_duration(path):
    proc = subprocess.run([str(FFPROBE), "-v", "quiet", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)],
                          capture_output=True, timeout=120)
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        streams = data.get("streams", [])
        if not any(s.get("codec_type") == "video" for s in streams):
            return 0.0  # not a playable video
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def pick_media(min_duration):
    import sqlite3
    con = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    src_cols = [r[1] for r in con.execute("PRAGMA table_info(sources)")]
    root_col = "path" if "path" in src_cols else "root"
    sql = (f"SELECT m.id, s.{root_col}, m.relative_path FROM media_files m "
           f"JOIN sources s ON s.id = m.source_id "
           f"WHERE m.available = 1 AND m.size_bytes > 20_000_000 LIMIT 500")
    rows = con.execute(sql).fetchall()
    con.close()
    probed = 0
    for mid, root, rel in rows:
        full = Path(root) / rel
        if not full.is_file():
            continue
        probed += 1
        d = ffprobe_duration(full)
        if d >= min_duration:
            return (mid, str(full), d), None
        if probed >= 60:
            break
    return None, f"no media >= {min_duration}s after probing {probed} candidates"


def build_plan(media_id, media_path, duration, total):
    from treecut.workflow.planning import EditPlan, EditSegment
    seg = EditSegment(order=1, media_id=media_id, path=media_path,
                      category="manual", source_start=0.0, source_end=min(total, duration),
                      timeline_start=0.0, timeline_end=min(total, duration),
                      match_score=0.9, matched_terms=("小户型岛台", "伸缩", "收纳"))
    return EditPlan(requested_duration=total, planned_duration=float(total),
                    complete=True, warnings=(), segments=(seg,))


def calibrate_narration(tts_model, low=24.5, high=24.85):
    from treecut.output.narration import synthesize, wav_duration
    work = AUDIT / f"b1_calib_{datetime.now().strftime('%H%M%S')}"
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "calib.wav"
    measured = []
    # 1) real-TTS duration of every sentence once
    per = []
    for s in SENTENCES:
        synthesize(s, wav, tts_model)
        per.append((s, wav_duration(wav)))
    # 2) greedy whole sentences while total <= high (never exceed by design)
    sel = []
    total = 0.0
    for i, (s, d) in enumerate(per):
        if total + d <= high:
            sel.append(i)
            total += d
        else:
            break
    text = "".join(SENTENCES[i] for i in sel)
    fulls = 0

    def synth_final(t):
        nonlocal fulls
        synthesize(t, wav, tts_model)
        fulls += 1
        d = wav_duration(wav)
        measured.append(round(d, 3))
        return d

    d = synth_final(text)
    spare = next(i for i in range(len(per)) if i not in sel)
    if not (low <= d <= high):
        chars = sum(len(SENTENCES[i]) for i in sel)
        rate = chars / d if d > 0 else 12.0
        need = max(0, int((low - d) * rate)) if d < low else 0
        text = text + SENTENCES[spare][:need]
        d = synth_final(text)
    # fine char-wise adjustment (+/- ~4 chars per step)
    for _ in range(8):
        if low <= d <= high:
            break
        if d < low:
            nxt = SENTENCES[spare][need:need + 4]
            if not nxt:
                break
            text += nxt
            need += 4
        else:
            if len(text) <= 20:
                break
            text = text[:-5]
        d = synth_final(text)
    if low <= d <= high:
        return text, round(d, 3), fulls
    raise RuntimeError(f"narration calibration failed; measured={measured}")


def run(mode):
    os.environ.pop("TREECUT_MODEL_ROOT", None)
    os.environ.pop("TREECUT_DATA_ROOT", None)  # inherited batch1 env would override default root
    from treecut.platform.paths import RuntimePaths
    from treecut.application import CreativeRequest, ProductionService
    paths = RuntimePaths.discover()
    paths.ensure()
    tts_model = paths.models / "LocalTTS"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    data_root = AUDIT / f"b1_{mode}_{ts}"
    os.environ["TREECUT_DATA_ROOT"] = str(data_root)
    db_dir = data_root / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    # each data root carries its own model-root pointer (same as deployment)
    from treecut.platform.paths import configure_models_path
    configure_models_path(data_root, r"E:\TreeCutRuntime\models")
    # plan_override path does not read the DB; copy anyway for capability parity
    if PROD_DB.exists():
        shutil.copy2(PROD_DB, db_dir / "materials.db")
    db_sha = sha256_file(db_dir / "materials.db") if (db_dir / "materials.db").exists() else None

    if mode == "fail":
        request = CreativeRequest(
            selling_points="小户型岛台 可伸缩设计", narration=SHORT_NARRATION,
            target_duration=25.0, output_mp4=True, output_jianying=False,
            output_preset="vertical", style="natural", duration_strategy="strict_reject")
        t0 = time.time()
        outcome = {"mode": "fail", "narration_chars": len(SHORT_NARRATION)}
        try:
            ProductionService().create(request)
            outcome["intercepted"] = False
            outcome["error"] = "NO ERROR - job unexpectedly succeeded"
        except Exception as exc:  # noqa: BLE001
            outcome["intercepted"] = True
            outcome["error"] = str(exc)
            outcome["error_type"] = type(exc).__name__
            code = next((c for c in ("NARRATION_TOO_SHORT", "NARRATION_TOO_LONG",
                                     "VOICE_COVERAGE_LOW", "VOICE_TAIL_TOO_LONG",
                                     "BGM_ONLY_AUDIO", "DURATION_CONTRACT_NOT_RUN")
                         if c in str(exc)), None)
            outcome["failure_code"] = code
        outcome["seconds"] = round(time.time() - t0, 1)
        outcome["data_root"] = str(data_root)
        outcome["db_copy_sha256"] = db_sha
        outfile = REPO_STORAGE / "TREECUT_B1_FAIL_REPRO.json"
    else:
        media, err = pick_media(26.0)
        if err:
            raise SystemExit(err)
        mid, mpath, mdur = media
        text, nlen, tries = calibrate_narration(tts_model)
        plan = build_plan(mid, mpath, mdur, 25.0)
        request = CreativeRequest(
            selling_points="小户型岛台 伸缩 收纳", narration=text,
            target_duration=25.0, output_mp4=True, output_jianying=True,
            output_preset="vertical", style="natural", duration_strategy="strict_reject")
        t0 = time.time()
        try:
            res = ProductionService().create(request, plan_override=plan)
            report = json.loads(Path(res.report_json).read_text(encoding="utf-8"))
            fin = Path(res.final_mp4)
            fin_dur = ffprobe_duration(fin)
            nwav = Path(res.project_dir) / "work" / "narration.wav"
            import wave
            with wave.open(str(nwav), "rb") as wf:
                nlen_real = round(wf.getnframes() / wf.getframerate(), 3)
            outcome = {
                "mode": "success", "PASS": True,
                "seconds": round(time.time() - t0, 1),
                "run_id": Path(res.project_dir).name,
                "project_dir": res.project_dir,
                "final_mp4": res.final_mp4, "final_mp4_sha256": sha256_file(fin),
                "final_mp4_duration_s": fin_dur,
                "jianying_draft": res.jianying_draft,
                "narration_chars": len(text), "narration_calib_tries": tries,
                "narration_duration_s": nlen_real,
                "narration_coverage_pct": round(nlen_real / fin_dur * 100, 2) if fin_dur else None,
                "duration_contract": report.get("duration_contract"),
                "statuses": report.get("statuses"),
                "quality_passed": report.get("quality", {}).get("passed"),
                "media": {"id": mid, "path": mpath, "duration_s": mdur},
                "data_root": str(data_root),
                "db_copy_sha256": db_sha,
            }
        except Exception as exc:  # noqa: BLE001
            outcome = {"mode": "success", "PASS": False,
                       "error": f"{type(exc).__name__}: {exc}",
                       "data_root": str(data_root)}
        outfile = REPO_STORAGE / "TREECUT_B1_SUCCESS_REPRO.json"
    outfile.write_text(json.dumps(outcome, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    print(json.dumps(outcome, ensure_ascii=False, indent=1))
    return outcome


if __name__ == "__main__":
    run(MODE)
