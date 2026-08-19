"""Portable runtime paths. Nothing defaults to the Windows C drive."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    install_root: Path
    data_root: Path
    models: Path
    cache: Path
    temp: Path
    logs: Path
    databases: Path
    materials: Path
    output: Path

    @classmethod
    def discover(cls) -> "RuntimePaths":
        install_root = Path(__file__).resolve().parents[3]
        data_root = Path(os.environ.get("TREECUT_DATA_ROOT", install_root / "runtime_data")).resolve()
        return cls(
            install_root=install_root,
            data_root=data_root,
            models=Path(os.environ.get("TREECUT_MODEL_ROOT", install_root / "models")).resolve(),
            cache=data_root / "cache",
            temp=data_root / "temp",
            logs=data_root / "logs",
            databases=data_root / "database",
            materials=data_root / "materials",
            output=data_root / "output",
        )

    def ensure(self) -> None:
        if os.name == "nt":
            for label, path in (("数据目录", self.data_root), ("模型目录", self.models)):
                if path.drive.upper() == "C:":
                    raise ValueError(f"{label}禁止位于 C 盘: {path}")
        for path in (self.data_root, self.models, self.cache, self.temp, self.logs,
                     self.databases, self.materials, self.output):
            path.mkdir(parents=True, exist_ok=True)

    def apply_environment(self) -> None:
        self.ensure()
        values = {
            "TREECUT_DATA_ROOT": self.data_root,
            "TREECUT_MODEL_ROOT": self.models,
            "TEMP": self.temp,
            "TMP": self.temp,
            "HF_HOME": self.cache / "huggingface",
            "HF_MODULES_CACHE": self.cache / "huggingface" / "modules",
            "MODELSCOPE_CACHE": self.cache / "modelscope",
            "TORCH_HOME": self.cache / "torch",
            "YOLO_CONFIG_DIR": self.cache / "ultralytics",
            "ULTRALYTICS_CONFIG_DIR": self.cache / "ultralytics",
            "XDG_CACHE_HOME": self.cache / "xdg",
            "PIP_CACHE_DIR": self.cache / "pip",
            "MPLCONFIGDIR": self.cache / "matplotlib",
            "PYTHONPYCACHEPREFIX": self.cache / "pycache",
        }
        for name, value in values.items():
            Path(value).mkdir(parents=True, exist_ok=True)
            os.environ[name] = str(value)
