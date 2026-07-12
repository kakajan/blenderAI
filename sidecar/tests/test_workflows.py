"""Workflow runner unit tests."""

from __future__ import annotations

import pytest

from blender_ai_sidecar.providers.base import StreamEvent
from blender_ai_sidecar.workflows import WorkflowRunner


class _FakeSkills:
    def __init__(self, skills: dict | None = None):
        self._skills = skills or {
            "modeling.blockout": {"id": "modeling.blockout"},
            "review.critique": {"id": "review.critique"},
        }

    def list_presets(self):
        return [
            {
                "id": "workflows/specialist_prop.yaml",
                "alias": "workflow.specialist_prop",
                "name": "Specialist Prop",
                "steps": [
                    {"skill": "modeling.blockout", "prompt": "Blockout only", "name": "Blockout"},
                    {"skill": "review.critique", "prompt": "Critique", "name": "Critique"},
                ],
            },
            {
                "id": "workflows/fail_fast.yaml",
                "alias": "workflow.fail_fast",
                "name": "Fail Fast",
                "steps": [
                    {"skill": "modeling.missing_skill", "prompt": "Nope", "name": "Missing"},
                    {"skill": "review.critique", "prompt": "Should not run", "name": "Critique"},
                ],
            },
            {
                "id": "workflows/tool_fail.yaml",
                "alias": "workflow.tool_fail",
                "name": "Tool Fail",
                "steps": [
                    {"skill": "modeling.blockout", "prompt": "Will fail tool", "name": "Blockout"},
                    {"skill": "review.critique", "prompt": "Should not run", "name": "Critique"},
                ],
            },
            {
                "id": "workflows/tool_fail_continue.yaml",
                "alias": "workflow.tool_fail_continue",
                "name": "Tool Fail Continue",
                "steps": [
                    {
                        "skill": "modeling.blockout",
                        "prompt": "Will fail tool",
                        "name": "Blockout",
                        "on_fail": "continue",
                    },
                    {"skill": "review.critique", "prompt": "Should run", "name": "Critique"},
                ],
            },
        ]

    def get(self, skill_id):
        if not skill_id:
            return None
        return self._skills.get(str(skill_id))

    def get_preset(self, workflow_id):
        for p in self.list_presets():
            if workflow_id in {p["id"], p.get("alias")}:
                return p
        return None


class _FakeAgent:
    def __init__(self, *, fail_tool_once: bool = False, emit_error: bool = False):
        self.calls = []
        self.fail_tool_once = fail_tool_once
        self.emit_error = emit_error

    async def run_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield StreamEvent(type="status", content="chat_ready", data={"chat_id": "c1"})
        if self.emit_error:
            yield StreamEvent(type="error", content="agent blew up")
            yield StreamEvent(type="done", data={"chat_id": "c1"})
            return
        if self.fail_tool_once:
            self.fail_tool_once = False
            yield StreamEvent(
                type="status",
                content="tool_result",
                data={"ok": False, "error": "boom"},
            )
            yield StreamEvent(type="done", data={"chat_id": "c1"})
            return
        yield StreamEvent(type="token", content=f"did {kwargs.get('skill_id')}")
        yield StreamEvent(type="done", data={"chat_id": "c1"})


@pytest.mark.asyncio
async def test_workflow_runs_steps_in_order():
    agent = _FakeAgent()
    runner = WorkflowRunner(agent, _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in runner.run_stream(
        workflow_id="workflow.specialist_prop",
        user_message="wooden chair",
        provider_id="ollama",
    ):
        events.append(ev)

    assert len(agent.calls) == 2
    assert agent.calls[0]["skill_id"] == "modeling.blockout"
    assert agent.calls[1]["skill_id"] == "review.critique"
    assert "Blockout only" in agent.calls[0]["user_message"]
    assert any(e.content == "workflow_started" for e in events if e.type == "status")
    assert any(e.content == "workflow_finished" for e in events if e.type == "status")
    assert events[-1].type == "done"


@pytest.mark.asyncio
async def test_workflow_resolve_prefers_exact_alias():
    runner = WorkflowRunner(_FakeAgent(), _FakeSkills())  # type: ignore[arg-type]
    preset = runner.resolve_workflow("workflow.specialist_prop")
    assert preset is not None
    assert preset["alias"] == "workflow.specialist_prop"

    by_id = runner.resolve_workflow("workflows/specialist_prop.yaml")
    assert by_id is not None
    assert by_id["id"] == "workflows/specialist_prop.yaml"

    by_stem = runner.resolve_workflow("specialist_prop")
    assert by_stem is not None


@pytest.mark.asyncio
async def test_workflow_missing():
    runner = WorkflowRunner(_FakeAgent(), _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in runner.run_stream(
        workflow_id="nope",
        user_message="x",
        provider_id="ollama",
    ):
        events.append(ev)
    assert events[0].type == "error"


@pytest.mark.asyncio
async def test_workflow_stops_on_missing_skill():
    agent = _FakeAgent()
    runner = WorkflowRunner(agent, _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in runner.run_stream(
        workflow_id="workflow.fail_fast",
        user_message="x",
        provider_id="ollama",
    ):
        events.append(ev)

    assert agent.calls == []
    assert any(e.type == "error" and "modeling.missing_skill" in (e.content or "") for e in events)
    assert events[-1].type == "done"
    assert (events[-1].data or {}).get("failed") is True
    assert not any(e.content == "workflow_finished" for e in events if e.type == "status")


@pytest.mark.asyncio
async def test_workflow_stops_on_tool_failure():
    agent = _FakeAgent(fail_tool_once=True)
    runner = WorkflowRunner(agent, _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in runner.run_stream(
        workflow_id="workflow.tool_fail",
        user_message="x",
        provider_id="ollama",
    ):
        events.append(ev)

    assert len(agent.calls) == 1
    assert any(e.content == "workflow_aborted" for e in events if e.type == "status")
    assert (events[-1].data or {}).get("failed") is True


@pytest.mark.asyncio
async def test_workflow_on_fail_continue():
    agent = _FakeAgent(fail_tool_once=True)
    runner = WorkflowRunner(agent, _FakeSkills())  # type: ignore[arg-type]
    events = []
    async for ev in runner.run_stream(
        workflow_id="workflow.tool_fail_continue",
        user_message="x",
        provider_id="ollama",
    ):
        events.append(ev)

    assert len(agent.calls) == 2
    assert any(e.content == "workflow_finished" for e in events if e.type == "status")
