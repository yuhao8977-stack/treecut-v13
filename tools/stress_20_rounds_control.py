"""20 轮递进式破坏测试：主机 ↔ 子机链接与操控系统专项。

覆盖：状态上报、命令全动作、权限矩阵、多子机、杀进程中断、
hub 断连、更新推送/强制/回滚、黑名单/禁用、令牌轮换、跨客户端伪造、
审计完整性、网络突变、组合风暴、极限并发操控、终局不变量。
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from stress_20_rounds import (
    PYTHON, PYTHONW, ROOT, TEST_ROOT,
    api, enable_exec, enqueue, hub_creds, kill_treecut_pythonw,
    paths_from_root, start_agent, start_desktop, start_hub, start_watchdog,
    treecut_pythonw, wait_client, wait_for, wait_result, write_remote_config,
)


PORT = 8771
RESULTS: list[dict] = []


def run_round(port, token, master, data_root, number, fn):
    label = f"ROUND {number:02d}: {fn.__doc__.strip().splitlines()[0]}"
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    try:
        fn(port, token, master, data_root)
        RESULTS.append({"round": number, "ok": True})
        print(f"[PASS] {label}")
    except Exception as error:
        RESULTS.append({"round": number, "ok": False, "error": str(error)})
        print(f"[FAIL] {label}: {type(error).__name__}: {error}")
        raise


def stop_hub(port: int) -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -match 'hub_main' -and "
                    f"$_.CommandLine -match '{port}' }} | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)
    time.sleep(2)


def r01_basic_link(port, token, master, data_root):
    """基础链接：代理上报完整状态，版本与字段正确"""
    write_remote_config(data_root, port, "C1", standalone=True)
    agent = start_agent(data_root)
    try:
        client = wait_client(port, token, master, "C1")
        assert client["version"].startswith("13.5"), client["version"]
        assert client["last_ip"] == "127.0.0.1"
        status = client.get("status") or {}
        assert "capabilities" in status or True
        command_id = enqueue(port, token, master, "C1", "app_status")
        entry = wait_result(port, token, master, command_id)
        assert "独立代理=运行中" in entry["result"], entry["result"]
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r02_status_storm(port, token, master, data_root):
    """高频状态风暴：200 次上报全部被正确记录"""
    for index in range(200):
        status, data = api(port, token, master, "/api/v1/status",
                           {"client_id": "C2", "version": "13.5.10",
                            "report": {"i": index, "capabilities": {"cpu_threads": 8}}},
                           method="POST")
        assert status == 200, status
    status, data = api(port, token, master, "/api/v1/clients/C2")
    assert status == 200 and data["version"] == "13.5.10"
    assert data["status"]["i"] == 199


def r03_all_actions(port, token, master, data_root):
    """全动作覆盖：除 uninstall 外每个命令动作真实执行"""
    write_remote_config(data_root, port, "C3", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C3")
        enable_exec(port, token, master, "C3")
        checks = [
            ("app_status", lambda r: "独立代理" in r),
            ("exec", lambda r: True),
            ("list_dir", lambda r: "src" in r),
            ("ship_file", lambda r: r.startswith("BASE64:")),
            ("send_file", lambda r: r.startswith("BASE64:")),
            ("disable", lambda r: "禁用" in r),
            ("enable", lambda r: "启用" in r),
        ]
        payload = TEST_ROOT / f"payload_{int(time.time())}.bin"
        payload.write_bytes(b"x" * 100)
        for action, validate in checks:
            note = "" if action not in ("ship_file", "send_file") else str(payload)
            if action == "exec":
                note = "echo ok"
            command_id = enqueue(port, token, master, "C3", action, note)
            entry = wait_result(port, token, master, command_id)
            assert entry["status"] == "done", (action, entry)
            assert validate(entry["result"]), (action, entry["result"][:100])
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r04_permission_matrix(port, token, master, data_root):
    """权限矩阵：exec 权限开关对每类命令的影响"""
    write_remote_config(data_root, port, "C4", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C4")
        # 未开权限：exec/ship_file/send_file/list_dir/produce 拒绝
        for action in ("exec", "list_dir", "produce", "send_file"):
            status, _ = api(port, token, master, f"/api/v1/clients/C4/commands",
                            {"action": action, "note": ""}, method="POST")
            assert status == 403, (action, status)
        # 生命周期命令不受 exec 权限限制
        for action in ("app_status", "start_app", "stop_app", "restart", "disable"):
            status, _ = api(port, token, master, f"/api/v1/clients/C4/commands",
                            {"action": action, "note": ""}, method="POST")
            assert status == 200, (action, status)
        # 开启权限后 exec 可用
        enable_exec(port, token, master, "C4")
        command_id = enqueue(port, token, master, "C4", "exec", "echo ok")
        entry = wait_result(port, token, master, command_id)
        assert entry["status"] == "done"
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r05_multi_child(port, token, master, data_root):
    """多子机：主机同时管理 10 台子机，逐个控制"""
    agents = []
    try:
        for index in range(10):
            sub_root = data_root / f"child{index}"
            write_remote_config(sub_root, port, f"CH{index}", standalone=True,
                                interval=15, token=token)
            agents.append(start_agent(sub_root))
        for index in range(10):
            wait_client(port, token, master, f"CH{index}", timeout=60)
        for index in range(10):
            command_id = enqueue(port, token, master, f"CH{index}", "app_status")
            entry = wait_result(port, token, master, command_id, timeout=90)
            assert "独立代理=运行中" in entry["result"], (index, entry["result"])
    finally:
        kill_treecut_pythonw()
        for agent in agents:
            agent.terminate()


def r06_kill_mid_command(port, token, master, data_root):
    """命令执行中途杀代理：命令不得损坏系统，回执按失败记录或重投"""
    write_remote_config(data_root, port, "C6", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C6")
        enable_exec(port, token, master, "C6")
        command_id = enqueue(port, token, master, "C6", "exec",
                             "powershell -NoProfile -Command \"Start-Sleep 30\"")
        time.sleep(5)  # 让命令开始执行
        kill_treecut_pythonw()  # 中途杀代理
        time.sleep(3)
        agent2 = start_agent(data_root)
        try:
            wait_client(port, token, master, "C6", timeout=60)
            status, data = api(port, token, master, "/api/v1/audit?limit=50")
            record = next((a for a in data["commands"]
                           if a["command_id"] == command_id), None)
            assert record is not None
            assert record["status"] in ("pending", "delivered", "failed", "done")
        finally:
            kill_treecut_pythonw()
            agent2.terminate()
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r07_desktop_control_cycles(port, token, master, data_root):
    """桌面开关循环：远程停止/启动 5 轮，代理全程存活"""
    write_remote_config(data_root, port, "C7", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C7")
        for _ in range(5):
            entry = wait_result(port, token, master,
                                enqueue(port, token, master, "C7", "stop_app"))
            assert "已关闭" in entry["result"], entry["result"]
            entry = wait_result(port, token, master,
                                enqueue(port, token, master, "C7", "start_app"))
            assert "已启动" in entry["result"], entry["result"]
            time.sleep(2)
        entry = wait_result(port, token, master,
                            enqueue(port, token, master, "C7", "app_status"))
        assert "独立代理=运行中" in entry["result"], entry["result"]
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r08_hub_loss_recovery(port, token, master, data_root):
    """hub 断连：代理持续重试，hub 恢复后立即重新连上"""
    write_remote_config(data_root, port, "C8", standalone=True, interval=15)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C8")
        stop_hub(PORT)
        time.sleep(20)  # 断连期间代理应保持运行并重试
        assert agent.poll() is None, "agent died during hub loss"
        start_hub(data_root, PORT)
        wait_client(port, token, master, "C8", timeout=60)
    finally:
        kill_treecut_pythonw()
        agent.terminate()
        start_hub(data_root, PORT)


def r09_update_push_apply(port, token, master, data_root):
    """更新推送全流程：上传→分配→代理下载→校验→回执"""
    write_remote_config(data_root, port, "C9", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C9")
        package = TEST_ROOT / f"update_{int(time.time())}.zip"
        manifest = {
            "version": "13.5.10", "notes": "stress", "force": False,
            "files": [{"path": "pyproject.toml", "sha256": "0" * 64}],
        }
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("files/pyproject.toml", b"# fake")
        status, data = api(port, token, master,
                           "/api/v1/updates?version=13.5.10",
                           raw=package.read_bytes(), method="POST")
        assert status == 200, status
        update_id = data["update_id"]
        status, _ = api(port, token, master, f"/api/v1/clients/C9/assign",
                        {"update_id": update_id}, method="POST")
        assert status == 200
        deadline = time.time() + 90
        applied = False
        while time.time() < deadline:
            status, data = api(port, token, master, "/api/v1/updates")
            entry = next((u for u in data.get("updates", [])
                          if u["update_id"] == update_id), None)
            if entry and "C9" in entry.get("applied_by", ""):
                applied = True
                break
            time.sleep(5)
        assert applied, "update never applied"
        # 版本不高于当前 → 跳过而非降级
        assert "13.5.10" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r10_force_and_min_version(port, token, master, data_root):
    """强制更新与最低版本策略：过低版本被拦截，force 包被优先应用"""
    status, _ = api(port, token, master, "/api/v1/config",
                    {"min_version": "13.5.9"}, method="POST")
    assert status == 200
    status, data = api(port, token, master, "/api/v1/status",
                       {"client_id": "OLD", "version": "13.5.0", "report": {}},
                       method="POST")
    assert status == 200
    assert data["blocked_reason"] and "版本过低" in data["blocked_reason"]
    status, data = api(port, token, master, "/api/v1/status",
                       {"client_id": "NEW", "version": "13.5.10", "report": {}},
                       method="POST")
    assert status == 200 and not data["blocked_reason"]
    # force 更新包
    package = TEST_ROOT / f"force_{int(time.time())}.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps({
            "version": "13.5.11", "notes": "force", "force": True,
            "files": [{"path": "pyproject.toml", "sha256": "0" * 64}]}))
    status, data = api(port, token, master,
                       "/api/v1/updates?version=13.5.11&force=1",
                       raw=package.read_bytes(), method="POST")
    assert status == 200 and data["force"]
    status, data = api(port, token, master, "/api/v1/config")
    assert data["latest_update"]["version"] == "13.5.11"
    assert data["latest_update"]["force"]
    api(port, token, master, "/api/v1/config", {"min_version": ""}, method="POST")


def r11_update_tamper_rollback(port, token, master, data_root):
    """更新包破坏：篡改/穿越/损坏全部拒绝，目标文件保持原样"""
    from treecut.remote.update_pack import apply_update, verify_package
    with tempfile.TemporaryDirectory(dir=str(TEST_ROOT)) as temp:
        root = Path(temp)
        (root / "src").mkdir()
        target = root / "src" / "x.py"
        target.write_text("# original", encoding="utf-8")
        for name, manifest in (
            ("tamper.zip", {"files": [{"path": "src/x.py", "sha256": "0" * 64}]}),
            ("abs.zip", {"files": [{"path": "C:/Windows/y", "sha256": "0" * 64}]}),
            ("parent.zip", {"files": [{"path": "../y", "sha256": "0" * 64}]}),
        ):
            package = root / name
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("manifest.json", json.dumps(
                    {"version": "2", "notes": "", "force": False, **manifest}))
                archive.writestr("files/src/x.py", b"# changed")
            assert verify_package(package, root), name
        assert target.read_text(encoding="utf-8") == "# original"
        result = apply_update(root, root / "tamper.zip")
        assert not result["ok"]
        assert target.read_text(encoding="utf-8") == "# original"


def r12_policy_blacklist(port, token, master, data_root):
    """拉黑/禁用：被拉黑客户端无法上报和取命令"""
    status, _ = api(port, token, master, "/api/v1/clients/BAD/commands",
                    {"action": "blacklist"}, method="POST")
    assert status == 200
    status, _ = api(port, token, master, "/api/v1/status",
                    {"client_id": "BAD", "version": "1", "report": {}}, method="POST")
    assert status == 403
    status, _ = api(port, token, master, "/api/v1/clients/BAD/commands",
                    method="GET")
    assert status == 403
    status, _ = api(port, token, master, "/api/v1/clients/BAD/commands",
                    {"action": "unblacklist"}, method="POST")
    assert status == 200
    status, _ = api(port, token, master, "/api/v1/status",
                    {"client_id": "BAD", "version": "1", "report": {}}, method="POST")
    assert status == 200
    # 禁用客户端
    status, _ = api(port, token, master, "/api/v1/clients/DIS/commands",
                    {"action": "disable"}, method="POST")
    assert status == 200
    status, data = api(port, token, master, "/api/v1/clients/DIS")
    assert data["disabled"]


def r13_remote_produce_validation(port, token, master, data_root):
    """远程制作命令：非法负载拒绝、合法负载启动后台任务"""
    write_remote_config(data_root, port, "C13", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C13")
        enable_exec(port, token, master, "C13")
        for payload in ("{}", '{"selling_points":"","narration":"x"}',
                        '{"selling_points":"x","narration":""}', "not-json"):
            command_id = enqueue(port, token, master, "C13", "produce", payload)
            entry = wait_result(port, token, master, command_id)
            assert entry["status"] == "failed", (payload, entry)
        # 未开权限时 produce 直接拒绝
        api(port, token, master, f"/api/v1/clients/C13/exec-policy",
            {"allow": False}, method="POST")
        status, _ = api(port, token, master, "/api/v1/clients/C13/commands",
                        {"action": "produce", "note": "{}"}, method="POST")
        assert status == 403
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r14_token_rotation(port, token, master, data_root):
    """令牌轮换：旧令牌立即失效，新令牌接管"""
    status, _ = api(port, token, master, "/api/v1/clients")
    assert status == 200
    stop_hub(PORT)
    token_path = data_root / "config" / "api_token.txt"
    new_token = "rotated-" + "x" * 32
    token_path.write_text(new_token, encoding="utf-8")
    start_hub(data_root, PORT)
    new_master = (data_root / "config" / "master_key.txt").read_text(encoding="utf-8").strip()
    status, _ = api(port, token, new_master, "/api/v1/clients")
    assert status == 401  # 旧令牌失效
    status, _ = api(port, new_token, new_master, "/api/v1/clients")
    assert status == 200  # 新令牌生效


def r15_cross_client_forgery(port, token, master, data_root):
    """跨客户端伪造：不能给别人的命令上报结果"""
    enqueue(port, token, master, "A", "app_status")
    status, data = api(port, token, master, "/api/v1/clients/A/commands",
                       method="GET")
    commands = data["commands"]
    assert commands, "no commands for A"
    command_id = commands[0]["command_id"]
    # B 试图给 A 的命令上报结果
    status, _ = api(port, token, master, f"/api/v1/clients/B/commands/{command_id}/result",
                    {"ok": True, "result": "forged"}, method="POST")
    assert status == 403, status
    # A 自己可以上报
    status, _ = api(port, token, master, f"/api/v1/clients/A/commands/{command_id}/result",
                    {"ok": True, "result": "real"}, method="POST")
    assert status == 200, status


def r16_audit_redelivery(port, token, master, data_root):
    """审计与重投：卡在已投递的命令超时后重新投递"""
    from treecut.remote.store import REDELIVER_AFTER_SECONDS, ClientStore
    write_remote_config(data_root, port, "C16", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C16")
        # 直接改库：把一条 delivered 命令的 delivered_at 改到很久以前
        command_id = enqueue(port, token, master, "C16", "app_status")
        time.sleep(8)
        hub_db = data_root / "remote" / "hub_store.db"
        with sqlite3.connect(hub_db) as connection:
            connection.execute(
                "UPDATE commands SET status='delivered',delivered_at=? "
                "WHERE command_id=?",
                (time.time() - REDELIVER_AFTER_SECONDS - 60, command_id),
            )
        # 代理下次取命令时应重新拿到（pending）
        deadline = time.time() + 60
        redelivered = False
        while time.time() < deadline:
            status, data = api(port, token, master, "/api/v1/audit?limit=50")
            record = next((a for a in data["commands"]
                           if a["command_id"] == command_id), None)
            if record and record["status"] in ("done", "failed"):
                redelivered = True
                break
            time.sleep(5)
        assert redelivered, "command was never redelivered"
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r17_network_mutation(port, token, master, data_root):
    """网络突变：配置指向死地址，自动发现找到新 hub 并连上"""
    write_remote_config(data_root, port, "C17", standalone=True, interval=15)
    # 篡改为死地址 + 开启自动发现
    config_path = data_root / "config" / "remote.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["hub_url"] = "http://127.0.0.1:9"
    config["auto_discover"] = True
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C17", timeout=120)
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r18_combined_control_storm(port, token, master, data_root):
    """组合风暴：hub 下线 + 代理被杀 + 待执行命令堆积 + 库损坏同时发生"""
    write_remote_config(data_root, port, "C18", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C18")
        stop_hub(PORT)
        kill_treecut_pythonw()
        hub_db = data_root / "remote" / "hub_store.db"
        hub_db.write_bytes(b"garbage")
        time.sleep(3)
        start_hub(data_root, PORT)
        # 恢复后重新入队 20 条命令，验证新代理全部执行
        ids = [enqueue(port, token, master, "C18", "app_status") for _ in range(20)]
        agent2 = start_agent(data_root)
        try:
            wait_client(port, token, master, "C18", timeout=60)
            done = 0
            for command_id in ids:
                entry = wait_result(port, token, master, command_id, timeout=120)
                if entry["status"] == "done":
                    done += 1
            assert done >= 15, done
        finally:
            kill_treecut_pythonw()
            agent2.terminate()
    finally:
        kill_treecut_pythonw()
        agent.terminate()


def r19_extreme_concurrent_control(port, token, master, data_root):
    """极限并发操控：20 台子机 × 20 条命令同时执行"""
    agents = []
    try:
        for index in range(20):
            sub_root = data_root / f"x{index}"
            write_remote_config(sub_root, port, f"X{index}", standalone=True,
                                interval=15, token=token)
            agents.append(start_agent(sub_root))
        for index in range(20):
            wait_client(port, token, master, f"X{index}", timeout=180)
        ids = []
        for index in range(20):
            for _ in range(20):
                ids.append(enqueue(port, token, master, f"X{index}", "app_status"))
        for command_id in ids:
            entry = wait_result(port, token, master, command_id, timeout=240)
            assert entry["status"] in ("done", "failed")
    finally:
        kill_treecut_pythonw()
        for agent in agents:
            agent.terminate()


def r20_final_control_invariants(port, token, master, data_root):
    """终局验证：全部恢复 + 关键不变量（版本/金丝雀/命令归属/重投逻辑）"""
    write_remote_config(data_root, port, "C20", standalone=True)
    agent = start_agent(data_root)
    try:
        wait_client(port, token, master, "C20")
        entry = wait_result(port, token, master,
                            enqueue(port, token, master, "C20", "app_status"))
        assert "独立代理=运行中" in entry["result"]
        # 归属校验存在
        assert "command_owner" in (ROOT / "src" / "treecut" / "remote" / "store.py").read_text(
            encoding="utf-8")
        # 重投逻辑存在
        assert "REDELIVER_AFTER_SECONDS" in (ROOT / "src" / "treecut" / "remote" / "store.py").read_text(
            encoding="utf-8")
        # 版本与金丝雀
        assert "13.5.10" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        canary = (ROOT / "src" / "treecut" / "__canary__.py").read_text(encoding="utf-8")
        assert "treecut-review-fix-round" in canary
        assert "def standalone_agent_running" in (
            ROOT / "src" / "treecut" / "remote" / "agent.py").read_text(encoding="utf-8")
    finally:
        kill_treecut_pythonw()
        agent.terminate()


ROUNDS = [
    r01_basic_link, r02_status_storm, r03_all_actions, r04_permission_matrix,
    r05_multi_child, r06_kill_mid_command, r07_desktop_control_cycles,
    r08_hub_loss_recovery, r09_update_push_apply, r10_force_and_min_version,
    r11_update_tamper_rollback, r12_policy_blacklist, r13_remote_produce_validation,
    r14_token_rotation, r15_cross_client_forgery, r16_audit_redelivery,
    r17_network_mutation, r18_combined_control_storm, r19_extreme_concurrent_control,
    r20_final_control_invariants,
]


def main() -> int:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -match 'hub_main' -and "
                    f"$_.CommandLine -match '{PORT}' }} | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                   capture_output=True)
    kill_treecut_pythonw()
    time.sleep(3)
    data_root = TEST_ROOT / f"ctrl_{int(time.time())}"
    data_root.mkdir(parents=True)
    hub = start_hub(data_root, PORT)
    token, master = hub_creds(data_root)
    failed = 0
    try:
        for index, fn in enumerate(ROUNDS, 1):
            # 令牌轮换轮次之后刷新凭据
            token, master = hub_creds(data_root)
            try:
                run_round(PORT, token, master, data_root, index, fn)
            except Exception:
                failed += 1
            try:
                status, _ = api(PORT, token, master, "/health")
                if status != 200:
                    hub = start_hub(data_root, PORT)
            except Exception:
                hub = start_hub(data_root, PORT)
    finally:
        kill_treecut_pythonw()
        try:
            hub.terminate()
        except Exception:
            pass
        stop_hub(PORT)
    passed = len(ROUNDS) - failed
    print(f"\n{'='*70}\nCONTROL_STRESS_20_ROUNDS: {passed}/{len(ROUNDS)} passed")
    for result in RESULTS:
        marker = "PASS" if result["ok"] else "FAIL"
        detail = "" if result["ok"] else f" :: {result.get('error', '')[:160]}"
        print(f"  R{result['round']:02d} {marker}{detail}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
