"""Cheap, deterministic model-file and runtime compatibility contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import importlib.util
import json
from pathlib import Path


@dataclass(frozen=True)
class ModelCheck:
    files_complete: bool
    runtime_compatible: bool
    load_verified: bool
    total_bytes: int
    issues: tuple[str, ...]
    signature: str = ""

    @property
    def ready(self) -> bool:
        return self.files_complete and self.runtime_compatible

    def to_dict(self) -> dict:
        return asdict(self) | {"ready": self.ready}


def _required(root: Path, rules: dict[str, int]) -> tuple[list[str], int]:
    issues, total = [], 0
    for relative, minimum in rules.items():
        path = root / relative
        if not path.is_file():
            issues.append(f"missing:{relative}")
            continue
        size = path.stat().st_size
        total += size
        if size < minimum:
            issues.append(f"too_small:{relative}:{size}<{minimum}")
    return issues, total


def _check(files_issues: list[str], total: int, runtime_issues: list[str]) -> ModelCheck:
    return ModelCheck(not files_issues, not runtime_issues, False, total,
                      tuple(files_issues + runtime_issues))


def _signature(path: Path) -> str:
    digest = hashlib.sha256()
    files = [path] if path.is_file() else (sorted(path.rglob("*")) if path.is_dir() else [])
    for item in files:
        if not item.is_file():
            continue
        stat = item.stat()
        relative = item.name if path.is_file() else str(item.relative_to(path))
        digest.update(f"{relative}|{stat.st_size}|{stat.st_mtime_ns}\n".encode("utf-8"))
    return digest.hexdigest() if files else ""


def _require_json(root: Path, names: tuple[str, ...], issues: list[str]) -> None:
    for name in names:
        path = root / name
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                issues.append(f"invalid:{name}:not_object")
        except Exception as error:
            issues.append(f"invalid:{name}:{type(error).__name__}")


def inspect_model_contracts(models: Path, *, cuda_available: bool,
                            cuda_runtime: bool,
                            locations: dict[str, Path] | None = None,
                            verification_receipt: Path | None = None) -> dict[str, ModelCheck]:
    checks: dict[str, ModelCheck] = {}
    locations = locations or {}
    roots: dict[str, Path] = {}

    root = models / "Florence-2-base"
    roots["florence"] = root
    issues, total = _required(root, {
        "model.safetensors": 400_000_000, "config.json": 1_000,
        "preprocessor_config.json": 200, "tokenizer.json": 1_000_000,
        "modeling_florence2.py": 50_000, "processing_florence2.py": 20_000,
    })
    _require_json(root, ("config.json", "preprocessor_config.json"), issues)
    runtime = [] if importlib.util.find_spec("transformers") else ["runtime_missing:transformers"]
    checks["florence"] = _check(issues, total, runtime)

    root = models / "Qwen3-VL-4B-Instruct-FP8"
    roots["qwen_vl"] = root
    issues, total = _required(root, {
        "config.json": 5_000, "model.safetensors.index.json": 10_000,
        "preprocessor_config.json": 200, "tokenizer.json": 5_000_000,
    })
    _require_json(root, ("config.json", "preprocessor_config.json", "model.safetensors.index.json"), issues)
    index = root / "model.safetensors.index.json"
    if index.is_file():
        try:
            weight_map = json.loads(index.read_text(encoding="utf-8")).get("weight_map") or {}
            shards = sorted(set(weight_map.values()))
            if not shards:
                issues.append("invalid:index_has_no_weight_map")
            for shard in shards:
                shard_path = root / shard
                if not shard_path.is_file():
                    issues.append(f"missing:{shard}")
                elif shard_path.stat().st_size < 100_000_000:
                    issues.append(f"too_small:{shard}:{shard_path.stat().st_size}<100000000")
                else:
                    total += shard_path.stat().st_size
        except Exception as error:
            issues.append(f"invalid:index_json:{type(error).__name__}")
    runtime = []
    if not importlib.util.find_spec("transformers"):
        runtime.append("runtime_missing:transformers")
    if not cuda_runtime:
        runtime.append("runtime_incompatible:torch_has_no_cuda_build")
    elif not cuda_available:
        runtime.append("hardware_unavailable:nvidia_cuda")
    checks["qwen_vl"] = _check(issues, total, runtime)

    root = models / "SenseVoiceSmall"
    roots["sensevoice"] = root
    issues, total = _required(root, {
        "model.pt": 800_000_000, "config.yaml": 1_000,
        "chn_jpn_yue_eng_ko_spectok.bpe.model": 300_000, "am.mvn": 5_000,
    })
    runtime = [] if importlib.util.find_spec("funasr") else ["runtime_missing:funasr"]
    checks["sensevoice"] = _check(issues, total, runtime)

    root = locations.get("whisper", models / "Whisper-small")
    roots["whisper"] = root
    issues, total = _required(root, {
        "model.bin": 100_000_000, "config.json": 200,
        "tokenizer.json": 1_000_000, "vocabulary.txt": 100_000,
    })
    _require_json(root, ("config.json",), issues)
    runtime = [] if importlib.util.find_spec("faster_whisper") else ["runtime_missing:faster_whisper"]
    checks["whisper"] = _check(issues, total, runtime)

    yolo = locations.get("yolo", models / "yolov8n.pt")
    roots["yolo"] = yolo
    if yolo.is_file() and yolo.stat().st_size >= 5_000_000:
        issues, total = [], yolo.stat().st_size
    else:
        size = yolo.stat().st_size if yolo.is_file() else 0
        issues, total = [f"missing_or_too_small:{yolo}:{size}<5000000"], size
    runtime = [] if importlib.util.find_spec("ultralytics") else ["runtime_missing:ultralytics"]
    checks["yolo"] = _check(issues, total, runtime)

    for key, folder in (("chinese_clip", "Chinese-CLIP-ViT-B-16"), ("bge_m3", "BGE-M3")):
        root = locations.get(key, models / folder)
        roots[key] = root
        rules = {"config.json": 200}
        if key == "chinese_clip":
            rules.update({"preprocessor_config.json": 100, "vocab.txt": 100_000})
        else:
            rules.update({"tokenizer.json": 1_000_000, "sentencepiece.bpe.model": 1_000_000})
        issues, total = _required(root, rules)
        _require_json(root, ("config.json",), issues)
        weights = ((list(root.glob("*.safetensors")) + list(root.glob("pytorch_model.bin")))
                   if root.is_dir() else [])
        if not weights:
            issues.append("missing:model weights")
        elif max(path.stat().st_size for path in weights) < 100_000_000:
            issues.append("too_small:weight_file")
        else:
            total += sum(path.stat().st_size for path in weights)
        runtime = [] if importlib.util.find_spec("transformers") else ["runtime_missing:transformers"]
        checks[key] = _check(issues, total, runtime)

    root = locations.get("local_tts", models / "LocalTTS")
    roots["local_tts"] = root
    onnx = sorted(root.rglob("*.onnx"), key=lambda path: path.stat().st_size, reverse=True) if root.is_dir() else []
    tokens = list(root.rglob("tokens.txt")) if root.is_dir() else []
    lexicons = list(root.rglob("lexicon.txt")) if root.is_dir() else []
    issues, total = [], 0
    if not onnx or onnx[0].stat().st_size < 100_000_000:
        issues.append("missing_or_too_small:tts_model.onnx")
    else:
        total += onnx[0].stat().st_size
    if not tokens or tokens[0].stat().st_size < 100:
        issues.append("missing_or_too_small:tokens.txt")
    else:
        total += tokens[0].stat().st_size
    if not lexicons or lexicons[0].stat().st_size < 100_000:
        issues.append("missing_or_too_small:lexicon.txt")
    else:
        total += lexicons[0].stat().st_size
    runtime = [] if importlib.util.find_spec("sherpa_onnx") else ["runtime_missing:sherpa_onnx"]
    checks["local_tts"] = _check(issues, total, runtime)
    receipt = {}
    if verification_receipt and verification_receipt.is_file():
        try:
            receipt = json.loads(verification_receipt.read_text(encoding="utf-8")).get("verified") or {}
        except Exception:
            receipt = {}
    for name, check in list(checks.items()):
        signature = _signature(roots[name])
        verified = bool(check.ready and signature and receipt.get(name) == signature)
        checks[name] = replace(check, load_verified=verified, signature=signature)
    return checks


def write_verification_receipt(path: Path, checks: dict[str, ModelCheck],
                               verified_names: list[str]) -> None:
    import time
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verified_at": time.time(),
        "verified": {
            name: checks[name].signature for name in verified_names
            if name in checks and checks[name].ready and checks[name].signature
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
