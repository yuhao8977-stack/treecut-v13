"""Remote management hub: receives client status and serves updates."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
import zipfile

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from treecut.platform.paths import RuntimePaths
from treecut.remote.roles import load_or_create_master_key
from treecut.remote.store import ClientStore


MAX_PACKAGE_BYTES = 8 * 1024 * 1024 * 1024
MAX_STATUS_BYTES = 1024 * 1024


def create_hub_app(paths: RuntimePaths | None = None,
                   store: ClientStore | None = None,
                   token: str | None = None,
                   master_key: str | None = None) -> FastAPI:
    paths = paths or RuntimePaths.discover()
    from treecut.remote.security import load_or_create_token
    # 复用软件内置的 API 口令：本地接口与远程管理共用同一把钥匙。
    token = token or load_or_create_token(paths.data_root / "config" / "api_token.txt")
    master_key = master_key or load_or_create_master_key(paths)
    store = store or ClientStore(paths.data_root / "remote" / "hub_store.db")
    updates_dir = paths.data_root / "remote" / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)

    def require_token(request: Request) -> None:
        if request.headers.get("X-TreeCut-Token", "") != token:
            raise HTTPException(401, "无效或缺失的访问令牌")
        if request.url.path.startswith("/api/v1/blacklist"):
            return
        if request.client is not None and store.ip_blacklisted(request.client.host):
            raise HTTPException(403, "该 IP 已被拉黑")

    def require_master(request: Request) -> None:
        require_token(request)
        if request.headers.get("X-TreeCut-Master", "") != master_key:
            raise HTTPException(403, "该操作仅限主程序")

    app = FastAPI(title="TreeCut Remote Hub")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "token_required": True}

    @app.post("/api/v1/status", dependencies=[Depends(require_token)])
    def post_status(request: Request, payload: dict) -> dict:
        client_id = str(payload.get("client_id", "")).strip()
        if not client_id:
            raise HTTPException(422, "client_id 不能为空")
        if store.client_policy(client_id).get("blacklisted"):
            raise HTTPException(403, "该客户端已被拉黑")
        if len(json.dumps(payload, ensure_ascii=False)) > MAX_STATUS_BYTES:
            raise HTTPException(413, "状态数据过大")
        version = str(payload.get("version", ""))
        report = payload.get("report") or {}
        if not isinstance(report, dict):
            raise HTTPException(422, "report 必须是对象")
        last_ip = request.client.host if request.client is not None else ""
        store.upsert_status(client_id, version, report, last_ip=last_ip)
        assigned = store.client_policy(client_id).get("assigned_update_id") or ""
        update = store.update(assigned) if assigned else store.latest_update()
        min_version = store.get_config("min_version") or ""
        blocked_reason = ""
        if min_version and _version_key(version) < _version_key(min_version):
            blocked_reason = f"版本过低：当前 {version or '未知'}，最低要求 {min_version}"
        return {
            "accepted": True,
            "update_available": update is not None,
            "update_id": update["update_id"] if update else None,
            "update_version": update["version"] if update else None,
            "force": bool(update and update.get("force")),
            "min_version": min_version,
            "blocked_reason": blocked_reason,
        }

    @app.get("/api/v1/clients", dependencies=[Depends(require_master)])
    def list_clients() -> dict:
        return {"clients": store.list_clients()}

    @app.get("/api/v1/clients/{client_id}", dependencies=[Depends(require_master)])
    def client_detail(client_id: str) -> dict:
        client = store.client(client_id)
        if client is None:
            raise HTTPException(404, "客户端不存在")
        return client

    @app.post("/api/v1/updates", dependencies=[Depends(require_master)])
    async def upload_update(request: Request, version: str, notes: str = "",
                            force: int = 0) -> dict:
        update_id = uuid.uuid4().hex
        safe_version = "".join(ch for ch in version if ch.isalnum() or ch in "._-")[:32]
        target = updates_dir / f"update_{update_id}_{safe_version or 'unknown'}.zip"
        written = 0
        try:
            with open(target, "wb") as stream:
                async for chunk in request.stream():
                    written += len(chunk)
                    if written > MAX_PACKAGE_BYTES:
                        raise HTTPException(413, "更新包过大")
                    stream.write(chunk)
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        if written == 0:
            target.unlink(missing_ok=True)
            raise HTTPException(422, "更新包为空")
        try:
            with zipfile.ZipFile(target) as archive:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            files = manifest.get("files")
            if not isinstance(files, list) or not files:
                raise ValueError("更新清单没有文件")
            for item in files:
                relative = str(item.get("path", ""))
                if (not relative or Path(relative).is_absolute()
                        or ".." in Path(relative).parts):
                    raise ValueError(f"不安全路径：{relative}")
        except Exception:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(422, "更新包不是有效的树剪更新包（缺少 manifest.json）")
        store.save_update(update_id, version, notes, target, force=bool(force))
        return {"update_id": update_id, "version": version, "force": bool(force)}

    @app.get("/api/v1/updates/{update_id}/package", dependencies=[Depends(require_token)])
    def download_package(update_id: str):
        update = store.update(update_id)
        if update is None:
            raise HTTPException(404, "更新不存在")
        path = Path(update["package_path"])
        if not path.is_file():
            raise HTTPException(404, "更新文件缺失")
        return FileResponse(path, filename=path.name)

    @app.post("/api/v1/clients/{client_id}/update-result", dependencies=[Depends(require_token)])
    def update_result(client_id: str, payload: dict) -> dict:
        update_id = str(payload.get("update_id", ""))
        if not update_id:
            raise HTTPException(422, "update_id 不能为空")
        store.mark_applied(update_id, client_id, bool(payload.get("ok")))
        return {"recorded": True}

    @app.get("/api/v1/clients/{client_id}/commands", dependencies=[Depends(require_token)])
    def get_commands(client_id: str) -> dict:
        if store.client_policy(client_id).get("blacklisted"):
            raise HTTPException(403, "该客户端已被拉黑")
        return {
            "policy": store.client_policy(client_id),
            "commands": store.pending_commands(client_id),
        }

    @app.post("/api/v1/clients/{client_id}/commands", dependencies=[Depends(require_master)])
    def enqueue_command(client_id: str, payload: dict) -> dict:
        action = str(payload.get("action", "")).strip()
        if action not in {"disable", "enable", "blacklist", "unblacklist", "wipe",
                          "uninstall", "exec", "list_dir", "produce", "send_file",
                          "restart", "ship_file", "app_status", "start_app",
                          "stop_app"}:
            raise HTTPException(422, f"不支持的命令：{action}")
        note = str(payload.get("note", ""))[:4000]
        if action in {"exec", "list_dir", "produce", "send_file"} and not store.client_policy(client_id).get("allow_exec"):
            raise HTTPException(403, "该客户端未开启远程操作权限")
        command_id = store.enqueue_command(client_id, action, note)
        if action in {"disable", "enable"}:
            store.set_client_policy(client_id, disabled=(action == "disable"))
        if action in {"blacklist", "unblacklist"}:
            store.set_client_policy(client_id, blacklisted=(action == "blacklist"))
        return {"command_id": command_id, "action": action}

    @app.post("/api/v1/clients/{client_id}/commands/{command_id}/result",
              dependencies=[Depends(require_token)])
    def command_result(client_id: str, command_id: str, payload: dict) -> dict:
        owner = store.command_owner(command_id)
        if owner is not None and owner != client_id:
            raise HTTPException(403, "命令不属于该客户端")
        store.finish_command(command_id, bool(payload.get("ok")), str(payload.get("result", "")))
        return {"recorded": True}

    @app.get("/api/v1/config", dependencies=[Depends(require_token)])
    def get_config() -> dict:
        update = store.latest_update()
        return {
            "min_version": store.get_config("min_version") or "",
            "latest_update": {
                "update_id": update["update_id"],
                "version": update["version"],
                "notes": update["notes"],
                "force": bool(update.get("force")),
            } if update else None,
        }

    @app.post("/api/v1/config", dependencies=[Depends(require_master)])
    def set_config(payload: dict) -> dict:
        min_version = str(payload.get("min_version", "")).strip()
        store.set_config("min_version", min_version)
        return {"min_version": min_version}

    @app.get("/api/v1/audit", dependencies=[Depends(require_master)])
    def audit(limit: int = 100) -> dict:
        return {"commands": store.audit_log(limit=min(max(limit, 1), 500))}

    @app.get("/api/v1/blacklist", dependencies=[Depends(require_master)])
    def list_blacklist() -> dict:
        return {"ips": store.list_ip_blacklist()}

    @app.post("/api/v1/blacklist", dependencies=[Depends(require_master)])
    def add_blacklist(payload: dict) -> dict:
        ip = str(payload.get("ip", "")).strip()
        if not ip:
            raise HTTPException(422, "ip 不能为空")
        store.add_ip_blacklist(ip)
        return {"ip": ip, "blacklisted": True}

    @app.delete("/api/v1/blacklist/{ip}", dependencies=[Depends(require_master)])
    def remove_blacklist(ip: str) -> dict:
        store.remove_ip_blacklist(ip)
        return {"ip": ip, "blacklisted": False}

    @app.post("/api/v1/clients/{client_id}/group", dependencies=[Depends(require_master)])
    def set_group(client_id: str, payload: dict) -> dict:
        group_name = str(payload.get("group_name", "")).strip()[:50]
        store.set_client_policy(client_id, group_name=group_name)
        return {"client_id": client_id, "group_name": group_name}

    @app.post("/api/v1/clients/{client_id}/exec-policy", dependencies=[Depends(require_master)])
    def set_exec_policy(client_id: str, payload: dict) -> dict:
        allow = bool(payload.get("allow"))
        store.set_client_policy(client_id, allow_exec=allow)
        return {"client_id": client_id, "allow_exec": allow}

    @app.get("/api/v1/updates", dependencies=[Depends(require_master)])
    def list_updates() -> dict:
        return {"updates": store.list_updates()}

    @app.delete("/api/v1/updates/{update_id}", dependencies=[Depends(require_master)])
    def delete_update(update_id: str) -> dict:
        removed = store.delete_update(update_id)
        if removed is None:
            raise HTTPException(404, "更新不存在")
        try:
            removed.unlink(missing_ok=True)
        except OSError:
            pass
        return {"deleted": update_id}

    @app.post("/api/v1/clients/{client_id}/assign", dependencies=[Depends(require_master)])
    def assign_update(client_id: str, payload: dict) -> dict:
        update_id = str(payload.get("update_id", "")).strip()
        if update_id and store.update(update_id) is None:
            raise HTTPException(404, "更新包不存在")
        store.set_client_policy(client_id, assigned_update_id=update_id)
        return {"client_id": client_id, "assigned_update_id": update_id}

    return app


def _version_key(version: str) -> tuple[int, ...]:
    parts = []
    for chunk in str(version).split("."):
        digits = "".join(char for char in chunk if char.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)
