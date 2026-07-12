from __future__ import annotations

import pytest

from blender_ai_sidecar.contracts import ProviderCapabilities
from blender_ai_sidecar.providers.base import infer_capabilities, model_info_with_caps
from blender_ai_sidecar.providers.router import ProviderRouter
from blender_ai_sidecar.store.db import Database


def test_infer_anthropic():
    caps = infer_capabilities("anthropic", "claude-sonnet-4-20250514")
    assert caps.vision is True
    assert caps.tool_calling == "anthropic"
    assert caps.max_images == 8


def test_infer_openai_vision_and_text():
    vision = infer_capabilities("openai", "gpt-4o")
    assert vision.vision is True
    assert vision.tool_calling == "openai"
    assert vision.max_images >= 4

    text = infer_capabilities("openai", "gpt-3.5-turbo")
    assert text.vision is False
    assert text.tool_calling == "openai"
    assert text.max_images == 0


def test_infer_ollama_vision():
    llava = infer_capabilities("ollama", "llava:latest")
    assert llava.vision is True
    assert llava.tool_calling == "regex"
    assert llava.max_images == 4

    llama = infer_capabilities("ollama", "llama3.2")
    assert llama.vision is False
    assert llama.max_images == 0


def test_infer_cursor():
    caps = infer_capabilities("cursor", "cursor-agent")
    assert caps.vision is False
    assert caps.tool_calling == "none"
    assert caps.max_images == 0


def test_model_info_with_caps():
    info = model_info_with_caps(
        model_id="gpt-4.1",
        provider_id="openai",
        provider_kind="openai",
    )
    assert info.supports_vision is True
    assert info.tool_calling == "openai"


@pytest.mark.asyncio
async def test_router_capabilities(tmp_path):
    db = Database(tmp_path / "caps.sqlite")
    await db.connect()
    router = ProviderRouter(db)
    caps = await router.capabilities("ollama", model="bakllava")
    assert isinstance(caps, ProviderCapabilities)
    assert caps.vision is True
    assert caps.tool_calling == "regex"
    openai_caps = await router.capabilities("openai", model="gpt-4o-mini")
    # gpt-4o-mini matches gpt-4o vision heuristic
    assert openai_caps.tool_calling == "openai"
    await db.close()
