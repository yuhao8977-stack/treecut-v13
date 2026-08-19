"""Real end-to-end destruction tests against the live local hub.

Round 2: watchdog crash-recovery, standalone-agent self-heal, and remote
start/stop/status over the real hub API.  Uses a throwaway data root and a
dedicated test client id so production data is untouched.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(r"D:\TreeCut_v13")
PYTHONW = ROOT / "runtime" / "pythonw.exe"
PYTHON = ROOT / "runtime" / "python.exe"
CLIENT = "TEST-SELFHEAL"
HUB = "http://127.0.0.1:8766"


def _token(name: str) -> str:
    path = ROOT / "runtime_data" / "config" / name
    return path.read_text(encoding="utf-8").strip()


TOKEN = _token("api_token.txt")
MASTER = _token("master_key.txt")


def api(path: str, payload=None, method: str = "GET", timeout: float = 30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        HUB + path, data=data, method=method,
        headers={"X-TreeCut-Token": TOKEN, "X-TreeCut-Master": MASTER,
                 "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def enqueue(action: str, note: str = "") -> str:
    created = api(f"/api/v1/clients/{CLIENT}/commands",
                  {"action": action, "note": note}, method="POST")
    return created["command_id"]


def wait_result(command_id: str, timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        audit = api("/api/v1/audit?limit=40")
        for entry in audit.get("commands", []):
            if entry["command_id"] == command_id and entry.get("status") in ("done", "failed"):
                return entry
        time.sleep(5)
    raise TimeoutError(f"command {command_id} not finished")


def treecut_pythonw() -> list[str]:
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
        "Where-Object { $_.CommandLine -match 'treecut' } | "
        "ForEach-Object { Write-Output ($_.ProcessId.ToString() + '|' + $_.CommandLine) }"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            capture_output=True, timeout=30)
    return [line for line in result.stdout.decode("utf-8", errors="replace").splitlines()
            if line.strip()]


def kill_treecut_pythonw() -> None:
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
        "Where-Object { $_.CommandLine -match 'treecut' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", command],
                   capture_output=True, timeout=30)


def start_env(data_root: Path, env: dict) -> dict:
    env = dict(env)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["TREECUT_DATA_ROOT"] = str(data_root)
    env["TREECUT_MODEL_ROOT"] = str(ROOT / "models")
    return env


def wait_for(predicate, timeout: float, label: str):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            print(f"[PASS] {label}")
            return
        time.sleep(3)
    raise AssertionError(f"[FAIL] {label}")


def main() -> int:
    test_root = ROOT / "runtime_data" / "test_temp"
    test_root.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="treecut_e2e_", dir=str(test_root)))
    print(f"temp data root: {temp}")
    data_root = temp / "data"
    config_dir = data_root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "remote.json").write_text(json.dumps({
        "hub_url": HUB, "token": TOKEN, "client_id": CLIENT,
        "interval_seconds": 15, "enabled": True,
        "auto_discover": False, "standalone": True,
    }, ensure_ascii=False), encoding="utf-8")
    base_env = start_env(data_root, dict(os.environ))
    processes: list[subprocess.Popen] = []
    try:
        # ---- Test A: watchdog restarts a crashed desktop ----
        print("=== A. watchdog crash recovery ===")
        watchdog = subprocess.Popen(
            [str(PYTHONW), "-m", "treecut.watchdog"], cwd=str(ROOT), env=base_env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes.append(watchdog)
        wait_for(lambda: any("-m treecut.desktop" in line for line in treecut_pythonw()),
                 45, "desktop started under watchdog")
        desktop_pid = next(
            (int(line.split("|", 1)[0]) for line in treecut_pythonw()
             if "-m treecut.desktop" in line),
        )
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Stop-Process -Id {desktop_pid} -Force"],
                       capture_output=True, timeout=30)
        def desktop_restarted() -> bool:
            return any(
                "-m treecut.desktop" in line
                and int(line.split("|", 1)[0]) != desktop_pid
                for line in treecut_pythonw()
            )
        wait_for(desktop_restarted, 45, "watchdog restarted desktop with a new pid")

        # ---- Test B: desktop guard relaunches a killed standalone agent ----
        print("=== B. standalone agent self-heal ===")
        kill_treecut_pythonw()
        time.sleep(3)
        desktop = subprocess.Popen(
            [str(PYTHONW), "-m", "treecut.desktop"], cwd=str(ROOT), env=base_env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        processes.append(desktop)
        wait_for(lambda: any("agent_main" in line for line in treecut_pythonw()),
                 60, "desktop launched the standalone agent")
        agent_pid = next(
            (int(line.split("|", 1)[0]) for line in treecut_pythonw()
             if "agent_main" in line),
        )
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Stop-Process -Id {agent_pid} -Force"],
                       capture_output=True, timeout=30)
        def agent_restarted() -> bool:
            return any(
                "agent_main" in line
                and int(line.split("|", 1)[0]) != agent_pid
                for line in treecut_pythonw()
            )
        wait_for(agent_restarted, 90, "desktop guard relaunched the standalone agent")

        # ---- Test C: remote control over the real hub ----
        print("=== C. remote start / stop / status via hub ===")
        entry = wait_result(enqueue("app_status"))
        assert "桌面程序=运行中" in entry["result"] and "独立代理=运行中" in entry["result"], entry["result"]
        print("[PASS] app_status shows desktop + agent running")

        entry = wait_result(enqueue("stop_app"))
        assert "已关闭" in entry["result"], entry["result"]
        wait_for(lambda: not any("-m treecut.desktop" in line for line in treecut_pythonw()),
                 45, "desktop closed by remote stop_app")
        wait_for(lambda: any("agent_main" in line for line in treecut_pythonw()),
                 30, "standalone agent survived stop_app")

        entry = wait_result(enqueue("app_status"))
        assert "桌面程序=未运行" in entry["result"] and "独立代理=运行中" in entry["result"], entry["result"]
        print("[PASS] app_status after stop: desktop off, agent alive")

        entry = wait_result(enqueue("start_app"))
        assert "已启动" in entry["result"], entry["result"]
        wait_for(lambda: any("-m treecut.desktop" in line for line in treecut_pythonw()),
                 60, "desktop started by remote start_app")

        entry = wait_result(enqueue("app_status"))
        assert "桌面程序=运行中" in entry["result"], entry["result"]
        print("[PASS] app_status after start: desktop running")

        entry = wait_result(enqueue("stop_app"))
        print("[PASS] final stop_app executed:", entry["result"])
        wait_for(lambda: not any("-m treecut.desktop" in line for line in treecut_pythonw()),
                 45, "desktop closed after final stop")
        print("=== E2E_DESTRUCTION_ALL_PASS ===")
        return 0
    finally:
        print("cleanup...")
        kill_treecut_pythonw()
        for process in processes:
            try:
                process.terminate()
            except Exception:
                pass
        # 清理测试在启动文件夹里写入的自启动条目（避免影响本机真实开机自启）
        startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / \
            "Start Menu" / "Programs" / "Startup"
        for name in ("TreeCut_autostart_agent.vbs", "TreeCut_autostart_desktop.vbs"):
            try:
                (startup / name).unlink(missing_ok=True)
            except OSError:
                pass
        # 从 hub 数据库移除测试客户端记录
        try:
            store = ROOT / "runtime_data" / "remote" / "hub_store.db"
            with sqlite3.connect(store) as connection:
                connection.execute("DELETE FROM clients WHERE client_id=?", (CLIENT,))
                connection.execute("DELETE FROM commands WHERE client_id=?", (CLIENT,))
            print("test client removed from hub store")
        except Exception as error:
            print("hub store cleanup skipped:", error)
        shutil.rmtree(temp, ignore_errors=True)
        print("cleanup done")


if __name__ == "__main__":
    raise SystemExit(main())
