from blender_ai_sidecar.bridge.tool_args import normalize_tool_args
import pytest


def test_create_object_size_list_becomes_dimensions():
    out = normalize_tool_args(
        "scene.create_object",
        {"type": "cube", "name": "Box", "size": [1.0, 2.0, 0.5], "location": [0, 0, 1]},
    )
    assert "size" not in out
    assert out["dimensions"] == [1.0, 2.0, 0.5]
    assert out["location"] == [0.0, 0.0, 1.0]


def test_create_object_scalar_location_expanded():
    out = normalize_tool_args("scene.create_object", {"type": "cube", "location": 2})
    assert out["location"] == [2.0, 2.0, 2.0]


def test_create_object_radius_list_coerced():
    out = normalize_tool_args(
        "scene.create_object",
        {"type": "cylinder", "radius": [0.5, 0.5, 0.5], "depth": 2},
    )
    assert out["radius"] == 0.5


def test_create_object_nested_location():
    out = normalize_tool_args(
        "scene.create_object",
        {"type": "cube", "location": [[0, 0, 1]]},
    )
    assert out["location"] == [0.0, 0.0, 1.0]


def test_create_object_mixed_component_list():
    out = normalize_tool_args(
        "scene.create_object",
        {"type": "cube", "location": [0, 0, [0.45]]},
    )
    assert out["location"] == [0.0, 0.0, 0.45]


def test_other_tools_unchanged():
    args = {"object": "Cube", "op": "bevel", "offset": 0.02}
    assert normalize_tool_args("mesh.ops", args) == args


def test_mesh_from_data_normalizes_parts():
    out = normalize_tool_args(
        "mesh.from_data",
        {
            "name": "Fox",
            "parts": [
                {
                    "name": "Fox_Body",
                    "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                    "faces": [[0, 1, 2]],
                    "location": 0,
                    "scale": [2, 2, 2],
                }
            ],
        },
    )
    assert out["flat_shade"] is True
    assert out["remove_doubles"] is True
    part = out["parts"][0]
    assert part["location"] == [0.0, 0.0, 0.0]
    assert part["scale"] == [2.0, 2.0, 2.0]
    assert part["vertices"] == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert part["faces"] == [[0, 1, 2]]


def test_mesh_from_data_rejects_bad_face_index():
    with pytest.raises(ValueError, match="face index 5 out of range"):
        normalize_tool_args(
            "mesh.from_data",
            {
                "parts": [
                    {
                        "name": "Bad",
                        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                        "faces": [[0, 1, 5]],
                    }
                ]
            },
        )


def test_mesh_from_data_rejects_empty_parts():
    with pytest.raises(ValueError, match="non-empty parts"):
        normalize_tool_args("mesh.from_data", {"parts": []})


def test_mesh_from_data_rejects_too_many_parts():
    parts = [
        {"name": f"P{i}", "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "faces": [[0, 1, 2]]}
        for i in range(21)
    ]
    with pytest.raises(ValueError, match="at most 20 parts"):
        normalize_tool_args("mesh.from_data", {"parts": parts})


def test_mesh_from_data_rejects_vertex_cap():
    verts = [[float(i), 0, 0] for i in range(501)]
    faces = [[0, 1, 2]]
    with pytest.raises(ValueError, match="exceeds limit of 500"):
        normalize_tool_args(
            "mesh.from_data",
            {"parts": [{"name": "Huge", "vertices": verts, "faces": faces}]},
        )

