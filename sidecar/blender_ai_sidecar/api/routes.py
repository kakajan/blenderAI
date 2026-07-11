from __future__ import annotations

import json
import secrets as pysecrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from blender_ai_sidecar import __version__
from blender_ai_sidecar.bridge import protocol as bridge
from blender_ai_sidecar.store import secrets

router = APIRouter()


class ProviderUpdate(BaseModel):
    id: str
    kind: str | None = None
    name: str | None = None
    enabled: bool | None = None
    base_url: str | None = None
    default_model: str | None = None
    api_key: str | None = None
    extra: dict[str, Any] | None = None
    sort_order: int | None = None


class SettingsUpdate(BaseModel):
    language: str | None = None
    ui_direction: str | None = None  # auto | ltr | rtl
    autonomy: str | None = None
    local_only: bool | None = None
    fallback_chain: list[str] | None = None
    default_provider_id: str | None = None
    default_chat_model: str | None = None
    default_skill_model: str | None = None
    mcp_token: str | None = None
    rotate_mcp_token: bool = False


class ChatStreamBody(BaseModel):
    message: str
    provider_id: str = "ollama"
    model: str | None = None
    skill_id: str | None = None
    chat_id: str | None = None
    scene_summary: dict[str, Any] | None = None


class NewChat(BaseModel):
    title: str = "New chat"
    provider_id: str | None = None
    model: str | None = None
    skill_id: str | None = None
    project_path: str | None = None


def _app_state(request: Request):
    return request.app.state


@router.get("/health")
async def health(request: Request):
    return {
        "ok": True,
        "version": __version__,
        "blender_connected": bridge.get_scene_cache().get("connected", False),
    }


@router.get("/api/providers")
async def list_providers(request: Request):
    db = _app_state(request).db
    items = await db.list_providers()
    for p in items:
        key = secrets.get_api_key(p["id"])
        p["has_api_key"] = bool(key)
        p["api_key_masked"] = secrets.mask_key(key)
    return {"providers": items}


@router.put("/api/providers")
async def put_provider(body: ProviderUpdate, request: Request):
    db = _app_state(request).db
    data = body.model_dump(exclude_none=True)
    api_key = data.pop("api_key", None)
    saved = await db.upsert_provider(data)
    if api_key is not None:
        secrets.set_api_key(body.id, api_key)
    key = secrets.get_api_key(body.id)
    saved["has_api_key"] = bool(key)
    saved["api_key_masked"] = secrets.mask_key(key)
    return saved


@router.post("/api/providers/{provider_id}/test")
async def test_provider(provider_id: str, request: Request):
    result = await _app_state(request).provider_router.test(provider_id)
    return result


@router.get("/api/providers/{provider_id}/models")
async def provider_models(provider_id: str, request: Request):
    models = await _app_state(request).provider_router.list_models(provider_id)
    return {"models": [m.model_dump() for m in models]}


@router.get("/api/settings")
async def get_settings(request: Request):
    db = _app_state(request).db
    raw_chain = await db.get_setting("fallback_chain", "[]")
    try:
        chain = json.loads(raw_chain)
    except json.JSONDecodeError:
        chain = []
    token = await db.get_setting("mcp_token", "")
    return {
        "language": await db.get_setting("language", "en"),
        "ui_direction": await db.get_setting("ui_direction", "auto"),
        "autonomy": await db.get_setting("autonomy", "ask"),
        "local_only": (await db.get_setting("local_only", "0")) == "1",
        "fallback_chain": chain,
        "default_provider_id": await db.get_setting("default_provider_id", "ollama"),
        "default_chat_model": await db.get_setting("default_chat_model", ""),
        "default_skill_model": await db.get_setting("default_skill_model", ""),
        "mcp_token_masked": secrets.mask_key(token) if token else "",
        "has_mcp_token": bool(token),
    }


