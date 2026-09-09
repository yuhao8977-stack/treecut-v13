"""Offline Chinese/English speech synthesis through sherpa-onnx."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from treecut.models.cache import get as cache_get


@dataclass(frozen=True)
class TtsFiles:
    model: Path
    tokens: Path
    lexicon: Path | None
    dict_dir: Path | None
    rule_fsts: tuple[Path, ...]


def discover_tts_files(model_root: Path) -> TtsFiles:
    models = sorted(model_root.rglob("*.onnx"), key=lambda path: path.stat().st_size, reverse=True) if model_root.is_dir() else []
    tokens = list(model_root.rglob("tokens.txt")) if model_root.is_dir() else []
    if not models or not tokens:
        raise FileNotFoundError(f"离线语音模型不完整：{model_root}")
    lexicons = list(model_root.rglob("lexicon.txt"))
    dict_dirs = [p for p in model_root.rglob("dict") if p.is_dir()]
    rule_fsts = tuple(sorted(model_root.rglob("*.fst")))
    return TtsFiles(
        models[0], tokens[0], lexicons[0] if lexicons else None,
        dict_dirs[0] if dict_dirs else None, rule_fsts,
    )


def synthesize(text: str, output_wav: Path, model_root: Path) -> Path:
    """Synthesize speech at the model's native speed; callers apply speed changes."""
    if not text.strip():
        raise ValueError("配音文字不能为空")
    import sherpa_onnx

    def _load():
        files = discover_tts_files(model_root)
        vits_args = {"model": str(files.model), "tokens": str(files.tokens)}
        if files.lexicon:
            vits_args["lexicon"] = str(files.lexicon)
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(**vits_args),
                num_threads=2,
                debug=False,
                provider="cpu",
            ),
            rule_fsts=",".join(str(path) for path in files.rule_fsts),
        )
        if not config.validate():
            raise RuntimeError("离线语音模型配置校验失败")
        return sherpa_onnx.OfflineTts(config)

    tts = cache_get(f"tts:{model_root}", _load)
    audio = tts.generate(text, sid=0)
    if len(audio.samples) == 0:
        raise RuntimeError("语音模型没有生成音频")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    sherpa_onnx.write_wave(str(output_wav), audio.samples, audio.sample_rate)
    return output_wav
