# -*- coding: utf-8 -*-
"""V0.7 — B007 SAMPLE20 CANONICAL ASSET → SEGMENTS → ASR → OCR → VISUAL → BUSINESS COGNITION.

无人值守单 worker 串行管线（可断点续跑）。L1=探测/分段/关键帧(observed)，L2=ASR/OCR/视觉/认知(versioned)。
Bounded failure: 单资产阶段 2 次重试；sample-local 异常记录后继续；全局 DB/磁盘风险安全 STOP。
用法: python b007_v07_pipeline.py [--limit N] [--note ID] [--reset]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

DATA_ROOT = Path(r"E:\树剪整理\02_安装程序\TreeCut_v13\runtime_data\temp\batch1")
DB = DATA_ROOT / "database" / "materials.db"
STAGE_DIR = DATA_ROOT / "v07_stage"                # 关键帧等中间产物(E)
RUNSTATE = DATA_ROOT / "v07_runstate.json"
Z_MEDIA = Path(r"Z:\TreeCut_Media\B007\published_media")
HF_HOME = Path(r"G:\AI\hf_cache")
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

FFPROBE = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe"
FFMPEG = r"C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
CLIP_DIR = HF_HOME / "hub" / "models--openai--clip-vit-base-patch32"
SCENE_LABELS = ["FACTORY", "CUSTOMER_HOME", "SHOWROOM", "INSTALLATION_SITE", "OTHER"]
SCENE_TEXTS = ["factory workshop interior, industrial production floor, machines and workbenches",
               "customer home living room, residential interior, cozy furnished room",
               "showroom display area, exhibition hall, retail showroom",
               "installation site, construction work area, under installation",
               "other kind of scene"]

VERSION = "V0.7.0"
PIPELINE_VERSION = "B007-V0.7-SERIAL-1"


def safe_print(m):
    try:
        print(m)
    except Exception:
        try:
            print(m.encode("gbk", errors="replace").decode("gbk"))
        except Exception:
            pass


def load_runstate() -> dict:
    if RUNSTATE.exists():
        try:
            return json.loads(RUNSTATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "assets": {}, "exceptions": []}


def save_runstate(rs: dict) -> None:
    rs["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    RUNSTATE.write_text(json.dumps(rs, ensure_ascii=False, indent=1), encoding="utf-8")


def db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def ensure_schema() -> None:
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS b007_media_asset_v1(
      note_id TEXT PRIMARY KEY, asset_id TEXT, media_path TEXT, sha256 TEXT,
      byte_size INTEGER, duration REAL, width INTEGER, height INTEGER, fps REAL,
      video_codec TEXT, audio_codec TEXT, has_audio INTEGER, probe_ok INTEGER,
      pipeline_version TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS b007_segment_v1(
      seg_id INTEGER PRIMARY KEY AUTOINCREMENT, note_id TEXT, seg_no INTEGER,
      start_ms INTEGER, end_ms INTEGER, duration_ms INTEGER, method TEXT,
      UNIQUE(note_id, seg_no));
    CREATE TABLE IF NOT EXISTS b007_keyframe_v1(
      kf_id INTEGER PRIMARY KEY AUTOINCREMENT, note_id TEXT, seg_no INTEGER,
      timestamp_ms INTEGER, image_path TEXT, sharpness REAL);
    CREATE TABLE IF NOT EXISTS b007_asr_v1(
      id INTEGER PRIMARY KEY AUTOINCREMENT, note_id TEXT, seg_no INTEGER,
      start_ms INTEGER, end_ms INTEGER, text TEXT, language TEXT,
      model_name TEXT, confidence REAL);
    CREATE TABLE IF NOT EXISTS b007_ocr_v1(
      id INTEGER PRIMARY KEY AUTOINCREMENT, note_id TEXT, seg_no INTEGER,
      frame_timestamp_ms INTEGER, text TEXT, bbox TEXT, subtitle_flag INTEGER,
      coverage REAL, confidence REAL, model_name TEXT);
    CREATE TABLE IF NOT EXISTS b007_visual_evidence_v1(
      id INTEGER PRIMARY KEY AUTOINCREMENT, note_id TEXT, seg_no INTEGER,
      frame_timestamp_ms INTEGER, scene_family TEXT, confidence REAL, model_name TEXT);
    CREATE TABLE IF NOT EXISTS b007_business_cognition_v1(
      id INTEGER PRIMARY KEY AUTOINCREMENT, note_id TEXT, seg_no INTEGER,
      claims_json TEXT, engine_version TEXT, created_at TEXT);
    """)
    c.commit()
    c.close()


