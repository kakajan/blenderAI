from blender_ai_sidecar.bridge import protocol as bridge
from blender_ai_sidecar.bridge.tool_args import normalize_tool_args


def test_allowlist_mesh_tools():
    from blender_ai_sidecar.tools import get_registry

    allow = get_registry().allowlist()
    for tool in (
        "mesh.extrude",
        "mesh.edge_loop",
        "mesh.profile_extrude",
        "mesh.select",
        "mesh.ops",
        "mesh.loft_profiles",
        "curve.create",
        "python.run",
    ):
        assert tool in allow
        assert tool in bridge._allowlist_from_registry()


def test_mesh_extrude_normalizes_distance():
    args = normalize_tool_args("mesh.extrude", {"object": "Body", "faces": "top_cap", "distance": "0.3"})
    assert args["distance"] == 0.3


def test_mesh_extrude_normalizes_direction():
    args = normalize_tool_args(
        "mesh.extrude",
        {"object": "Body", "faces": "by_normal", "direction": [0, -1, 0], "distance": 0.1},
    )
    assert args["direction"] == [0.0, -1.0, 0.0]


def test_mesh_extrude_inset_after():
    args = normalize_tool_args(
        "mesh.extrude",
        {"object": "Body", "distance": 0.2, "inset_after": "0.015"},
    )
    assert args["inset_after"] == 0.015


def test_mesh_edge_loop_count():
    args = normalize_tool_args("mesh.edge_loop", {"object": "Body", "count": "2", "axis": "z"})
    assert args["count"] == 2


def test_mesh_profile_extrude_normalizes():
    args = normalize_tool_args(
        "mesh.profile_extrude",
        {
            "name": "Wing",
            "profile": [[0, 0], ["0.3", 0.1]],
            "depth": "0.05",
            "location": [1, 2, 3],
        },
    )
    assert args["depth"] == 0.05
    assert args["profile"][1] == [0.3, 0.1]
    assert args["location"] == [1.0, 2.0, 3.0]
