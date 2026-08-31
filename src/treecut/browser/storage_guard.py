# -*- coding: utf-8 -*-
"""Phase B1 — StorageHealthGuard（§13/14/15/16 + 用户批准版）。

检查 C / E / Z 磁盘健康 + AI 模型缓存是否回落到 C 盘：
- C free < 80GB → WARNING；< 50GB → CRITICAL（禁媒体/缓存写 C）
- E free < 50GB → WARNING（运行盘）
- Z 不可用/不可写 → MEDIA_STORAGE_UNAVAILABLE（STOP 媒体任务，绝不 fallback C）
- 大型 AI cache（HF/ModelScope/Ollama/TreeCut model cache）指向 C → AI_CACHE_ON_SYSTEM_DRIVE
- E staging 超过上限 → STAGING_STORAGE_WARNING

输出 STORAGE_HEALTH_GUARD_V1.json；面板启动时记录状态。
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

WARNING_C_FREE_GB = 80.0
CRITICAL_C_FREE_GB = 50.0
WARNING_E_FREE_GB = 50.0
STAGING_MAX_GB = 20.0


def _free_gb(drive: str) -> float | None:
    try:
        return shutil.disk_usage(f"{drive}:\\").free / 2**30
    except OSError:
        return None


def _cache_dirs() -> list[tuple[str, str]]:
    """(label, path) —— 仅按实际存在/配置的目录检查，不读取内容。"""
    home = Path(os.environ.get("USERPROFILE", ""))
    candidates = [
        ("HF_HOME", os.environ.get("HF_HOME", str(home / ".cache" / "huggingface"))),
        ("HF_HUB_CACHE", os.environ.get("HF_HUB_CACHE", "")),
        ("MODELSCOPE_CACHE", os.environ.get("MODELSCOPE_CACHE", str(home / ".modelscope"))),
        ("OLLAMA_MODELS", os.environ.get("OLLAMA_MODELS", str(home / ".ollama" / "models"))),
        ("TREECUT_MODEL_ROOT", os.environ.get("TREECUT_MODEL_ROOT", "")),
    ]
    return [(label, p) for label, p in candidates if p]


class StorageHealthGuard:
    def check(self, staging_dir: str | None = None) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        result: dict = {"checked_at": now, "warnings": [], "criticals": []}

        c_free = _free_gb("C")
        e_free = _free_gb("E")
        z_free = _free_gb("Z")

        result["c_free_gb"] = round(c_free, 1) if c_free is not None else None
        result["e_free_gb"] = round(e_free, 1) if e_free is not None else None
        result["z_free_gb"] = round(z_free, 1) if z_free is not None else None

        if c_free is not None:
            if c_free < CRITICAL_C_FREE_GB:
                result["c_level"] = "CRITICAL"
                result["criticals"].append(
                    f"C盘可用 {c_free:.1f}GB < {CRITICAL_C_FREE_GB}GB：禁止任何 TreeCut 媒体/缓存写入 C 盘")
            elif c_free < WARNING_C_FREE_GB:
                result["c_level"] = "WARNING"
                result["warnings"].append(f"C盘可用 {c_free:.1f}GB < {WARNING_C_FREE_GB}GB：系统盘空间偏低")
            else:
                result["c_level"] = "OK"

        if e_free is not None and e_free < WARNING_E_FREE_GB:
            result["e_level"] = "WARNING"
            result["warnings"].append(f"E盘（运行盘）可用 {e_free:.1f}GB < {WARNING_E_FREE_GB}GB")
        else:
            result["e_level"] = "OK" if e_free is not None else "UNKNOWN"

        if z_free is None:
            result["z_level"] = "MEDIA_STORAGE_UNAVAILABLE"
            result["criticals"].append("MEDIA_STORAGE_UNAVAILABLE：素材盘不可用，媒体任务必须 STOP，绝不 fallback 到 C 盘")
        else:
            result["z_level"] = "OK"

        # AI cache 回落 C 盘检查
        ai_on_c = []
        for label, path in _cache_dirs():
            if path and path.lower().startswith("c:"):
                ai_on_c.append({"label": label, "path": path})
        result["ai_cache_on_system_drive"] = ai_on_c
        if ai_on_c:
            result["warnings"].append(
                "AI_CACHE_ON_SYSTEM_DRIVE：模型缓存指向 C 盘（" +
                ", ".join(a["label"] for a in ai_on_c) + "）——防止未来复发")

        # E staging 上限
        if staging_dir and Path(staging_dir).exists():
            try:
                total = sum(p.stat().st_size for p in Path(staging_dir).rglob("*")
                            if p.is_file())
                staging_gb = total / 2**30
                result["staging_gb"] = round(staging_gb, 2)
                if staging_gb > STAGING_MAX_GB:
                    result["warnings"].append(
                        f"STAGING_STORAGE_WARNING：E staging {staging_gb:.1f}GB > {STAGING_MAX_GB}GB，"
                        "验证完成的大媒体应尽快 promote 到 Z")
            except OSError:
                result["staging_gb"] = None

        return result

    def to_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.check(), ensure_ascii=False, indent=1), encoding="utf-8")
        return path


def main() -> int:
    out = Path(r"C:\Users\admin\github\treecut-v13\reports\storage\STORAGE_HEALTH_GUARD_V1.json")
    guard = StorageHealthGuard()
    result = guard.check()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
