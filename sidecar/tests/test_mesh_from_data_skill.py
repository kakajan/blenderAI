from blender_ai_sidecar.config import repo_root
from blender_ai_sidecar.skills.engine import SkillEngine, resolve_skill_tools


def test_low_poly_skill_tools_strict():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    engine.load()
    skill = engine.get("modeling.low_poly")
    assert skill is not None
    allowed = resolve_skill_tools(skill)
    assert "mesh.from_data" in allowed
    assert "material.create" in allowed
    assert "object.delete" in allowed
    assert "mesh.ops" not in allowed
    assert "scene.create_object" not in allowed
    assert "modifier.add" not in allowed


def test_low_poly_skill_loads_preset():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    engine.load()
    skill = engine.get("modeling.low_poly")
    assert skill is not None
    assert "mesh.from_data" in skill.get("system_prompt_text", "")
    assert skill.get("max_steps") == 5
