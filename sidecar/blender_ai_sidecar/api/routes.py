from __future__ import annotations

import json
import secrets as pysecrets
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from blender_ai_sidecar import __version__
from blender_ai_sidecar import app_log
from blender_ai_sidecar.auth import (
    ensure_token,
    extract_token_from_request,
    require_http_token,
    require_loopback_client,
    require_ws_token,
    write_auth_file,
)
from blender_ai_sidecar.bridge import protocol as bridge
from blender_ai_sidecar.config import get_settings as get_app_settings
from blender_ai_sidecar.orchestration import get_run_registry
from blender_ai_sidecar.policy import PolicyEngine, resolve_skill_tools
from blender_ai_sidecar.store import secrets

router = APIRouter()
# Token-gated HTTP API (WebSocket stays on ``router`` and authenticates on hello).
protected = APIRouter(dependencies=[Depends(require_http_token)])


def _attach_run_id(event: Any, run_id: str) -> Any:
    """Ensure streamed events carry run_id for observability / confirmation UX."""
    if not run_id or not hasattr(event, "type"):
        return event
    data = dict(getattr(event, "data", None) or {})
    if data.get("run_id") == run_id:
        return event
    data["run_id"] = run_id
    try:
        event.data = data
    except Exception:
        pass
    return event


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
    learning_enabled: bool | None = None
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
    max_steps: int | None = None
    image_base64: str | None = None
    image_mime: str = "image/png"
    critique_rounds: int | None = None
    workflow_id: str | None = None


class WorkflowRunBody(BaseModel):
    workflow_id: str
    message: str
    provider_id: str = "ollama"
    model: str | None = None
    chat_id: str | None = None
    scene_summary: dict[str, Any] | None = None
    max_steps_per_stage: int | None = None
    image_base64: str | None = None
    image_mime: str = "image/png"


class NewChat(BaseModel):
    title: str = "New chat"
    provider_id: str | None = None
    model: str | None = None
    skill_id: str | None = None
    project_path: str | None = None


class LogEntryIn(BaseModel):
    level: str = "info"
    source: str = "webui"
    component: str = ""
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class LogBatchIn(BaseModel):
    entries: list[LogEntryIn] = Field(default_factory=list)


class ReportIn(BaseModel):
    kind: str = "error"  # error | crash | feedback
    source: str = "webui"
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


def _app_state(request: Request):
    return request.app.state


@router.get("/health")
async def health(request: Request):
    cache = bridge.get_scene_cache()
    return {
        "ok": True,
        "version": __version__,
        "blender_connected": bool(cache.get("connected")),
        "bridge_transport": bridge.bridge_transport(),
        "scene_summary": cache.get("summary") or {},
    }


@router.get("/api/auth/session")
async def auth_session(request: Request):
    """Loopback-only bootstrap so WebUI can obtain the local token once."""
    require_loopback_client(request)
    # Prefer an already-presented token if the client sent one; otherwise ensure.
    existing = extract_token_from_request(request)
    db = _app_state(request).db
    token = existing or await ensure_token(db)
    if existing:
        # Keep DB/auth file in sync when client already has a token.
        expected = await ensure_token(db)
        if existing == expected:
            token = existing
        else:
            token = expected
    return {"ok": True, "token": token}


class BridgeHelloIn(BaseModel):
    owner: str | None = None
    summary: dict[str, Any] | None = None


class BridgePollIn(BaseModel):
    owner: str | None = None
    timeout: float = 2.0


class BridgeMessageIn(BaseModel):
    type: str
    id: str | None = None
    result: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    owner: str | None = None


@protected.post("/api/bridge/hello")
async def bridge_hello(body: BridgeHelloIn):
    """Register Blender over HTTP (fallback when WebSocket is unavailable)."""
    owner = bridge.register_http_blender(body.owner or str(uuid.uuid4()))
    if body.summary is not None:
        bridge.set_scene_cache(connected=True, summary=body.summary)
    return {"ok": True, "owner": owner, "connected": True}


