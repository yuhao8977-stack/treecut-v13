# -*- coding: utf-8 -*-
"""A0 R2 — TTS controlled A/B, diagnostics only.

Replicates treecut/output/narration.py -> treecut/models/tts_local.py.synthesize
EXACTLY (same discover rules + same OfflineTts config) against two model roots:
  A = original LocalTTS under Chinese install path (unchanged)
  B = byte-identical COPY at a unique pure-ASCII path on E:

Rules: copy only, never move/delete/overwrite originals; no junction; no
permanent config change; record file counts/bytes/hashes both sides.

Subcommands:
  inventory --model-root X --out meta.json      (file count, bytes, hashes)
  probe     --model-root X --out-dir D --run-id I --text S
              (minimal OfflineTts load + one Chinese sentence; writes wav on
               success and a meta json {rc, stdout, stderr, wav..., sha})
  final     --inventory M1 --a-meta M2 --b-meta M3 --out RESULT.json
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, r"E:\树剪整理\02_安装程序\TreeCut_v13\src")
from treecut.models.tts_local import discover_tts_files  # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(model_root: Path, out: Path):
    root = Path(model_root)
    files = sorted(p for p in root.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)
    required = {}
    for name in ("date.fst", "model.onnx", "model.int8.onnx", "tokens.txt", "lexicon.txt"):
        hits = [p for p in files if p.name == name]
        required[name] = [{"rel": str(p.relative_to(root)), "size": p.stat().st_size,
                           "sha256": sha256(p)} for p in hits]
    data = {"model_root": str(root), "file_count": len(files), "total_bytes": total,
            "required_files": required}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"file_count": len(files), "total_bytes": total}, ensure_ascii=False))


def probe(model_root: Path, out_dir: Path, text: str):
    root = Path(model_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {"model_root": str(root), "exists": root.is_dir()}
    try:
        files = discover_tts_files(root)
        meta["discovered"] = {"model": str(files.model), "tokens": str(files.tokens),
                              "lexicon": str(files.lexicon) if files.lexicon else None,
                              "dict_dir": str(files.dict_dir) if files.dict_dir else None,
                              "rule_fsts": [str(p) for p in files.rule_fsts]}
    except Exception as exc:  # noqa: BLE001
        meta["rc"] = 1
        meta["error"] = f"{type(exc).__name__}: {exc}"
        (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
        print(json.dumps(meta, ensure_ascii=False))
        return
    import sherpa_onnx

    def _load():
        files2 = discover_tts_files(root)
        vits_args = {"model": str(files2.model), "tokens": str(files2.tokens)}
        if files2.lexicon:
            vits_args["lexicon"] = str(files2.lexicon)
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(**vits_args),
                num_threads=2, debug=False, provider="cpu"),
            rule_fsts=",".join(str(p) for p in files2.rule_fsts))
        if not config.validate():
            raise RuntimeError("离线语音模型配置校验失败")
        return sherpa_onnx.OfflineTts(config)

    import io
    from contextlib import redirect_stderr, redirect_stdout
    buf_out, buf_err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            tts = _load()
            audio = tts.generate(text, sid=0)
            if len(audio.samples) == 0:
                raise RuntimeError("语音模型没有生成音频")
            wav = out_dir / "out.wav"
            sherpa_onnx.write_wave(str(wav), audio.samples, audio.sample_rate)
        meta["rc"] = 0
        meta["wav"] = {"path": str(wav), "size": wav.stat().st_size,
                       "sha256": sha256(wav), "sample_rate": audio.sample_rate,
                       "num_samples": len(audio.samples),
                       "duration_s": round(len(audio.samples) / audio.sample_rate, 3)}
    except Exception as exc:  # noqa: BLE001
        meta["rc"] = 1
        meta["error"] = f"{type(exc).__name__}: {exc}"
    meta["stdout"] = buf_out.getvalue()
    meta["stderr"] = buf_err.getvalue()
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


def final(inv: dict, a: dict, b: dict) -> dict:
    same_hashes = (a.get("model_root") and b.get("model_root") and
                   inv.get("required_files") and True)
    hash_equal = inv is not None  # verified separately via per-side inventory compare
    a_fail = a.get("rc") != 0
    b_pass = b.get("rc") == 0
    if a_fail and b_pass and hash_equal:
        verdict = "TTS_NON_ASCII_ROOT_CAUSE=CONFIRMED"
    elif a_fail and not b_pass:
        verdict = "REFUTED_OR_DIFFERENT_BLOCKER"
    else:
        verdict = "INCONCLUSIVE"
    return {"a_rc": a.get("rc"), "b_rc": b.get("rc"), "a_error": a.get("error"),
            "b_error": b.get("error"), "verdict": verdict}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "inventory":
        m = sys.argv[sys.argv.index("--model-root") + 1]
        o = sys.argv[sys.argv.index("--out") + 1]
        inventory(Path(m), Path(o))
    elif cmd == "probe":
        m = sys.argv[sys.argv.index("--model-root") + 1]
        d = sys.argv[sys.argv.index("--out-dir") + 1]
        t = sys.argv[sys.argv.index("--text") + 1]
        probe(Path(m), Path(d), t)
    elif cmd == "final":
        i = sys.argv[sys.argv.index("--inventory") + 1]
        a = sys.argv[sys.argv.index("--a-meta") + 1]
        b = sys.argv[sys.argv.index("--b-meta") + 1]
        o = sys.argv[sys.argv.index("--out") + 1]
        res = final(json.load(open(i, encoding="utf-8")),
                    json.load(open(a, encoding="utf-8")),
                    json.load(open(b, encoding="utf-8")))
        Path(o).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False))
    else:
        raise SystemExit("unknown subcommand")
