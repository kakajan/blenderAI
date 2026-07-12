from blender_ai_sidecar.modeling.session_metrics import (
    count_modeling_methods,
    critique_refactor_hint,
    needs_primitive_refactor,
)
from blender_ai_sidecar.chat.skill_router import primitive_guardrail_message, is_surface_tool


def test_primitive_guardrail_message():
    msg = primitive_guardrail_message(3)
    assert "3 primitives" in msg
    assert "mesh.extrude" in msg


def test_surface_tool_resets_streak_concept():
    assert is_surface_tool("mesh.extrude")
    assert not is_surface_tool("scene.create_object")


def test_needs_primitive_refactor():
    metrics = count_modeling_methods(
        [{"tool": "scene.create_object"}] * 15 + [{"tool": "mesh.ops"}]
    )
    assert metrics["primitive_count"] == 15
    assert metrics["mesh_ops_count"] == 1
    assert needs_primitive_refactor(metrics)


def test_no_refactor_when_balanced():
    tools = [{"tool": "scene.create_object"}] * 3
    tools += [{"tool": "mesh.extrude"}] * 4
    metrics = count_modeling_methods(tools)
    assert not needs_primitive_refactor(metrics)


def test_critique_refactor_hint():
    metrics = {"primitive_count": 20, "mesh_ops_count": 1}
    hint = critique_refactor_hint(metrics)
    assert "METHOD SCORE LOW" in hint
    assert "sphere" in hint.lower() or "extrude" in hint.lower()
