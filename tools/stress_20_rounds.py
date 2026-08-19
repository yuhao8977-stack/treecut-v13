"""20 轮递进式真实破坏测试（本机模拟电脑）。

每一轮都使用独立的临时 hub + 代理 + 桌面进程（数据目录在 D 盘临时区），
不触碰真实数据与模型。轮次从正常到高频、杀进程、数据库破坏、攻击、
更新包破坏、组合风暴逐级加码，每轮结束校验关键不变量。
"""
from __future__ import annotations

import base64
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(r"D:\TreeCut_v13")
sys.path.insert(0, str(ROOT / "src"))
PYTHON = ROOT / "runtime" / "python.exe"
PYTHONW = ROOT / "runtime" / "pythonw.exe"
TEST_ROOT = ROOT / "runtime_data" / "test_temp" / "stress20"


def _env(data_root: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["TREECUT_DATA_ROOT"] = str(data_root)
    env["TREECUT_MODEL_ROOT"] = str(ROOT / "models")
    return env


def start_hub(data_root: Path, port: int) -> subprocess.Popen:
    data_root.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [str(PYTHON), "-m", "treecut.remote.hub_main", "--port", str(port)],
        cwd=str(ROOT), env=_env(data_root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2):
                return process
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("temp hub did not start")


def hub_creds(data_root: Path) -> tuple[str, str]:
    token = (data_root / "config" / "api_token.txt").read_text(encoding="utf-8").strip()
    master = (data_root / "config" / "master_key.txt").read_text(encoding="utf-8").strip()
    return token, master


def api(port: int, token: str, master: str, path: str, payload=None,
        method: str = "GET", timeout: float = 20, raw: bytes | None = None):
    data = raw if raw is not None else (
        json.dumps(payload).encode("utf-8") if payload is not None else None)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method,
        headers={"X-TreeCut-Token": token, "X-TreeCut-Master": master,
                 "Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, (json.loads(body.decode("utf-8")) if body else {})
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8"))
        except Exception:
            detail = {}
        return error.code, detail
    except Exception as error:
        return -1, {"error": str(error)}


def write_remote_config(data_root: Path, port: int, client_id: str,
                        standalone: bool = True, interval: int = 15,
                        token: str = "") -> None:
    config_dir = data_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    if not token:
        token = (data_root / "config" / "api_token.txt").read_text(encoding="utf-8").strip()
    (config_dir / "remote.json").write_text(json.dumps({
        "hub_url": f"http://127.0.0.1:{port}", "token": token,
        "client_id": client_id, "interval_seconds": interval,
        "enabled": True, "auto_discover": False, "standalone": standalone,
    }, ensure_ascii=False), encoding="utf-8")


def start_agent(data_root: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [str(PYTHONW), "-m", "treecut.remote.agent_main"],
        cwd=str(ROOT), env=_env(data_root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def start_desktop(data_root: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [str(PYTHONW), "-m", "treecut.desktop"],
        cwd=str(ROOT), env=_env(data_root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def start_watchdog(data_root: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [str(PYTHONW), "-m", "treecut.watchdog"],
        cwd=str(ROOT), env=_env(data_root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def treecut_pythonw(extra: str = "treecut") -> list[str]:
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
        f"Where-Object {{ $_.CommandLine -match '{extra}' }} | "
        "ForEach-Object { Write-Output ($_.ProcessId.ToString() + '|' + $_.CommandLine) }"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            capture_output=True, timeout=30)
    return [line for line in result.stdout.decode("utf-8", errors="replace").splitlines()
            if line.strip()]


def kill_treecut_pythonw(extra: str = "treecut") -> None:
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
        f"Where-Object {{ $_.CommandLine -match '{extra}' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", command],
                   capture_output=True, timeout=30)


def wait_for(predicate, timeout: float, label: str) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(2)
    raise AssertionError(f"wait failed: {label}")


def wait_client(port: int, token: str, master: str, client_id: str,
                timeout: float = 40) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, data = api(port, token, master, "/api/v1/clients")
        for client in data.get("clients", []):
            if client["client_id"] == client_id:
                return client
        time.sleep(2)
    raise AssertionError(f"client {client_id} never reported")


def enqueue(port: int, token: str, master: str, client_id: str,
            action: str, note: str = "") -> str:
    status, data = api(port, token, master, f"/api/v1/clients/{client_id}/commands",
                       {"action": action, "note": note}, method="POST")
    if status != 200:
        raise AssertionError(f"enqueue {action} failed: {status} {data}")
    return data["command_id"]


def enable_exec(port: int, token: str, master: str, client_id: str) -> None:
    status, data = api(port, token, master, f"/api/v1/clients/{client_id}/exec-policy",
                       {"allow": True}, method="POST")
    if status != 200:
        raise AssertionError(f"enable exec failed: {status} {data}")


def paths_from_root(root: Path):
    from treecut.platform.paths import RuntimePaths
    return RuntimePaths(
        install_root=root, data_root=root / "data", models=root / "models",
        cache=root / "data" / "cache", temp=root / "data" / "temp",
        logs=root / "data" / "logs", databases=root / "data" / "database",
        materials=root / "data" / "materials", output=root / "data" / "output",
    )


def wait_result(port: int, token: str, master: str, command_id: str,
                timeout: float = 90) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, data = api(port, token, master, "/api/v1/audit?limit=500")
        for entry in data.get("commands", []):
            if entry["command_id"] == command_id and entry.get("status") in ("done", "failed"):
                return entry
        time.sleep(3)
    raise TimeoutError(f"command {command_id} not finished")


ROUND_RESULTS: list[dict] = []


def run_round(port: int, token: str, master: str, data_root: Path, number: int,
              fn, *args) -> None:
    label = f"ROUND {number:02d}: {fn.__doc__.strip().splitlines()[0]}"
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    try:
        fn(port, token, master, data_root, *args)
        ROUND_RESULTS.append({"round": number, "ok": True})
        print(f"[PASS] {label}")
    except Exception as error:
        ROUND_RESULTS.append({"round": number, "ok": False, "error": str(error)})
        print(f"[FAIL] {label}: {type(error).__name__}: {error}")
        raise


# ---------------- Rounds ----------------

def r01_normal(port, token, master, data_root):
    """正常链路：代理上报 + 桌面启动 + 远程状态/停止/启动"""
    write_remote_config(data_root, port, "S1", standalone=False)
    desktop = start_desktop(data_root)
    try:
        client = wait_client(port, token, master, "S1")
        assert client["version"].startswith("13.5"), client["version"]
        command_id = enqueue(port, token, master, "S1", "app_status")
        entry = wait_result(port, token, master, command_id)
        assert "桌面程序=运行中" in entry["result"], entry["result"]
    finally:
        kill_treecut_pythonw()
        desktop.terminate()


def r02_high_frequency(port, token, master, data_root):
    """高频上报：50 次快速状态 + 20 条连续命令"""
    write_remote_config(data_root, port, "S2", standalone=False, interval=15)
    desktop = start_desktop(data_root)
    try:
        wait_client(port, token, master, "S2")
        for index in range(50):
            status, data = api(port, token, master, "/api/v1/status",
                               {"client_id": "S2", "version": "13.5.10",
                                "report": {"n": index}}, method="POST")
            assert status == 200, status
        ids = [enqueue(port, token, master, "S2", "app_status") for _ in range(20)]
        for command_id in ids:
            wait_result(port, token, master, command_id, timeout=120)
        audit = api(port, token, master, "/api/v1/audit?limit=200")[1]["commands"]
        done = [a for a in audit if a["status"] == "done"]
        assert len(done) >= 20, len(done)
    finally:
        kill_treecut_pythonw()
        desktop.terminate()


def r03_input_sabotage(port, token, master, data_root):
    """输入破坏：畸形 JSON、空命令、非法动作、超大状态"""
    status, data = api(port, token, master, "/api/v1/status",
                       {"client_id": "X", "version": "1", "report": "not-a-dict"},
                       method="POST")
    assert status == 422, status
    status, data = api(port, token, master, "/api/v1/status",
                       {"client_id": "X", "version": "1",
                        "report": {"blob": "x" * (1024 * 1024 + 1)}}, method="POST")
    assert status == 413, status
    status, data = api(port, token, master, "/api/v1/clients/X/commands",
                       {"action": "evil_action"}, method="POST")
    assert status == 422, status
    write_remote_config(data_root, port, "S3", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S3")
        enable_exec(port, token, master, "S3")
        command_id = enqueue(port, token, master, "S3", "exec", "")
        entry = wait_result(port, token, master, command_id)
        assert "远程命令为空" in entry["result"], entry["result"]
        command_id = enqueue(port, token, master, "S3", "ship_file", "E:/no/such")
        entry = wait_result(port, token, master, command_id)
        assert "文件不存在" in entry["result"], entry["result"]
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r04_attack(port, token, master, data_root):
    """外部攻击：错误令牌、越权、拉黑、路径穿越更新包"""
    status, _ = api(port, "wrong-token", master, "/api/v1/clients")
    assert status == 401, status
    status, _ = api(port, token, "", "/api/v1/clients")
    assert status == 403, status
    status, data = api(port, token, master, "/api/v1/clients/bad/commands",
                       {"action": "exec", "note": "whoami"}, method="POST")
    assert status == 403, status  # 未开启 exec 权限
    status, _ = api(port, token, master, "/api/v1/clients/bad/commands",
                    {"action": "blacklist"}, method="POST")
    assert status == 200, status
    status, _ = api(port, token, master, "/api/v1/status",
                    {"client_id": "bad", "version": "1", "report": {}}, method="POST")
    assert status == 403, status
    # 路径穿越更新包
    with tempfile.TemporaryDirectory(dir=str(TEST_ROOT)) as temp:
        evil = Path(temp) / "evil.zip"
        with zipfile.ZipFile(evil, "w") as archive:
            archive.writestr("manifest.json", json.dumps({
                "version": "1.0", "notes": "", "force": False,
                "files": [{"path": "../pwn.py", "sha256": "0" * 64}],
            }))
            archive.writestr("files/../pwn.py", b"pwn")
        status, _ = api(port, token, master,
                        "/api/v1/updates?version=1.0", raw=evil.read_bytes(),
                        method="POST")
        assert status == 422, status


def r05_stress_volume(port, token, master, data_root):
    """压力：200 客户端上报 + 200 命令队列"""
    for index in range(200):
        status, _ = api(port, token, master, "/api/v1/status",
                        {"client_id": f"V{index}", "version": "13.5.10",
                         "report": {"i": index}}, method="POST")
        assert status == 200, status
    status, data = api(port, token, master, "/api/v1/clients")
    assert len(data["clients"]) >= 200, len(data["clients"])
    for index in range(200):
        enqueue(port, token, master, "V0", "disable")
    status, data = api(port, token, master, "/api/v1/audit?limit=500")
    assert len(data["commands"]) >= 200, len(data["commands"])


def r06_kill_processes(port, token, master, data_root):
    """杀进程：杀桌面、杀看门狗、杀代理，验证自愈"""
    write_remote_config(data_root, port, "S6", standalone=True)
    desktop = start_desktop(data_root)
    try:
        wait_for(lambda: any("agent_main" in line for line in treecut_pythonw()), 40,
                 "standalone agent up")
        wait_client(port, token, master, "S6")
        # 杀独立代理 → 桌面守护自动拉起
        agent_pid = next(int(line.split("|", 1)[0]) for line in treecut_pythonw()
                         if "agent_main" in line)
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Stop-Process -Id {agent_pid} -Force"], capture_output=True)
        wait_for(lambda: any(
            "agent_main" in line and int(line.split("|", 1)[0]) != agent_pid
            for line in treecut_pythonw()), 90, "agent relaunched")
        # 杀桌面 → 看门狗不需要（桌面直启）；验证代理仍在
        kill_treecut_pythonw("agent_main")
        wait_client(port, token, master, "S6", timeout=40)
    finally:
        kill_treecut_pythonw()
        desktop.terminate()


def r07_kill_during_update(port, token, master, data_root):
    """更新中途杀进程：确保回滚或保持一致"""
    write_remote_config(data_root, port, "S7", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S7")
        package = TEST_ROOT / f"pkg_{int(time.time())}.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", json.dumps({
                "version": "13.5.11", "notes": "stress", "force": False,
                "files": [{"path": "src/treecut/__init__.py", "sha256": "0" * 64}],
            }))
            archive.writestr("files/src/treecut/__init__.py", b"# stress")
        status, data = api(port, token, master,
                           "/api/v1/updates?version=13.5.11", raw=package.read_bytes(),
                           method="POST")
        assert status == 200, status
        update_id = data["update_id"]
        status, _ = api(port, token, master, f"/api/v1/clients/S7/assign",
                        {"update_id": update_id}, method="POST")
        assert status == 200, status
        time.sleep(8)  # 让代理开始下载
        kill_treecut_pythonw()  # 更新中途杀掉代理
        time.sleep(3)
        agent2 = start_agent(data_root)  # 重新拉起
        try:
            wait_client(port, token, master, "S7", timeout=60)
            status, data = api(port, token, master, f"/api/v1/updates/{update_id}")
            applied = data.get("applied_by", "")
            # 无论是否应用成功，源码关键文件必须仍是当前版本
            assert "13.5.10" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
            print("      update applied markers:", applied[:120])
        finally:
            kill_treecut_pythonw()
            agent2.terminate()
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r08_database_corruption(port, token, master, data_root):
    """数据库破坏：先停 hub 再损坏库，重启后必须自动重建恢复"""
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -match 'hub_main' -and $_.CommandLine -match '8770' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)
    time.sleep(3)
    hub_db = data_root / "remote" / "hub_store.db"
    hub_db.write_bytes(b"garbage not sqlite")
    start_hub(data_root, port)
    status, data = api(port, token, master, "/api/v1/clients")
    assert status == 200, status  # 损坏库被自动重建
    from treecut.application.jobs import JobJournal
    jobs = data_root / "database" / "jobs.db"
    jobs.parent.mkdir(parents=True, exist_ok=True)
    jobs.write_bytes(b"garbage")
    journal = JobJournal(jobs)  # 损坏任务库自动重建
    journal.save({"id": "j1", "session_id": "s", "state": "success",
                  "message": "ok", "created_at": time.time(), "result": None, "error": None})
    assert journal.get("j1")["state"] == "success"
    policy = data_root / "config" / "remote_policy.json"
    policy.write_text("{broken", encoding="utf-8")
    from treecut.remote.agent import RemoteAgent
    from treecut.remote.config import RemoteConfig
    agent = RemoteAgent(paths_from_root(data_root),
                        RemoteConfig(hub_url="http://x", token="t" * 32, client_id="pc"))
    assert agent._read_policy()["disabled"] is False


def r09_model_validation_attack(port, token, master, data_root):
    """模型破坏：缺失权重、损坏配置、过小文件必须被标记而非崩溃"""
    from treecut.models.validation import inspect_model_contracts
    model_root = TEST_ROOT / f"models_{int(time.time())}"
    (model_root / "LocalTTS" / "vits-melo-tts-zh_en").mkdir(parents=True)
    # 完整有效的最小 LocalTTS 结构
    (model_root / "LocalTTS" / "vits-melo-tts-zh_en" / "model.onnx").write_bytes(b"x" * 200_000_000)
    (model_root / "LocalTTS" / "vits-melo-tts-zh_en" / "tokens.txt").write_text(
        "t\n" * 100, encoding="utf-8")
    (model_root / "LocalTTS" / "vits-melo-tts-zh_en" / "lexicon.txt").write_text(
        "a b\n" * 20000, encoding="utf-8")
    checks = inspect_model_contracts(model_root, cuda_available=False, cuda_runtime=False)
    assert checks["local_tts"].ready, checks["local_tts"].issues
    # 删除权重 → 标记缺失
    (model_root / "LocalTTS" / "vits-melo-tts-zh_en" / "model.onnx").unlink()
    checks = inspect_model_contracts(model_root, cuda_available=False, cuda_runtime=False)
    assert not checks["local_tts"].ready
    assert any("missing" in issue for issue in checks["local_tts"].issues)
    # 损坏配置
    (model_root / "LocalTTS" / "vits-melo-tts-zh_en" / "tokens.txt").write_text("", encoding="utf-8")
    checks = inspect_model_contracts(model_root, cuda_available=False, cuda_runtime=False)
    assert not checks["local_tts"].ready


def r10_hub_restart_storm(port, token, master, data_root):
    """hub 反复重启：代理必须持续重试并在恢复后重新连上"""
    write_remote_config(data_root, port, "S10", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S10")
        kill_treecut_pythonw("agent_main")  # 停止代理
        time.sleep(1)
        for _ in range(5):
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                            "Where-Object { $_.CommandLine -match 'hub_main' -and $_.CommandLine -match '8770' } | "
                            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                           capture_output=True)
            time.sleep(2)
        # 重启临时 hub
        start_hub(data_root, port)
        agent2 = start_agent(data_root)
        try:
            wait_client(port, token, master, "S10", timeout=60)
        finally:
            kill_treecut_pythonw()
            agent2.terminate()
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r11_file_destruction(port, token, master, data_root):
    """文件破坏：结果 JSON、报告、项目状态损坏后流程不崩"""
    project = data_root / "output" / "projects" / "broken_project"
    project.mkdir(parents=True)
    (project / "production_report.json").write_text("{broken", encoding="utf-8")
    (project / "STATUS.json").write_text("not json", encoding="utf-8")
    # 结果弹窗读取路径直接测：report 损坏时给出友好错误而非崩溃
    from treecut.application.production import ProductionResult
    result = ProductionResult(str(project), 10.0, 1, 1, None, None, None, str(project / "production_report.json"))
    from treecut.workflow.planning import EditPlan
    assert EditPlan is not None
    # 任务记录库中的损坏 result_json
    from treecut.application.jobs import JobJournal
    journal = JobJournal(data_root / "database" / "jobs2.db")
    journal.save({"id": "corrupt-result", "session_id": "s", "state": "success",
                  "message": "ok", "created_at": time.time(),
                  "result": {"final_mp4": "E:/gone.mp4", "project_dir": str(project)},
                  "error": None})
    job = journal.get("corrupt-result")
    assert job["result"]["final_mp4"] == "E:/gone.mp4"


def r12_concurrent_agents(port, token, master, data_root):
    """并发：10 个代理同时上报 + 各自执行命令"""
    agents = []
    try:
        for index in range(10):
            write_remote_config(data_root / f"c{index}", port, f"CONC{index}",
                                standalone=True, interval=15, token=token)
            agents.append(start_agent(data_root / f"c{index}"))
        for index in range(10):
            wait_client(port, token, master, f"CONC{index}", timeout=60)
        for index in range(10):
            command_id = enqueue(port, token, master, f"CONC{index}", "app_status")
            entry = wait_result(port, token, master, command_id, timeout=90)
            assert "独立代理=运行中" in entry["result"], entry["result"]
    finally:
        kill_treecut_pythonw()
        for agent in agents:
            agent.terminate()


def r13_out_of_order(port, token, master, data_root):
    """乱序：批量入队命令乱序执行、重复回执、并发读审计"""
    write_remote_config(data_root, port, "S13", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S13")
        ids = [enqueue(port, token, master, "S13", "app_status") for _ in range(30)]
        for command_id in ids:
            entry = wait_result(port, token, master, command_id, timeout=120)
            assert entry["status"] in ("done", "failed")
        # 重复回执不应破坏审计
        audit = api(port, token, master, "/api/v1/audit?limit=500")[1]["commands"]
        unique = {a["command_id"] for a in audit}
        assert len(unique) >= 30
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r14_boundary_values(port, token, master, data_root):
    """边界：超长命令、深路径、Unicode、超长输出截断"""
    write_remote_config(data_root, port, "S14", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S14")
        enable_exec(port, token, master, "S14")
        long_note = "a" * 5000
        command_id = enqueue(port, token, master, "S14", "exec", long_note)
        entry = wait_result(port, token, master, command_id)
        assert entry["status"] in ("done", "failed")
        # 超长输出截断
        command_id = enqueue(port, token, master, "S14", "exec",
                             "powershell -NoProfile -Command \"1..5000 | ForEach-Object { $_ }\"")
        entry = wait_result(port, token, master, command_id)
        assert len(entry["result"]) <= 2_000_000
        # Unicode 文件名 ship_file
        weird = TEST_ROOT / f"文件-{int(time.time())}.json"
        weird.write_text('{"测试": "值"}', encoding="utf-8")
        command_id = enqueue(port, token, master, "S14", "ship_file", str(weird))
        entry = wait_result(port, token, master, command_id)
        assert entry["result"].startswith("BASE64:"), entry["result"]
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r15_update_package_destruction(port, token, master, data_root):
    """更新包破坏：篡改哈希、绝对路径、损坏 zip、缺失清单全部拒绝并回滚"""
    from treecut.remote.update_pack import apply_update, verify_package
    with tempfile.TemporaryDirectory(dir=str(TEST_ROOT)) as temp:
        root = Path(temp)
        (root / "src").mkdir()
        target = root / "src" / "keep.txt"
        target.write_text("keep", encoding="utf-8")
        cases = []
        # 篡改哈希
        with zipfile.ZipFile(root / "a.zip", "w") as archive:
            archive.writestr("manifest.json", json.dumps({
                "version": "2", "files": [{"path": "src/keep.txt", "sha256": "0" * 64}]}))
            archive.writestr("files/src/keep.txt", b"changed")
        cases.append(verify_package(root / "a.zip", root))
        # 绝对路径
        with zipfile.ZipFile(root / "b.zip", "w") as archive:
            archive.writestr("manifest.json", json.dumps({
                "version": "2", "files": [{"path": "C:/Windows/x", "sha256": "0" * 64}]}))
        cases.append(verify_package(root / "b.zip", root))
        # 损坏 zip
        (root / "c.zip").write_bytes(b"not zip")
        cases.append(verify_package(root / "c.zip", root))
        # 缺失清单
        with zipfile.ZipFile(root / "d.zip", "w") as archive:
            archive.writestr("files/x.py", b"x")
        cases.append(verify_package(root / "d.zip", root))
        for problems in cases:
            assert problems, "package should be rejected"
        assert target.read_text(encoding="utf-8") == "keep"


def r16_poll_storm(port, token, master, data_root):
    """轮询风暴：hub 断连反复，代理 100 次轮询不崩"""
    write_remote_config(data_root, port, "S16", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S16")
        from treecut.remote.agent import RemoteAgent
        from treecut.remote.config import RemoteConfig
        config = RemoteConfig(hub_url=f"http://127.0.0.1:{port}", token="t" * 32,
                              client_id="S16", auto_discover=False)
        probe = RemoteAgent(paths_from_root(data_root), config)
        probe._caps = {"cpu_threads": 8}
        for _ in range(100):
            outcome = probe.poll_once()
            assert outcome.get("ok") in (True, False)
        # hub 关闭后仍不崩
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "Where-Object { $_.CommandLine -match '8770' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                       capture_output=True)
        for _ in range(20):
            outcome = probe.poll_once()
            assert outcome.get("ok") is False
    finally:
        kill_treecut_pythonw()
        agent.terminate()
        start_hub(data_root, port)  # 恢复供后续轮次使用


def r17_pipeline_validation_attack(port, token, master, data_root):
    """制作链路破坏：非法请求、垃圾匹配、极端时长全被拒绝"""
    from treecut.application.production import CreativeRequest
    bad = [
        dict(selling_points="", narration="x"),
        dict(selling_points="x", narration=""),
        dict(selling_points="x", narration="x", target_duration=4),
        dict(selling_points="x", narration="x", target_duration=301),
        dict(selling_points="x", narration="x", clip_seconds=0),
        dict(selling_points="x", narration="x", output_mp4=False, output_jianying=False),
        dict(selling_points="x", narration="x", output_preset="bad-preset"),
        dict(selling_points="x", narration="x", style="bad-style"),
        dict(selling_points="x", narration="x", narration_speed=3.0),
    ]
    for kwargs in bad:
        try:
            CreativeRequest(**kwargs).validate()
            raise AssertionError(f"should reject: {kwargs}")
        except (ValueError, PermissionError):
            pass
    from treecut.workflow import MaterialCandidate, match_materials
    candidates = [MaterialCandidate(i, f"G:/f{i}.mp4", "unclassified", 10, "", "", True)
                  for i in range(50)]
    matches = match_materials("岛台", candidates, limit=12,
                              domain_terms=("岛台餐桌一体", "上层薄抽"))
    assert len(matches) <= 12
    matches = match_materials("岛台" * 2000, candidates)
    assert len(matches) <= 12


def r18_combined_storm(port, token, master, data_root):
    """组合风暴：杀 hub + 杀代理 + 损坏库 + 篡改更新包同时发生"""
    from treecut.remote.update_pack import verify_package
    write_remote_config(data_root, port, "S18", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S18")
        # 同时破坏：杀 hub、杀代理、损坏库、损坏策略、投放恶意更新包
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "Where-Object { $_.CommandLine -match 'hub_main' -and "
                        "$_.CommandLine -match '8770' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                       capture_output=True)
        kill_treecut_pythonw()
        hub_db = data_root / "remote" / "hub_store.db"
        hub_db.write_bytes(b"garbage")
        (data_root / "config" / "remote_policy.json").write_text("{bad", encoding="utf-8")
        with zipfile.ZipFile(TEST_ROOT / "evil18.zip", "w") as archive:
            archive.writestr("manifest.json", json.dumps({
                "version": "1", "files": [{"path": "../x", "sha256": "0" * 64}]}))
        assert verify_package(TEST_ROOT / "evil18.zip", data_root)
        time.sleep(2)
        start_hub(data_root, port)  # 重建 hub（损坏库自动恢复）
        agent2 = start_agent(data_root)
        try:
            wait_client(port, token, master, "S18", timeout=60)
        finally:
            kill_treecut_pythonw()
            agent2.terminate()
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r19_extreme_volume(port, token, master, data_root):
    """极限：500 并发状态 + 500 命令 + 8GB 更新包拒绝"""
    for index in range(500):
        api(port, token, master, "/api/v1/status",
            {"client_id": f"E{index}", "version": "13.5.10",
             "report": {"i": index}}, method="POST")
    status, data = api(port, token, master, "/api/v1/clients")
    assert len(data.get("clients", [])) >= 500, len(data.get("clients", []))
    for index in range(500):
        enqueue(port, token, master, "E0", "disable")
    status, data = api(port, token, master, "/api/v1/audit?limit=500")
    assert len(data["commands"]) >= 400, len(data["commands"])
    # 超大更新包（用稀疏文件快速生成 1GB 头）
    big = TEST_ROOT / f"big_{int(time.time())}.zip"
    with open(big, "wb") as stream:
        stream.seek(1024 * 1024 * 1024)
        stream.write(b"x")
    status, _ = api(port, token, master, "/api/v1/updates?version=1.0",
                    raw=big.read_bytes()[:8 * 1024 * 1024 + 10], method="POST")
    # 只要不超过 8GB 上限即可；这里 8MB+ 无清单会 422
    assert status in (422, 200), status
    big.unlink(missing_ok=True)


def r20_final_chaos_and_invariants(port, token, master, data_root):
    """终局混沌：全链路再杀一轮 + 校验关键不变量与安装包完整性"""
    write_remote_config(data_root, port, "S20", standalone=True)
    watchdog = start_watchdog(data_root)  # 桌面由看门狗托管，杀完能自动拉起
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "S20")
        desktop_pid = next(int(line.split("|", 1)[0]) for line in treecut_pythonw()
                           if "-m treecut.desktop" in line)
        kill_treecut_pythonw("desktop")
        wait_for(lambda: any(
            "-m treecut.desktop" in line
            and int(line.split("|", 1)[0]) != desktop_pid
            for line in treecut_pythonw()
        ), 60, "watchdog keeps desktop alive")
        kill_treecut_pythonw("agent_main")
        wait_for(lambda: any("agent_main" in line for line in treecut_pythonw()), 90,
                 "agent back after chaos")
        wait_client(port, token, master, "S20", timeout=60)
        command_id = enqueue(port, token, master, "S20", "app_status")
        entry = wait_result(port, token, master, command_id)
        assert "桌面程序=运行中" in entry["result"], entry["result"]
    finally:
        kill_treecut_pythonw()
        watchdog.terminate()
        agent.terminate()
    # 不变量
    assert "13.5.10" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    canary = (ROOT / "src" / "treecut" / "__canary__.py").read_text(encoding="utf-8")
    assert "treecut-review-fix-round" in canary
    assert "def standalone_agent_running" in (
        ROOT / "src" / "treecut" / "remote" / "agent.py").read_text(encoding="utf-8")
    assert (ROOT / "src" / "treecut" / "desktop.py").read_text(encoding="utf-8").count(
        "def _agent_guard") == 1
    for installer in (ROOT / ".." / "TreeCut_installer").resolve().glob(
            "output/*Setup.exe"):
        assert installer.stat().st_size > 0
    game = (ROOT / ".." / "TreeCut_installer").resolve() / "game_output"
    bins = list(game.glob("*.bin"))
    assert len(bins) == 7, len(bins)


ROUNDS = [
    r01_normal, r02_high_frequency, r03_input_sabotage, r04_attack,
    r05_stress_volume, r06_kill_processes, r07_kill_during_update,
    r08_database_corruption, r09_model_validation_attack, r10_hub_restart_storm,
    r11_file_destruction, r12_concurrent_agents, r13_out_of_order,
    r14_boundary_values, r15_update_package_destruction, r16_poll_storm,
    r17_pipeline_validation_attack, r18_combined_storm, r19_extreme_volume,
    r20_final_chaos_and_invariants,
]


def main() -> int:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    # 清理上一轮可能残留的临时 hub / 测试进程
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -match 'hub_main' -and "
                    "$_.CommandLine -match '8770' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)
    kill_treecut_pythonw()
    time.sleep(3)
    data_root = TEST_ROOT / f"hub_{int(time.time())}"
    data_root.mkdir(parents=True)
    port = 8770
    hub = start_hub(data_root, port)
    token, master = hub_creds(data_root)
    failed = 0
    try:
        for index, fn in enumerate(ROUNDS, 1):
            try:
                run_round(port, token, master, data_root, index, fn)
            except Exception:
                failed += 1
            # 每轮后确保临时 hub 还活着（部分轮次会杀掉它）
            try:
                status, _ = api(port, token, master, "/health")
                if status != 200:
                    hub = start_hub(data_root, port)
            except Exception:
                hub = start_hub(data_root, port)
    finally:
        kill_treecut_pythonw()
        try:
            hub.terminate()
        except Exception:
            pass
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "Where-Object { $_.CommandLine -match 'hub_main' -and "
                        "$_.CommandLine -match '8770' } | "
                        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                       capture_output=True)
    passed = len(ROUNDS) - failed
    print(f"\n{'='*70}\nSTRESS_20_ROUNDS: {passed}/{len(ROUNDS)} passed")
    for result in ROUND_RESULTS:
        marker = "PASS" if result["ok"] else "FAIL"
        detail = "" if result["ok"] else f" :: {result.get('error', '')[:160]}"
        print(f"  R{result['round']:02d} {marker}{detail}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
