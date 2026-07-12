from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from blender_ai_sidecar.store.db import Database

TOOL_JSON_RE = re.compile(
    r"```(?:json)?\s*(?:tool\s*)?(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)

_POSITIVE = frozenset({"up", "good", "yes", "helpful", "correct", "approve", "like", "success", "positive"})
_NEGATIVE = frozenset({"down", "bad", "no", "wrong", "reject", "dislike", "fail", "incorrect", "negative"})
from blender_ai_sidecar.modeling.session_metrics import infer_modeling_method

_SURFACE_TOOLS = frozenset(
    {"mesh.ops", "mesh.extrude", "mesh.from_data", "mesh.profile_extrude", "mesh.edge_loop"}
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def extract_tool_recipes(
    messages: list[dict[str, Any]],
    *,
    successful_tools: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Pull tool calls from assistant messages.

    When ``successful_tools`` is provided (from ok tool_runs), only recipes whose
    tool name appears in that set are kept.
    """
    recipes: list[dict[str, Any]] = []
    for msg in messages:
        if str(msg.get("role") or "") != "assistant":
            continue
        content = str(msg.get("content") or "")
        for match in TOOL_JSON_RE.finditer(content):
            try:
                call = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            tool = call.get("tool")
            if not tool:
                continue
            if successful_tools is not None and str(tool) not in successful_tools:
                continue
            recipes.append(
                {
                    "tool": tool,
                    "args": call.get("args") or {},
                }
            )
    return recipes


def summarize_tool_recipes(recipes: list[dict[str, Any]], *, limit: int = 12) -> str:
    if not recipes:
        return ""
    lines = ["## Successful tool recipes from past sessions"]
    for item in recipes[:limit]:
        args = json.dumps(item.get("args") or {}, ensure_ascii=False)
        if len(args) > 180:
            args = args[:177] + "…"
        lines.append(f'- `{item.get("tool")}` args: `{args}`')
    return "\n".join(lines)


class LearningEngine:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def learning_enabled(self) -> bool:
        """Gate for retrieval / injection into the agent prompt."""
        raw = await self.db.get_setting("learning_enabled", "1")
        return str(raw).strip() not in {"0", "false", "no", "off"}

    async def recipes_from_successful_runs(self, chat_id: str) -> list[dict[str, Any]]:
        """Build recipes only from tool_runs that succeeded for this chat."""
        runs = await self.db.list_tool_runs(chat_id=chat_id, ok_only=True, limit=200)
        recipes: list[dict[str, Any]] = []
        for run in reversed(runs):  # chronological
            tool = run.get("tool")
            if not tool:
                continue
            recipes.append({"tool": tool, "args": run.get("args") or {}})
        return recipes

    async def record_tool_run(
        self,
        *,
        chat_id: str | None,
        skill_id: str | None,
        tool: str,
        args: dict[str, Any],
        result: dict[str, Any],
        step: int = 0,
        user_goal: str = "",
    ) -> None:
        await self.db.insert_tool_run(
            {
                "id": str(uuid.uuid4()),
                "chat_id": chat_id,
                "skill_id": skill_id,
                "tool": tool,
                "args_json": json.dumps(args or {}, ensure_ascii=False)[:4000],
                "ok": 1 if result.get("ok") else 0,
                "result_json": json.dumps(result or {}, ensure_ascii=False)[:4000],
                "user_goal": (user_goal or "")[:500],
                "step": step,
                "created_at": _now(),
            }
        )

    async def record_feedback(
        self,
        *,
        chat_id: str | None,
        skill_id: str | None,
        rating: str,
        note: str = "",
        user_goal: str = "",
    ) -> dict[str, Any]:
        rating_norm = (rating or "").strip().lower()
        if rating_norm not in _POSITIVE | _NEGATIVE:
            raise ValueError("rating must be positive or negative (e.g. up/down, good/bad)")

        positive = rating_norm in _POSITIVE
        entry = {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "skill_id": skill_id,
            "rating": "positive" if positive else "negative",
            "note": (note or "")[:1000],
            "user_goal": (user_goal or "")[:500],
            "tool_recipes_json": "[]",
            "created_at": _now(),
        }

        if chat_id:
            # Prefer recipes tied to successful tool_runs; fall back to message parse
            # filtered by successful tool names when runs exist.
            run_recipes = await self.recipes_from_successful_runs(chat_id)
            if run_recipes:
                entry["tool_recipes_json"] = json.dumps(run_recipes[:24], ensure_ascii=False)
            else:
                messages = await self.db.list_messages(chat_id)
                ok_runs = await self.db.list_tool_runs(chat_id=chat_id, ok_only=True, limit=200)
                if ok_runs:
                    ok_tools = {str(r.get("tool") or "") for r in ok_runs if r.get("tool")}
                    recipes = extract_tool_recipes(messages, successful_tools=ok_tools)
                else:
                    recipes = extract_tool_recipes(messages)
                if recipes:
                    entry["tool_recipes_json"] = json.dumps(recipes[:24], ensure_ascii=False)

        await self.db.insert_learning(entry)
        return entry

    async def find_relevant(
        self,
        *,
        user_goal: str,
        skill_id: str | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        if not await self.learning_enabled():
            return []

        rows = await self.db.list_learnings(skill_id=skill_id, rating="positive", limit=40)
        if not rows:
            rows = await self.db.list_learnings(rating="positive", limit=40)

        negatives = await self.db.list_learnings(skill_id=skill_id, rating="negative", limit=40)
        if not negatives and skill_id:
            negatives = await self.db.list_learnings(rating="negative", limit=40)
        neg_token_sets: list[tuple[str | None, set[str]]] = [
            (
                str(n.get("skill_id") or "") or None,
                _tokenize(
                    " ".join(
                        [
                            str(n.get("user_goal") or ""),
                            str(n.get("note") or ""),
                        ]
                    )
                ),
            )
            for n in negatives
        ]

        goal_tokens = _tokenize(user_goal)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            text = " ".join(
                [
                    str(row.get("user_goal") or ""),
                    str(row.get("note") or ""),
                    str(row.get("skill_id") or ""),
                ]
            )
            tokens = _tokenize(text)
            score = float(len(goal_tokens & tokens))
            if skill_id and row.get("skill_id") == skill_id:
                score += 3
            recipes = json.loads(row.get("tool_recipes_json") or "[]")
            for recipe in recipes:
                if str(recipe.get("tool") or "") in _SURFACE_TOOLS:
                    score += 2

            # Skip / downrank when a negative learning overlaps goal tokens for same skill.
            skip = False
            for neg_skill, neg_tokens in neg_token_sets:
                if not neg_tokens or not goal_tokens:
                    continue
                if skill_id and neg_skill and neg_skill != skill_id:
                    continue
                if not skill_id:
                    row_skill = str(row.get("skill_id") or "") or None
                    if neg_skill and row_skill and neg_skill != row_skill:
                        continue
                overlap = goal_tokens & neg_tokens
                if not overlap:
                    continue
                if len(overlap) >= 2:
                    skip = True
                    break
                score *= 0.35
            if skip:
                continue

            if score > 0 or not goal_tokens:
                scored.append((score, row))

        scored.sort(key=lambda x: (x[0], x[1].get("created_at") or ""), reverse=True)
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _, row in scored:
            key = str(row.get("user_goal") or row.get("id"))
            if key in seen:
                continue
            seen.add(key)
            recipes = json.loads(row.get("tool_recipes_json") or "[]")
            row = dict(row)
            row["tool_recipes"] = recipes
            out.append(row)
            if len(out) >= limit:
                break
        return out

    def format_learnings_for_prompt(self, learnings: list[dict[str, Any]]) -> str:
        if not learnings:
            return ""
        parts = [
            "Relevant learnings from past successful sessions (reuse patterns that worked):",
        ]
        for i, row in enumerate(learnings, 1):
            goal = (row.get("user_goal") or row.get("note") or "similar task").strip()
            parts.append(f"{i}. Goal: {goal[:220]}")
            recipes = row.get("tool_recipes") or []
            recipe_text = summarize_tool_recipes(recipes, limit=6)
            if recipe_text:
                parts.append(recipe_text)
            note = (row.get("note") or "").strip()
            if note and note != goal:
                parts.append(f"   Note: {note[:200]}")
        return "\n".join(parts)

    async def record_capability_gap(
        self,
        *,
        user_goal: str,
        missing_tools: list[str] | None = None,
        domain: str | None = None,
        chat_id: str | None = None,
        skill_id: str | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        """Record that an intent needed primitives we do not ship yet (no freeform exec)."""
        tools = [str(t) for t in (missing_tools or []) if t]
        entry = {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "skill_id": skill_id or (f"gap.{domain}" if domain else "gap.unspecified"),
            "rating": "gap",
            "note": (note or f"Missing primitives: {', '.join(tools) or 'unspecified'}")[:1000],
            "user_goal": (user_goal or "")[:500],
            "tool_recipes_json": json.dumps(
                [{"tool": t, "args": {}, "status": "missing"} for t in tools],
                ensure_ascii=False,
            ),
            "created_at": _now(),
        }
        await self.db.insert_learning(entry)
        return entry

    async def list_capability_gaps(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self.db.list_learnings(rating="gap", limit=limit)
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["tool_recipes"] = json.loads(row.get("tool_recipes_json") or "[]")
            except Exception:
                item["tool_recipes"] = []
            out.append(item)
        return out

    async def draft_skill_from_chat(
        self,
        skills,
        *,
        chat_id: str,
        name: str | None = None,
        description: str | None = None,
        base_skill_id: str | None = None,
    ) -> dict[str, Any]:
        messages = await self.db.list_messages(chat_id)
        if not messages:
            raise ValueError("Chat has no messages")

        chats = await self.db.list_chats()
        chat = next((c for c in chats if c["id"] == chat_id), None)
        title = (chat or {}).get("title") or "Learned skill"
        skill_name = (name or title).strip() or "Learned skill"
        if len(skill_name) > 80:
            skill_name = skill_name[:77] + "…"

        user_parts = [str(m.get("content") or "").strip() for m in messages if m.get("role") == "user"]
        assistant_parts = [
            str(m.get("content") or "").strip() for m in messages if m.get("role") == "assistant"
        ]
        recipes = extract_tool_recipes(messages)
        surface_edits = sum(1 for r in recipes if str(r.get("tool") or "") in _SURFACE_TOOLS)
        if surface_edits < 2:
            raise ValueError(
                "Chat needs at least 2 surface edits (mesh.ops/mesh.extrude/mesh.from_data) to promote a skill"
            )

        base_skill = skills.get(base_skill_id) if base_skill_id else None
        if not base_skill and chat:
            base_skill = skills.get(str(chat.get("skill_id") or ""))

        tools = list((base_skill or {}).get("tools") or [])
        if not tools:
            from blender_ai_sidecar.skills.engine import get_known_tools

            tools = [
                "scene.create_object",
                "mesh.from_data",
                "mesh.ops",
                "object.transform",
                "material.create",
                "material.assign",
                "particle.fur_set",
                "viewport.capture",
                "viewport.set_shading",
                "camera.set",
                "light.set",
                "world.set",
            ]
            tools = [t for t in tools if t in get_known_tools()]

        prompt_lines = [
            f"# Learned skill: {skill_name}",
            "",
            "This skill was promoted from a successful BlenderAI session.",
            "",
            "## User goals",
        ]
        for i, part in enumerate([p for p in user_parts if p][:12], 1):
            prompt_lines.append(f"{i}. {part}")

        if recipes:
            prompt_lines.extend(["", summarize_tool_recipes(recipes, limit=16)])

        if assistant_parts:
            prompt_lines.extend(["", "## Session guidance"])
            for part in assistant_parts[:6]:
                cleaned = re.sub(r"\[tool:[^\]]+\]", "", part).strip()
                if cleaned:
                    prompt_lines.append(cleaned[:500])

        prompt_lines.extend(
            [
                "",
                "## Rules learned",
                "- Reuse the tool sequence above when a similar request appears.",
                "- Verify characters from front, side, and back with viewport.capture views.",
                "- Use integrated silhouettes — avoid snowman stacks of loose spheres.",
                "- Finish with viewport.set_shading MATERIAL or RENDERED before claiming done.",
            ]
        )

        desc = (description or "").strip() or f"Learned from chat: {title}"
        method = infer_modeling_method(recipes)
        return {
            "id": "",
            "name": skill_name,
            "description": desc[:240],
            "method": method,
            "domains": (base_skill or {}).get("domains") or ["modeling"],
            "tools": tools,
            "prompt": "\n".join(prompt_lines).strip(),
            "risk": (base_skill or {}).get("risk") or "medium",
            "viewport_capture": (base_skill or {}).get("viewport_capture") or "optional",
            "max_steps": (base_skill or {}).get("max_steps") or 40,
        }
