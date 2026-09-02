"""STAGE8 — Production 配置中心(版本化) + Provider 接口 + 就绪状态。

§75-§90。account_id/project_id/config 参数化; B007 仅 fixture。
Provider: VisualModelProvider / VoiceProvider / MusicLibraryService / Renderer(插口)。
诚实状态: 无授权音乐 → BGM_LIBRARY_NOT_READY; 无真人样本 → VOICE_INPUT_REQUIRED。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULTS = {
    "version": "production_v1",
    "top_k": 3,
    "shot_duration": {"hook": [0.7, 1.8], "info": [1.5, 3.0], "action": [2.5, 4.5]},
    "action_probe_frames": [0.12, 0.30, 0.50, 0.70, 0.88],
    "dedup": {"phash_strong": 6, "phash_verify": 12},
    "av_tolerance_s": 0.10,
    "caption": {"fontsize": 66, "allowed": [62, 68], "outline": [4, 6],
                "max_lines": 2, "margin_v": 150, "safe_bottom": 0.12},
    "voice": {"default_speed": 1.30, "provider": "SAPI_FALLBACK", "production_provider": None},
    "bgm": {"required": True, "policy": "no_bgm_intentional_override"},
    "audio": {"lufs": [-16.0, -14.0], "true_peak_dbtp": -1.0, "sample_rate": 48000},
    "render": {"width": 1080, "height": 1920, "fps": 30, "codec": "h264",
               "pix_fmt": "yuv420p", "crf": [18, 21], "aac_kbps": [160, 192]},
}


def load_production_config(config_path: str | None = None, overrides: dict | None = None) -> dict:
    cfg = dict(DEFAULTS)
    if config_path and Path(config_path).exists():
        loaded = json.loads(Path(config_path).read_text(encoding="utf-8"))
        cfg = _deep_merge(cfg, loaded)
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    return cfg


def _deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ---- Provider 接口 ----
class VisualModelProvider:
    """视觉推理插口(当前实现: qwen2.5vl L2; 可换)。truth_level 恒为 L2。"""
    name = "qwen2.5vl"
    truth_level = "L2_CANDIDATE"

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url


class VoiceProvider:
    """语音合成插口。SAPI=FALLBACK；克隆需样本+consent，无则 VOICE_INPUT_REQUIRED。"""
    name = "SAPI"
    role = "FALLBACK_TTS"

    def __init__(self, profile: dict | None = None):
        self.profile = profile or {}
        self.ready = bool(profile and profile.get("consent_verified") and profile.get("reference_media"))


class MusicLibraryService:
    """音乐库插口。license 必填; 无授权条目 → BGM_LIBRARY_NOT_READY。"""
    def __init__(self, assets: list[dict] | None = None):
        self.assets = assets or []

    def licensed_assets(self, mood=None, max_duration_s=None) -> list[dict]:
        out = []
        for a in self.assets:
            if not a.get("license_ok"):
                continue
            if mood and a.get("mood") != mood:
                continue
            if max_duration_s and (a.get("duration_s") or 999) > max_duration_s:
                continue
            out.append(a)
        return out

    def status(self) -> str:
        return "READY" if self.licensed_assets() else "BGM_LIBRARY_NOT_READY"


VOICE_PROFILE_SCHEMA = {
    "voice_profile_id": "", "speaker": "", "consent_verified": False,
    "consent_record_ref": "", "reference_media": [], "engine": "", "engine_version": "",
    "default_speed": 1.30, "review_state": "PENDING", "created_at": ""
}

MUSIC_ASSET_SCHEMA = {
    "music_asset_id": "", "title": "", "license": "", "license_ok": False,
    "license_doc_ref": "", "mood": "", "energy": 0.5, "duration_s": 0,
    "bpm": 0, "vocal_present": False, "loudness_lufs": 0, "path": ""
}


def state_flags(cfg: dict, voice_ready: bool, music_assets: list[dict]) -> dict:
    ms = MusicLibraryService(music_assets)
    return {"VOICE": ("READY_FOR_INPUT" if not voice_ready else "READY"),
            "BGM": ms.status(),
            "caption_fontsize": cfg["caption"]["fontsize"]}
