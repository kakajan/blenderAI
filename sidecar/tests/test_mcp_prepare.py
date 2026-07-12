from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from blender_ai_sidecar.api.routes import McpPrepareBody, mcp_prepare
from blender_ai_sidecar.chat.agent import ChatAgent
from blender_ai_sidecar.providers.router import ProviderRouter
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.store.db import Database


@pytest.mark.asyncio
async def test_mcp_prepare_returns_delegated_context(tmp_path):
    db = Database(tmp_path / "test.db")
    await db.connect()
    skills = SkillEngine()
    skills.load()
    prov = ProviderRouter(db)
    agent = ChatAgent(db, prov, skills)

    request = MagicMock()
    request.app.state.db = db
    request.app.state.skills = skills
    request.app.state.agent = agent
    request.app.state.provider_router = prov

    body = McpPrepareBody(message="block out a table", skill_id="modeling.blockout")
    data = await mcp_prepare(body, request)
    assert data["ok"] is True
    assert data["mode"] == "delegated"
    assert data["provider_id"] == "cursor"
    assert data["skill_id"] == "modeling.blockout"
    assert "scene.create_object" in data["allowed_tools"]
    assert "block out a table" in data["user_message"]
    assert "invoke_tool" in data["instructions"]
    await db.close()
