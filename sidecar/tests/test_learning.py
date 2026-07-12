from __future__ import annotations

import json

import pytest

from blender_ai_sidecar.learning.engine import (
    LearningEngine,
    extract_tool_recipes,
    summarize_tool_recipes,
)
from blender_ai_sidecar.skills.engine import SkillEngine, get_known_tools
from blender_ai_sidecar.store.db import Database


@pytest.mark.asyncio
async def test_extract_tool_recipes_from_messages():
    messages = [
        {
            "role": "assistant",
            "content": '```json tool\n{"tool":"scene.create_object","args":{"type":"uv_sphere","name":"Bird"}}\n```',
        },
        {"role": "user", "content": "Tool result: ok"},
        {
            "role": "assistant",
            "content": '```json tool\n{"tool":"material.create","args":{"name":"Mat_Purple"}}\n```',
        },
    ]
    recipes = extract_tool_recipes(messages)
    assert len(recipes) == 2
    assert recipes[0]["tool"] == "scene.create_object"
    assert recipes[1]["tool"] == "material.create"


def test_summarize_tool_recipes():
    text = summarize_tool_recipes(
        [{"tool": "particle.fur_set", "args": {"preset": "soft", "count": 1200}}]
    )
    assert "particle.fur_set" in text
    assert "soft" in text


@pytest.mark.asyncio
async def test_capability_gap_record_and_list(tmp_path):
    db = Database(tmp_path / "gaps.sqlite")
    await db.connect()
    engine = LearningEngine(db)
    entry = await engine.record_capability_gap(
        user_goal="bake cloth simulation",
        missing_tools=["physics.cloth_bake"],
        domain="physics",
        note="Need cloth primitive",
    )
    assert entry["rating"] == "gap"
    gaps = await engine.list_capability_gaps()
    assert gaps
    assert gaps[0]["user_goal"] == "bake cloth simulation"
    assert any(r.get("tool") == "physics.cloth_bake" for r in gaps[0].get("tool_recipes") or [])
    await db.close()


@pytest.mark.asyncio
async def test_tool_run_logging(tmp_path):
    db = Database(tmp_path / "runs.sqlite")
    await db.connect()
    engine = LearningEngine(db)

    await engine.record_tool_run(
        chat_id="c1",
        skill_id="modeling.turnaround_character",
        tool="viewport.capture",
        args={"views": ["front", "side", "back"]},
        result={"ok": True, "views": [{"view": "front"}]},
        step=2,
        user_goal="build bird",
    )

    runs = await db.list_tool_runs(chat_id="c1", ok_only=True)
    assert len(runs) == 1
    assert runs[0]["tool"] == "viewport.capture"
    assert runs[0]["args"]["views"] == ["front", "side", "back"]
    await db.close()


@pytest.mark.asyncio
async def test_draft_skill_from_chat(tmp_path):
    db = Database(tmp_path / "skill.sqlite")
    await db.connect()
    now = "2026-07-12T00:00:00+00:00"
    await db.create_chat(
        {
            "id": "chat-bird",
            "title": "Purple bird",
            "skill_id": "modeling.character_stylized",
            "created_at": now,
            "updated_at": now,
        }
    )
    await db.add_message(
        {
            "id": "m1",
            "chat_id": "chat-bird",
            "role": "user",
            "content": "Create a purple chibi bird from 3 views",
            "created_at": now,
        }
    )
    await db.add_message(
        {
            "id": "m2",
            "chat_id": "chat-bird",
            "role": "assistant",
            "content": (
                '```json tool\n{"tool":"scene.create_object","args":{"name":"PB_Body"}}\n```\n'
                '```json tool\n{"tool":"mesh.extrude","args":{"object":"PB_Body","faces":"top_cap","distance":0.2}}\n```\n'
                '```json tool\n{"tool":"mesh.ops","args":{"object":"PB_Body","op":"bevel","offset":0.02}}\n```'
            ),
            "created_at": now,
        }
    )

    skills = SkillEngine(
        skills_dir=tmp_path / "skills",
        presets_dir=tmp_path / "presets",
        user_skills_dir=tmp_path / "user_skills",
        user_presets_dir=tmp_path / "user_presets",
    )
    engine = LearningEngine(db)
    draft = await engine.draft_skill_from_chat(
        skills,
        chat_id="chat-bird",
        name="Learned Purple Bird",
    )
    assert draft["name"] == "Learned Purple Bird"
    assert draft.get("method") in {"surface_advanced", "hybrid_sculpt_surface"}
    assert "scene.create_object" in draft["prompt"]
    assert "PB_Body" in draft["prompt"]
    assert "particle.fur_set" in draft["tools"] or "viewport.capture" in draft["tools"]
    await db.close()


