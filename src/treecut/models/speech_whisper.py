"""Local Faster-Whisper adapter with word timing."""
from __future__ import annotations

from pathlib import Path
import os
import re


class WhisperTranscriber:
    def __init__(self, model_dir: Path, device: str = "cpu"):
        if not (model_dir / "model.bin").is_file() or not (model_dir / "config.json").is_file():
            raise FileNotFoundError(f"Whisper 模型不完整：{model_dir}")
        # The portable CPU bundle contains OpenMP users from both PyTorch and
        # CTranslate2.  Keep their coexistence explicit for the isolated local runtime.
        os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        from faster_whisper import WhisperModel

        compute_type = "float16" if device == "cuda" else "int8"
        self.model = WhisperModel(str(model_dir), device=device, compute_type=compute_type,
                                  local_files_only=True)

    def transcribe(self, video: Path, media_id: int | None = None) -> dict:
        segments, info = self.model.transcribe(
            str(video), beam_size=1, word_timestamps=True, vad_filter=True,
        )
        items, words = [], []
        for segment in segments:
            text = segment.text.strip()
            items.append({"start": round(segment.start, 3), "end": round(segment.end, 3),
                          "text": text, "emotion": "unknown", "events": []})
            for word in segment.words or []:
                words.append({"start": round(word.start, 3), "end": round(word.end, 3),
                              "text": word.word.strip(), "probability": round(word.probability, 4)})
        parts = [item["text"] for item in items if item["text"]]
        has_cjk = bool(re.search(r"[\u3400-\u9fff]", "".join(parts)))
        transcript = ("".join(parts) if has_cjk else " ".join(parts)).strip()
        return {"model": "faster-whisper", "language": info.language,
                "timeline_precision": "word", "transcript": transcript,
                "has_speech": bool(transcript), "segments": items, "words": words}
