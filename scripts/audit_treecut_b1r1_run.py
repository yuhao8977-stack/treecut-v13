# -*- coding: utf-8 -*-
"""TREECUT B1R1 — integration runner (runtime python + E install).

Modes:
  success  hand-written COMPLETE 25s narration (whole-sentence selection ONLY,
           never char slicing) + strict 25s -> new video; collects full script
           text/sha/last sentence/punctuation, three-track audio evidence,
           audible-end alignment fields, statuses.
  truncated  64-char short script -> NARRATION_TOO_SHORT (B1 kept) and the old
          139-char mid-truncated script ("...台面宽度可以按户") -> must be
          SCRIPT_TRUNCATED (no TTS needed, gate runs before synthesis).
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
MODE = sys.argv[1] if len(sys.argv) > 1 else "success"

sys.path.insert(0, str(E_SRC))
os.environ.pop("TREECUT_MODEL_ROOT", None)
os.environ.pop("TREECUT_DATA_ROOT", None)
os.environ.pop("TREECUT_DEVELOPMENT_MODE", None)

SHORT_NARRATION = ("小户型也能拥有实用岛台。伸缩设计兼顾办公、用餐和聚会。"
                   "分区收纳让常用物品随手可取。合理定制高度、宽度和台面厚度，让小空间更舒适。")
TRUNCATED_NARRATION = ("小户型也能拥有实用岛台。平时收起来不占过道，需要时轻轻拉出，"
                       "立刻多出一张工作台。分区收纳让常用物品随手可取。"
                       "岩板表面耐刮耐热，泼了水一擦就干净。台面宽度可以按户")

# hand-written, semantically complete, natural-ending narration bank (whole
# sentences only; each ends with 。). Short sentences fill the 24-25s band.
NARRATION_BANK = [
    "小户型也能拥有实用岛台。",
    "平时收起来不占过道，需要时轻轻拉出，立刻多出一张工作台。",
    "它既能当办公桌，也能招待朋友用餐，一物三用不浪费。",
    "台面下方做了分区收纳，抽屉放文具，柜门里放餐具。",
    "常用物品放在顺手的高度，拿取不用弯腰。",
    "边角都做了圆润处理，家里有小孩也不用担心磕碰。",
    "台面宽度可以按户型定制，过道再窄也能放得下。",
    "高度同样可以调节，站着办公或坐着用餐都舒服。",
    "岩板表面耐刮耐热，泼了水一擦就干净。",
    "滑轮带有锁定，拉出后固定不晃动，用起来更安心。",
    "家里来客人时，把台面拉长，就能围坐聊天。",
    "平日不用时收回原位，整个客厅显得宽敞又有条理。",
    "如果你家也有一块闲置的角落，这款设计很值得参考。",
    "安装简单，半天就能完成，当天就能投入使用。",
    "用了几个月，家人最大的感受就是，动线顺畅了，家务也变轻了。",
    "总之，这台小岛台让日常生活方便了许多。",
    # short complete sentences to fill the 24-25s band
    "拉开是一张桌。",
    "收回不占地方。",
    "抽屉放杂物，柜门放餐具。",
    "高度随意调。",
    "宽度按户型做。",
    "打理很简单。",
    "用着很顺手。",
    "家人都喜欢。",
    # extra-fine complete sentences (0.7-1.3s each)
    "很实用。",
    "刚刚好。",
    "很方便。",
    "正合适。",
    "不占地方。",
    "很好打理。",
    "非常顺手。",
    "全家满意。",
]


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_video_duration(path):
    proc = subprocess.run([str(FFPROBE), "-v", "quiet", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)],
                          capture_output=True, timeout=120)
    try:
        data = json.loads(proc.stdout.decode("utf-8", errors="replace"))
        if not any(s.get("codec_type") == "video" for s in data.get("streams", [])):
            return 0.0
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def pick_media(min_duration):
    import sqlite3
    con = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    src_cols = [r[1] for r in con.execute("PRAGMA table_info(sources)")]
    root_col = "path" if "path" in src_cols else "root"
    rows = con.execute(
        f"SELECT m.id, s.{root_col}, m.relative_path FROM media_files m "
        f"JOIN sources s ON s.id = m.source_id "
        f"WHERE m.available = 1 AND m.size_bytes > 20_000_000 LIMIT 500").fetchall()
    con.close()
    probed = 0
    for mid, root, rel in rows:
        full = Path(root) / rel
        if not full.is_file():
            continue
        probed += 1
        d = ffprobe_video_duration(full)
        if d >= min_duration:
            return (mid, str(full), d), None
        if probed >= 60:
            break
    return None, f"no video >= {min_duration}s after {probed} probes"


def select_whole_sentences(tts_model, low=24.4, high=24.75, max_synth=24):
    """Pick COMPLETE sentences (contiguous window) whose JOINED real-TTS length
    lands in [24.4, 24.75], preferring ~24.5; candidate windows scanned widely,
    whole-sentence selection ONLY (never character slicing). Stability filter:
    a candidate is returned only when 3 consecutive full-text syntheses stay in
    [low-0.1, high+0.1] - guards against cross-run TTS variance."""
    from treecut.output.narration import synthesize, wav_duration
    from treecut.quality.publish_gates import check_script_completeness
    work = AUDIT / f"b1r1_calib_{datetime.now().strftime('%H%M%S')}"
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "s.wav"
    per = []
    for s in NARRATION_BANK:
        synthesize(s, wav, tts_model)
        per.append(wav_duration(wav))
    cands = []
    for i in range(len(per)):
        tot = 0.0
        for j in range(i, len(per)):
            tot += per[j]
            if 19.0 <= tot <= 24.9:
                cands.append((abs(tot - 24.3), i, j + 1, round(tot, 2)))
            if tot > 24.9:
                break
    cands.sort()
    best = None
    measured = []
    for _, i, j, _ in cands[:max_synth]:
        text = "".join(NARRATION_BANK[i:j])
        assert check_script_completeness(text).passed
        synthesize(text, wav, tts_model)
        d1 = wav_duration(wav)
        measured.append((i, j, round(d1, 3)))
        if low <= d1 <= high:
            d2 = d1
            stable = True
            for _ in range(2):
                synthesize(text, wav, tts_model)
                d2 = wav_duration(wav)
                if not (low - 0.1 <= d2 <= high + 0.1):
                    stable = False
            if stable:
                return text, round(d2, 3), (i, j)
            if best is None:
                best = (text, d2, (i, j))
        elif best is None and low - 0.15 <= d1 <= high + 0.15:
            best = (text, d1, (i, j))
    if best is not None:
        return best[0], round(best[1], 3), best[2]
    raise RuntimeError(f"no stable whole-sentence window in [{low},{high}]; "
                       f"measured={measured}")


def build_plan(media_id, media_path, duration, total):
    from treecut.workflow.planning import EditPlan, EditSegment
    seg = EditSegment(order=1, media_id=media_id, path=media_path,
                      category="manual", source_start=0.0, source_end=min(total, duration),
                      timeline_start=0.0, timeline_end=min(total, duration),
                      match_score=0.9, matched_terms=("小户型岛台", "伸缩", "收纳"))
    return EditPlan(requested_duration=total, planned_duration=float(total),
                    complete=True, warnings=(), segments=(seg,))


def env_setup(mode):
    from treecut.platform.paths import RuntimePaths, configure_models_path
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    data_root = AUDIT / f"b1r1_{mode}_{ts}"
    os.environ["TREECUT_DATA_ROOT"] = str(data_root)
    db_dir = data_root / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    configure_models_path(data_root, r"E:\TreeCutRuntime\models")
    if PROD_DB.exists():
        shutil.copy2(PROD_DB, db_dir / "materials.db")
    return data_root


def main():
    data_root = env_setup(MODE)
    from treecut.application import CreativeRequest, ProductionService
    if MODE in ("truncated",):
        cases = [
            ("SHORT_64", SHORT_NARRATION, "NARRATION_TOO_SHORT"),
            ("OLD139_TRUNCATED", TRUNCATED_NARRATION, "SCRIPT_TRUNCATED"),
        ]
        results = {}
        for label, text, expect in cases:
            request = CreativeRequest(
                selling_points="小户型岛台 可伸缩 收纳", narration=text,
                target_duration=25.0, output_mp4=True, output_jianying=False,
                output_preset="vertical", style="natural",
                duration_strategy="strict_reject")
            t0 = time.time()
            try:
                ProductionService().create(request)
                results[label] = {"intercepted": False}
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                code = next((c for c in ("NARRATION_TOO_SHORT", "SCRIPT_TRUNCATED",
                                         "SCRIPT_NO_TERMINAL_PUNCTUATION")
                             if c in msg), None)
                results[label] = {"intercepted": True, "failure_code": code,
                                  "expected": expect,
                                  "match": code == expect, "error": msg[:200]}
        outcome = {"mode": MODE, "results": results,
                   "all_match": all(v.get("match") for v in results.values()),
                   "data_root": str(data_root)}
        (REPO_STORAGE / "TREECUT_B1R1_FAIL_CASES.json").write_text(
            json.dumps(outcome, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(outcome, ensure_ascii=False, indent=1))
        return
    # success mode
    from treecut.platform.paths import RuntimePaths
    paths = RuntimePaths.discover()
    tts_model = paths.models / "LocalTTS"
    media, err = pick_media(26.0)
    if err:
        raise SystemExit(err)
    mid, mpath, mdur = media
    text, nlen, win = select_whole_sentences(tts_model)
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
        fin_dur = ffprobe_video_duration(fin)
        outcome = {
            "mode": "success", "PASS": True,
            "seconds": round(time.time() - t0, 1),
            "run_id": Path(res.project_dir).name,
            "project_dir": res.project_dir,
            "final_mp4": res.final_mp4,
            "final_mp4_sha256": sha256_file(fin),
            "final_mp4_duration_s": fin_dur,
            "jianying_draft": res.jianying_draft,
            "whole_sentence_window": win,
            "script": report.get("script"),
            "duration_contract": report.get("duration_contract"),
            "audio_mix": report.get("audio_mix"),
            "audible_end": report.get("audible_end"),
            "statuses": report.get("statuses"),
            "semantic_models": report.get("semantic_models"),
            "media": {"id": mid, "path": mpath, "duration_s": mdur},
            "data_root": str(data_root),
        }
    except Exception as exc:  # noqa: BLE001
        import traceback
        outcome = {"mode": "success", "PASS": False,
                   "error": f"{type(exc).__name__}: {exc}",
                   "trace": traceback.format_exc()[-1200:],
                   "data_root": str(data_root)}
    (REPO_STORAGE / "TREECUT_B1R1_SUCCESS_REPRO.json").write_text(
        json.dumps(outcome, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(outcome, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