@protected.post("/api/bridge/poll")
async def bridge_poll(body: BridgePollIn):
    """Long-poll for tool_request messages destined for Blender."""
    if body.owner:
        if not bridge.touch_http_blender(body.owner):
            # Stale / unknown owner — re-register
            owner = bridge.register_http_blender(body.owner)
        else:
            owner = body.owner
    else:
        owner = bridge.register_http_blender(str(uuid.uuid4()))
    msg = await bridge.poll_outbound(timeout=min(max(body.timeout, 0.1), 8.0))
    if msg is None:
        return {"ok": True, "owner": owner, "type": "idle"}
    return {"ok": True, "owner": owner, **msg}


@protected.post("/api/bridge/message")
async def bridge_message(body: BridgeMessageIn):
    """Receive tool_result / scene_summary from Blender over HTTP."""
    if body.owner:
        bridge.touch_http_blender(body.owner)
    msg_type = body.type
    if msg_type == "tool_result":
        bridge.resolve_tool(body.id or "", body.result or {})
        return {"ok": True}
    if msg_type == "scene_summary":
        bridge.set_scene_cache(connected=True, summary=body.summary or {})
        return {"ok": True}
    if msg_type == "goodbye":
        bridge.clear_http_blender(body.owner)
        return {"ok": True}
    return {"ok": False, "error": f"Unknown type: {msg_type}"}


