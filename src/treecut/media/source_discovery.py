"""Discover local, removable and network material sources on Windows."""
from __future__ import annotations

import ctypes
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm", ".mts", ".m2ts"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

DRIVE_TYPES = {
    0: "unknown", 1: "invalid", 2: "removable", 3: "fixed",
    4: "network", 5: "optical", 6: "ramdisk",
}


@dataclass(frozen=True)
class DriveInfo:
    root: str
    volume_id: str
    kind: str
    label: str
    total_gb: float
    free_gb: float
    accessible: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MediaSummary:
    source: str
    video_count: int = 0
    audio_count: int = 0
    image_count: int = 0
    total_bytes: int = 0
    stopped_early: bool = False
    errors: list[str] = field(default_factory=list)
    example_videos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["total_gb"] = round(self.total_bytes / 2**30, 3)
        return data


def _volume_metadata(root: str) -> tuple[str, str]:
    if os.name != "nt":
        return Path(root).name, str(os.stat(root).st_dev)
    label_buffer = ctypes.create_unicode_buffer(261)
    filesystem_buffer = ctypes.create_unicode_buffer(261)
    serial = ctypes.c_uint(0)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root), label_buffer, len(label_buffer), ctypes.byref(serial),
        None, None, filesystem_buffer, len(filesystem_buffer),
    )
    return (label_buffer.value, f"{serial.value:08X}") if ok else ("", root.upper())


def volume_identity(path: str | Path) -> tuple[str, str, str]:
    """Return volume root, stable volume id and path relative to that volume."""
    resolved = Path(path).resolve()
    anchor = resolved.anchor or str(resolved)
    _, volume_id = _volume_metadata(anchor)
    try:
        relative = str(resolved.relative_to(anchor))
    except ValueError:
        relative = ""
    return anchor, volume_id, relative


def discover_drives(include_network: bool = True) -> list[DriveInfo]:
    if os.name != "nt":
        usage = shutil.disk_usage("/")
        return [DriveInfo("/", str(os.stat("/").st_dev), "fixed", "", round(usage.total / 2**30, 1),
                          round(usage.free / 2**30, 1), True)]

    mask = ctypes.windll.kernel32.GetLogicalDrives()
    drives = []
    for index in range(26):
        if not mask & (1 << index):
            continue
        root = f"{chr(65 + index)}:\\"
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
        kind = DRIVE_TYPES.get(drive_type, "unknown")
        if kind == "network" and not include_network:
            continue
        accessible = os.path.isdir(root)
        total = free = 0
        if accessible:
            try:
                usage = shutil.disk_usage(root)
                total, free = usage.total, usage.free
            except OSError:
                accessible = False
        label, volume_id = _volume_metadata(root) if accessible else ("", root.upper())
        drives.append(DriveInfo(
            root=root, volume_id=volume_id, kind=kind, label=label,
            total_gb=round(total / 2**30, 1), free_gb=round(free / 2**30, 1),
            accessible=accessible,
        ))
    return drives


def summarize_media(source: str | Path, max_files: int = 200_000,
                    examples: int = 10) -> MediaSummary:
    root = Path(source)
    summary = MediaSummary(source=str(root.resolve()))
    if not root.is_dir():
        summary.errors.append("目录不存在或无法访问")
        return summary

    seen = 0
    for current, directories, files in os.walk(root, followlinks=False):
        # Never traverse junctions/symlinks into another disk or recursive tree.
        directories[:] = [
            name for name in directories
            if not (Path(current) / name).is_symlink()
            and name.lower() not in {"$recycle.bin", "system volume information", "windows", "program files", "program files (x86)"}
        ]
        for name in files:
            seen += 1
            if seen > max_files:
                summary.stopped_early = True
                return summary
            path = Path(current) / name
            extension = path.suffix.lower()
            if extension not in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS:
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                if len(summary.errors) < 20:
                    summary.errors.append(f"{path}: {exc}")
                continue
            summary.total_bytes += size
            if extension in VIDEO_EXTENSIONS:
                summary.video_count += 1
                if len(summary.example_videos) < examples:
                    summary.example_videos.append(str(path))
            elif extension in AUDIO_EXTENSIONS:
                summary.audio_count += 1
            else:
                summary.image_count += 1
    return summary
