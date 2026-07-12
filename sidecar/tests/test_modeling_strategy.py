from blender_ai_sidecar.chat.modeling_strategy import plan_modeling_strategy


def test_strategy_character_detailed():
    s = plan_modeling_strategy("Create a detailed purple chibi bird with soft fur")
    assert s is not None
    assert s.id in {"hybrid_blockout_surface", "hybrid_sculpt_surface", "reference_turnaround"}


def test_strategy_character_with_reference_image():
    s = plan_modeling_strategy(
        "Build this bird from the reference",
        skill_id="modeling.surface_advanced",
        has_reference_image=True,
    )
    assert s is not None
    assert s.id == "reference_turnaround"
    assert len(s.phases) >= 3


def test_strategy_sculpt_organic():
    s = plan_modeling_strategy("Organic sculpting character with smooth forms")
    assert s is not None
    assert s.id == "hybrid_sculpt_surface"
    assert any("Sculpt" in p.name for p in s.phases)


def test_strategy_hardsurface_prop():
    s = plan_modeling_strategy("Hard-surface mechanical prop with boolean cuts")
    assert s is not None
    assert s.id == "hardsurface_boolean"


def test_strategy_low_poly():
    s = plan_modeling_strategy("Low-poly game asset fox", skill_id="modeling.low_poly")
    assert s is not None
    assert s.id == "low_poly_direct"
    assert s.phases[0].tools == ["mesh.from_data"]


def test_strategy_bridge_loft():
    s = plan_modeling_strategy("Create a vase using spin/loft profile")
    assert s is not None
    assert s.id == "bridge_loft"


def test_strategy_blockout_only():
    s = plan_modeling_strategy("Quick blockout silhouette only")
    assert s is not None
    assert s.id == "blockout_only"


def test_strategy_edit_existing_scene():
    s = plan_modeling_strategy(
        "Add more detail to the model",
        scene_summary={"objects": [{"name": "Body", "type": "MESH"}, {"name": "Wing", "type": "MESH"}]},
    )
    assert s is not None
    assert s.id == "hybrid_edit_existing"
    assert "mesh objects" in s.rationale.lower()


def test_strategy_prompt_block():
    s = plan_modeling_strategy("Detailed chibi bird", skill_id="modeling.surface_advanced")
    assert s is not None
    text = s.to_prompt_block()
    assert "Modeling Strategy" in text
    assert "Phase 1" in text
    assert "mesh.extrude" in text or "Surface edit" in text


def test_strategy_status_data():
    s = plan_modeling_strategy("Low-poly fox", skill_id="modeling.low_poly")
    assert s is not None
    data = s.to_status_data()
    assert data["strategy_id"] == "low_poly_direct"
    assert isinstance(data["phases"], list)