class BridgeInvokeIn(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    timeout: float = 30.0
    confirmed: bool = False
    skill_id: str | None = None


class McpPrepareBody(BaseModel):
    message: str
    skill_id: str | None = None


@protected.post("/api/bridge/invoke")
async def bridge_invoke(body: BridgeInvokeIn, request: Request):
    """Invoke a Blender tool through the live bridge (localhost sidecar)."""
    state = _app_state(request)
    autonomy = await state.db.get_setting("autonomy", "ask")
    skill = state.skills.get(body.skill_id) if body.skill_id else None
    connected = bool(bridge.get_scene_cache().get("connected"))
    decision = PolicyEngine().decide(
        tool=body.tool,
        skill=skill,
        autonomy=autonomy,
        path="bridge",
        confirmed=body.confirmed,
        blender_connected=connected,
    )
    if decision.action == "confirm":
        return {
            "ok": False,
            "error": decision.reason or f"Confirmation required for {body.tool}",
            "error_code": "confirmation_required",
            "requires_confirmation": True,
        }
    if decision.action == "deny":
        return {
            "ok": False,
            "error": decision.reason or f"Tool denied: {body.tool}",
            "error_code": "denied",
        }
    return await bridge.request_tool(body.tool, body.args, timeout=min(max(body.timeout, 1.0), 60.0))


@protected.post("/api/mcp/prepare")
async def mcp_prepare(body: McpPrepareBody, request: Request):
    """Return skill + scene context for MCP clients using the Cursor delegated provider."""
    from blender_ai_sidecar.chat.agent import _tool_docs
    from blender_ai_sidecar.chat.modeling_strategy import format_strategy_for_prompt, plan_modeling_strategy

    state = _app_state(request)
    skill = state.skills.get(body.skill_id) if body.skill_id else None
    connected = bool(bridge.get_scene_cache().get("connected"))
    scene_summary = bridge.get_scene_cache().get("summary") or {}
    allowed = resolve_skill_tools(skill)

    system_parts = [
        (skill or {}).get("system_prompt_text")
        or state.skills._load_prompt("presets/general/blender_assistant.md")
        or "You are BlenderAI."
    ]
    if scene_summary:
        system_parts.append("Scene summary:\n" + json.dumps(scene_summary, ensure_ascii=False)[:6000])
    else:
        system_parts.append("Scene summary: unavailable (no live Blender scene cache).")

    modeling_strategy = plan_modeling_strategy(
        body.message,
        skill_id=body.skill_id,
        scene_summary=scene_summary,
    )
    strategy_text = format_strategy_for_prompt(modeling_strategy)
    if strategy_text:
        system_parts.append(strategy_text)

    try:
        from blender_ai_sidecar.learning.engine import LearningEngine

        learning = LearningEngine(state.db)
        learnings = await learning.find_relevant(
            user_goal=body.message,
            skill_id=body.skill_id,
            limit=3,
        )
        learning_text = learning.format_learnings_for_prompt(learnings)
        if learning_text:
            system_parts.append(learning_text)
    except Exception:
        pass

    if skill:
        system_parts.append(
            f"Active skill: {skill.get('id')}. Allowed tools ONLY: {', '.join(allowed)}. "
            "Do not call any other tool — the request will be rejected."
        )
    else:
        system_parts.append(f"Allowed tools: {', '.join(allowed)}.")

    system_parts.append(_tool_docs(allowed))
    if connected:
        system_parts.append("Bridge status: Blender is connected. Tools can run via invoke_tool.")
    else:
        system_parts.append(
            "Bridge status: Blender is NOT connected. Tools will fail until the N-Panel shows connected."
        )

    return {
        "ok": True,
        "mode": "delegated",
        "provider_id": "cursor",
        "skill_id": body.skill_id,
        "skill_name": (skill or {}).get("name"),
        "allowed_tools": allowed,
        "system_prompt": "\n\n".join(system_parts),
        "scene_summary": scene_summary,
        "user_message": body.message,
        "blender_connected": connected,
        "instructions": (
            "The MCP client (Cursor Agent) should call invoke_tool for each Blender tool. "
            "Emit one tool at a time and verify ok:true before continuing."
        ),
    }


@protected.get("/api/logs")
async def list_logs(
    request: Request,
    level: str | None = None,
    source: str | None = None,
    limit: int = 200,
):
    db = _app_state(request).db
    items = await db.list_logs(level=level, source=source, limit=limit)
    return {"logs": items}


@protected.post("/api/logs")
async def post_log(body: LogEntryIn, request: Request):
    db = _app_state(request).db
    entry = await app_log.emit(
        db,
        body.level,
        body.source,
        body.message,
        component=body.component,
        detail=body.detail,
    )
    return entry


@protected.post("/api/logs/batch")
async def post_logs_batch(body: LogBatchIn, request: Request):
    db = _app_state(request).db
    saved = []
    for item in body.entries[:100]:
        saved.append(
            await app_log.emit(
                db,
                item.level,
                item.source,
                item.message,
                component=item.component,
                detail=item.detail,
            )
        )
    return {"ok": True, "count": len(saved), "logs": saved}


@protected.delete("/api/logs")
async def clear_logs(request: Request):
    count = await _app_state(request).db.clear_logs()
    return {"ok": True, "deleted": count}


@protected.get("/api/reports")
async def list_reports(request: Request, limit: int = 50):
    items = await _app_state(request).db.list_reports(limit=limit)
    return {"reports": items}


@protected.get("/api/reports/{report_id}")
async def get_report(report_id: str, request: Request):
    from fastapi import HTTPException

    item = await _app_state(request).db.get_report(report_id)
    if not item:
        raise HTTPException(404, "Report not found")
    return item


@protected.post("/api/reports")
async def create_report(body: ReportIn, request: Request):
    db = _app_state(request).db
    # Config settings (not the /api/settings route handler).
    settings = get_app_settings()
    detail = dict(body.detail or {})
    if body.note:
        detail["user_note"] = body.note
    report = await app_log.create_report(
        db,
        settings.data_dir,
        kind=body.kind,
        source=body.source,
        summary=body.summary,
        detail=detail,
    )
    return report


@protected.get("/api/providers")
async def list_providers(request: Request):
    db = _app_state(request).db
    items = await db.list_providers()
    for p in items:
        key = secrets.get_api_key(p["id"])
        p["has_api_key"] = bool(key)
        p["api_key_masked"] = secrets.mask_key(key)
    return {"providers": items}


@protected.put("/api/providers")
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


@protected.post("/api/providers/{provider_id}/test")
async def test_provider(provider_id: str, request: Request):
    result = await _app_state(request).provider_router.test(provider_id)
    return result


@protected.get("/api/providers/{provider_id}/models")
async def provider_models(provider_id: str, request: Request):
    models = await _app_state(request).provider_router.list_models(provider_id)
    return {"models": [m.model_dump() for m in models]}


@protected.get("/api/settings")
async def api_get_settings(request: Request):
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
        "learning_enabled": (await db.get_setting("learning_enabled", "1")) == "1",
        "fallback_chain": chain,
        "default_provider_id": await db.get_setting("default_provider_id", "cursor"),
        "default_chat_model": await db.get_setting("default_chat_model", ""),
        "default_skill_model": await db.get_setting("default_skill_model", ""),
        "mcp_token_masked": secrets.mask_key(token) if token else "",
        "has_mcp_token": bool(token),
    }


