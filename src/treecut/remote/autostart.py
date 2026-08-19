"""Self-registered startup entries: managed machines connect with zero manual steps."""
from __future__ import annotations

import os
from pathlib import Path


def startup_dir() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _hub_vbs(install_root: Path, port: int = 8766) -> str:
    root = str(install_root)
    return (
        'Set sh = CreateObject("WScript.Shell")\n'
        f'sh.CurrentDirectory = "{root}"\n'
        f'sh.Environment("PROCESS")("PYTHONPATH") = "{root}\\src"\n'
        f'sh.Run """{root}\\runtime\\python.exe"" -m treecut.remote.hub_main --port {port}", 0, False\n'
    )


def _desktop_vbs(install_root: Path) -> str:
    root = str(install_root)
    return (
        'Set sh = CreateObject("WScript.Shell")\n'
        f'sh.CurrentDirectory = "{root}"\n'
        f'sh.Environment("PROCESS")("PYTHONPATH") = "{root}\\src"\n'
        f'sh.Run """{root}\\runtime\\pythonw.exe"" -m treecut.watchdog", 1, False\n'
    )


def _agent_vbs(install_root: Path) -> str:
    """Standalone always-on agent: keeps the child reachable even when the app is closed."""
    root = str(install_root)
    return (
        'Set sh = CreateObject("WScript.Shell")\n'
        f'sh.CurrentDirectory = "{root}"\n'
        f'sh.Environment("PROCESS")("PYTHONPATH") = "{root}\\src"\n'
        f'sh.Run """{root}\\runtime\\pythonw.exe"" -m treecut.remote.agent_main", 0, False\n'
    )


def ensure_autostart(kind: str, install_root: Path, port: int = 8766,
                     directory: Path | None = None) -> Path | None:
    """Create (or refresh) the startup entry so booting the machine starts it."""
    if kind not in {"hub", "desktop", "agent"}:
        raise ValueError(f"未知自启动类型: {kind}")
    target_dir = directory or startup_dir()
    target = target_dir / f"TreeCut_autostart_{kind}.vbs"
    content = {
        "hub": _hub_vbs(install_root, port),
        "desktop": _desktop_vbs(install_root),
        "agent": _agent_vbs(install_root),
    }[kind]
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_text(encoding="ascii") != content:
            target.write_text(content, encoding="ascii")
        return target
    except OSError:
        return None


def remove_autostart(kind: str, directory: Path | None = None) -> None:
    if kind not in {"hub", "desktop", "agent"}:
        raise ValueError(f"未知自启动类型: {kind}")
    target = (directory or startup_dir()) / f"TreeCut_autostart_{kind}.vbs"
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass
