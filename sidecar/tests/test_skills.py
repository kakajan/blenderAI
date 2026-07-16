from pathlib import Path

from blender_ai_sidecar.config import repo_root
from blender_ai_sidecar.skills.engine import SkillEngine, normalize_skill_id, resolve_skill_tools


def test_presets_list():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    presets = engine.list_presets()
    assert len(presets) >= 3
    assert all("source" in p for p in presets)
    assert all(p.get("source") == "bundled" for p in presets)


def test_normalize_skill_id():
    assert normalize_skill_id("my table").startswith("user.")
    assert normalize_skill_id("user.custom_light") == "user.custom_light"


def test_resolve_skill_tools_modeling_base():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    engine.load()
    boolean = engine.get("modeling.boolean")
    assert boolean is not None
    allowed = resolve_skill_tools(boolean)
    assert "object.duplicate" in allowed
    assert "scene.create_object" in allowed
    assert "modifier.add" in allowed

    primitives = engine.get("modeling.primitives")
    assert primitives is not None
    prim_allowed = resolve_skill_tools(primitives)
    assert prim_allowed == ["scene.create_object"]

    low_poly = engine.get("modeling.low_poly")
    assert low_poly is not None
    low_poly_allowed = resolve_skill_tools(low_poly)
    assert low_poly_allowed == [
        "mesh.from_data",
        "material.create",
        "material.assign",
        "object.delete",
        "object.parent",
        "collection.organize",
        "camera.set",
        "light.set",
    ]

    critique = engine.get("review.critique")
    assert critique is not None
    critique_allowed = resolve_skill_tools(critique)
    assert critique_allowed == ["viewport.capture"]

    iterate = engine.get("review.iterate")
    assert iterate is not None
    iterate_allowed = resolve_skill_tools(iterate)
    assert "object.duplicate" in iterate_allowed
    assert "viewport.capture" in iterate_allowed

    surface = engine.get("modeling.surface_advanced")
    assert surface is not None
    surface_allowed = resolve_skill_tools(surface)
    assert "mesh.extrude" in surface_allowed
    assert "mesh.profile_extrude" in surface_allowed
    assert "mesh.edge_loop" in surface_allowed
    assert "scene.create_object" in surface_allowed
    # Modeling base merge should include procedural tools.
    assert "python.run" in surface_allowed
    assert "mesh.loft_profiles" in surface_allowed

    procedural = engine.get("modeling.procedural")
    assert procedural is not None
    assert procedural.get("max_steps") == 96
    proc_allowed = resolve_skill_tools(procedural)
    assert "python.run" in proc_allowed
    assert "curve.create" in proc_allowed
    assert "asset.import" in proc_allowed
    assert "mesh.loft_profiles" in proc_allowed


def test_user_skill_crud(tmp_path: Path):
    engine = SkillEngine(
        skills_dir=repo_root() / "skills",
        presets_dir=repo_root() / "presets",
        user_skills_dir=tmp_path / "user_skills",
        user_presets_dir=tmp_path / "user_presets",
    )
    engine.load()
    bundled_count = len(engine.list())
    assert bundled_count >= 10

    skill = engine.save_user_skill(
        {
            "name": "Custom Table",
            "id": "user.custom_table",
            "description": "Build tables",
            "domains": ["modeling"],
            "tools": ["scene.create_object", "mesh.ops"],
            "prompt": "Create clean furniture tables.",
            "risk": "low",
        }
    )
    assert skill["id"] == "user.custom_table"
    assert skill["source"] == "user"
    assert skill["editable"] is True
    assert "furniture" in skill["system_prompt_text"]
    assert (tmp_path / "user_skills" / "user.custom_table.yaml").exists()

    engine2 = SkillEngine(
        skills_dir=repo_root() / "skills",
        presets_dir=repo_root() / "presets",
        user_skills_dir=tmp_path / "user_skills",
        user_presets_dir=tmp_path / "user_presets",
    )
    loaded = engine2.load()
    assert any(s["id"] == "user.custom_table" for s in loaded)
    assert len(loaded) == bundled_count + 1

    assert engine2.delete_user_skill("user.custom_table") is True
    assert engine2.get("user.custom_table") is None


def test_user_preset_crud(tmp_path: Path):
    engine = SkillEngine(
        skills_dir=repo_root() / "skills",
        presets_dir=repo_root() / "presets",
        user_skills_dir=tmp_path / "user_skills",
        user_presets_dir=tmp_path / "user_presets",
    )
    bundled = engine.list_presets()
    bundled_count = len(bundled)

    preset = engine.save_user_preset(
        {
            "name": "Warm Catalog",
            "id": "user.warm_catalog",
            "category": "styles",
            "description": "Warm product shots",
            "prompt": "Use warm soft lighting and gentle reflections.",
        }
    )
    assert preset["id"] == "user.warm_catalog"
    assert preset["source"] == "user"
    assert preset["editable"] is True
    assert preset["category"] == "styles"
    assert "warm soft" in preset["prompt"]
    assert (tmp_path / "user_presets" / "user.warm_catalog.yaml").exists()

    engine2 = SkillEngine(
        skills_dir=repo_root() / "skills",
        presets_dir=repo_root() / "presets",
        user_skills_dir=tmp_path / "user_skills",
        user_presets_dir=tmp_path / "user_presets",
    )
    loaded = engine2.list_presets()
    assert any(p["id"] == "user.warm_catalog" for p in loaded)
    assert len(loaded) == bundled_count + 1
    got = engine2.get_preset("user.warm_catalog")
    assert got is not None
    assert got["name"] == "Warm Catalog"

    assert engine2.delete_user_preset("user.warm_catalog") is True
    assert engine2.get_preset("user.warm_catalog") is None


def test_draft_preset_from_messages():
    engine = SkillEngine(
        skills_dir=repo_root() / "skills",
        presets_dir=repo_root() / "presets",
    )
    draft = engine.draft_preset_from_messages(
        "Table build",
        [
            {"role": "user", "content": "Make a 120cm modern table"},
            {"role": "assistant", "content": "⚙ scene.create_object\n✓ tool ok: Table\nCreated a table with clean proportions."},
            {"role": "user", "content": "Add warm wood material"},
        ],
    )
    assert draft["name"] == "Table build"
    assert draft["category"] == "workflows"
    assert "120cm modern table" in draft["prompt"]
    assert "warm wood" in draft["prompt"]
    assert "Created a table" in draft["prompt"]


def test_character_stylized_includes_fur_tools():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    engine.load()
    skill = engine.get("modeling.character_stylized")
    assert skill is not None
    allowed = resolve_skill_tools(skill)
    assert "particle.fur_set" in allowed
    assert "viewport.set_shading" in allowed
    assert "viewport.capture" in allowed


def test_draft_preset_preserves_tool_json():
    engine = SkillEngine(
        skills_dir=repo_root() / "skills",
        presets_dir=repo_root() / "presets",
    )
    draft = engine.draft_preset_from_messages(
        "Bird build",
        [
            {"role": "user", "content": "Purple bird"},
            {
                "role": "assistant",
                "content": '```json tool\n{"tool":"viewport.capture","args":{"views":["front","side","back"]}}\n```',
            },
        ],
    )
    assert "Tool recipes that worked" in draft["prompt"]
    assert "viewport.capture" in draft["prompt"]
    assert "front" in draft["prompt"]
