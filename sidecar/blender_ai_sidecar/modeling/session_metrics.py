from __future__ import annotations

from typing import Any

SURFACE_EDIT_TOOLS = frozenset(
    {
        "mesh.ops",
        "mesh.extrude",
        "mesh.from_data",
        "mesh.profile_extrude",
        "mesh.edge_loop",
    }
)


def count_modeling_methods(session_tools: list[dict[str, Any]]) -> dict[str, int]:
    """Count tool usage in a modeling session for critique and refactor hints."""
    primitive_count = 0
    mesh_ops_count = 0
    surface_count = 0
    sculpt_count = 0

    for entry in session_tools:
        tool = str(entry.get("tool") or "")
        if tool == "scene.create_object":
            primitive_count += 1
        if tool in {"mesh.ops", "mesh.extrude", "mesh.edge_loop"}:
            mesh_ops_count += 1
        if tool in SURFACE_EDIT_TOOLS:
            surface_count += 1
        if tool in {"sculpt.remesh", "sculpt.set_brush"}:
            sculpt_count += 1

    return {
        "primitive_count": primitive_count,
        "mesh_ops_count": mesh_ops_count,
        "surface_count": surface_count,
        "sculpt_count": sculpt_count,
    }


def needs_primitive_refactor(metrics: dict[str, int]) -> bool:
    return metrics.get("primitive_count", 0) > 12 and metrics.get("mesh_ops_count", 0) < 2


def critique_refactor_hint(metrics: dict[str, int]) -> str:
    if not needs_primitive_refactor(metrics):
        return ""
    return (
        f"METHOD SCORE LOW: {metrics['primitive_count']} primitives but only "
        f"{metrics['mesh_ops_count']} mesh edits. Recommend refactor: delete loose parts, "
        "rebuild with cube + mesh.extrude + SUBSURF instead of sphere stacking."
    )


def infer_modeling_method(recipes: list[dict[str, Any]]) -> str:
    """Detect dominant modeling method from tool recipes for learned skills."""
    tools = [str(r.get("tool") or "") for r in recipes]
    if not tools:
        return "surface_advanced"

    primitive_n = sum(1 for t in tools if t == "scene.create_object")
    surface_n = sum(1 for t in tools if t in SURFACE_EDIT_TOOLS)
    sculpt_n = sum(1 for t in tools if t.startswith("sculpt."))

    if sum(1 for t in tools if t == "mesh.from_data") >= 1 and primitive_n <= 1:
        return "low_poly"
    if sculpt_n >= 1 and surface_n >= 1:
        return "hybrid_sculpt_surface"
    if surface_n >= 2:
        return "surface_advanced"
    if primitive_n >= 3 and surface_n == 0:
        return "primitives_only"
    return "surface_advanced"
