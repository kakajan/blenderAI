from pathlib import Path

from blender_ai_sidecar.config import repo_root
from blender_ai_sidecar.skills.engine import SkillEngine, normalize_skill_id


def test_presets_list():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    presets = engine.list_presets()
    assert len(presets) >= 3


def test_normalize_skill_id():
    assert normalize_skill_id("my table").startswith("user.")
    assert normalize_skill_id("user.custom_light") == "user.custom_light"


def test_user_skill_crud(tmp_path: Path):
    engine = SkillEngine(
        skills_dir=repo_root() / "skills",
        presets_dir=repo_root() / "presets",
        user_skills_dir=tmp_path / "user_skills",
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
    )
    loaded = engine2.load()
    assert any(s["id"] == "user.custom_table" for s in loaded)
    assert len(loaded) == bundled_count + 1

    assert engine2.delete_user_skill("user.custom_table") is True
    assert engine2.get("user.custom_table") is None
