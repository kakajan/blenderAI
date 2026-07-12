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
  scope_key TEXT DEFAULT '',
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

CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,
  source TEXT NOT NULL,
  component TEXT DEFAULT '',
  message TEXT NOT NULL,
  detail_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  source TEXT NOT NULL,
  summary TEXT NOT NULL,
  detail_json TEXT DEFAULT '{}',
  file_path TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(ts DESC);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_reports_ts ON reports(ts DESC);

CREATE TABLE IF NOT EXISTS tool_runs (
  id TEXT PRIMARY KEY,
  chat_id TEXT,
  skill_id TEXT,
  tool TEXT NOT NULL,
  args_json TEXT DEFAULT '{}',
  ok INTEGER NOT NULL DEFAULT 0,
  result_json TEXT DEFAULT '{}',
  user_goal TEXT DEFAULT '',
  step INTEGER DEFAULT 0,
  scope_key TEXT DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_learnings (
  id TEXT PRIMARY KEY,
  chat_id TEXT,
  skill_id TEXT,
  rating TEXT NOT NULL,
  note TEXT DEFAULT '',
  user_goal TEXT DEFAULT '',
  tool_recipes_json TEXT DEFAULT '[]',
  scope_key TEXT DEFAULT '',
  source TEXT DEFAULT '',
  confidence REAL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_runs_chat ON tool_runs(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_runs_skill ON tool_runs(skill_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learnings_skill ON session_learnings(skill_id, rating, created_at DESC);
"""

DEFAULT_PROVIDERS = [
    ("cursor", "cursor", "Cursor Agent (MCP)", 1, "", "cursor-agent", -1),
    ("ollama", "ollama", "Ollama", 1, "http://127.0.0.1:11434", "", 0),
    ("openai", "openai", "OpenAI", 0, "https://api.openai.com/v1", "gpt-4o-mini", 1),
    ("anthropic", "anthropic", "Anthropic (Claude)", 0, "https://api.anthropic.com", "claude-sonnet-4-20250514", 2),
    ("deepseek", "openai_compatible", "DeepSeek", 0, "https://api.deepseek.com/v1", "deepseek-chat", 3),
    ("qwen", "openai_compatible", "Qwen", 0, "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen-plus", 4),
    ("glm", "openai_compatible", "GLM", 0, "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", 5),
    # OpenCode Zen gateway — chat/completions models (e.g. big-pickle, glm-5, kimi-k2.5).
    # GPT/Claude Zen routes use /responses or /messages; pick a chat-completions model in UI.
    ("opencode", "openai_compatible", "OpenCode Zen", 0, "https://opencode.ai/zen/v1", "big-pickle", 6),
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
        await self._migrate(self._conn)
        await self._seed_providers()

    @staticmethod
    async def _migrate(conn: aiosqlite.Connection) -> None:
        """Additive column migrations for existing DBs (PRAGMA table_info + ALTER)."""

        async def columns(table: str) -> set[str]:
            cur = await conn.execute(f"PRAGMA table_info({table})")
            rows = await cur.fetchall()
            return {str(r[1]) for r in rows}

        async def add_column(table: str, name: str, decl: str) -> None:
            existing = await columns(table)
            if name in existing:
                return
            try:
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
            except Exception:
                # Column may already exist under race / older SQLite quirks.
                pass

        await add_column("session_learnings", "scope_key", "TEXT DEFAULT ''")
        await add_column("session_learnings", "source", "TEXT DEFAULT ''")
        await add_column("session_learnings", "confidence", "REAL DEFAULT 0")
        await add_column("tool_runs", "scope_key", "TEXT DEFAULT ''")
        await add_column("chats", "scope_key", "TEXT DEFAULT ''")
        await conn.commit()

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
        # INSERT OR IGNORE so upgrades pick up newly shipped defaults without
        # overwriting user edits to existing provider rows.
        await self.conn.executemany(
            "INSERT OR IGNORE INTO providers (id, kind, name, enabled, base_url, default_model, sort_order) VALUES (?,?,?,?,?,?,?)",
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

    async def clear_chats(self) -> int:
        """Delete all chats and messages. Returns number of chats removed."""
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM chats")
        row = await cur.fetchone()
        count = int(row["c"]) if row else 0
        # FK cascade may be off; delete messages first.
        await self.conn.execute("DELETE FROM messages")
        await self.conn.execute("DELETE FROM chats")
        await self.conn.commit()
        return count

    async def insert_log(self, entry: dict[str, Any]) -> dict[str, Any]:
        await self.conn.execute(
            """INSERT INTO logs (id, ts, level, source, component, message, detail_json)
               VALUES (?,?,?,?,?,?,?)""",
            (
                entry["id"],
                entry["ts"],
                entry["level"],
                entry["source"],
                entry.get("component") or "",
                entry["message"],
                json.dumps(entry.get("detail") or {}),
            ),
        )
        await self.conn.commit()
        # Keep last 2000 rows
        await self.conn.execute(
            """DELETE FROM logs WHERE id NOT IN (
                 SELECT id FROM logs ORDER BY ts DESC LIMIT 2000
               )"""
        )
        await self.conn.commit()
        return entry

    async def list_logs(
        self,
        *,
        level: str | None = None,
        source: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if level:
            levels = [x.strip().lower() for x in level.split(",") if x.strip()]
            if levels:
                placeholders = ",".join("?" for _ in levels)
                clauses.append(f"lower(level) IN ({placeholders})")
                params.extend(levels)
        if source:
            clauses.append("source=?")
            params.append(source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur = await self.conn.execute(
            f"SELECT * FROM logs {where} ORDER BY ts DESC LIMIT ?",
            (*params, max(1, min(limit, 1000))),
        )
        out = []
        for r in await cur.fetchall():
            d = dict(r)
            d["detail"] = json.loads(d.pop("detail_json") or "{}")
            out.append(d)
        return out

    async def clear_logs(self) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) AS c FROM logs")
        row = await cur.fetchone()
        count = int(row["c"]) if row else 0
        await self.conn.execute("DELETE FROM logs")
        await self.conn.commit()
        return count

    async def insert_report(self, entry: dict[str, Any]) -> dict[str, Any]:
        await self.conn.execute(
            """INSERT INTO reports (id, ts, kind, source, summary, detail_json, file_path)
               VALUES (?,?,?,?,?,?,?)""",
            (
                entry["id"],
                entry["ts"],
                entry["kind"],
                entry["source"],
                entry["summary"],
                json.dumps(entry.get("detail") or {}),
                entry.get("file_path") or "",
            ),
        )
        await self.conn.commit()
        return entry

    async def list_reports(self, *, limit: int = 50) -> list[dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT * FROM reports ORDER BY ts DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        )
        out = []
        for r in await cur.fetchall():
            d = dict(r)
            d["detail"] = json.loads(d.pop("detail_json") or "{}")
            out.append(d)
        return out

    async def get_report(self, report_id: str) -> dict[str, Any] | None:
        cur = await self.conn.execute("SELECT * FROM reports WHERE id=?", (report_id,))
        row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["detail"] = json.loads(d.pop("detail_json") or "{}")
        return d

    async def insert_tool_run(self, entry: dict[str, Any]) -> dict[str, Any]:
        await self.conn.execute(
            """INSERT INTO tool_runs
               (id, chat_id, skill_id, tool, args_json, ok, result_json, user_goal, step, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                entry["id"],
                entry.get("chat_id"),
                entry.get("skill_id"),
                entry["tool"],
                entry.get("args_json") or "{}",
                int(entry.get("ok") or 0),
                entry.get("result_json") or "{}",
                entry.get("user_goal") or "",
                int(entry.get("step") or 0),
                entry["created_at"],
            ),
        )
        await self.conn.commit()
        await self.conn.execute(
            """DELETE FROM tool_runs WHERE id NOT IN (
                 SELECT id FROM tool_runs ORDER BY created_at DESC LIMIT 5000
               )"""
        )
        await self.conn.commit()
        return entry

    async def list_tool_runs(
        self,
        *,
        chat_id: str | None = None,
        skill_id: str | None = None,
        ok_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if chat_id:
            clauses.append("chat_id=?")
            params.append(chat_id)
        if skill_id:
            clauses.append("skill_id=?")
            params.append(skill_id)
        if ok_only:
            clauses.append("ok=1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur = await self.conn.execute(
            f"SELECT * FROM tool_runs {where} ORDER BY created_at DESC LIMIT ?",
            (*params, max(1, min(limit, 500))),
        )
        out = []
        for r in await cur.fetchall():
            d = dict(r)
            d["ok"] = bool(d["ok"])
            d["args"] = json.loads(d.pop("args_json") or "{}")
            d["result"] = json.loads(d.pop("result_json") or "{}")
            out.append(d)
        return out

    async def insert_learning(self, entry: dict[str, Any]) -> dict[str, Any]:
        await self.conn.execute(
            """INSERT INTO session_learnings
               (id, chat_id, skill_id, rating, note, user_goal, tool_recipes_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                entry["id"],
                entry.get("chat_id"),
                entry.get("skill_id"),
                entry["rating"],
                entry.get("note") or "",
                entry.get("user_goal") or "",
                entry.get("tool_recipes_json") or "[]",
                entry["created_at"],
            ),
        )
        await self.conn.commit()
        await self.conn.execute(
            """DELETE FROM session_learnings WHERE id NOT IN (
                 SELECT id FROM session_learnings ORDER BY created_at DESC LIMIT 1000
               )"""
        )
        await self.conn.commit()
        return entry

    async def list_learnings(
        self,
        *,
        skill_id: str | None = None,
        rating: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if skill_id:
            clauses.append("skill_id=?")
            params.append(skill_id)
        if rating:
            clauses.append("rating=?")
            params.append(rating)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur = await self.conn.execute(
            f"SELECT * FROM session_learnings {where} ORDER BY created_at DESC LIMIT ?",
            (*params, max(1, min(limit, 200))),
        )
        return [dict(r) for r in await cur.fetchall()]

    async def clear_learnings(self, *, skill_id: str | None = None) -> int:
        if skill_id:
            cur = await self.conn.execute(
                "SELECT COUNT(*) AS c FROM session_learnings WHERE skill_id=?",
                (skill_id,),
            )
            row = await cur.fetchone()
            count = int(row["c"]) if row else 0
            await self.conn.execute("DELETE FROM session_learnings WHERE skill_id=?", (skill_id,))
        else:
            cur = await self.conn.execute("SELECT COUNT(*) AS c FROM session_learnings")
            row = await cur.fetchone()
            count = int(row["c"]) if row else 0
            await self.conn.execute("DELETE FROM session_learnings")
        await self.conn.commit()
        return count

    async def delete_learning(self, learning_id: str) -> bool:
        cur = await self.conn.execute("DELETE FROM session_learnings WHERE id=?", (learning_id,))
        await self.conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _provider_row(row: aiosqlite.Row) -> dict[str, Any]:
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        d["extra"] = json.loads(d.pop("extra_json") or "{}")
        d["has_api_key"] = False  # filled by API layer
        return d
