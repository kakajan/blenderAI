from blender_ai_sidecar.config import repo_root
from blender_ai_sidecar.skills.engine import SkillEngine


def test_presets_list():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    presets = engine.list_presets()
    assert len(presets) >= 3
