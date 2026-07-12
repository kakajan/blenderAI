"""Agent recovers with a short reply when the follow-up model returns empty."""

from __future__ import annotations

import pytest

from blender_ai_sidecar.chat.agent import ChatAgent
from blender_ai_sidecar.providers.base import ChatRequest, StreamEvent


class _FakeDB:
    async def create_chat(self, row):
        return row

    async def add_message(self, row):
        return row


class _FakeSkills:
    def get(self, skill_id):
        return None

    def _load_prompt(self, path):
        return "You are BlenderAI."


class _FakeRouter:
    def __init__(self):
        self.calls = 0

    async def chat_stream(self, provider_id, req: ChatRequest, *, local_only: bool = False):
        self.calls += 1
        if self.calls == 1:
            # First turn: emit a tool call fence
            text = (
                '```json tool\n'
                '{"tool":"scene.create_object","args":{"type":"uv_sphere","name":"Ball"}}\n'
                "```"
            )
            yield StreamEvent(type="token", content=text)
            yield StreamEvent(type="done")
            return
        # Follow-up after tool: empty model
        yield StreamEvent(type="status", content="empty_model_response:stop")
        yield StreamEvent(type="done")


@pytest.mark.asyncio
async def test_agent_synthesizes_after_empty_followup(monkeypatch):
    from blender_ai_sidecar.bridge import protocol as bridge

    async def fake_tool(tool, args, timeout=30.0):
        return {"ok": True, "data": {"name": args.get("name"), "type": args.get("type")}}

    monkeypatch.setattr(bridge, "request_tool", fake_tool)
    monkeypatch.setattr(bridge, "get_scene_cache", lambda: {"connected": True, "summary": {}})

    router = _FakeRouter()
    agent = ChatAgent(_FakeDB(), router, _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in agent.run_stream(
        provider_id="ollama",
        model="test",
        skill_id=None,
        user_message="create a ball",
    ):
        events.append(ev)

    tokens = [e.content for e in events if e.type == "token"]
    assert any("Created Ball" in (t or "") for t in tokens)
    assert events[-1].type == "done"
    assert router.calls == 2
