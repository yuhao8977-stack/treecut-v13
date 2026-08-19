"""Restart the desktop on early-exit crashes; stop on normal close."""
from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path

from treecut.platform.paths import RuntimePaths


def run_watchdog(command: list[str], min_run_seconds: float = 60.0,
                 restart_limit: int = 3, log_path: Path | None = None,
                 cwd: Path | None = None, restart_delay: float = 2.0) -> int:
    """Run a command repeatedly; restart when it exits faster than expected."""
    restarts = 0
    log = open(log_path, "a", encoding="utf-8") if log_path else None

    def note(message: str) -> None:
        if log is not None:
            log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {message}\n")
            log.flush()

    try:
        while True:
            started = time.time()
            note("启动目标程序")
            process = subprocess.Popen(command, cwd=str(cwd) if cwd else None)
            exit_code = process.wait()
            duration = time.time() - started
            if duration >= min_run_seconds:
                note(f"目标正常退出（运行 {duration:.0f} 秒，退出码 {exit_code}）")
                return 0
            restarts += 1
            note(f"目标异常退出（运行 {duration:.0f} 秒，退出码 {exit_code}），第 {restarts} 次重启")
            if restarts >= restart_limit:
                note("重启次数达到上限，停止")
                return 1
            time.sleep(restart_delay)
    finally:
        if log is not None:
            log.close()


def run_desktop_watchdog() -> int:
    paths = RuntimePaths.discover()
    paths.apply_environment()
    command = [str(paths.install_root / "runtime" / "pythonw.exe"), "-m", "treecut.desktop"]
    return run_watchdog(command, min_run_seconds=60.0, restart_limit=3,
                        log_path=paths.logs / "watchdog.log", cwd=paths.install_root)


def main() -> int:
    return run_desktop_watchdog()


if __name__ == "__main__":
    raise SystemExit(main())
