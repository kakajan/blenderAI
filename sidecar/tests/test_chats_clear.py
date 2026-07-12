"""Tests for clearing chat history."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from blender_ai_sidecar.store.db import Database


def test_clear_chats(tmp_path: Path):
    async def run():
        db = Database(tmp_path / "test.sqlite")
        await db.connect()
        now = datetime.now(timezone.utc).isoformat()
        await db.create_chat(
            {
                "id": "c1",
                "title": "One",
                "created_at": now,
                "updated_at": now,
            }
        )
        await db.add_message(
            {
                "id": "m1",
                "chat_id": "c1",
                "role": "user",
                "content": "hi",
                "created_at": now,
            }
        )
        assert len(await db.list_chats()) == 1
        assert len(await db.list_messages("c1")) == 1
        deleted = await db.clear_chats()
        assert deleted == 1
        assert await db.list_chats() == []
        assert await db.list_messages("c1") == []
        await db.close()

    asyncio.run(run())
