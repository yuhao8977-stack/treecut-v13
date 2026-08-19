"""Generate offline dependency SBOM, model provenance, notices, and file hashes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform


MODEL_RECORDS = [
    {"path": "models/Florence-2-base", "name": "Florence-2-base",
     "source": "https://huggingface.co/microsoft/Florence-2-base", "license": "MIT",
     "commercial_review": "cleared_by_declared_license"},
    {"path": "models/Qwen3-VL-4B-Instruct-FP8", "name": "Qwen3-VL-4B-Instruct",
     "source": "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct", "license": "Apache-2.0",
     "commercial_review": "cleared_by_declared_license"},
    {"path": "models/SenseVoiceSmall", "name": "SenseVoiceSmall",
     "source": "https://modelscope.cn/models/iic/SenseVoiceSmall", "license": "ModelScope model-license",
     "commercial_review": "manual_review_required"},
    {"path": "models/Whisper-small", "name": "faster-whisper-small",
     "source": "https://huggingface.co/Systran/faster-whisper-small",
     "revision": "536b0662742c02347bc0e980a01041f333bce120", "license": "MIT",
     "commercial_review": "cleared_by_declared_license"},
    {"path": "models/Chinese-CLIP-ViT-B-16", "name": "Chinese-CLIP-ViT-B-16",
     "source": "https://huggingface.co/OFA-Sys/chinese-clip-vit-base-patch16",
     "revision": "36e679e65c2a2fead755ae21162091293ad37834", "license": "Not declared on model card",
     "commercial_review": "manual_review_required"},
    {"path": "models/BGE-M3", "name": "BGE-M3",
     "source": "https://huggingface.co/BAAI/bge-m3",
     "revision": "5617a9f61b028005a4858fdac845db406aefb181", "license": "MIT",
     "commercial_review": "cleared_by_declared_license"},
    {"path": "models/LocalTTS/vits-melo-tts-zh_en", "name": "MeloTTS zh_en ONNX",
     "source": "https://github.com/myshell-ai/MeloTTS", "license": "MIT (bundled LICENSE)",
     "commercial_review": "cleared_by_bundled_license"},
    {"path": "models/yolov8n.pt", "name": "Ultralytics YOLOv8n",
     "source": "https://www.ultralytics.com/license", "license": "AGPL-3.0 or Enterprise",
     "commercial_review": "BLOCKED_without_AGPL_compliance_or_Enterprise_license"},
]

PACKAGE_LICENSE_OVERRIDES = {
    "kaldiio": {
        "license": "NTT evaluation-only license (bundled LICENSE)",
        "commercial_review": "BLOCKED_remove_from_distributable_runtime_or_obtain_permission",
    },
    "pyjianyingdraft": {
        "license": "Apache-2.0 (bundled LICENSE)",
        "commercial_review": "cleared_by_bundled_license",
    },
    "tiktoken": {
        "license": "MIT",
        "commercial_review": "cleared_by_upstream_license",
    },
}


def _license(dist) -> str:
    value = dist.metadata.get("License-Expression") or dist.metadata.get("License") or ""
    value = " ".join(value.split())
    if value and len(value) <= 160 and value.lower() not in {"unknown", "none"}:
        return value
    classifiers = dist.metadata.get_all("Classifier") or []
    found = [item.split(" :: ")[-1] for item in classifiers if "License ::" in item]
    return "; ".join(found) if found else "UNKNOWN"


def dependency_components() -> list[dict]:
    result = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or ""
        if not name:
            continue
        key = name.lower().replace("_", "-")
        result[key] = {
            "name": name, "version": dist.version, "license": _license(dist),
            "homepage": dist.metadata.get("Home-page") or dist.metadata.get("Project-URL") or "",
        }
        result[key].update(PACKAGE_LICENSE_OVERRIDES.get(key, {}))
    return [result[key] for key in sorted(result)]


def immutable_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if (relative.parts and relative.parts[0] == "runtime_data") or "__pycache__" in relative.parts:
            continue
        if path.suffix.lower() == ".pyc" or relative.as_posix() == "release/release_manifest.json":
            continue
        yield path, relative


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_metadata(root: Path, include_hashes: bool = True) -> None:
    release = root / "release"
    release.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()
    components = dependency_components()
    sbom = {"format": "TreeCut dependency lock v1", "generated_at": generated,
            "python": platform.python_version(), "components": components}
    (release / "dependencies.lock.json").write_text(
        json.dumps(sbom, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    models = []
    for record in MODEL_RECORDS:
        item = dict(record)
        target = root / record["path"]
        item["present"] = target.exists()
        item["bytes"] = (target.stat().st_size if target.is_file() else
                         sum(path.stat().st_size for path in target.rglob("*") if path.is_file())) if target.exists() else 0
        models.append(item)
    (release / "models.lock.json").write_text(
        json.dumps({"format": "TreeCut model provenance v1", "generated_at": generated,
                    "models": models}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    unknown = [item for item in components if item["license"] == "UNKNOWN"]
    blocked = [
        item for item in models
        if item["present"] and "BLOCKED" in item["commercial_review"]
    ]
    blocked_packages = [
        item for item in components if "BLOCKED" in item.get("commercial_review", "")
    ]
    lines = ["# TreeCut third-party notices", "", f"Generated: {generated}", "",
             "## Release blockers", ""]
    lines.extend(f"- MODEL BLOCKER: {item['name']} — {item['commercial_review']}" for item in blocked)
    lines.extend([f"- PACKAGE LICENSE UNKNOWN: {item['name']} {item['version']}" for item in unknown])
    lines.extend(
        f"- PACKAGE BLOCKER: {item['name']} {item['version']} -- {item['commercial_review']}"
        for item in blocked_packages
    )
    lines.extend(["", "## Python packages", "", "| Package | Version | License |", "|---|---:|---|"])
    lines.extend(f"| {item['name']} | {item['version']} | {item['license'].replace('|', '/')} |" for item in components)
    lines.extend(["", "## Models", "", "| Model | License | Source | Review |", "|---|---|---|---|"])
    lines.extend(f"| {item['name']} | {item['license']} | {item['source']} | {item['commercial_review']} |" for item in models)
    (release / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if include_hashes:
        checkpoint_path = root / "runtime_data" / "release_hash_checkpoint.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            checkpoint = {}
        entries = []
        files = sorted(immutable_files(root), key=lambda item: item[1].as_posix())
        for index, (path, relative) in enumerate(files, 1):
            stat = path.stat()
            name = relative.as_posix()
            cached = checkpoint.get(name) or {}
            if cached.get("bytes") == stat.st_size and cached.get("mtime_ns") == stat.st_mtime_ns:
                digest = cached["sha256"]
            else:
                digest = sha256(path)
                checkpoint[name] = {
                    "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": digest,
                }
            entries.append({"path": name, "bytes": stat.st_size, "sha256": digest})
            if index % 100 == 0 or stat.st_size >= 100_000_000 or index == len(files):
                checkpoint_path.write_text(
                    json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8"
                )
                print(f"Hashed {index}/{len(files)}: {name}", flush=True)
        manifest = {"format": "TreeCut release manifest v1", "generated_at": generated,
                    "file_count": len(entries), "total_bytes": sum(x["bytes"] for x in entries),
                    "files": entries}
        (release / "release_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--skip-hashes", action="store_true")
    args = parser.parse_args()
    write_metadata(args.root.resolve(), include_hashes=not args.skip_hashes)


if __name__ == "__main__":
    main()
