from blender_ai_sidecar.bridge import protocol as bridge
from blender_ai_sidecar.bridge.tool_args import normalize_tool_args
from blender_ai_sidecar.skills.engine import get_known_tools


def test_mesh_select_in_allowlist():
    assert "mesh.select" in bridge.ALLOWLIST


def test_known_tools_include_mesh_surface_tools():
    tools = get_known_tools()
    for name in ("mesh.select", "mesh.extrude", "mesh.edge_loop", "mesh.profile_extrude"):
        assert name in tools


def test_mesh_select_semantic_args_passthrough():
    """Semantic selectors are passed through to the extension bridge."""
    args = normalize_tool_args(
        "mesh.select",
        {
            "object": "Body",
            "target": "faces",
            "by_normal": {"direction": [0, -1, 0], "threshold": 0.7},
        },
    )
    assert args["by_normal"]["direction"] == [0, -1, 0]

    top_cap = normalize_tool_args(
        "mesh.select",
        {"object": "Body", "top_cap": {"axis": "z", "percent": 0.2}},
    )
    assert top_cap["top_cap"]["percent"] == 0.2

    ring = normalize_tool_args(
        "mesh.select",
        {"object": "Body", "ring": {"axis": "z", "center": 0.5, "width": 0.1}},
    )
    assert ring["ring"]["center"] == 0.5

    boundary = normalize_tool_args(
        "mesh.select",
        {"object": "Body", "target": "edges", "boundary": True},
    )
    assert boundary["boundary"] is True