@router.put("/api/settings")
async def put_settings(body: SettingsUpdate, request: Request):
    db = _app_state(request).db
    data = body.model_dump(exclude_none=True)
    if data.pop("rotate_mcp_token", False):
        token = pysecrets.token_urlsafe(24)
        await db.set_setting("mcp_token", token)
    if "mcp_token" in data:
        await db.set_setting("mcp_token", data.pop("mcp_token") or "")
    if "fallback_chain" in data:
        await db.set_setting("fallback_chain", json.dumps(data.pop("fallback_chain")))
    if "local_only" in data:
        await db.set_setting("local_only", "1" if data.pop("local_only") else "0")
    for k, v in data.items():
        await db.set_setting(k, str(v))
    return await get_settings(request)


@router.get("/api/skills")
async def list_skills(request: Request):
    skills = _app_state(request).skills.list()
    # strip huge prompts in list view
    slim = []
    for s in skills:
        item = {k: v for k, v in s.items() if k != "system_prompt_text"}
        item["has_prompt"] = bool(s.get("system_prompt_text"))
        slim.append(item)
    return {"skills": slim}


@router.get("/api/presets")
async def list_presets(request: Request):
    return {"presets": _app_state(request).skills.list_presets()}


@router.get("/api/chats")
async def list_chats(request: Request):
    return {"chats": await _app_state(request).db.list_chats()}


@router.post("/api/chats")
async def create_chat(body: NewChat, request: Request):
    now = datetime.now(timezone.utc).isoformat()
    chat = {
        "id": str(uuid.uuid4()),
        "title": body.title,
        "project_path": body.project_path,
        "provider_id": body.provider_id,
        "model": body.model,
        "skill_id": body.skill_id,
        "created_at": now,
        "updated_at": now,
    }
    await _app_state(request).db.create_chat(chat)
    return chat


@router.get("/api/chats/{chat_id}/messages")
async def chat_messages(chat_id: str, request: Request):
    return {"messages": await _app_state(request).db.list_messages(chat_id)}


@router.post("/api/chat/stream")
async def chat_stream(body: ChatStreamBody, request: Request):
    state = _app_state(request)
    local_only = (await state.db.get_setting("local_only", "0")) == "1"

    async def gen():
        async for event in state.agent.run_stream(
            provider_id=body.provider_id,
            model=body.model,
            skill_id=body.skill_id,
            user_message=body.message,
            chat_id=body.chat_id,
            scene_summary=body.scene_summary or bridge.get_scene_cache().get("summary"),
            local_only=local_only,
        ):
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    app = ws.app

    async def send_to_blender(msg: dict[str, Any]) -> None:
        await ws.send_json(msg)

    # Prefer blender clients identifying themselves
    client_role = "ui"
    try:
        bridge.set_blender_sender(send_to_blender)
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "hello":
                client_role = data.get("role", "ui")
                if client_role == "blender":
                    bridge.set_scene_cache(connected=True)
                    bridge.set_blender_sender(send_to_blender)
                    await ws.send_json({"type": "hello_ack", "ok": True})
            elif msg_type == "scene_summary":
                bridge.set_scene_cache(connected=True, summary=data.get("summary") or {})
            elif msg_type == "tool_result":
                bridge.resolve_tool(data.get("id", ""), data.get("result") or {})
            elif msg_type == "chat":
                local_only = (await app.state.db.get_setting("local_only", "0")) == "1"
                async for event in app.state.agent.run_stream(
                    provider_id=data.get("provider_id") or "ollama",
                    model=data.get("model"),
                    skill_id=data.get("skill_id"),
                    user_message=data.get("message") or "",
                    chat_id=data.get("chat_id"),
                    scene_summary=data.get("scene_summary"),
                    local_only=local_only,
                ):
                    await ws.send_json({"type": "chat_event", "event": event.model_dump()})
            else:
                await ws.send_json({"type": "pong", "echo": msg_type})
    except WebSocketDisconnect:
        if client_role == "blender":
            bridge.set_scene_cache(connected=False)
            bridge.set_blender_sender(None)
