"""Hot-load user skills from skills_user / user_skills."""

from __future__ import annotations

from pathlib import Path

from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.tools import get_registry, reset_registry_for_tests


def test_registry_has_adaptive_primitives():
    reset_registry_for_tests()
    names = set(get_registry().names())
    assert "anim.keyframes" in names
    assert "blender.introspect" in names
    assert get_registry().get("blender.introspect").risk == "read"


def test_hot_load_skills_user_dir(tmp_path):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    user = tmp_path / "user_skills"
    alias = tmp_path / "skills_user"
    alias.mkdir()
    (alias / "user.studio_bounce.yaml").write_text(
        "\n".join(
            [
                "id: user.studio_bounce",
                "version: 1",
                "name: Studio Bounce",
                "domains: [animation, lighting]",
                "tools: [anim.keyframes, light.set, camera.set, render.set, blender.introspect]",
                "description: Personal throw/bounce + studio lights recipe",
                "risk: medium",
                "requires_confirmation: false",
                "viewport_capture: optional",
            ]
        ),
        encoding="utf-8",
    )
    engine = SkillEngine(
        skills_dir=bundled,
        presets_dir=tmp_path / "presets",
        user_skills_dir=user,
    )
    engine.skills_user_dir = alias
    engine.load()
    skill = engine.get("user.studio_bounce")
    assert skill is not None
    assert "anim.keyframes" in (skill.get("tools") or [])
