"""Remote client configuration stored beside the other runtime config files."""
from __future__ import annotations

import json
import socket
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class RemoteConfig:
    hub_url: str = ""
    token: str = ""
    client_id: str = ""
    interval_seconds: int = 60
    enabled: bool = True
    auto_discover: bool = True
    standalone: bool = False

    def valid(self) -> bool:
        if not (self.hub_url and self.token and self.client_id):
            return False
        return self.hub_url.startswith(("http://", "https://"))


def default_client_id() -> str:
    host = socket.gethostname() or "treecut"
    return f"{host}-{uuid.uuid4().hex[:6]}"


def load_config(path: Path) -> RemoteConfig:
    if not path.is_file():
        return RemoteConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = RemoteConfig.__dataclass_fields__
        config = RemoteConfig(**{key: data[key] for key in fields if key in data})
        try:
            config.interval_seconds = max(15, int(config.interval_seconds))
        except (TypeError, ValueError):
            config.interval_seconds = 60
        config.enabled = bool(config.enabled)
        config.auto_discover = bool(config.auto_discover)
        config.standalone = bool(config.standalone)
        return config
    except Exception:
        return RemoteConfig()


def save_config(path: Path, config: RemoteConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