@protected.put("/api/settings")
async def put_settings(body: SettingsUpdate, request: Request):
    db = _app_state(request).db
    data = body.model_dump(exclude_none=True)
    if data.pop("rotate_mcp_token", False):
        token = pysecrets.token_urlsafe(24)
        await db.set_setting("mcp_token", token)
        write_auth_file(token)
    if "mcp_token" in data:
        token = data.pop("mcp_token") or ""
        await db.set_setting("mcp_token", token)
        if token:
            write_auth_file(token)
    if "fallback_chain" in data:
        await db.set_setting("fallback_chain", json.dumps(data.pop("fallback_chain")))
    if "local_only" in data:
        await db.set_setting("local_only", "1" if data.pop("local_only") else "0")
    if "learning_enabled" in data:
        await db.set_setting("learning_enabled", "1" if data.pop("learning_enabled") else "0")
    for k, v in data.items():
        await db.set_setting(k, str(v))
    return await api_get_settings(request)


class SkillUpsert(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    domains: list[str] | str = Field(default_factory=lambda: ["custom"])
    tools: list[str] | str = Field(default_factory=list)
    prompt: str = ""
    risk: str = "medium"
    requires_confirmation: bool = False
    viewport_capture: str = "optional"
    version: int = 1


class PresetUpsert(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    category: str = "custom"
    prompt: str = ""
    steps: list[Any] | str | None = None


class PresetFromChat(BaseModel):
    chat_id: str | None = None
    messages: list[dict[str, Any]] | None = None
    name: str | None = None
    description: str | None = None
    category: str = "workflows"
    id: str | None = None
    save: bool = False


class LearningFeedbackBody(BaseModel):
    chat_id: str | None = None
    skill_id: str | None = None
    rating: str
    note: str = ""
    user_goal: str = ""


class CapabilityGapBody(BaseModel):
    user_goal: str
    missing_tools: list[str] = []
    domain: str | None = None
    chat_id: str | None = None
    skill_id: str | None = None
    note: str = ""


class SkillFromChatBody(BaseModel):
    chat_id: str
    name: str | None = None
    description: str | None = None
    base_skill_id: str | None = None
    save: bool = False


@protected.get("/api/skills")
async def list_skills(request: Request):
    from blender_ai_sidecar.skills.engine import get_known_tools

    skills = _app_state(request).skills.list()
    slim = []
    for s in skills:
        item = {k: v for k, v in s.items() if k not in {"system_prompt_text"}}
        item["has_prompt"] = bool(s.get("system_prompt_text"))
        item["source"] = s.get("source") or "bundled"
        item["editable"] = bool(s.get("editable"))
        slim.append(item)
    return {"skills": slim, "known_tools": get_known_tools()}


@protected.get("/api/skills/meta")
async def skills_meta():
    from blender_ai_sidecar.skills.engine import get_known_tools

    return {"known_tools": get_known_tools()}


@protected.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str, request: Request):
    skill = _app_state(request).skills.get(skill_id)
    if not skill:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Skill not found")
    return {
        "skill": {
            **{k: v for k, v in skill.items() if k != "_path"},
            "source": skill.get("source") or "bundled",
            "editable": bool(skill.get("editable")),
        }
    }


@protected.post("/api/skills")
async def create_skill(body: SkillUpsert, request: Request):
    from fastapi import HTTPException

    try:
        skill = _app_state(request).skills.save_user_skill(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"skill": {k: v for k, v in skill.items() if k != "_path"}}


@protected.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, body: SkillUpsert, request: Request):
    from fastapi import HTTPException

    data = body.model_dump()
    data["id"] = skill_id
    try:
        skill = _app_state(request).skills.save_user_skill(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"skill": {k: v for k, v in skill.items() if k != "_path"}}


@protected.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str, request: Request):
    from fastapi import HTTPException

    try:
        ok = _app_state(request).skills.delete_user_skill(skill_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"ok": True}


@protected.post("/api/skills/reload")
async def reload_skills(request: Request):
    skills = _app_state(request).skills.reload()
    return {"ok": True, "count": len(skills)}


