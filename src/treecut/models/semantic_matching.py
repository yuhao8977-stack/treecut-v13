"""Offline Chinese semantic scorers used to rerank explainable material matches."""
from __future__ import annotations

import gc
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from treecut.models.cache import get as cache_get


def _candidate_text(candidate) -> str:
    return " ".join(part for part in (
        candidate.category, candidate.caption, candidate.transcript,
        " ".join(candidate.object_terms), Path(candidate.path).stem,
    ) if part).strip()


def bge_similarity_scores(query: str, candidates: Iterable, model_dir: Path) -> dict[int, float]:
    """Return normalized dense cosine similarities without network access."""
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoTokenizer

    items = list(candidates)
    if not items:
        return {}

    def _load() -> tuple:
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        model = AutoModel.from_pretrained(str(model_dir), local_files_only=True).eval()
        return tokenizer, model

    tokenizer, model = cache_get(f"bge:{model_dir}", _load)
    texts = [query] + [_candidate_text(item) for item in items]
    batch = tokenizer(texts, padding=True, truncation=True, max_length=256,
                      return_tensors="pt")
    with torch.inference_mode():
        vectors = functional.normalize(model(**batch).last_hidden_state[:, 0], p=2, dim=1)
        values = (vectors[1:] @ vectors[0]).tolist()
    del vectors, batch
    gc.collect()
    return {item.media_id: round(float(score), 6) for item, score in zip(items, values)}


def clip_similarity_scores(query: str, candidates: Iterable, model_dir: Path,
                           maximum_images: int = 16,
                           ffmpeg: Path | None = None,
                           ffprobe: Path | None = None) -> dict[int, float]:
    """Compare Chinese query text with stored representative frames locally."""
    import torch
    import torch.nn.functional as functional
    from PIL import Image
    from transformers import ChineseCLIPModel, ChineseCLIPProcessor

    def _fallback_frame(item, temp_dir: Path):
        if ffmpeg is None or ffprobe is None:
            return None
        source = Path(item.path)
        if not source.is_file():
            return None
        try:
            probe = subprocess.run(
                [str(ffprobe), "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(source)],
                capture_output=True, check=False, timeout=60,
            )
            duration = float(probe.stdout.decode("utf-8", errors="replace").strip() or 0)
        except (ValueError, OSError):
            duration = 0.0
        if duration <= 0:
            return None
        moment = max(0.0, min(duration - 0.05, duration * 0.45))
        output = temp_dir / f"fallback_{item.media_id}.jpg"
        result = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{moment:.3f}", "-i", str(source), "-frames:v", "1",
             "-q:v", "3", str(output)],
            capture_output=True, check=False, timeout=90,
        )
        if result.returncode != 0 or not output.is_file() or output.stat().st_size < 1000:
            return None
        return output

    selected = []
    with tempfile.TemporaryDirectory(prefix="treecut_clip_") as temp:
        temp_dir = Path(temp)
        for item in candidates:
            frame = Path(item.representative_frame) if item.representative_frame else None
            if frame and frame.is_file():
                selected.append((item, frame))
            else:
                fallback = _fallback_frame(item, temp_dir)
                if fallback is not None:
                    selected.append((item, fallback))
            if len(selected) >= maximum_images:
                break
        if not selected:
            return {}
        def _load() -> tuple:
            processor = ChineseCLIPProcessor.from_pretrained(
                str(model_dir), local_files_only=True, use_fast=False,
            )
            model = ChineseCLIPModel.from_pretrained(str(model_dir), local_files_only=True).eval()
            return processor, model

        processor, model = cache_get(f"clip:{model_dir}", _load)
        opened = [Image.open(frame).convert("RGB") for _, frame in selected]
        try:
            text_batch = processor(text=[query], return_tensors="pt", padding=True)
            image_batch = processor(images=opened, return_tensors="pt")
            with torch.inference_mode():
                # transformers >= 4.57 no longer returns pooler_output from the
                # ChineseCLIP text model, so get_text_features() raises
                # TypeError(None). Use the [CLS] hidden state + text projection,
                # which is the same pooling the official implementation intends.
                text_outputs = model.text_model(
                    input_ids=text_batch["input_ids"],
                    attention_mask=text_batch["attention_mask"],
                    token_type_ids=text_batch.get("token_type_ids"),
                )
                pooled_text = text_outputs.last_hidden_state[:, 0]
                text = functional.normalize(model.text_projection(pooled_text), p=2, dim=1)
                images = functional.normalize(model.get_image_features(**image_batch), p=2, dim=1)
                values = (images @ text[0]).tolist()
        finally:
            for image in opened:
                image.close()
        gc.collect()
        return {item.media_id: round(float(score), 6)
                for (item, _), score in zip(selected, values)}


def semantic_scores(query: str, candidates: Iterable, models_root: Path,
                    use_bge: bool, use_clip: bool,
                    ffmpeg: Path | None = None,
                    ffprobe: Path | None = None) -> tuple[dict[int, float], dict[int, float], list[str]]:
    """Run optional models independently; a failed enhancement never fakes success."""
    items = list(candidates)
    bge, clip, errors = {}, {}, []
    if use_bge:
        try:
            bge = bge_similarity_scores(query, items, models_root / "BGE-M3")
        except Exception as error:
            errors.append(f"BGE-M3: {type(error).__name__}: {error}")
    if use_clip:
        try:
            clip = clip_similarity_scores(
                query, items, models_root / "Chinese-CLIP-ViT-B-16",
                ffmpeg=ffmpeg, ffprobe=ffprobe,
            )
        except Exception as error:
            errors.append(f"Chinese-CLIP: {type(error).__name__}: {error}")
    return bge, clip, errors
