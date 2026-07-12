"""Agent loads prior chat history when chat_id is set."""

from __future__ import annotations

import pytest

from blender_ai_sidecar.chat.agent import ChatAgent, DEFAULT_MAX_STEPS
from blender_ai_sidecar.providers.base import ChatRequest, StreamEvent


class _FakeDB:
    def __init__(self):
        self.prior = [
            {"role": "user", "content": "earlier request"},
            {"role": "assistant", "content": "earlier reply"},
        ]
        self.added = []

    async def create_chat(self, row):
        return row

    async def add_message(self, row):
        self.added.append(row)
        return row

    async def list_messages(self, chat_id):
        return list(self.prior)


class _FakeSkills:
    def get(self, skill_id):
        if skill_id == "modeling.create_mesh":
            return {
                "id": "modeling.create_mesh",
                "domains": ["modeling"],
                "tools": ["scene.create_object"],
                "system_prompt_text": "Model things.",
                "viewport_capture": "optional",
            }
        return None

    def _load_prompt(self, path):
        return "You are BlenderAI."


class _CaptureRouter:
    def __init__(self):
        self.last_req: ChatRequest | None = None

    async def chat_stream(self, provider_id, req: ChatRequest, *, local_only: bool = False):
        self.last_req = req
        yield StreamEvent(type="token", content="ok done")
        yield StreamEvent(type="done")


@pytest.mark.asyncio
async def test_agent_loads_history(monkeypatch):
    from blender_ai_sidecar.bridge import protocol as bridge

    monkeypatch.setattr(bridge, "get_scene_cache", lambda: {"connected": True, "summary": {}})

    router = _CaptureRouter()
    db = _FakeDB()
    agent = ChatAgent(db, router, _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in agent.run_stream(
        provider_id="ollama",
        model="test",
        skill_id=None,
        user_message="continue",
        chat_id="existing",
    ):
        events.append(ev)

    assert router.last_req is not None
    roles = [m.role for m in router.last_req.messages]
    contents = [m.content for m in router.last_req.messages]
    assert "system" in roles
    assert any("earlier request" in c for c in contents)
    assert any("earlier reply" in c for c in contents)
    assert events[-1].type == "done"


@pytest.mark.asyncio
async def test_modeling_skill_default_max_steps(monkeypatch):
    from blender_ai_sidecar.bridge import protocol as bridge

    monkeypatch.setattr(bridge, "get_scene_cache", lambda: {"connected": False, "summary": {}})

    router = _CaptureRouter()
    agent = ChatAgent(_FakeDB(), router, _FakeSkills())  # type: ignore[arg-type]
    status = None
    async for ev in agent.run_stream(
        provider_id="ollama",
        model="test",
        skill_id="modeling.create_mesh",
        user_message="make a chair",
    ):
        if ev.type == "status" and ev.content == "chat_ready":
            status = ev
    assert status is not None
    assert status.data.get("max_steps") == DEFAULT_MAX_STEPS
