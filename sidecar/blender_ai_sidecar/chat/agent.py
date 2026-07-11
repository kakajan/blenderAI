from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from blender_ai_sidecar.bridge import protocol as bridge
from blender_ai_sidecar.providers.base import ChatMessage, ChatRequest, StreamEvent
from blender_ai_sidecar.providers.router import ProviderRouter
from blender_ai_sidecar.skills.engine import SkillEngine
from blender_ai_sidecar.store.db import Database

TOOL_RE = re.compile(r"```json\s*tool\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


class ChatAgent:
    def __init__(self, db: Database, router: ProviderRouter, skills: SkillEngine) -> None:
        self.db = db
        self.router = router
        self.skills = skills

    async def run_stream(
        self,
        *,
        provider_id: str,
        model: str | None,
        skill_id: str | None,
        user_message: str,
        chat_id: str | None = None,
        scene_summary: dict[str, Any] | None = None,
        local_only: bool = False,
        max_steps: int = 4,
    ) -> AsyncIterator[StreamEvent]:
        skill = self.skills.get(skill_id) if skill_id else None
        system_parts = [
            (skill or {}).get("system_prompt_text")
            or self.skills._load_prompt("presets/general/blender_assistant.md")
            or "You are BlenderAI."
        ]
        if scene_summary:
            system_parts.append("Scene summary:\n" + json.dumps(scene_summary, ensure_ascii=False)[:4000])
        if skill:
            system_parts.append(
                f"Active skill: {skill.get('id')}. Allowed tools: {', '.join(skill.get('tools') or [])}."
            )
            system_parts.append(
                'To call a tool, emit a fenced block:\n```json tool\n{"tool":"scene.create_object","args":{...}}\n```'
            )

        messages = [
            ChatMessage(role="system", content="\n\n".join(system_parts)),
            ChatMessage(role="user", content=user_message),
        ]

        now = datetime.now(timezone.utc).isoformat()
        if not chat_id:
            chat_id = str(uuid.uuid4())
            await self.db.create_chat(
                {
                    "id": chat_id,
                    "title": user_message[:60] or "Chat",
                    "provider_id": provider_id,
                    "model": model,
                    "skill_id": skill_id,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        await self.db.add_message(
            {
                "id": str(uuid.uuid4()),
                "chat_id": chat_id,
                "role": "user",
                "content": user_message,
                "created_at": now,
            }
        )
        yield StreamEvent(type="status", content="chat_ready", data={"chat_id": chat_id})

        assistant_text = ""
        for step in range(max_steps):
            req = ChatRequest(messages=messages, model=model)
            chunk_text = ""
            async for event in self.router.chat_stream(provider_id, req, local_only=local_only):
                if event.type == "token":
                    chunk_text += event.content
                    assistant_text += event.content
                    yield event
                elif event.type == "error":
                    yield event
                    return
                elif event.type == "done":
                    break
                else:
                    yield event

            tool_match = TOOL_RE.search(chunk_text)
            if not tool_match:
                break
            try:
                call = json.loads(tool_match.group(1))
            except json.JSONDecodeError:
                break
            tool = call.get("tool")
            args = call.get("args") or {}
            if tool not in bridge.ALLOWLIST:
                yield StreamEvent(type="error", content=f"Tool not allowlisted: {tool}")
                break
            yield StreamEvent(type="tool_call", content=tool, data={"args": args})
            result = await bridge.request_tool(tool, args)
            yield StreamEvent(type="status", content="tool_result", data=result)
            messages.append(ChatMessage(role="assistant", content=chunk_text))
            messages.append(
                ChatMessage(role="user", content="Tool result:\n" + json.dumps(result, ensure_ascii=False)[:3000])
            )
            assistant_text += f"\n[tool:{tool}]"
        else:
            pass

        await self.db.add_message(
            {
                "id": str(uuid.uuid4()),
                "chat_id": chat_id,
                "role": "assistant",
                "content": assistant_text,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        yield StreamEvent(type="done", data={"chat_id": chat_id})