@protected.get("/api/presets")
async def list_presets(request: Request):
    presets = _app_state(request).skills.list_presets()
    slim = []
    for p in presets:
        item = {k: v for k, v in p.items() if k not in {"_path", "prompt"}}
        prompt = str(p.get("prompt") or "")
        item["prompt_preview"] = prompt[:220]
        item["has_prompt"] = bool(prompt) or bool(p.get("steps"))
        slim.append(item)
    return {"presets": slim}


@protected.post("/api/presets/reload")
async def reload_presets(request: Request):
    presets = _app_state(request).skills.reload_presets()
    return {"ok": True, "count": len(presets)}


@protected.post("/api/presets/from-chat")
async def preset_from_chat(body: PresetFromChat, request: Request):
    from fastapi import HTTPException

    state = _app_state(request)
    messages = list(body.messages or [])
    title = (body.name or "").strip() or "Chat preset"

    if body.chat_id:
        chats = await state.db.list_chats()
        chat = next((c for c in chats if c["id"] == body.chat_id), None)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if not body.name:
            title = (chat.get("title") or title).strip() or title
        if not messages:
            messages = await state.db.list_messages(body.chat_id)

    if not messages:
        raise HTTPException(status_code=400, detail="No chat messages to convert")

    try:
        draft = state.skills.draft_preset_from_messages(
            title,
            messages,
            name=body.name,
            description=body.description,
            category=body.category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.id:
        draft["id"] = body.id

    if not body.save:
        return {"draft": draft}

    try:
        preset = state.skills.save_user_preset(draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"draft": draft, "preset": {k: v for k, v in preset.items() if k != "_path"}}


@protected.post("/api/presets")
async def create_preset(body: PresetUpsert, request: Request):
    from fastapi import HTTPException

    try:
        preset = _app_state(request).skills.save_user_preset(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"preset": {k: v for k, v in preset.items() if k != "_path"}}


@protected.get("/api/presets/{preset_id:path}")
async def get_preset(preset_id: str, request: Request):
    from fastapi import HTTPException

    preset = _app_state(request).skills.get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"preset": {k: v for k, v in preset.items() if k != "_path"}}


@protected.put("/api/presets/{preset_id:path}")
async def update_preset(preset_id: str, body: PresetUpsert, request: Request):
    from fastapi import HTTPException

    data = body.model_dump()
    data["id"] = preset_id
    try:
        preset = _app_state(request).skills.save_user_preset(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"preset": {k: v for k, v in preset.items() if k != "_path"}}


@protected.delete("/api/presets/{preset_id:path}")
async def delete_preset(preset_id: str, request: Request):
    from fastapi import HTTPException

    try:
        ok = _app_state(request).skills.delete_user_preset(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"ok": True}


@protected.post("/api/learnings/feedback")
async def learning_feedback(body: LearningFeedbackBody, request: Request):
    from fastapi import HTTPException

    from blender_ai_sidecar.learning.engine import LearningEngine

    try:
        entry = await LearningEngine(_app_state(request).db).record_feedback(
            chat_id=body.chat_id,
            skill_id=body.skill_id,
            rating=body.rating,
            note=body.note,
            user_goal=body.user_goal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "learning": entry}


@protected.get("/api/learnings/relevant")
async def learning_relevant(
    request: Request,
    user_goal: str = "",
    skill_id: str | None = None,
    limit: int = 5,
):
    from blender_ai_sidecar.learning.engine import LearningEngine

    rows = await LearningEngine(_app_state(request).db).find_relevant(
        user_goal=user_goal,
        skill_id=skill_id,
        limit=max(1, min(limit, 20)),
    )
    return {"learnings": rows}


@protected.post("/api/learnings/capability-gap")
async def learning_capability_gap(body: CapabilityGapBody, request: Request):
    from blender_ai_sidecar.learning.engine import LearningEngine

    entry = await LearningEngine(_app_state(request).db).record_capability_gap(
        user_goal=body.user_goal,
        missing_tools=body.missing_tools,
        domain=body.domain,
        chat_id=body.chat_id,
        skill_id=body.skill_id,
        note=body.note,
    )
    return {"ok": True, "gap": entry}


