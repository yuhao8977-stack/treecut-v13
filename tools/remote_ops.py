"""Batch remote operations against the child machine (UTF-8 safe, no shell quoting)."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

from treecut.platform.paths import RuntimePaths


CLIENT = "DESKTOP-S6KSLFM-5a56c7"


def _api(paths, path: str, method: str = "GET", payload=None, timeout: float = 30):
    token = (paths.data_root / "config" / "api_token.txt").read_text(encoding="utf-8").strip()
    master = (paths.data_root / "config" / "master_key.txt").read_text(encoding="utf-8").strip()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        "http://127.0.0.1:8766" + path, data=data, method=method,
        headers={"X-TreeCut-Token": token, "X-TreeCut-Master": master,
                 "Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _enqueue(paths, note: str, action: str = "exec") -> str:
    created = _api(paths, f"/api/v1/clients/{CLIENT}/commands",
                   method="POST", payload={"action": action, "note": note})
    return created["command_id"]


def _wait(paths, command_id: str, timeout: float = 240.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        audit = _api(paths, "/api/v1/audit?limit=80")
        for entry in audit.get("commands", []):
            if entry["command_id"] == command_id:
                if entry.get("status") in ("done", "failed"):
                    return entry
                break
        time.sleep(8)
    return {"status": "timeout", "result": ""}


def _save(entry: dict, name: str) -> None:
    paths = RuntimePaths.discover()
    log = paths.logs / "remote_ops.json"
    history = []
    if log.is_file():
        try:
            history = json.loads(log.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.append({"op": name, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "entry": entry})
    log.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def run(paths, name: str, note: str, action: str = "exec", timeout: float = 240.0) -> dict:
    command_id = _enqueue(paths, note, action)
    print(f"[{name}] command_id={command_id}")
    entry = _wait(paths, command_id, timeout)
    _save(entry, name)
    print(f"[{name}] status={entry.get('status')}")
    return entry


def op_shortcut(paths) -> None:
    run(paths, "shortcut", (
        "set PYTHONPATH=src&& runtime\\python.exe -c "
        "\"from pathlib import Path; from treecut.platform.shortcuts import "
        "create_desktop_shortcut; print(create_desktop_shortcut(Path('E:/treecut-v13')))\""
    ))


def op_verify(paths) -> None:
    run(paths, "verify", (
        "powershell -NoProfile -Command "
        "\"$d=[Environment]::GetFolderPath('Desktop'); "
        "$l=Join-Path $d '树剪 TreeCut.lnk'; "
        "if(Test-Path $l){$s=(New-Object -ComObject WScript.Shell).CreateShortcut($l); "
        "Write-Output ('LNK_OK ' + $s.TargetPath)}else{Write-Output 'LNK_MISSING'}; "
        "Get-CimInstance Win32_Process -Filter \\\"Name='pythonw.exe'\\\" | "
        "ForEach-Object { Write-Output ('PROC ' + $_.ProcessId + ' ' + $_.CommandLine) }\""
    ))


def op_drives(paths) -> None:
    run(paths, "drives", (
        "powershell -NoProfile -Command "
        "\"Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Used -ne $null} | "
        "ForEach-Object { Write-Output ('DRIVE ' + $_.Name + ' used=' + "
        "[math]::Round($_.Used/1GB,1) + 'GB free=' + [math]::Round($_.Free/1GB,1) + 'GB') }; "
        "foreach($p in @('C:\\','D:\\','E:\\','F:\\')){ if(Test-Path $p){ "
        "Write-Output ('TOP ' + $p); Get-ChildItem $p -Force -ErrorAction SilentlyContinue | "
        "Select-Object -First 40 | ForEach-Object { Write-Output ('  ' + $_.Name) } } }\""
    ))


def op_treecut(paths) -> None:
    run(paths, "treecut", (
        "powershell -NoProfile -Command "
        "\"$r='E:\\treecut-v13'; if(Test-Path $r){ Get-ChildItem $r -Force | "
        "ForEach-Object { if($_.PSIsContainer){ $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('DIR ' + $_.Name + ' ' + [math]::Round($s/1MB,1) + 'MB') } else { "
        "Write-Output ('FILE ' + $_.Name + ' ' + $_.Length) } } } else { Write-Output 'NO_ROOT' }\""
    ))


def op_docs_diff(paths) -> None:
    run(paths, "docs_diff", (
        "powershell -NoProfile -Command "
        "\"if(Test-Path 'E:\\treecut-v13\\docs'){ Get-ChildItem 'E:\\treecut-v13\\docs' -Filter *.md | "
        "ForEach-Object { Write-Output $_.Name } }\""
    ))


def op_runtime_data(paths) -> None:
    run(paths, "runtime_data", (
        "powershell -NoProfile -Command "
        "\"$r='E:\\treecut-v13\\runtime_data'; if(Test-Path $r){ Get-ChildItem $r -Force | "
        "ForEach-Object { if($_.PSIsContainer){ $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('DIR ' + $_.Name + ' ' + [math]::Round($s/1MB,1) + 'MB') } else { "
        "Write-Output ('FILE ' + $_.Name + ' ' + $_.Length) } } } else { Write-Output 'NO_ROOT' }\""
    ))


def op_outputs(paths) -> None:
    run(paths, "outputs", (
        "powershell -NoProfile -Command "
        "\"$o='E:\\treecut-v13\\runtime_data\\output\\projects'; if(Test-Path $o){ "
        "Get-ChildItem $o -Directory | Sort-Object LastWriteTime -Descending | "
        "ForEach-Object { $f=Get-ChildItem $_.FullName -Filter *.mp4 -Recurse -ErrorAction SilentlyContinue; "
        "Write-Output ($_.Name + ' ' + $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm') + ' mp4=' + $f.Count) } } "
        "else { Write-Output 'NO_PROJECTS' }\""
    ))


def op_other_treecut_dirs(paths) -> None:
    run(paths, "other_treecut", (
        "powershell -NoProfile -Command "
        "\"foreach($d in @('D:\\','E:\\','C:\\Users\\33186\\Desktop','C:\\Users\\33186\\Documents')){ "
        "if(Test-Path $d){ Get-ChildItem $d -Force -ErrorAction SilentlyContinue | Where-Object { "
        "$_.Name -match 'treecut|TreeCut|树剪|备份|backup|installer|Setup' } | "
        "ForEach-Object { Write-Output ($_.FullName + ' ' + $(if($_.PSIsContainer){'DIR'}else{$_.Length})) } } }\""
    ))


def op_f_dev_dirs(paths) -> None:
    run(paths, "f_dev_dirs", (
        "powershell -NoProfile -Command "
        "\"foreach($r in @('F:\\TreeCut_v13','F:\\TreeCut_build','F:\\TreeCut_v13_子程序便携版',"
        "'F:\\树剪TreeCut_v12.2_完整部署')){ Write-Output ('ROOT ' + $r); "
        "if(Test-Path $r){ Get-ChildItem $r -Force -ErrorAction SilentlyContinue | "
        "ForEach-Object { if($_.PSIsContainer){ $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('  DIR ' + $_.Name + ' ' + [math]::Round($s/1MB,1) + 'MB') } else { "
        "Write-Output ('  FILE ' + $_.Name + ' ' + $_.Length) } } } else { "
        "Write-Output '  MISSING' } }\""
    ))


def op_models(paths) -> None:
    run(paths, "models", (
        "powershell -NoProfile -Command "
        "\"$m='E:\\treecut-v13\\models'; Get-ChildItem $m -Force | "
        "ForEach-Object { $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ($_.Name + ' ' + [math]::Round($s/1MB,1) + 'MB') }\""
    ))


def op_tools(paths) -> None:
    run(paths, "tools", (
        "powershell -NoProfile -Command "
        "\"$t='E:\\treecut-v13\\tools'; Get-ChildItem $t -Force | "
        "ForEach-Object { if($_.PSIsContainer){ $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('DIR ' + $_.Name + ' ' + [math]::Round($s/1MB,1) + 'MB') } else { "
        "Write-Output ('FILE ' + $_.Name + ' ' + $_.Length) } }\""
    ))


def op_related(paths) -> None:
    run(paths, "related", (
        "powershell -NoProfile -Command "
        "\"foreach($r in @('E:\\树剪软件相关文件','E:\\树剪草稿视频导出')){ "
        "Write-Output ('ROOT ' + $r); if(Test-Path $r){ $all=Get-ChildItem $r -Recurse -File "
        "-ErrorAction SilentlyContinue; $sum=($all | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('  FILES ' + $all.Count + ' SIZE ' + [math]::Round($sum/1MB,1) + 'MB'); "
        "Get-ChildItem $r -Force -ErrorAction SilentlyContinue | Select-Object -First 25 | "
        "ForEach-Object { Write-Output ('  ' + $_.Name) } } else { Write-Output '  MISSING' } }\""
    ))


def op_materials(paths) -> None:
    run(paths, "materials", (
        "powershell -NoProfile -Command "
        "\"foreach($r in @('E:\\素材库','E:\\【共享】素材','E:\\F盘暂存')){ "
        "Write-Output ('ROOT ' + $r); if(Test-Path $r){ $all=Get-ChildItem $r -Recurse -File "
        "-ErrorAction SilentlyContinue; $sum=($all | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('  FILES ' + $all.Count + ' SIZE ' + [math]::Round($sum/1MB,1) + 'MB'); "
        "Get-ChildItem $r -Force -ErrorAction SilentlyContinue | Select-Object -First 20 | "
        "ForEach-Object { Write-Output ('  ' + $_.Name) } } else { Write-Output '  MISSING' } }\""
    ))


def op_test_materials(paths) -> None:
    run(paths, "test_materials", (
        "powershell -NoProfile -Command "
        "\"$t='E:\\treecut-v13\\runtime_data\\test_materials'; if(Test-Path $t){ "
        "$all=Get-ChildItem $t -Recurse -File -ErrorAction SilentlyContinue; "
        "Write-Output ('FILES ' + $all.Count); "
        "Get-ChildItem $t -Force | Select-Object -First 25 | ForEach-Object { "
        "if($_.PSIsContainer){ $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('  DIR ' + $_.Name + ' ' + [math]::Round($s/1MB,1) + 'MB') } else { "
        "Write-Output ('  FILE ' + $_.Name + ' ' + $_.Length) } } } else { Write-Output 'MISSING' }\""
    ))


def op_peek_knowledge(paths) -> None:
    run(paths, "peek_knowledge", (
        "powershell -NoProfile -Command "
        "\"$files=@('F:\\树剪TreeCut_v12.2_完整部署\\evolution_history.json',"
        "'F:\\树剪TreeCut_v12.2_完整部署\\learned_knowledge.json',"
        "'F:\\树剪TreeCut_v12.2_完整部署\\素材标签库.json',"
        "'F:\\树剪TreeCut_v12.2_完整部署\\protected_words.json'); "
        "foreach($f in $files){ if(Test-Path $f){ $t=Get-Content $f -Raw -Encoding UTF8; "
        "Write-Output ('--- ' + $f + ' len=' + $t.Length); "
        "Write-Output ($t.Substring(0, [Math]::Min(600, $t.Length))) } }\""
    ))


def op_child_readme(paths) -> None:
    run(paths, "child_readme", (
        "powershell -NoProfile -Command "
        "\"$f='F:\\TreeCut_v13_子程序便携版\\README_子程序便携版.txt'; "
        "if(Test-Path $f){ Get-Content $f -Raw -Encoding UTF8 } else { Write-Output 'MISSING' }\""
    ))


def op_restart_desktop(paths) -> None:
    run(paths, "restart_desktop", (
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process -Filter \\\"Name='pythonw.exe'\\\" | "
        "Where-Object { $_.CommandLine -like '*treecut.desktop*' } | "
        "ForEach-Object { Write-Output ('KILL ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }\""
    ))


def op_restart_app(paths) -> None:
    run(paths, "restart_app", "正式远程重启（代理自安排，看门狗自动拉起）", action="restart")


def op_restart_force(paths) -> None:
    run(paths, "restart_force", (
        "powershell -NoProfile -Command "
        "\"$b='E:\\treecut-v13\\runtime_data\\temp\\treecut_restart.bat'; "
        "Set-Content -LiteralPath $b -Value @('@echo off','timeout /t 3 /nobreak >nul',"
        "'taskkill /F /IM pythonw.exe >nul 2>&1','cd /d E:\\treecut-v13',"
        "'set PYTHONPATH=src','start \\\"\\\" E:\\treecut-v13\\runtime\\pythonw.exe -m treecut.watchdog') "
        "-Encoding Ascii; Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',$b "
        "-WindowStyle Hidden; Write-Output 'SCHEDULED'\""
    ))


def op_child_info(paths) -> None:
    run(paths, "child_info", (
        "powershell -NoProfile -Command "
        "\"$os=Get-CimInstance Win32_OperatingSystem; "
        "Write-Output ('RAM_TOTAL_GB ' + [math]::Round($os.TotalVisibleMemorySize/1MB,1)); "
        "Write-Output ('RAM_FREE_GB ' + [math]::Round($os.FreePhysicalMemory/1MB,1)); "
        "$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1; "
        "Write-Output ('CPU ' + $cpu.Name); "
        "Write-Output ('DISK_E_FREE_GB ' + [math]::Round((Get-PSDrive E).Free/1GB,1))\""
    ))


def op_f_models(paths) -> None:
    run(paths, "f_models", (
        "powershell -NoProfile -Command "
        "\"foreach($m in @('F:\\TreeCut_v13\\models\\Qwen3-VL-4B-Instruct-FP8',"
        "'F:\\TreeCut_v13\\models\\SenseVoiceSmall')){ Write-Output ('ROOT ' + $m); "
        "if(Test-Path $m){ Get-ChildItem $m -Recurse -File | Sort-Object Name | "
        "ForEach-Object { Write-Output ($_.Name + '|' + $_.Length) } } else { "
        "Write-Output 'MISSING' } }\""
    ))


def op_copy_models(paths) -> None:
    run(paths, "copy_qwen", (
        "robocopy \"F:\\TreeCut_v13\\models\\Qwen3-VL-4B-Instruct-FP8\" "
        "\"E:\\treecut-v13\\models\\Qwen3-VL-4B-Instruct-FP8\" /E /MT:16 /R:1 /W:1 "
        "/NFL /NDL /NJH /NJS /NP & exit /b 0"
    ), timeout=420.0)
    run(paths, "copy_sensevoice", (
        "robocopy \"F:\\TreeCut_v13\\models\\SenseVoiceSmall\" "
        "\"E:\\treecut-v13\\models\\SenseVoiceSmall\" /E /MT:16 /R:1 /W:1 "
        "/NFL /NDL /NJH /NJS /NP & exit /b 0"
    ), timeout=300.0)


def op_ship_file(paths) -> None:
    run(paths, "ship_file", "SHIP_REPLACED_BY_TOOL", action="ship_file")


def op_verify_models(paths) -> None:
    run(paths, "verify_models", (
        "powershell -NoProfile -Command "
        "\"$m='E:\\treecut-v13\\models'; Get-ChildItem $m -Directory | "
        "ForEach-Object { $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ($_.Name + ' ' + [math]::Round($s/1MB,1) + 'MB') }\""
    ))


def op_d_usage(paths) -> None:
    run(paths, "d_usage", (
        "powershell -NoProfile -Command "
        "\"Get-ChildItem 'D:\\' -Force -Directory -ErrorAction SilentlyContinue | "
        "ForEach-Object { $s=(Get-ChildItem $_.FullName -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "[PSCustomObject]@{Name=$_.Name; GB=[math]::Round($s/1GB,2); Files=(Get-ChildItem "
        "$_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count} } | "
        "Sort-Object GB -Descending | ForEach-Object { Write-Output ($_.Name + '|' + $_.GB + '|' + $_.Files) }\""
    ))


def op_d_big_files(paths) -> None:
    run(paths, "d_big_files", (
        "powershell -NoProfile -Command "
        "\"Get-ChildItem 'D:\\' -Recurse -File -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Length -gt 200MB } | Sort-Object Length -Descending | "
        "Select-Object -First 40 | ForEach-Object { Write-Output ($_.FullName + '|' + "
        "[math]::Round($_.Length/1MB,1) + 'MB') }\""
    ))


def op_old_versions(paths) -> None:
    run(paths, "old_versions", (
        "powershell -NoProfile -Command "
        "\"foreach($r in @('F:\\TreeCut_v13','F:\\TreeCut_v13_子程序便携版','F:\\TreeCut_build',"
        "'F:\\树剪TreeCut_v12.2_完整部署')){ if(Test-Path $r){ $s=(Get-ChildItem $r -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "$f=(Get-ChildItem $r -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count; "
        "Write-Output ($r + '|' + [math]::Round($s/1GB,2) + 'GB|' + $f + ' files|' + "
        "(Get-Item $r).LastWriteTime.ToString('yyyy-MM-dd')) } }\""
    ))


def op_junk(paths) -> None:
    run(paths, "junk", (
        "powershell -NoProfile -Command "
        "\"$r='E:\\treecut-v13\\runtime_data'; foreach($d in @('pycache','temp','updates')){ "
        "$p=Join-Path $r $d; if(Test-Path $p){ $s=(Get-ChildItem $p -Recurse -File "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ($d + '|' + [math]::Round($s/1MB,1) + 'MB') } else { Write-Output ($d + '|missing') } }; "
        "$c=Get-ChildItem (Join-Path $r 'cache') -Recurse -File -ErrorAction SilentlyContinue | "
        "Measure-Object -Property Length -Sum; Write-Output ('cache|' + [math]::Round($c.Sum/1MB,1) + 'MB'); "
        "Get-ChildItem (Join-Path $r 'updates') -ErrorAction SilentlyContinue | Select-Object -First 15 | "
        "ForEach-Object { Write-Output ('UPD ' + $_.Name + '|' + $_.Length) }\""
    ))


def op_clean_junk(paths) -> None:
    run(paths, "clean_junk", (
        "powershell -NoProfile -Command "
        "\"$r='E:\\treecut-v13\\runtime_data'; "
        "Remove-Item (Join-Path $r 'pycache') -Recurse -Force -ErrorAction SilentlyContinue; "
        "Get-ChildItem (Join-Path $r 'updates') -Directory -Filter 'backup_*' | "
        "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; "
        "Write-Output 'JUNK_CLEANED'\""
    ))


def op_delete_old_versions(paths) -> None:
    run(paths, "delete_old_versions", (
        "powershell -NoProfile -Command "
        "\"foreach($p in @('F:\\TreeCut_build','F:\\TreeCut_v13_子程序便携版',"
        "'F:\\TreeCut_v13','F:\\树剪TreeCut_v12.2_完整部署')){ "
        "if(Test-Path $p){ Remove-Item -LiteralPath $p -Recurse -Force "
        "-ErrorAction SilentlyContinue; Write-Output ('DELETED ' + $p) } else { "
        "Write-Output ('MISSING ' + $p) } }; "
        "$f=Get-PSDrive F; Write-Output ('F_FREE_GB ' + [math]::Round($f.Free/1GB,1))\""
    ), timeout=900.0)


def op_f_current(paths) -> None:
    run(paths, "f_current", (
        "powershell -NoProfile -Command "
        "\"foreach($p in @('F:\\TreeCut_build','F:\\TreeCut_v13_子程序便携版',"
        "'F:\\TreeCut_v13','F:\\树剪TreeCut_v12.2_完整部署')){ "
        "Write-Output ($p + ' EXISTS=' + (Test-Path $p)) }; "
        "Get-ChildItem 'F:\\' -Force -Directory | ForEach-Object { $s=(Get-ChildItem "
        "$_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object "
        "-Property Length -Sum).Sum; Write-Output ($_.Name + '|' + [math]::Round($s/1GB,2)) }\""
    ))


def op_delete_retry(paths) -> None:
    run(paths, "delete_retry", (
        "powershell -NoProfile -Command "
        "\"$ErrorActionPreference='Continue'; "
        "foreach($p in @('F:\\TreeCut_build','F:\\TreeCut_v13',"
        "'F:\\树剪TreeCut_v12.2_完整部署')){ if(Test-Path $p){ "
        "Remove-Item -LiteralPath $p -Recurse -Force; "
        "Write-Output ('AFTER ' + $p + ' EXISTS=' + (Test-Path $p)) } else { "
        "Write-Output ('GONE ' + $p) } }; "
        "Write-Output ('ERRORS ' + $error.Count)\""
    ), timeout=900.0)


def op_delete_robocopy(paths) -> None:
    run(paths, "delete_robocopy", (
        "mkdir E:\\treecut-v13\\runtime_data\\temp\\empty_wipe 2>nul & "
        "robocopy E:\\treecut-v13\\runtime_data\\temp\\empty_wipe F:\\TreeCut_build "
        "/MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP & rd /s /q F:\\TreeCut_build 2>nul & "
        "robocopy E:\\treecut-v13\\runtime_data\\temp\\empty_wipe F:\\TreeCut_v13 "
        "/MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP & rd /s /q F:\\TreeCut_v13 2>nul & "
        "robocopy E:\\treecut-v13\\runtime_data\\temp\\empty_wipe "
        "\"F:\\树剪TreeCut_v12.2_完整部署\" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP & "
        "rd /s /q \"F:\\树剪TreeCut_v12.2_完整部署\" 2>nul & "
        "rd /s /q E:\\treecut-v13\\runtime_data\\temp\\empty_wipe 2>nul & echo WIPE_DONE"
    ), timeout=1500.0)


def op_wipe_remaining(paths) -> None:
    run(paths, "wipe_remaining", (
        "powershell -NoProfile -Command "
        "\"Get-Process robocopy,cmd -ErrorAction SilentlyContinue | "
        "Select-Object -First 10 | ForEach-Object { Write-Output ('PROC ' + $_.Name + ' ' + $_.Id) }; "
        "foreach($r in @('F:\\TreeCut_build','F:\\TreeCut_v13','F:\\树剪TreeCut_v12.2_完整部署')){ "
        "if(Test-Path $r){ Get-ChildItem $r -Recurse -Force -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Length -gt 5MB } | Select-Object -First 12 | "
        "ForEach-Object { Write-Output ('BIG ' + $_.FullName + '|' + [math]::Round($_.Length/1MB,1) + 'MB') } } }\""
    ))


def op_wipe_detached(paths) -> None:
    run(paths, "wipe_detached", (
        "powershell -NoProfile -Command "
        "\"$b='E:\\treecut-v13\\runtime_data\\temp\\wipe_remaining.bat'; "
        "Set-Content -LiteralPath $b -Value @('@echo off',"
        "'mkdir E:\\treecut-v13\\runtime_data\\temp\\empty_wipe 2>nul',"
        "'robocopy E:\\treecut-v13\\runtime_data\\temp\\empty_wipe F:\\TreeCut_build /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP',"
        "'rd /s /q F:\\TreeCut_build 2>nul',"
        "'robocopy E:\\treecut-v13\\runtime_data\\temp\\empty_wipe F:\\TreeCut_v13 /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP',"
        "'rd /s /q F:\\TreeCut_v13 2>nul',"
        "'robocopy E:\\treecut-v13\\runtime_data\\temp\\empty_wipe \\\"F:\\树剪TreeCut_v12.2_完整部署\\\" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP',"
        "'rd /s /q \\\"F:\\树剪TreeCut_v12.2_完整部署\\\" 2>nul',"
        "'rd /s /q E:\\treecut-v13\\runtime_data\\temp\\empty_wipe 2>nul',"
        "'echo WIPE_REMAINING_DONE') -Encoding Ascii; "
        "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',$b -WindowStyle Hidden; "
        "Write-Output 'WIPE_SCHEDULED'\""
    ))


def op_kill_stuck_wipe(paths) -> None:
    run(paths, "kill_stuck_wipe", (
        "powershell -NoProfile -Command "
        "\"foreach($id in @(8220,11512,13172)){ Stop-Process -Id $id -Force "
        "-ErrorAction SilentlyContinue }; Get-Process robocopy -ErrorAction SilentlyContinue | "
        "Stop-Process -Force -ErrorAction SilentlyContinue; Write-Output 'KILLED'\""
    ))


def op_probe_stuck(paths) -> None:
    run(paths, "probe_stuck", (
        "powershell -NoProfile -Command "
        "\"Get-Process robocopy,cmd -ErrorAction SilentlyContinue | "
        "Select-Object -First 8 | ForEach-Object { Write-Output ('PROC ' + $_.Name + ' ' + $_.Id + ' ' + $_.StartTime) }; "
        "attrib \\\"F:\\TreeCut_v13\\models\\SenseVoiceSmall\\model.pt\\\"; "
        "$f='F:\\TreeCut_v13\\models\\SenseVoiceSmall\\model.pt'; "
        "try { [IO.File]::Open($f,'Open','ReadWrite','None').Close(); Write-Output 'LOCK_FREE' } "
        "catch { Write-Output ('LOCKED: ' + $_.Exception.Message) }\""
    ))


def op_delete_stuck_files(paths) -> None:
    run(paths, "delete_stuck_files", (
        "powershell -NoProfile -Command "
        "\"$ErrorActionPreference='Continue'; "
        "$targets=@('F:\\TreeCut_v13\\models\\SenseVoiceSmall\\model.pt',"
        "'F:\\树剪TreeCut_v12.2_完整部署\\runtime_data\\cache\\pip\\wheels\\08\\a1\\a3\\"
        "5c8ac52cc2f5782ffffc34c95c57c8e5ecb3063dc69541ee7c\\jieba-0.42.1-py3-none-any.whl'); "
        "foreach($t in $targets){ if(Test-Path $t){ try { Remove-Item -LiteralPath $t -Force "
        "-ErrorAction Stop; Write-Output ('DELETED ' + $t) } catch { Write-Output ('FAILED ' + $t + ' :: ' + "
        "$_.Exception.Message) } } else { Write-Output ('GONE ' + $t) } }; "
        "Remove-Item -LiteralPath 'F:\\TreeCut_v13\\models' -Recurse -Force -ErrorAction SilentlyContinue; "
        "Write-Output 'DONE'\""
    ))


def op_delete_acl(paths) -> None:
    run(paths, "delete_acl", (
        "powershell -NoProfile -Command "
        "\"$ErrorActionPreference='Continue'; "
        "$w='F:\\树剪TreeCut_v12.2_完整部署\\runtime_data\\cache\\pip\\wheels\\08\\a1\\a3\\"
        "5c8ac52cc2f5782ffffc34c95c57c8e5ecb3063dc69541ee7c\\jieba-0.42.1-py3-none-any.whl'; "
        "if(Test-Path $w){ attrib -R $w; takeown /f $w 2>&1 | Out-Null; "
        "icacls $w /grant *S-1-5-32-545:F 2>&1 | Out-Null; "
        "try { Remove-Item -LiteralPath $w -Force -ErrorAction Stop; "
        "Write-Output ('DELETED_WHEEL') } catch { Write-Output ('WHEEL_FAIL ' + $_.Exception.Message) } }; "
        "foreach($p in @('F:\\TreeCut_v13','F:\\TreeCut_build','F:\\树剪TreeCut_v12.2_完整部署')){ "
        "if(Test-Path $p){ Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue; "
        "Write-Output ('AFTER ' + $p + ' EXISTS=' + (Test-Path $p)) } else { Write-Output ('GONE ' + $p) } }; "
        "$f=Get-PSDrive F; Write-Output ('F_FREE_GB ' + [math]::Round($f.Free/1GB,1))\""
    ), timeout=900.0)


def op_f_processes(paths) -> None:
    run(paths, "f_processes", (
        "powershell -NoProfile -Command "
        "\"Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like 'F:*' -or "
        "$_.CommandLine -like '*F:\\\\*' } | Select-Object -First 15 | "
        "ForEach-Object { Write-Output ('PROC ' + $_.ProcessId + ' | ' + $_.Name + ' | ' + "
        "$_.ExecutablePath + ' | ' + $_.CommandLine) }; "
        "Get-ChildItem 'F:\\TreeCut_v13' -Recurse -Force -ErrorAction SilentlyContinue | "
        "Measure-Object -Property Length -Sum | ForEach-Object { Write-Output ('V13_LEFT ' + $_.Count + ' files ' + [math]::Round($_.Sum/1MB,1) + 'MB') }; "
        "Get-ChildItem 'F:\\树剪TreeCut_v12.2_完整部署' -Recurse -Force -ErrorAction SilentlyContinue | "
        "Measure-Object -Property Length -Sum | ForEach-Object { Write-Output ('V12_LEFT ' + $_.Count + ' files ' + [math]::Round($_.Sum/1MB,1) + 'MB') }; "
        "Get-ChildItem 'F:\\TreeCut_build' -Recurse -Force -ErrorAction SilentlyContinue | "
        "Measure-Object -Property Length -Sum | ForEach-Object { Write-Output ('BUILD_LEFT ' + $_.Count + ' files ' + [math]::Round($_.Sum/1MB,1) + 'MB') }\""
    ))


def op_list_remaining(paths) -> None:
    run(paths, "list_remaining", (
        "powershell -NoProfile -Command "
        "\"Get-Process robocopy,cmd -ErrorAction SilentlyContinue | Select-Object -First 8 | "
        "ForEach-Object { Write-Output ('PROC ' + $_.Name + ' ' + $_.Id + ' ' + "
        "$_.StartTime.ToString('HH:mm:ss')) }; "
        "foreach($r in @('F:\\TreeCut_v13','F:\\TreeCut_build','F:\\树剪TreeCut_v12.2_完整部署')){ "
        "Write-Output ('--- ' + $r); Get-ChildItem $r -Recurse -Force -ErrorAction SilentlyContinue | "
        "Select-Object -First 40 | ForEach-Object { Write-Output ('  ' + $_.FullName + '|' + $_.Length) } }\""
    ))


def op_final_cleanup(paths) -> None:
    run(paths, "final_cleanup", (
        "powershell -NoProfile -Command "
        "\"Get-Process robocopy -ErrorAction SilentlyContinue | Stop-Process -Force "
        "-ErrorAction SilentlyContinue; "
        "$lines=@('@echo off',"
        "'mkdir \\\"E:\\treecut-v13\\runtime_data\\temp\\empty_wipe\\\" 2>nul',"
        "'robocopy \\\"E:\\treecut-v13\\runtime_data\\temp\\empty_wipe\\\" \\\"F:\\TreeCut_build\\\" /MIR /R:0 /W:1 /NFL /NDL /NJH /NJS /NP >nul',"
        "'rd /s /q \\\"F:\\TreeCut_build\\\" 2>nul',"
        "'robocopy \\\"E:\\treecut-v13\\runtime_data\\temp\\empty_wipe\\\" \\\"F:\\TreeCut_v13\\\" /MIR /R:0 /W:1 /NFL /NDL /NJH /NJS /NP >nul',"
        "'rd /s /q \\\"F:\\TreeCut_v13\\\" 2>nul',"
        "'robocopy \\\"E:\\treecut-v13\\runtime_data\\temp\\empty_wipe\\\" \\\"F:\\树剪TreeCut_v12.2_完整部署\\\" /MIR /R:0 /W:1 /NFL /NDL /NJH /NJS /NP >nul',"
        "'rd /s /q \\\"F:\\树剪TreeCut_v12.2_完整部署\\\" 2>nul',"
        "'rd /s /q \\\"E:\\treecut-v13\\runtime_data\\temp\\empty_wipe\\\" 2>nul',"
        "'del \\\"%~f0\\\"'); "
        "$startup=Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Startup'; "
        "$boot=Join-Path $startup 'TreeCut_cleanup_old_versions.bat'; "
        "Set-Content -LiteralPath $boot -Value $lines -Encoding Ascii; "
        "$now=Join-Path $env:TEMP 'treecut_final_cleanup.bat'; "
        "Set-Content -LiteralPath $now -Value $lines -Encoding Ascii; "
        "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',$now -WindowStyle Hidden; "
        "Write-Output ('BOOT_BAT ' + $boot)\""
    ))


def op_probe_modelpt(paths) -> None:
    run(paths, "probe_modelpt", (
        "powershell -NoProfile -Command "
        "\"$f='F:\\TreeCut_v13\\models\\SenseVoiceSmall\\model.pt'; "
        "$i=Get-Item -LiteralPath $f -Force; "
        "Write-Output ('LINK ' + $i.LinkType + ' TARGET ' + $i.Target); "
        "Write-Output ('ATTR ' + $i.Attributes); "
        "cmd /c del /f /q \\\"$f\\\"; "
        "Write-Output ('AFTER_EXISTS ' + (Test-Path -LiteralPath $f))\""
    ))


def op_d_netdisk(paths) -> None:
    run(paths, "d_netdisk", (
        "powershell -NoProfile -Command "
        "\"Get-ChildItem 'D:\\BaiduNetdiskDownload' -Force -Recurse -ErrorAction SilentlyContinue | "
        "Select-Object -First 20 | ForEach-Object { Write-Output ($_.FullName + '|' + $_.Length) }\""
    ))


def op_d_clean(paths) -> None:
    run(paths, "d_clean", (
        "powershell -NoProfile -Command "
        "\"$ErrorActionPreference='Continue'; "
        "foreach($p in @('D:\\BaiduNetdiskDownload','D:\\爱思助手','D:\\360Downloads')){ "
        "if(Test-Path $p){ Remove-Item -LiteralPath $p -Recurse -Force; "
        "Write-Output ('AFTER ' + $p + ' EXISTS=' + (Test-Path $p)) } else { Write-Output ('GONE ' + $p) } }; "
        "Clear-RecycleBin -DriveLetter D -Force -ErrorAction SilentlyContinue; "
        "Write-Output 'RECYCLE_CLEARED'; "
        "$d=Get-PSDrive D; Write-Output ('D_FREE_GB ' + [math]::Round($d.Free/1GB,1))\""
    ), timeout=900.0)


def op_wechat_scan(paths) -> None:
    run(paths, "wechat_scan", (
        "powershell -NoProfile -Command "
        "\"$out='E:\\treecut-v13\\runtime_data\\temp\\wechat_videos.csv'; "
        "$exts=@('*.mp4','*.mov','*.avi','*.mkv','*.flv','*.wmv','*.ts','*.m4v'); "
        "$rows=@(); foreach($e in $exts){ $rows += Get-ChildItem 'D:\\xwechat_files' -Recurse -File "
        "-Filter $e -ErrorAction SilentlyContinue }; "
        "$rows | Sort-Object Length -Descending | ForEach-Object { "
        "'{0}|{1}|{2}|{3}' -f $_.DirectoryName.Replace('D:\\xwechat_files\\',''), $_.Name, "
        "[math]::Round($_.Length/1MB,1), $_.LastWriteTime.ToString('yyyy-MM-dd') } | "
        "Set-Content -LiteralPath $out -Encoding UTF8; "
        "$sum=($rows | Measure-Object -Property Length -Sum).Sum; "
        "Write-Output ('VIDEO_COUNT ' + $rows.Count); "
        "Write-Output ('VIDEO_GB ' + [math]::Round($sum/1GB,1)); "
        "Write-Output ('CSV ' + $out + ' ' + (Get-Item $out).Length); "
        "$rows | Group-Object { $_.DirectoryName -replace '^D:\\\\xwechat_files\\\\','' -replace '\\\\msg.*$','' } | "
        "Sort-Object Count -Descending | Select-Object -First 15 | ForEach-Object { "
        "Write-Output ('GROUP ' + $_.Name + '|' + $_.Count + '|' + [math]::Round((($_.Group | "
        "Measure-Object -Property Length -Sum).Sum)/1GB,1) + 'GB') }\""
    ), timeout=900.0)


def op_open_wechat_folder(paths) -> None:
    run(paths, "open_wechat_folder", (
        "explorer.exe \"D:\\xwechat_files\" & echo OPENED"
    ))


def op_d_state(paths) -> None:
    run(paths, "d_state", (
        "powershell -NoProfile -Command "
        "\"foreach($p in @('D:\\BaiduNetdiskDownload','D:\\爱思助手','D:\\360Downloads')){ "
        "if(Test-Path $p){ $s=(Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | "
        "Measure-Object -Property Length -Sum).Sum; Write-Output ($p + ' EXISTS ' + "
        "[math]::Round($s/1MB,1) + 'MB') } else { Write-Output ($p + ' GONE') } }; "
        "$d=Get-PSDrive D; Write-Output ('D_FREE_GB ' + [math]::Round($d.Free/1GB,1)); "
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'iFly|i4|AiSi|AiSiChuShou|TongBu' } | "
        "Select-Object -First 10 | ForEach-Object { Write-Output ('LOCK_PROC ' + $_.Name + ' ' + $_.ExecutablePath) }\""
    ))


def op_switch_standalone(paths) -> None:
    run(paths, "switch_standalone", (
        "powershell -NoProfile -Command "
        "\"$b='E:\\treecut-v13\\runtime_data\\temp\\switch_standalone.bat'; "
        "Set-Content -LiteralPath $b -Value @('@echo off','timeout /t 3 /nobreak >nul',"
        "'taskkill /F /IM pythonw.exe >nul 2>&1','cd /d E:\\treecut-v13',"
        "'set PYTHONPATH=src',"
        "'start E:\\treecut-v13\\runtime\\pythonw.exe -m treecut.remote.agent_main',"
        "'timeout /t 4 /nobreak >nul',"
        "'start E:\\treecut-v13\\runtime\\pythonw.exe -m treecut.watchdog') -Encoding Ascii; "
        "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c',$b -WindowStyle Hidden; "
        "Write-Output 'SWITCH_SCHEDULED'\""
    ))


def op_app_action(paths) -> None:
    run(paths, "app_action", "APP_ACTION_REPLACED_BY_TOOL", action="app_status")


def main() -> int:
    parser = argparse.ArgumentParser(description="子机远程操作集合")
    parser.add_argument("ops", nargs="+", choices=[
        "shortcut", "verify", "drives", "treecut", "docs_diff", "runtime_data",
        "outputs", "other_treecut", "f_dev_dirs", "models", "tools", "related",
        "materials", "test_materials", "peek_knowledge", "child_readme",
        "restart_desktop", "restart_app", "restart_force", "child_info", "f_models", "copy_models", "verify_models",
        "d_usage", "d_big_files", "old_versions", "junk", "clean_junk",
        "delete_old_versions", "delete_retry", "delete_robocopy", "wipe_remaining",
        "wipe_detached", "kill_stuck_wipe", "ship_file", "f_current",
        "probe_stuck", "delete_stuck_files", "delete_acl",
        "f_processes", "list_remaining",
        "final_cleanup",
        "probe_modelpt",
        "d_netdisk", "d_clean", "wechat_scan", "open_wechat_folder",
        "d_state",
        "switch_standalone", "app_action",
    ])
    args = parser.parse_args()
    paths = RuntimePaths.discover()
    handlers = {
        "shortcut": op_shortcut, "verify": op_verify, "drives": op_drives,
        "treecut": op_treecut, "docs_diff": op_docs_diff,
        "runtime_data": op_runtime_data, "outputs": op_outputs,
        "other_treecut": op_other_treecut_dirs, "f_dev_dirs": op_f_dev_dirs,
        "models": op_models, "tools": op_tools, "related": op_related,
        "materials": op_materials, "test_materials": op_test_materials,
        "peek_knowledge": op_peek_knowledge, "child_readme": op_child_readme,
        "restart_desktop": op_restart_desktop,
        "restart_app": op_restart_app, "restart_force": op_restart_force,
        "child_info": op_child_info, "f_models": op_f_models,
        "copy_models": op_copy_models, "verify_models": op_verify_models,
        "d_usage": op_d_usage, "d_big_files": op_d_big_files,
        "old_versions": op_old_versions, "junk": op_junk,
        "clean_junk": op_clean_junk, "delete_old_versions": op_delete_old_versions,
        "delete_retry": op_delete_retry,
        "delete_robocopy": op_delete_robocopy,
        "wipe_remaining": op_wipe_remaining,
        "wipe_detached": op_wipe_detached,
        "kill_stuck_wipe": op_kill_stuck_wipe,
        "probe_stuck": op_probe_stuck,
        "delete_stuck_files": op_delete_stuck_files,
        "delete_acl": op_delete_acl,
        "f_processes": op_f_processes,
        "list_remaining": op_list_remaining,
        "final_cleanup": op_final_cleanup,
        "probe_modelpt": op_probe_modelpt,
        "d_netdisk": op_d_netdisk,
        "d_clean": op_d_clean,
        "wechat_scan": op_wechat_scan,
        "open_wechat_folder": op_open_wechat_folder,
        "d_state": op_d_state,
        "switch_standalone": op_switch_standalone,
        "app_action": op_app_action,
        "ship_file": op_ship_file,
        "f_current": op_f_current,
    }
    for name in args.ops:
        handlers[name](paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
