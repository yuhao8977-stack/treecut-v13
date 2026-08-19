"""Desktop shortcut management for portable and installed TreeCut copies.

The portable copy (a plain folder) has no installer, so the desktop app
creates (and refreshes) its own desktop shortcut on startup.  The installer
also creates one, which makes both delivery paths behave the same: after the
software first runs, a "树剪 TreeCut" shortcut exists on the desktop.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


SHORTCUT_NAME = "树剪 TreeCut.lnk"


def desktop_dir() -> Path:
    """Return the real Desktop folder (OneDrive-aware), never a guess."""
    if os.name != "nt":
        return Path.home() / "Desktop"
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        # FOLDERID_Desktop = {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
        desktop_id = GUID(
            0xB4BFCC3A, 0xDB2C, 0x424C,
            (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41),
        )
        pointer = ctypes.c_wchar_p()
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(desktop_id), 0, None, ctypes.byref(pointer),
        )
        if result == 0 and pointer.value:
            path = Path(pointer.value)
            ctypes.windll.ole32.CoTaskMemFree(pointer)
            if path.is_dir():
                return path
    except Exception:
        pass
    profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    for candidate in (profile / "Desktop", profile / "OneDrive" / "Desktop"):
        if candidate.is_dir():
            return candidate
    return profile / "Desktop"


def shortcut_target(install_root: Path) -> Path:
    return Path(install_root) / "启动树剪v13.cmd"


def icon_location(install_root: Path) -> str:
    icon = Path(install_root) / "assets" / "icon.ico"
    if icon.is_file():
        return f"{icon},0"
    pythonw = Path(install_root) / "runtime" / "pythonw.exe"
    if pythonw.is_file():
        return f"{pythonw},0"
    return ""


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _write_script() -> tuple[Path, Path]:
    """Return (create_script, read_script) temporary VBS helpers (ASCII only)."""
    temp_dir = Path(tempfile.gettempdir())
    create_script = temp_dir / "treecut_mklnk.vbs"
    read_script = temp_dir / "treecut_readlnk.vbs"
    create_script.write_text(
        "Set sh = CreateObject(\"WScript.Shell\")\n"
        "Set lnk = sh.CreateShortcut(WScript.Arguments(0))\n"
        "lnk.TargetPath = WScript.Arguments(1)\n"
        "lnk.WorkingDirectory = WScript.Arguments(2)\n"
        "If WScript.Arguments.Count > 3 And WScript.Arguments(3) <> \"\" Then\n"
        "  lnk.IconLocation = WScript.Arguments(3)\n"
        "End If\n"
        "lnk.Save\n",
        encoding="ascii",
    )
    read_script.write_text(
        "Set sh = CreateObject(\"WScript.Shell\")\n"
        "Set lnk = sh.CreateShortcut(WScript.Arguments(0))\n"
        "If LCase(lnk.TargetPath) = LCase(WScript.Arguments(1)) Then\n"
        "  WScript.Echo \"1\"\n"
        "Else\n"
        "  WScript.Echo \"0\"\n"
        "End If\n",
        encoding="ascii",
    )
    return create_script, read_script


def _run(script: Path, *args: str) -> str:
    command = ["cscript.exe", "//nologo", str(script), *args]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8",
        errors="replace", creationflags=subprocess.CREATE_NO_WINDOW, timeout=30,
    )
    if result.returncode != 0:
        raise OSError(result.stderr.strip() or f"cscript 退出码 {result.returncode}")
    return result.stdout.strip()


def _target_matches(link: Path, expected: Path) -> bool:
    _, read_script = _write_script()
    try:
        return _run(read_script, str(link), str(expected)) == "1"
    except (OSError, subprocess.SubprocessError):
        return False


def create_desktop_shortcut(
    install_root: Path,
    directory: Path | None = None,
    name: str = SHORTCUT_NAME,
) -> str:
    """Create or refresh the desktop shortcut; returns created/exists/skipped."""
    if os.name != "nt":
        return "skipped"
    install_root = Path(install_root).resolve()
    target = shortcut_target(install_root)
    if not target.is_file():
        return "skipped"
    desktop = Path(directory) if directory is not None else desktop_dir()
    try:
        desktop.mkdir(parents=True, exist_ok=True)
    except OSError:
        return "skipped"
    link = desktop / name
    if link.is_file() and _target_matches(link, target):
        return "exists"
    create_script, _ = _write_script()
    _run(create_script, str(link), str(target), str(install_root), icon_location(install_root))
    return "created"