@protected.get("/api/learnings/capability-gaps")
async def learning_capability_gaps(request: Request, limit: int = 50):
    from blender_ai_sidecar.learning.engine import LearningEngine

    rows = await LearningEngine(_app_state(request).db).list_capability_gaps(
        limit=max(1, min(limit, 200))
    )
    return {"gaps": rows}


@protected.get("/api/knowledge/search")
async def knowledge_search(q: str = "", limit: int = 5, tags: str | None = None):
    from blender_ai_sidecar.knowledge import format_for_prompt, load_index, retrieve

    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    chunks = retrieve(q, limit=max(1, min(limit, 10)), tags=tag_list or None)
    return {
        "ok": True,
        "query": q,
        "api_url": load_index().get("api_url"),
        "chunks": chunks,
        "prompt_block": format_for_prompt(chunks),
    }


@protected.get("/api/learnings/tool-runs")
async def learning_tool_runs(
    request: Request,
    chat_id: str | None = None,
    skill_id: str | None = None,
    ok_only: bool = True,
    limit: int = 50,
):
    rows = await _app_state(request).db.list_tool_runs(
        chat_id=chat_id,
        skill_id=skill_id,
        ok_only=ok_only,
        limit=limit,
    )
    return {"tool_runs": rows}


@protected.delete("/api/learnings")
async def clear_learnings(request: Request, skill_id: str | None = None):
    count = await _app_state(request).db.clear_learnings(skill_id=skill_id)
    return {"ok": True, "deleted": count}


