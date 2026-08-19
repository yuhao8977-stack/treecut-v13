"""SQLite store for remote client status and pending updates."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


REDELIVER_AFTER_SECONDS = 600  # 已投递但长时间无回执的命令重新投递


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    last_seen REAL NOT NULL,
    status_json TEXT NOT NULL,
    applied_version TEXT NOT NULL DEFAULT '',
    disabled INTEGER NOT NULL DEFAULT 0,
    blacklisted INTEGER NOT NULL DEFAULT 0,
    group_name TEXT NOT NULL DEFAULT '',
    last_ip TEXT NOT NULL DEFAULT '',
    assigned_update_id TEXT NOT NULL DEFAULT '',
    allow_exec INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS updates (
    update_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    package_path TEXT NOT NULL,
    applied_by TEXT NOT NULL DEFAULT '',
    force INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS commands (
    command_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL,
    delivered_at REAL,
    result TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS hub_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ip_blacklist (
    ip TEXT PRIMARY KEY
);
"""


class ClientStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.executescript(SCHEMA)
                self._migrate(connection)
        except sqlite3.DatabaseError:
            # 数据库损坏时保留现场（改名备份）并重建，避免管理端整体不可用。
            corrupt = path.with_name(
                f"{path.stem}.corrupt_{time.strftime('%Y%m%d_%H%M%S')}",
            )
            try:
                path.replace(corrupt)
            except OSError:
                path.unlink(missing_ok=True)
            with self._connect() as connection:
                connection.executescript(SCHEMA)
                self._migrate(connection)

    @staticmethod
    def _migrate(connection) -> None:
        """Add columns introduced after the first release of the store."""
        client_columns = {row[1] for row in connection.execute("PRAGMA table_info(clients)")}
        additions = {
            "disabled": "ALTER TABLE clients ADD COLUMN disabled INTEGER NOT NULL DEFAULT 0",
            "blacklisted": "ALTER TABLE clients ADD COLUMN blacklisted INTEGER NOT NULL DEFAULT 0",
            "group_name": "ALTER TABLE clients ADD COLUMN group_name TEXT NOT NULL DEFAULT ''",
        }
        for column, statement in additions.items():
            if column not in client_columns:
                connection.execute(statement)
        if "last_ip" not in client_columns:
            connection.execute("ALTER TABLE clients ADD COLUMN last_ip TEXT NOT NULL DEFAULT ''")
        if "assigned_update_id" not in client_columns:
            connection.execute("ALTER TABLE clients ADD COLUMN assigned_update_id TEXT NOT NULL DEFAULT ''")
        if "allow_exec" not in client_columns:
            connection.execute("ALTER TABLE clients ADD COLUMN allow_exec INTEGER NOT NULL DEFAULT 0")
        update_columns = {row[1] for row in connection.execute("PRAGMA table_info(updates)")}
        if "force" not in update_columns:
            connection.execute("ALTER TABLE updates ADD COLUMN force INTEGER NOT NULL DEFAULT 0")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def upsert_status(self, client_id: str, version: str, status: dict,
                      last_ip: str = "") -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO clients(client_id, version, last_seen, status_json, last_ip) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(client_id) DO UPDATE SET version=excluded.version,"
                "last_seen=excluded.last_seen,status_json=excluded.status_json,"
                "last_ip=excluded.last_ip",
                (client_id, version, time.time(), json.dumps(status, ensure_ascii=False), last_ip),
            )

    def list_clients(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT client_id,version,last_seen,status_json,applied_version,"
                "disabled,blacklisted,group_name,last_ip,assigned_update_id,allow_exec "
                "FROM clients ORDER BY last_seen DESC"
            ).fetchall()
        return [self._row(row) for row in rows]

    def client(self, client_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT client_id,version,last_seen,status_json,applied_version,"
                "disabled,blacklisted,group_name,last_ip,assigned_update_id,allow_exec "
                "FROM clients WHERE client_id=?", (client_id,),
            ).fetchone()
        return self._row(row) if row is not None else None

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        data = dict(row)
        try:
            data["status"] = json.loads(data.pop("status_json"))
        except Exception:
            data["status"] = {}
        return data

    def save_update(self, update_id: str, version: str, notes: str, package_path: Path,
                    force: bool = False) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO updates(update_id,version,notes,created_at,package_path,force) "
                "VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(update_id) DO UPDATE SET version=excluded.version,"
                "notes=excluded.notes,package_path=excluded.package_path,"
                "created_at=excluded.created_at,force=excluded.force",
                (update_id, version, notes, time.time(), str(package_path), 1 if force else 0),
            )

    def latest_update(self) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT update_id,version,notes,created_at,package_path,applied_by,force "
                "FROM updates ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row is not None else None

    def update(self, update_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT update_id,version,notes,created_at,package_path,applied_by,force "
                "FROM updates WHERE update_id=?", (update_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def mark_applied(self, update_id: str, client_id: str, ok: bool) -> None:
        marker = f"{client_id}:{'ok' if ok else 'fail'}"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT version FROM updates WHERE update_id=?", (update_id,),
            ).fetchone()
            connection.execute(
                "UPDATE updates SET applied_by="
                "CASE WHEN applied_by='' THEN ? ELSE applied_by || ',' || ? END "
                "WHERE update_id=?", (marker, marker, update_id),
            )
            if row is not None and ok:
                connection.execute(
                    "UPDATE clients SET applied_version=? WHERE client_id=?", (row["version"], client_id),
                )

    def set_client_policy(self, client_id: str, *, disabled: bool | None = None,
                          blacklisted: bool | None = None, group_name: str | None = None,
                          assigned_update_id: str | None = None,
                          allow_exec: bool | None = None) -> None:
        assignments: list[str] = []
        params: list[object] = []
        if disabled is not None:
            assignments.append("disabled=?")
            params.append(1 if disabled else 0)
        if blacklisted is not None:
            assignments.append("blacklisted=?")
            params.append(1 if blacklisted else 0)
        if group_name is not None:
            assignments.append("group_name=?")
            params.append(group_name)
        if assigned_update_id is not None:
            assignments.append("assigned_update_id=?")
            params.append(assigned_update_id)
        if allow_exec is not None:
            assignments.append("allow_exec=?")
            params.append(1 if allow_exec else 0)
        if not assignments:
            return
        params.append(client_id)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO clients(client_id,version,last_seen,status_json,last_ip) "
                "VALUES(?,?,?,?,?) ON CONFLICT(client_id) DO NOTHING",
                (client_id, "", 0.0, "{}", ""),
            )
            connection.execute(
                f"UPDATE clients SET {', '.join(assignments)} WHERE client_id=?",
                tuple(params),
            )

    def client_policy(self, client_id: str) -> dict:
        client = self.client(client_id)
        if client is None:
            return {"disabled": False, "blacklisted": False, "group_name": ""}
        return {
            "disabled": bool(client.get("disabled")),
            "blacklisted": bool(client.get("blacklisted")),
            "group_name": client.get("group_name", ""),
            "assigned_update_id": client.get("assigned_update_id", ""),
            "allow_exec": bool(client.get("allow_exec")),
        }

    def enqueue_command(self, client_id: str, action: str, note: str = "") -> str:
        command_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO commands(command_id,client_id,action,status,created_at,note) "
                "VALUES(?,?,?,'pending',?,?)",
                (command_id, client_id, action, time.time(), note),
            )
        return command_id

    def pending_commands(self, client_id: str) -> list[dict]:
        with self._connect() as connection:
            # 客户端取走命令后若崩溃，命令会卡在“已投递”：
            # 超时后重新变为待投递，保证命令最终被执行或明确失败。
            connection.execute(
                "UPDATE commands SET status='pending',delivered_at=NULL "
                "WHERE client_id=? AND status='delivered' "
                "AND delivered_at IS NOT NULL AND delivered_at < ?",
                (client_id, time.time() - REDELIVER_AFTER_SECONDS),
            )
            rows = connection.execute(
                "SELECT command_id,client_id,action,status,created_at,note "
                "FROM commands WHERE client_id=? AND status='pending' ORDER BY created_at",
                (client_id,),
            ).fetchall()
            delivered_ids = [row["command_id"] for row in rows]
            if delivered_ids:
                placeholders = ",".join("?" * len(delivered_ids))
                connection.execute(
                    f"UPDATE commands SET status='delivered',delivered_at=? "
                    f"WHERE command_id IN ({placeholders})",
                    (time.time(), *delivered_ids),
                )
        return [dict(row) for row in rows]

    def command_owner(self, command_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT client_id FROM commands WHERE command_id=?", (command_id,),
            ).fetchone()
        return row["client_id"] if row is not None else None

    def finish_command(self, command_id: str, ok: bool, result: str = "") -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE commands SET status=?,result=? WHERE command_id=?",
                ("done" if ok else "failed", result[:2_000_000], command_id),
            )

    def set_config(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO hub_config(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_config(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM hub_config WHERE key=?", (key,),
            ).fetchone()
        return row["value"] if row is not None else None

    def add_ip_blacklist(self, ip: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT OR IGNORE INTO ip_blacklist(ip) VALUES(?)", (ip,))

    def remove_ip_blacklist(self, ip: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM ip_blacklist WHERE ip=?", (ip,))

    def ip_blacklisted(self, ip: str) -> bool:
        with self._connect() as connection:
            return connection.execute(
                "SELECT 1 FROM ip_blacklist WHERE ip=?", (ip,),
            ).fetchone() is not None

    def list_ip_blacklist(self) -> list[str]:
        with self._connect() as connection:
            return [row["ip"] for row in
                    connection.execute("SELECT ip FROM ip_blacklist ORDER BY ip")]

    def audit_log(self, limit: int = 100) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT command_id,client_id,action,status,created_at,delivered_at,result,note "
                "FROM commands ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_updates(self) -> list[dict]:
        with self._connect() as connection:
              rows = connection.execute(
                  "SELECT update_id,version,notes,created_at,package_path,applied_by,force "
                  "FROM updates ORDER BY created_at DESC, rowid DESC"
              ).fetchall()
        return [dict(row) for row in rows]

    def delete_update(self, update_id: str) -> Path | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT package_path FROM updates WHERE update_id=?", (update_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM updates WHERE update_id=?", (update_id,))
            connection.execute(
                "UPDATE clients SET assigned_update_id='' WHERE assigned_update_id=?", (update_id,),
            )
        return Path(row["package_path"])
