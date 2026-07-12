from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from blender_ai_sidecar.config import repo_root
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.skills.schema import SkillValidationError, validate_skill_dict


def test_validate_skill_ok():
    data, warnings = validate_skill_dict(
        {
            "id": "modeling.primitives",
            "version": 1,
            "name": "Primitives",
            "tools": ["scene.create_object", "not.a.real.tool"],
        }
    )
    assert data["id"] == "modeling.primitives"
    assert data["version"] == "1"
    assert data["tools"] == ["scene.create_object"]
    assert any("unknown tools" in w for w in warnings)


def test_validate_skill_bad_id():
    with pytest.raises(SkillValidationError):
        validate_skill_dict({"id": "BadId", "version": "1", "tools": []})


def test_validate_skill_missing_version():
    with pytest.raises(SkillValidationError):
        validate_skill_dict({"id": "user.custom_x", "tools": ["scene.summary"]})


def test_engine_skips_invalid_skill(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    good = {
        "id": "user.good_skill",
        "version": "1",
        "name": "Good",
        "tools": ["scene.summary"],
        "system_prompt": "",
    }
    bad = {
        "id": "Invalid",
        "version": "1",
        "name": "Bad",
        "tools": ["scene.summary"],
    }
    (skills_dir / "user.good_skill.yaml").write_text(
        yaml.safe_dump(good), encoding="utf-8"
    )
    (skills_dir / "bad.yaml").write_text(yaml.safe_dump(bad), encoding="utf-8")

    engine = SkillEngine(
        skills_dir=skills_dir,
        presets_dir=tmp_path / "presets",
        user_skills_dir=tmp_path / "user_skills",
        user_presets_dir=tmp_path / "user_presets",
    )
    engine.load()
    assert "user.good_skill" in engine._skills
    assert "Invalid" not in engine._skills
    assert any("skip bad.yaml" in w for w in engine.load_warnings)


def test_bundled_skills_load_cleanly():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    skills = engine.load()
    assert len(skills) >= 10
    hard = [w for w in engine.load_warnings if w.startswith("skip ")]
    assert hard == [], hard
