"""Tests for docs/blender-refs knowledge retrieval."""

from __future__ import annotations

from blender_ai_sidecar.knowledge import format_for_prompt, load_index, reset_knowledge_cache, retrieve


def test_blender_refs_index_loads():
    reset_knowledge_cache()
    data = load_index()
    assert data.get("chunks")
    assert data.get("api_url")


def test_retrieve_animation_query():
    reset_knowledge_cache()
    chunks = retrieve("keyframe bounce animation camera follow", limit=3)
    assert chunks
    ids = {c.get("id") for c in chunks}
    assert ids & {"anim-keyframes", "anim-camera-follow", "render-motion-blur"}


def test_retrieve_by_tags():
    reset_knowledge_cache()
    chunks = retrieve("", limit=2, tags=["lighting", "studio"])
    assert chunks
    assert any("light" in " ".join(c.get("tags") or []).lower() for c in chunks)


def test_format_for_prompt():
    reset_knowledge_cache()
    text = format_for_prompt(retrieve("motion blur eevee", limit=2))
    assert "Blender reference" in text or "Motion blur" in text or "motion" in text.lower()