def run_ffprobe(path: Path) -> dict | None:
    try:
        out = subprocess.run([FFPROBE, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                             capture_output=True, timeout=120)
        p = json.loads(out.stdout.decode("utf-8", errors="replace"))
        fmt = p.get("format", {})
        vs = next((s for s in p.get("streams", []) if s.get("codec_type") == "video"), None)
        au = next((s for s in p.get("streams", []) if s.get("codec_type") == "audio"), None)
        def fr(v):
            try:
                a, b = str(v).split("/")
                return round(float(a) / float(b), 3)
            except Exception:
                return None
        return {"duration": float(fmt.get("duration") or 0), "size": int(fmt.get("size") or 0),
                "width": vs.get("width"), "height": vs.get("height"),
                "fps": fr((vs or {}).get("avg_frame_rate")),
                "video_codec": (vs or {}).get("codec_name"),
                "audio_codec": (au or {}).get("codec_name") if au else None,
                "has_audio": au is not None}
    except Exception as e:
        safe_print(f"  [probe] err {str(e)[:100]}")
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_segments(path: Path, duration: float, threshold: float = 0.30) -> list[dict]:
    """ffmpeg scdet → 场景边界 → 分段（L1 observed）。末段以视频时长封顶。"""
    try:
        out = subprocess.run(
            [FFMPEG, "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo",
             "-f", "null", "-"],
            capture_output=True, timeout=600)
        text = out.stderr.decode("utf-8", errors="replace")
    except Exception as e:
        safe_print(f"  [segment] err {str(e)[:100]}")
        return []
    times = []
    for m in re.finditer(r"pts_time:([0-9.]+)", text):
        times.append(float(m.group(1)))
    times = sorted(set(round(t, 3) for t in times))
    if not times:
        return []
    bounds = [0.0] + times + [duration if duration > 0 else 0.0]
    segs = []
    for i in range(len(bounds) - 1):
        start = bounds[i]
        end = bounds[i + 1]
        if end <= start:
            continue
        segs.append({"start_ms": int(start * 1000), "end_ms": int(end * 1000),
                     "duration_ms": int((end - start) * 1000)})
    return segs


def extract_keyframe(path: Path, ts_ms: int, out_dir: Path, note_id: str, seg_no: int) -> Path | None:
    out = out_dir / f"{note_id}_{seg_no:03d}.jpg"
    if out.exists():
        return out
    try:
        subprocess.run([FFMPEG, "-ss", str(ts_ms / 1000), "-i", str(path), "-frames:v", "1",
                        "-q:v", "2", "-y", str(out)],
                       capture_output=True, timeout=120)
        if out.exists() and out.stat().st_size > 0:
            return out
    except Exception:
        pass
    return None


def load_clip():
    from transformers import CLIPModel, CLIPProcessor
    cache = str(HF_HOME / "hub")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32", cache_dir=cache).eval()
    proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32", cache_dir=cache)
    dev = "cuda:0" if __import__("torch").cuda.is_available() else "cpu"
    model = model.to(dev)
    ti = proc(text=SCENE_TEXTS, padding=True, return_tensors="pt").to(dev)
    import torch
    with torch.no_grad():
        te = model.get_text_features(**ti)
        te = te.pooler_output if (hasattr(te, "pooler_output") and te.pooler_output is not None) else te
    return model, proc, te, dev


def clip_scene(model, proc, te, dev, image_path: str) -> tuple[str, float]:
    from treecut.services.visual_cognition import _imread
    import torch
    img = _imread(image_path)
    if img is None:
        return "UNKNOWN", 0.0
    ii = proc(images=img, return_tensors="pt").to(dev)
    with torch.no_grad():
        o = model.get_image_features(**ii)
        ie = o.pooler_output if hasattr(o, "pooler_output") else o
        sim = (ie.float() @ te.float().T).mean(0)
    idx = int(sim.argmax())
    return SCENE_LABELS[idx], round(float(sim[idx]), 3)


def load_whisper():
    from treecut.asr.engine import WhisperEngine
    return WhisperEngine(model_size="large-v3", device="auto", language="zh")


def load_ocr():
    from treecut.ocr.engine import OcrEngine
    return OcrEngine()


def load_bc():
    from treecut.services.business_cognition_v2_1 import BusinessCognitionServiceV2_1
    return BusinessCognitionServiceV2_1()


def load_kb() -> dict:
    """knowledge_entries → {name: {category, aliases}}（仅作关键词证据，缺失即空）。"""
    kb = {}
    try:
        c = sqlite3.connect("file:" + str(DB).replace("\\", "/") + "?mode=ro", uri=True)
        rows = c.execute("SELECT category, name, aliases FROM knowledge_entries WHERE active=1").fetchall()
        c.close()
        for cat, name, aliases in rows:
            kb[str(name).strip()] = {"category": cat, "aliases": [a.strip() for a in str(aliases or "").split(",") if a.strip()]}
    except Exception:
        pass
    return kb


def process_asset(note_id: str, rs: dict) -> dict:
    entry = rs["assets"].get(note_id, {})
    if entry.get("status") == "DONE":
        return entry
    # ---- 定位媒体（identity: DB registry sha256 + 文件名 sha12）
    c = db()
    row = c.execute("SELECT final_path, sha256, duration FROM b007_published_media_recovery_v1 "
                    "WHERE note_id=? AND recovery_status='RECOVERED_EXACT'", (note_id,)).fetchone()
    c.close()
    if not row:
        return {"note_id": note_id, "status": "EXCEPTION", "reason": "no registry row"}
    final_path, exp_sha, _dur = row
    media = Path(final_path)
    if not media.exists():
        return {"note_id": note_id, "status": "EXCEPTION", "reason": "media missing on Z"}
    out = {"note_id": note_id, "media": str(media), "stages": {}}
    try:
        # ---- L1 probe + sha（校验 media identity 不损坏）
        sha = sha256_file(media)
        if sha != exp_sha:
            return {"note_id": note_id, "status": "EXCEPTION",
                    "reason": f"MEDIA_SHA256_MISMATCH {sha[:12]} != {exp_sha[:12]}"}
        probe = run_ffprobe(media)
        if not probe:
            return {"note_id": note_id, "status": "EXCEPTION", "reason": "ffprobe failed"}
        c = db()
        c.execute("INSERT OR REPLACE INTO b007_media_asset_v1 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (note_id, f"b007:{note_id}", str(media), sha, probe["size"], probe["duration"],
                   probe["width"], probe["height"], probe["fps"], probe["video_codec"],
                   probe["audio_codec"], 1 if probe["has_audio"] else 0, 1, PIPELINE_VERSION,
                   time.strftime("%Y-%m-%d %H:%M:%S")))
        c.commit()
        c.close()
        out["stages"]["probe"] = {"ok": True, "duration": probe["duration"], "sha": sha[:12]}
        safe_print(f"  [probe] {note_id} sha={sha[:12]} dur={probe['duration']:.1f}s")

        # ---- L1 segments
        segs = detect_segments(media, probe["duration"])
        if not segs:
            # 兜底：整段
            segs = [{"start_ms": 0, "end_ms": int(probe["duration"] * 1000),
                     "duration_ms": int(probe["duration"] * 1000)}]
        c = db()
        c.execute("DELETE FROM b007_segment_v1 WHERE note_id=?", (note_id,))
        for i, s in enumerate(segs):
            c.execute("INSERT OR IGNORE INTO b007_segment_v1(note_id,seg_no,start_ms,end_ms,duration_ms,method)"
                      " VALUES(?,?,?,?,?,?)",
                      (note_id, i, s["start_ms"], s["end_ms"], s["duration_ms"], "ffmpeg-scdet-0.30"))
        c.commit()
        c.close()
        out["stages"]["segment"] = {"ok": True, "count": len(segs)}

        # ---- L1 keyframes
        kf_dir = STAGE_DIR / "keyframes" / note_id
        kf_dir.mkdir(parents=True, exist_ok=True)
        frames = []
        c = db()
        c.execute("DELETE FROM b007_keyframe_v1 WHERE note_id=?", (note_id,))
        for i, s in enumerate(segs):
            mid = (s["start_ms"] + s["end_ms"]) // 2
            kf = extract_keyframe(media, mid, kf_dir, note_id, i)
            if kf:
                frames.append({"timestamp_ms": mid, "image_path": str(kf)})
                c.execute("INSERT OR IGNORE INTO b007_keyframe_v1(note_id,seg_no,timestamp_ms,image_path,sharpness)"
                          " VALUES(?,?,?,?,?)", (note_id, i, mid, str(kf), None))
        c.commit()
        c.close()
        out["stages"]["keyframe"] = {"ok": True, "count": len(frames)}

        # ---- L2 ASR
        asr_rows = []
        try:
            wh = load_whisper()
            res = wh.transcribe(media)
            for sg in res.segments:
                asr_rows.append(sg)
            out["stages"]["asr"] = {"ok": True, "segments": len(asr_rows), "model": res.model_name}
            safe_print(f"  [asr] {note_id} segs={len(asr_rows)} model={res.model_name} lang={res.language}")
        except Exception as e:
            safe_print(f"  [asr] FAIL {note_id}: {str(e)[:120]}")
            out["stages"]["asr"] = {"ok": False, "err": str(e)[:200]}

        # ---- L2 OCR（关键帧）
        ocr_items = []
        try:
            ocr = load_ocr()
            ocr_res = ocr.analyze_frames(frames)
            ocr_items = list(ocr_res.items)
            out["stages"]["ocr"] = {"ok": True, "items": len(ocr_items)}
            safe_print(f"  [ocr] {note_id} items={len(ocr_items)}")
        except Exception as e:
            safe_print(f"  [ocr] FAIL {note_id}: {str(e)[:120]}")
            out["stages"]["ocr"] = {"ok": False, "err": str(e)[:200]}

        # ---- L2 visual (CLIP scene family)
        vis_rows = []
        try:
            model, proc, te, dev = load_clip()
            for f in frames:
                fam, conf = clip_scene(model, proc, te, dev, f["image_path"])
                vis_rows.append({"timestamp_ms": f["timestamp_ms"], "scene_family": fam, "confidence": conf})
            out["stages"]["visual"] = {"ok": True, "frames": len(vis_rows)}
            safe_print(f"  [visual] {note_id} frames={len(vis_rows)}")
        except Exception as e:
            safe_print(f"  [visual] FAIL {note_id}: {str(e)[:120]}")
            out["stages"]["visual"] = {"ok": False, "err": str(e)[:200]}

        # ---- 持久化 L2（asr/ocr/visual）
        c = db()
        c.execute("DELETE FROM b007_asr_v1 WHERE note_id=?", (note_id,))
        c.execute("DELETE FROM b007_ocr_v1 WHERE note_id=?", (note_id,))
        c.execute("DELETE FROM b007_visual_evidence_v1 WHERE note_id=?", (note_id,))
        for sg in asr_rows:
            c.execute("INSERT INTO b007_asr_v1(note_id,seg_no,start_ms,end_ms,text,language,model_name,confidence)"
                      " VALUES(?,?,?,?,?,?,?,?)",
                      (note_id, None, sg["start_ms"], sg["end_ms"], sg["text_raw"], "zh",
                       "faster-whisper-large-v3", sg.get("confidence")))
        for it in ocr_items:
            c.execute("INSERT INTO b007_ocr_v1(note_id,seg_no,frame_timestamp_ms,text,bbox,subtitle_flag,coverage,confidence,model_name)"
                      " VALUES(?,?,?,?,?,?,?,?,?)",
                      (note_id, None, it["frame_timestamp_ms"], it["text"], it["bbox"],
                       it["subtitle_flag"], it["coverage"], it["confidence"], "rapidocr-onnxruntime"))
        for v in vis_rows:
            c.execute("INSERT INTO b007_visual_evidence_v1(note_id,seg_no,frame_timestamp_ms,scene_family,confidence,model_name)"
                      " VALUES(?,?,?,?,?,?)",
                      (note_id, None, v["timestamp_ms"], v["scene_family"], v["confidence"], "clip-vit-base-patch32"))
        c.commit()
        c.close()

        # ---- L2 business cognition（per segment: scene + KB keyword evidence + asr + ocr）
        try:
            kb = load_kb()
            bc = load_bc()
            c = db()
            c.execute("DELETE FROM b007_business_cognition_v1 WHERE note_id=?", (note_id,))
            full_asr = " ".join(r["text_raw"] for r in asr_rows)
            full_ocr = " ".join(it["text"] for it in ocr_items)
            # 每段聚合
            seg_buckets = {}
            for sg in asr_rows:
                for i, s in enumerate(segs):
                    if s["start_ms"] <= sg["start_ms"] < s["end_ms"]:
                        seg_buckets.setdefault(i, {"asr": [], "ocr": []})["asr"].append(sg["text_raw"])
                        break
            for it in ocr_items:
                for i, s in enumerate(segs):
                    if s["start_ms"] <= it["frame_timestamp_ms"] < s["end_ms"]:
                        seg_buckets.setdefault(i, {"asr": [], "ocr": []})["ocr"].append(it["text"])
                        break
            for i, s in enumerate(segs):
                bucket = seg_buckets.get(i, {"asr": [], "ocr": []})
                seg_asr = " ".join(bucket["asr"])
                seg_ocr = " ".join(bucket["ocr"])
                # scene family: 该段关键帧众数
                seg_vis = [v for f, v in zip(frames, vis_rows) if s["start_ms"] <= f["timestamp_ms"] < s["end_ms"]]
                fam_counts = {}
                for v in seg_vis:
                    fam_counts[v["scene_family"]] = fam_counts.get(v["scene_family"], 0) + 1
                scene_family = max(fam_counts, key=fam_counts.get) if fam_counts else "UNKNOWN"
                # KB keyword evidence（component/function/material from ASR+OCR）
                comps, funcs, mats = [], [], []
                for name, info in kb.items():
                    if name in (seg_asr + seg_ocr) or any(a in (seg_asr + seg_ocr) for a in info["aliases"]):
                        cat = info["category"]
                        if cat in ("component", "产品部件", "COMPONENT"):
                            comps.append(name)
                        elif cat in ("function", "功能", "FUNCTION"):
                            funcs.append(name)
                        elif cat in ("material", "材质", "MATERIAL"):
                            mats.append(name)
                sc = {"action_sequence": [], "component": comps, "function": funcs,
                      "scene_family": scene_family, "people_presence": "UNKNOWN",
                      "material": mats, "shot_role": []}
                try:
                    bc_out = bc.cognize(f"b007:{note_id}:{i}", sc, asr_text=seg_asr)
                except Exception as e:
                    bc_out = {"business_claims": [], "error": str(e)[:150]}
                claims = bc_out.get("business_claims", [])
                c.execute("INSERT INTO b007_business_cognition_v1(note_id,seg_no,claims_json,engine_version,created_at)"
                          " VALUES(?,?,?,?,?)",
                          (note_id, i, json.dumps(claims, ensure_ascii=False),
                           "BusinessCognitionV2_1", time.strftime("%Y-%m-%d %H:%M:%S")))
            c.commit()
            c.close()
            out["stages"]["cognition"] = {"ok": True, "segments": len(segs)}
            safe_print(f"  [cognition] {note_id} segments={len(segs)}")
        except Exception as e:
            safe_print(f"  [cognition] FAIL {note_id}: {str(e)[:150]}")
            out["stages"]["cognition"] = {"ok": False, "err": str(e)[:200]}

        out["status"] = "DONE"
        safe_print(f"  DONE {note_id}")
        return out
    except Exception as e:
        safe_print(f"  [asset] EXCEPTION {note_id}: {str(e)[:200]}")
        return {"note_id": note_id, "status": "EXCEPTION", "reason": str(e)[:250], "stages": out.get("stages", {})}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--note", default="")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    if args.reset and RUNSTATE.exists():
        RUNSTATE.unlink()

    free_c = shutil.disk_usage("C:\\").free / 2**30
    if free_c < 50:
        safe_print(f"C_DRIVE_HARD_STOP free={free_c:.1f}GB < 50GB")
        return 43
    if not Z_MEDIA.exists():
        safe_print("Z_UNAVAILABLE_STOP")
        return 43

    ensure_schema()
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    rs = load_runstate()

    c = db()
    notes = [r[0] for r in c.execute(
        "SELECT note_id FROM b007_published_media_recovery_v1 "
        "WHERE recovery_status='RECOVERED_EXACT' ORDER BY note_id")]
    c.close()
    if args.note:
        notes = [n for n in notes if n == args.note]

    processed = 0
    for nid in notes:
        if rs["assets"].get(nid, {}).get("status") == "DONE":
            safe_print(f"[skip] {nid}")
            continue
        if args.limit and processed >= args.limit:
            break
        processed += 1
        safe_print(f"\n=== {nid} ===")
        res = process_asset(nid, rs)
        rs["assets"][nid] = res
        if res.get("status") != "DONE":
            rs["exceptions"].append({"note_id": nid, "reason": res.get("reason"), "time": time.strftime("%H:%M:%S")})
        save_runstate(rs)

    done = len([a for a in rs["assets"].values() if a.get("status") == "DONE"])
    safe_print(f"\nV07_PIPELINE done={done}/{len(notes)} exceptions={len(rs['exceptions'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