@protected.delete("/api/learnings/{learning_id}")
async def delete_learning(learning_id: str, request: Request):
    from fastapi import HTTPException

    ok = await _app_state(request).db.delete_learning(learning_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Learning not found")
    return {"ok": True}


@protected.post("/api/skills/from-chat")
async def skill_from_chat(body: SkillFromChatBody, request: Request):
    from fastapi import HTTPException

    from blender_ai_sidecar.evals import run_case
    from blender_ai_sidecar.evals import EvalCase
    from blender_ai_sidecar.learning.engine import LearningEngine

    state = _app_state(request)
    try:
        draft = await LearningEngine(state.db).draft_skill_from_chat(
            state.skills,
            chat_id=body.chat_id,
            name=body.name,
            description=body.description,
            base_skill_id=body.base_skill_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Lightweight promotion gate: draft must expose surface tools and pass a synthetic eval.
    draft_skill = {
        "id": draft.get("id") or "user.draft",
        "tools": draft.get("tools") or [],
        "domains": draft.get("domains") or ["modeling"],
    }
    gate = run_case(
        EvalCase(
            id="promote-gate",
            prompt=body.name or "promote",
            skill_id=str(draft_skill["id"]),
            forbidden_tools=[],
            required_tool_substring="mesh",
        ),
        draft_skill,
    )
    if not body.save:
        return {"draft": draft, "eval": {"ok": gate.ok, "errors": gate.errors, "allowed": gate.allowed}}

    if not gate.ok:
        raise HTTPException(
            status_code=400,
            detail={"message": "Promotion blocked by eval gate", "errors": gate.errors},
        )

    # Explicit human approval required — save=true is that approval signal.
    draft["provenance"] = {
        "promoted_from_chat": body.chat_id,
        "approved": True,
        "eval_ok": True,
    }
    try:
        skill = state.skills.save_user_skill(draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "draft": draft,
        "eval": {"ok": gate.ok, "errors": gate.errors},
        "skill": {k: v for k, v in skill.items() if k != "_path"},
    }


@protected.get("/api/chats")
async def list_chats(request: Request):
    return {"chats": await _app_state(request).db.list_chats()}


@protected.delete("/api/chats")
async def clear_chats(request: Request):
    count = await _app_state(request).db.clear_chats()
    return {"ok": True, "deleted": count}


@protected.post("/api/chats")
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


@protected.get("/api/chats/{chat_id}/messages")
async def chat_messages(chat_id: str, request: Request):
    return {"messages": await _app_state(request).db.list_messages(chat_id)}


class ChatStopBody(BaseModel):
    run_id: str | None = None


class RunConfirmBody(BaseModel):
    approved: bool = True


@protected.post("/api/chat/stop")
async def chat_stop(body: ChatStopBody = ChatStopBody()):
    registry = get_run_registry()
    stopped = await registry.request_stop(body.run_id)
    return {"ok": True, "stopped": stopped}


@protected.post("/api/runs/{run_id}/confirm")
async def confirm_run(run_id: str, body: RunConfirmBody):
    registry = get_run_registry()
    ok = await registry.confirm(run_id, approved=body.approved)
    return {"ok": ok}


@protected.post("/api/chat/stream")
async def chat_stream(body: ChatStreamBody, request: Request):
    state = _app_state(request)
    local_only = (await state.db.get_setting("local_only", "0")) == "1"
    registry = get_run_registry()

    async def gen():
        handle = await registry.create(
            chat_id=body.chat_id,
            meta={"kind": "workflow" if body.workflow_id else "chat_stream"},
        )
        cancel = handle.cancel
        try:
            if body.workflow_id:
                from blender_ai_sidecar.workflows import WorkflowRunner

                runner = WorkflowRunner(state.agent, state.skills)
                stream = runner.run_stream(
                    workflow_id=body.workflow_id,
                    user_message=body.message,
                    provider_id=body.provider_id,
                    model=body.model,
                    chat_id=body.chat_id,
                    scene_summary=body.scene_summary or bridge.get_scene_cache().get("summary"),
                    local_only=local_only,
                    image_base64=body.image_base64,
                    image_mime=body.image_mime or "image/png",
                    max_steps_per_stage=body.max_steps,
                    cancel=cancel,
                )
            else:
                stream = state.agent.run_stream(
                    provider_id=body.provider_id,
                    model=body.model,
                    skill_id=body.skill_id,
                    user_message=body.message,
                    chat_id=body.chat_id,
                    scene_summary=body.scene_summary or bridge.get_scene_cache().get("summary"),
                    local_only=local_only,
                    max_steps=body.max_steps,
                    image_base64=body.image_base64,
                    image_mime=body.image_mime or "image/png",
                    critique_rounds=body.critique_rounds,
                    cancel=cancel,
                    run_id=handle.run_id,
                )
            async for event in stream:
                event = _attach_run_id(event, handle.run_id)
                if event.type == "error":
                    await app_log.emit(
                        state.db,
                        "error",
                        "sidecar",
                        event.content or "Chat stream error",
                        component="chat",
                    )
                elif event.type == "status" and (event.content or "").startswith("empty_model_response"):
                    await app_log.emit(
                        state.db,
                        "warning",
                        "sidecar",
                        f"Model returned empty content ({event.content})",
                        component="chat",
                    )
                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as exc:
            await app_log.emit(
                state.db,
                "error",
                "sidecar",
                str(exc),
                component="chat",
                detail={"traceback": app_log.format_exception(exc)},
            )
            from blender_ai_sidecar.providers.base import StreamEvent

            err = StreamEvent(type="error", content=str(exc))
            yield f"data: {err.model_dump_json()}\n\n"
            await registry.finish(handle.run_id, "failed")
            return
        finally:
            if handle.state not in {"done", "cancelled", "failed"}:
                await registry.finish(handle.run_id, "done")

    return StreamingResponse(gen(), media_type="text/event-stream")


@protected.get("/api/workflows")
async def list_workflows(request: Request):
    presets = _app_state(request).skills.list_presets()
    workflows = []
    for p in presets:
        steps = p.get("steps")
        if not isinstance(steps, list) or not steps:
            continue
        workflows.append(
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "description": p.get("description") or "",
                "category": p.get("category"),
                "steps": [
                    {
                        "skill": s.get("skill") if isinstance(s, dict) else None,
                        "name": (s.get("name") if isinstance(s, dict) else None)
                        or (s.get("skill") if isinstance(s, dict) else None),
                        "prompt": (s.get("prompt") if isinstance(s, dict) else "") or "",
                    }
                    for s in steps
                    if isinstance(s, dict)
                ],
            }
        )
    return {"workflows": workflows}


@protected.post("/api/workflows/run")
async def run_workflow(body: WorkflowRunBody, request: Request):
    """SSE stream — same event format as /api/chat/stream."""
    state = _app_state(request)
    local_only = (await state.db.get_setting("local_only", "0")) == "1"
    from blender_ai_sidecar.workflows import WorkflowRunner

    runner = WorkflowRunner(state.agent, state.skills)
    registry = get_run_registry()

    async def gen():
        handle = await registry.create(chat_id=body.chat_id, meta={"kind": "workflow_run"})
        try:
            async for event in runner.run_stream(
                workflow_id=body.workflow_id,
                user_message=body.message,
                provider_id=body.provider_id,
                model=body.model,
                chat_id=body.chat_id,
                scene_summary=body.scene_summary or bridge.get_scene_cache().get("summary"),
                local_only=local_only,
                image_base64=body.image_base64,
                image_mime=body.image_mime or "image/png",
                max_steps_per_stage=body.max_steps_per_stage,
                cancel=handle.cancel,
            ):
                event = _attach_run_id(event, handle.run_id)
                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as exc:
            from blender_ai_sidecar.providers.base import StreamEvent

            err = StreamEvent(type="error", content=str(exc))
            yield f"data: {err.model_dump_json()}\n\n"
            await registry.finish(handle.run_id, "failed")
            return
        finally:
            if handle.state not in {"done", "cancelled", "failed"}:
                await registry.finish(handle.run_id, "done")

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    app = ws.app
    connection_id = id(ws)
    owns_blender_bridge = False
    authed = False

    async def send_to_blender(msg: dict[str, Any]) -> None:
        await ws.send_json(msg)

    # Only the Blender extension may own the tool sender — never a WebUI/other client.
    client_role = "ui"
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "hello":
                try:
                    await require_ws_token(ws, data)
                except PermissionError:
                    return
                authed = True
                client_role = data.get("role", "ui")
                if client_role == "blender":
                    bridge.set_scene_cache(connected=True)
                    bridge.set_blender_sender(send_to_blender, owner=connection_id)
                    owns_blender_bridge = True
                    await ws.send_json({"type": "hello_ack", "ok": True})
                else:
                    await ws.send_json({"type": "hello_ack", "ok": True, "role": client_role})
            elif not authed:
                await ws.send_json({"type": "error", "error": "Send hello with token first"})
            elif msg_type == "scene_summary":
                if client_role == "blender":
                    bridge.set_scene_cache(connected=True, summary=data.get("summary") or {})
            elif msg_type == "tool_result":
                if client_role == "blender":
                    bridge.resolve_tool(data.get("id", ""), data.get("result") or {})
            elif msg_type == "stop_generation":
                run_id = data.get("run_id")
                stopped = await get_run_registry().request_stop(run_id)
                await ws.send_json({"type": "stop_ack", "ok": True, "stopped": stopped})
            elif msg_type == "chat":
                registry = get_run_registry()
                handle = await registry.create(
                    chat_id=data.get("chat_id"),
                    meta={"kind": "ws_chat"},
                )
                local_only = (await app.state.db.get_setting("local_only", "0")) == "1"
                try:
                    async for event in app.state.agent.run_stream(
                        provider_id=data.get("provider_id") or "ollama",
                        model=data.get("model"),
                        skill_id=data.get("skill_id"),
                        user_message=data.get("message") or "",
                        chat_id=data.get("chat_id"),
                        scene_summary=data.get("scene_summary"),
                        local_only=local_only,
                        max_steps=data.get("max_steps"),
                        image_base64=data.get("image_base64"),
                        image_mime=data.get("image_mime") or "image/png",
                        critique_rounds=data.get("critique_rounds") or 0,
                        cancel=handle.cancel,
                    ):
                        await ws.send_json({"type": "chat_event", "event": event.model_dump()})
                finally:
                    if handle.state not in {"done", "cancelled", "failed"}:
                        await registry.finish(handle.run_id, "done")
            else:
                await ws.send_json({"type": "pong", "echo": msg_type})
    except WebSocketDisconnect:
        pass
    finally:
        # Only clear the global bridge if this connection still owns it
        # (a newer Blender WS may have taken over).
        if owns_blender_bridge:
            bridge.clear_blender_sender_if(connection_id)


# Mount token-gated HTTP routes onto the public router (WS stays unscoped).
router.include_router(protected)
