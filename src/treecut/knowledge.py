"""Domain knowledge bundled with TreeCut (protected words, selling-point terms)."""
from __future__ import annotations

import json
from pathlib import Path

from treecut.platform.paths import RuntimePaths


_PROTECTED_WORDS_FILE = "protected_words.json"
_SELLING_POINT_LIBRARY_FILE = "素材标签库.json"


def knowledge_dir(base_dir: Path | None = None) -> Path:
    """assets/knowledge inside the install; never required to exist."""
    root = Path(base_dir) if base_dir is not None else RuntimePaths.discover().install_root
    return root / "assets" / "knowledge"


def _load_json(name: str, base_dir: Path | None = None) -> dict:
    path = knowledge_dir(base_dir) / name
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def protected_words(base_dir: Path | None = None) -> tuple[str, ...]:
    """Flatten the v12-era TTS protected-word categories into a deduplicated tuple."""
    payload = _load_json(_PROTECTED_WORDS_FILE, base_dir)
    words: list[str] = []
    for category in payload.get("categories", {}).values():
        if isinstance(category, list):
            for raw in category:
                word = str(raw).strip()
                if word and word not in words:
                    words.append(word)
    return tuple(words)


def selling_point_terms(base_dir: Path | None = None) -> tuple[str, ...]:
    """Selling-point vocabulary from the v12-era material tag library."""
    payload = _load_json(_SELLING_POINT_LIBRARY_FILE, base_dir)
    terms: list[str] = []
    for key, info in (payload.get("selling_points") or {}).items():
        for raw in (str(key), str((info or {}).get("original_name") or "")):
            value = raw.strip()
            if value and value not in terms:
                terms.append(value)
    return tuple(terms)


def domain_vocabulary(base_dir: Path | None = None) -> tuple[str, ...]:
    """Combined industry vocabulary: selling-point terms plus protected words."""
    seen: set[str] = set()
    combined: list[str] = []
    for term in selling_point_terms(base_dir) + protected_words(base_dir):
        if term not in seen:
            seen.add(term)
            combined.append(term)
    return tuple(combined)