@pytest.mark.asyncio
async def test_learning_disabled_returns_empty(tmp_path):
    db = Database(tmp_path / "learn_off.sqlite")
    await db.connect()
    engine = LearningEngine(db)
    await engine.record_feedback(
        chat_id=None,
        skill_id="modeling.character_stylized",
        rating="positive",
        note="Purple chibi bird",
        user_goal="create purple chibi bird character",
    )
    await db.set_setting("learning_enabled", "0")
    rows = await engine.find_relevant(user_goal="purple chibi bird", skill_id="modeling.character_stylized")
    assert rows == []
    await db.close()


@pytest.mark.asyncio
async def test_negative_learning_skips_overlap(tmp_path):
    db = Database(tmp_path / "learn_neg.sqlite")
    await db.connect()
    engine = LearningEngine(db)
    await engine.record_feedback(
        chat_id=None,
        skill_id="modeling.character_stylized",
        rating="positive",
        note="Purple chibi bird with soft fur",
        user_goal="create purple chibi bird character",
    )
    await engine.record_feedback(
        chat_id=None,
        skill_id="modeling.character_stylized",
        rating="negative",
        note="snowman stack failed",
        user_goal="create purple chibi bird character",
    )
    rows = await engine.find_relevant(
        user_goal="purple chibi bird character",
        skill_id="modeling.character_stylized",
        limit=3,
    )
    assert rows == []
    await db.close()


@pytest.mark.asyncio
async def test_recipes_from_successful_runs(tmp_path):
    db = Database(tmp_path / "recipes.sqlite")
    await db.connect()
    engine = LearningEngine(db)
    await engine.record_tool_run(
        chat_id="c1",
        skill_id="modeling.primitives",
        tool="scene.create_object",
        args={"type": "cube"},
        result={"ok": True},
        step=1,
    )
    await engine.record_tool_run(
        chat_id="c1",
        skill_id="modeling.primitives",
        tool="mesh.ops",
        args={"op": "bevel"},
        result={"ok": False, "error": "fail"},
        step=2,
    )
    recipes = await engine.recipes_from_successful_runs("c1")
    assert len(recipes) == 1
    assert recipes[0]["tool"] == "scene.create_object"
    await db.close()


@pytest.mark.asyncio
async def test_db_migrate_scope_columns(tmp_path):
    db = Database(tmp_path / "migrate.sqlite")
    await db.connect()
    cur = await db.conn.execute("PRAGMA table_info(session_learnings)")
    cols = {r[1] for r in await cur.fetchall()}
    assert "scope_key" in cols
    assert "source" in cols
    assert "confidence" in cols
    cur = await db.conn.execute("PRAGMA table_info(tool_runs)")
    cols = {r[1] for r in await cur.fetchall()}
    assert "scope_key" in cols
    cur = await db.conn.execute("PRAGMA table_info(chats)")
    cols = {r[1] for r in await cur.fetchall()}
    assert "scope_key" in cols
    await db.close()


def test_known_tools_includes_new_bridge_tools():
    tools = get_known_tools()
    assert "particle.fur_set" in tools
    assert "viewport.set_shading" in tools
    assert "mesh.extrude" in tools
    assert "mesh.edge_loop" in tools
    assert "mesh.profile_extrude" in tools


def test_draft_preset_includes_tool_recipes():
    engine = SkillEngine()
    draft = engine.draft_preset_from_messages(
        "Bird session",
        [
            {"role": "user", "content": "Make a purple bird"},
            {
                "role": "assistant",
                "content": '```json tool\n{"tool":"particle.fur_set","args":{"preset":"soft"}}\n```\nDone.',
            },
        ],
    )
    assert "Tool recipes that worked" in draft["prompt"]
    assert "particle.fur_set" in draft["prompt"]
