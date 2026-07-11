from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS providers (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  base_url TEXT,
  default_model TEXT,
  extra_json TEXT DEFAULT '{}',
  sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chats (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  project_path TEXT,
  provider_id TEXT,
  model TEXT,
  skill_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  chat_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  meta_json TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings_kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

DEFAULT_PROVIDERS = [
    ("ollama", "ollama", "Ollama", 1, "http://127.0.0.1:11434", "", 0),
    ("openai", "openai", "OpenAI", 0, "https://api.openai.com/v1", "gpt-4o-mini", 1),
    ("anthropic", "anthropic", "Anthropic (Claude)", 0, "https://api.anthropic.com", "claude-sonnet-4-20250514", 2),
    ("deepseek", "openai_compatible", "DeepSeek", 0, "https://api.deepseek.com/v1", "deepseek-chat", 3),
    ("qwen", "openai_compatible", "Qwen", 0, "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-plus", 4),
    ("glm", "openai_compatible", "GLM", 0, "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", 5),
]


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        await self._seed_providers()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if not self._conn:
            raise RuntimeError("Database not connected")
        return self._conn

    async def _seed_providers(self) -> None:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM providers")
        row = await cur.fetchone()
        if row and row["c"] > 0:
            return
        await self.conn.executemany(
            "INSERT INTO providers (id, kind, name, enabled, base_url, default_model, sort_order) VALUES (?,?,?,?,?,?,?)",
            DEFAULT_PROVIDERS,
        )
        await self.conn.commit()

    async def list_providers(self) -> list[dict[str, Any]]:
        cur = await self.conn.execute("SELECT * FROM providers ORDER BY sort_order, id")
        rows = await cur.fetchall()
        return [self._provider_row(r) for r in rows]

    async def get_provider(self, provider_id: str) -> dict[str, Any] | None:
        cur = await self.conn.execute("SELECT * FROM providers WHERE id=?", (provider_id,))
        row = await cur.fetchone()
        return self._provider_row(row) if row else None

    async def upsert_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        existing = await self.get_provider(data["id"])
        extra = data.get("extra") or {}
        if existing:
            await self.conn.execute(
                """UPDATE providers SET kind=?, name=?, enabled=?, base_url=?, default_model=?,
                   extra_json=?, sort_order=? WHERE id=?""",
                (
                    data.get("kind", existing["kind"]),
                    data.get("name", existing["name"]),
                    1 if data.get("enabled", existing["enabled"]) else 0,
                    data.get("base_url", existing["base_url"]),
                    data.get("default_model", existing["default_model"]),
                    json.dumps(extra if extra else existing.get("extra") or {}),
                    data.get("sort_order", existing["sort_order"]),
                    data["id"],
                ),
            )
        else:
            await self.conn.execute(
                """INSERT INTO providers (id, kind, name, enabled, base_url, default_model, extra_json, sort_order)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    data["id"],
                    data.get("kind", "openai_compatible"),
                    data.get("name", data["id"]),
                    1 if data.get("enabled", True) else 0,
                    data.get("base_url"),
                    data.get("default_model"),
                    json.dumps(extra),
                    data.get("sort_order", 99),
                ),
            )
        await self.conn.commit()
        result = await self.get_provider(data["id"])
        assert result
        return result

    async def get_setting(self, key: str, default: str = "") -> str:
        cur = await self.conn.execute("SELECT value FROM settings_kv WHERE key=?", (key,))
        row = await cur.fetchone()
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            "INSERT INTO settings_kv(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await self.conn.commit()

    async def list_chats(self) -> list[dict[str, Any]]:
        cur = await self.conn.execute("SELECT * FROM chats ORDER BY updated_at DESC")
        return [dict(r) for r in await cur.fetchall()]

    async def create_chat(self, chat: dict[str, Any]) -> dict[str, Any]:
        await self.conn.execute(
            """INSERT INTO chats (id, title, project_path, provider_id, model, skill_id, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                chat["id"],
                chat["title"],
                chat.get("project_path"),
                chat.get("provider_id"),
                chat.get("model"),
                chat.get("skill_id"),
                chat["created_at"],
                chat["updated_at"],
            ),
        )
        await self.conn.commit()
        return chat

    async def add_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        await self.conn.execute(
            """INSERT INTO messages (id, chat_id, role, content, meta_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                msg["id"],
                msg["chat_id"],
                msg["role"],
                msg["content"],
                json.dumps(msg.get("meta") or {}),
                msg["created_at"],
            ),
        )
        await self.conn.execute(
            "UPDATE chats SET updated_at=? WHERE id=?",
            (msg["created_at"], msg["chat_id"]),
        )
        await self.conn.commit()
        return msg

    async def list_messages(self, chat_id: str) -> list[dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at",
            (chat_id,),
        )
        out = []
        for r in await cur.fetchall():
            d = dict(r)
            d["meta"] = json.loads(d.pop("meta_json") or "{}")
            out.append(d)
        return out

    @staticmethod
    def _provider_row(row: aiosqlite.Row) -> dict[str, Any]:
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        d["extra"] = json.loads(d.pop("extra_json") or "{}")
        d["has_api_key"] = False  # filled by API layer
        return d
