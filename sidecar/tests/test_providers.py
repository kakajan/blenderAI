from __future__ import annotations

import json

import httpx
import pytest

from blender_ai_sidecar.providers.ollama import OllamaProvider
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.config import repo_root


@pytest.mark.asyncio
async def test_ollama_list_models(monkeypatch):
    payload = {"models": [{"name": "llama3.2:latest"}, {"name": "qwen2.5:7b"}]}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url):
            assert url.endswith("/api/tags")
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = OllamaProvider()
    models = await provider.list_models()
    assert [m.id for m in models] == ["llama3.2:latest", "qwen2.5:7b"]


def test_skills_load():
    engine = SkillEngine(skills_dir=repo_root() / "skills", presets_dir=repo_root() / "presets")
    skills = engine.load()
    assert len(skills) >= 10
    ids = {s["id"] for s in skills}
    assert "modeling.create_mesh" in ids
    assert "materials.create_pbr" in ids
    skill = engine.get("modeling.create_mesh")
    assert skill is not None
    assert "Modeling" in skill.get("system_prompt_text", "") or "modeling" in skill.get("system_prompt_text", "").lower()
