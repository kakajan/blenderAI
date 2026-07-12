from blender_ai_sidecar.chat.skill_router import infer_skill, is_surface_tool, primitive_guardrail_message


def test_infer_skill_character_detailed():
    assert infer_skill("Create a detailed purple chibi bird from reference") == "modeling.surface_advanced"


def test_infer_skill_character_simple():
    assert infer_skill("Make a chibi bird") == "modeling.character_stylized"


def test_infer_skill_hardsurface():
    assert infer_skill("Add bevels and boolean cuts to this hard-surface prop") == "modeling.hardsurface"


def test_infer_skill_low_poly():
    assert infer_skill("Low-poly game asset fox") == "modeling.low_poly"


def test_infer_skill_blockout():
    assert infer_skill("Quick blockout silhouette only") == "modeling.blockout"


def test_infer_skill_primitives_only():
    assert infer_skill("Just a cube primitives only") == "modeling.primitives"


def test_infer_skill_respects_explicit():
    assert infer_skill("detailed bird", "modeling.blockout") == "modeling.blockout"


def test_infer_skill_none_for_generic():
    assert infer_skill("hello") is None


def test_is_surface_tool():
    assert is_surface_tool("mesh.extrude")
    assert is_surface_tool("mesh.ops")
    assert not is_surface_tool("scene.create_object")


def test_primitive_guardrail_message():
    msg = primitive_guardrail_message(3)
    assert "3 primitives" in msg
    assert "mesh.extrude" in msg
