"""Agent continues tool calls after success when the task needs more steps."""

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


class _MultiStepRouter:
    def __init__(self):
        self.calls = 0

    async def chat_stream(self, provider_id, req: ChatRequest, *, local_only: bool = False):
        self.calls += 1
        if self.calls == 1:
            text = (
                '```json tool\n'
                '{"tool":"scene.create_object","args":{"type":"cube","name":"Table"}}\n'
                "```"
            )
            yield StreamEvent(type="token", content=text)
            yield StreamEvent(type="done")
            return
        if self.calls == 2:
            text = (
                '```json tool\n'
                '{"tool":"mesh.ops","args":{"object":"Table","op":"bevel","offset":0.02,"select_all":true}}\n'
                "```"
            )
            yield StreamEvent(type="token", content=text)
            yield StreamEvent(type="done")
            return
        yield StreamEvent(type="token", content="Beveled the table top.")
        yield StreamEvent(type="done")


@pytest.mark.asyncio
async def test_agent_continues_after_successful_tool(monkeypatch):
    from blender_ai_sidecar.bridge import protocol as bridge

    tools_called = []

    async def fake_tool(tool, args, timeout=30.0):
        tools_called.append(tool)
        return {"ok": True, "name": args.get("object") or args.get("name"), "op": args.get("op")}

    monkeypatch.setattr(bridge, "request_tool", fake_tool)
    monkeypatch.setattr(bridge, "get_scene_cache", lambda: {"connected": True, "summary": {}})

    router = _MultiStepRouter()
    agent = ChatAgent(_FakeDB(), router, _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in agent.run_stream(
        provider_id="ollama",
        model="test",
        skill_id=None,
        user_message="make a detailed table",
    ):
        events.append(ev)

    assert tools_called == ["scene.create_object", "mesh.ops"]
    assert router.calls == 3
    tokens = "".join(e.content or "" for e in events if e.type == "token")
    assert "Beveled" in tokens
    assert events[-1].type == "done"
