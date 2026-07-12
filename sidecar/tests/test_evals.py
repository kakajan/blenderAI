from __future__ import annotations

from blender_ai_sidecar.config import repo_root
from blender_ai_sidecar.skills.engine import SkillEngine
from evals import load_cases, run_case, run_evals


def test_load_eval_cases():
    cases = load_cases()
    assert len(cases) >= 2
    assert all(c.skill_id for c in cases)


def test_run_evals_against_bundled_skills():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    engine.load()
    by_id = {s["id"]: s for s in engine.list()}
    results = run_evals(by_id)
    assert results
    failed = [r for r in results if not r.ok]
    assert failed == [], [r.errors for r in failed]


def test_run_case_primitives():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    engine.load()
    case = next(c for c in load_cases() if c.skill_id == "modeling.primitives")
    result = run_case(case, engine.get("modeling.primitives"))
    assert result.ok
    assert "scene.create_object" in result.allowed
    assert "mesh.ops" not in result.allowed
