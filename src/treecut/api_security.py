"""Local API bearer secret stored only in TreeCut's portable data root."""
from __future__ import annotations

from pathlib import Path
import secrets


def load_or_create_api_token(data_root: Path) -> str:
    path = data_root / "config" / "api_token.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        token = path.read_text(encoding="ascii").strip()
        if len(token) >= 32:
            return token
    token = secrets.token_urlsafe(32)
    temp = path.with_suffix(".txt.tmp")
    temp.write_text(token + "\n", encoding="ascii")
    temp.replace(path)
    return token
