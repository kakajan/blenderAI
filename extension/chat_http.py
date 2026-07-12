"""Sidecar chat HTTP/SSE client for the N-Panel (background thread + UI timer)."""

from __future__ import annotations

import json
import socket
import threading
import urllib.error
import urllib.request
from typing import Any

import bpy

from . import chat_state
from . import preferences
from .bridge import client as bridge_client
from .context import scene as scene_ctx

_lock = threading.Lock()
_cancel = threading.Event()
_thread: threading.Thread | None = None
_queue: list[tuple] = []
_timer_registered = False
_last_redraw = 0.0
_REDRAW_MIN_INTERVAL = 0.12
_FLUSH_INTERVAL = 0.1


def cancel_stream() -> None:
    _cancel.set()
    with _lock:
        _queue.append(("status", ""))
        _queue.append(("busy", False))
    # Also clear busy immediately (timer may be stalled)
    state = chat_state.get_chat()
    if state is not None:
        state.busy = False
        state.status_line = ""
    _ensure_timer()


def unregister_timers() -> None:
    """Called from addon unregister to avoid leaking the UI flush timer."""
    global _timer_registered
    if bpy.app.timers.is_registered(_flush_timer):
        bpy.app.timers.unregister(_flush_timer)
    _timer_registered = False


def is_streaming() -> bool:
    return _thread is not None and _thread.is_alive()


def _push(*events: tuple) -> None:
    with _lock:
        _queue.extend(events)
    _ensure_timer()


def _ensure_timer() -> None:
    global _timer_registered
    if _timer_registered and bpy.app.timers.is_registered(_flush_timer):
        return
    if not bpy.app.timers.is_registered(_flush_timer):
        bpy.app.timers.register(_flush_timer, first_interval=_FLUSH_INTERVAL)
    _timer_registered = True


def _tag_redraw(*, force: bool = False) -> None:
    global _last_redraw
    import time

    now = time.monotonic()
    if not force and (now - _last_redraw) < _REDRAW_MIN_INTERVAL:
        return
    _last_redraw = now
    for wm in bpy.data.window_managers:
        for window in wm.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()


def _flush_timer() -> float | None:
    global _timer_registered
    with _lock:
        events = _queue[:]
        _queue.clear()

    state = chat_state.get_chat()
    if state is None:
        # Timer context sometimes lacks window_manager — retry, do not drop events
        if events:
            with _lock:
                _queue[0:0] = events
            return 0.1
        _timer_registered = False
        return None

    # Coalesce consecutive token events into one append (fewer PropertyGroup writes).
    coalesced: list[tuple] = []
    token_buf = ""
    for ev in events:
        if ev[0] == "token":
            token_buf += str(ev[1])
            continue
        if token_buf:
            coalesced.append(("token", token_buf))
            token_buf = ""
        coalesced.append(ev)
    if token_buf:
        coalesced.append(("token", token_buf))

    for ev in coalesced:
        kind = ev[0]
        if kind == "busy":
            state.busy = bool(ev[1])
        elif kind == "status":
            state.status_line = str(ev[1])[:256]
        elif kind == "chat_id":
            state.chat_id = str(ev[1])
        elif kind == "user":
            image_path = str(ev[2]) if len(ev) > 2 else ""
            chat_state.append_message(state, "user", str(ev[1]), image_path=image_path)
        elif kind == "assistant_start":
            chat_state.append_message(state, "assistant", "")
        elif kind == "token":
            if state.messages:
                last = state.messages[-1]
                if last.role == "assistant":
                    last.text = (last.text + str(ev[1]))[: chat_state.MAX_MESSAGE_CHARS]
        elif kind == "replace_assistant":
            # Full text hydrate from history API
            text = str(ev[1])[: chat_state.MAX_MESSAGE_CHARS]
            if state.messages and state.messages[-1].role == "assistant":
                state.messages[-1].text = text
            else:
                chat_state.append_message(state, "assistant", text)
        elif kind == "error":
            chat_state.append_message(state, "error", str(ev[1]))
            state.busy = False
            state.status_line = ""
        elif kind == "done":
            state.busy = False
            state.status_line = ""

    force_redraw = any(ev[0] in ("done", "error", "busy", "user", "assistant_start") for ev in coalesced)
    _tag_redraw(force=force_redraw or bool(coalesced))

    if state.busy or is_streaming() or events:
        return _FLUSH_INTERVAL

    _timer_registered = False
    return None


def _http_json(url: str, payload: dict[str, Any] | None = None, method: str = "GET", timeout: float = 30.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = bridge_client.auth_headers({"Accept": "application/json"})
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_model(base: str, provider_id: str, preferred: str) -> str:
    """Use preference model if installed; else provider default; else first listed."""
    available: list[str] = []
    default_model = ""
    try:
        data = _http_json(f"{base}/api/providers", timeout=3.0)
        for p in data.get("providers") or []:
            if p.get("id") == provider_id and p.get("default_model"):
                default_model = str(p["default_model"])
                break
    except Exception:
        pass
    try:
        data = _http_json(f"{base}/api/providers/{provider_id}/models", timeout=5.0)
        for m in data.get("models") or []:
            mid = str(m.get("id") or m.get("name") or "")
            if mid:
                available.append(mid)
    except Exception:
        pass

    if preferred and (not available or preferred in available):
        return preferred
    if preferred and available and preferred not in available:
        # Stale N-Panel enum (model uninstalled) — fall back instead of hard-failing.
        pass
    if default_model and (not available or default_model in available):
        return default_model
    if available:
        return available[0]
    return preferred or default_model or ""


def _ensure_chat_id(base: str, state_chat_id: str, provider_id: str, model: str) -> str:
    if state_chat_id:
        return state_chat_id
    chat = _http_json(
        f"{base}/api/chats",
        {
            "title": "Blender N-Panel",
            "provider_id": provider_id or None,
            "model": model or None,
        },
        method="POST",
    )
    return str(chat.get("id") or "")


def _parse_sse_block(part: str) -> dict[str, Any] | None:
    """Extract JSON from an SSE block (handles optional event: lines)."""
    data_line = ""
    for line in part.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_line = line[5:].strip()
    if not data_line or data_line == "[DONE]":
        return None
    try:
        return json.loads(data_line)
    except json.JSONDecodeError:
        return None


def _stream_sse(url: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=bridge_client.auth_headers(
            {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
            }
        ),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        try:
            sock = resp.fp.raw._sock  # type: ignore[attr-defined]
            sock.settimeout(0.5)
        except Exception:
            pass

        buffer = ""
        while not _cancel.is_set():
            try:
                chunk = resp.read(1024)
            except (TimeoutError, socket.timeout):
                continue
            except Exception as exc:
                if "timed out" in str(exc).lower():
                    continue
                raise
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buffer:
                part, buffer = buffer.split("\n\n", 1)
                event = _parse_sse_block(part)
                if not event:
                    continue
                et = event.get("type")
                if et == "token":
                    _push(("token", event.get("content") or ""))
                elif et == "error":
                    # Do not abort the stream — the agent may still emit a recovery
                    # reply (e.g. after a successful tool) and a final "done".
                    err = event.get("content") or "Stream error"
                    _push(("replace_assistant", err), ("status", str(err)[:120]))
                elif et == "tool_call":
                    tool = event.get("content") or "tool"
                    _push(("status", f"Running {tool}…"))
                elif et == "status":
                    content = event.get("content") or ""
                    if content == "tool_result":
                        _push(("status", "Tool finished — writing reply…"))
                    elif content.startswith("empty_model_response"):
                        _push(("status", "Model returned no text — finishing…"))
                    elif content in ("Model thinking…", "thinking"):
                        _push(("status", "Model thinking…"))
                    elif content and content not in ("chat_ready",):
                        _push(("status", content))
                elif et == "done":
                    return


def _hydrate_assistant_from_history(base: str, chat_id: str) -> None:
    """If SSE tokens were missed, pull the saved assistant message from the DB."""
    if not chat_id:
        return
    try:
        data = _http_json(f"{base}/api/chats/{chat_id}/messages", timeout=10.0)
        messages = data.get("messages") or []
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and (msg.get("content") or "").strip():
                _push(("replace_assistant", msg["content"]))
                return
    except Exception:
        pass


def _wait_for_sidecar(base: str, attempts: int = 12, delay: float = 0.25) -> bool:
    """Poll /health on the worker thread (never call from the UI thread)."""
    import time

    for _ in range(attempts):
        if _cancel.is_set():
            return False
        try:
            req = urllib.request.Request(
                base + "/health",
                headers=bridge_client.auth_headers({"Accept": "application/json"}),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def _worker(
    base: str,
    message: str,
    provider_id: str,
    model: str,
    chat_id: str,
    summary: dict[str, Any] | None,
    image_path: str = "",
    skill_id: str = "",
    workflow_id: str = "",
) -> None:
    try:
        if not _wait_for_sidecar(base):
            from . import log_client

            log_client.error("Sidecar is offline", component="chat")
            _push(("error", "Sidecar is offline. Click Start in the N-Panel."), ("busy", False))
            return

        # Model resolution belongs here (HTTP) — never on the UI thread.
        model = resolve_model(base, provider_id, model)
        if model:
            _push(("status", f"Model: {model}"))

        new_id = _ensure_chat_id(base, chat_id, provider_id, model)
        if new_id and new_id != chat_id:
            _push(("chat_id", new_id))
            chat_id = new_id

        _push(("user", message, image_path), ("assistant_start",), ("status", "Generating…"))
        payload: dict[str, Any] = {
            "message": message,
            "provider_id": provider_id or "ollama",
            "model": model or None,
            "chat_id": new_id or None,
            "scene_summary": summary,
        }
        if skill_id and not workflow_id:
            payload["skill_id"] = skill_id
        if workflow_id:
            payload["workflow_id"] = workflow_id
        if image_path:
            try:
                import base64
                import os

                if os.path.isfile(image_path):
                    with open(image_path, "rb") as f:
                        payload["image_base64"] = base64.b64encode(f.read()).decode("ascii")
                    payload["image_mime"] = "image/png"
            except Exception:
                pass
        _stream_sse(f"{base}/api/chat/stream", payload)
        # Fallback: history may have the reply even if SSE tokens were dropped
        _hydrate_assistant_from_history(base, new_id or chat_id)

        if _cancel.is_set():
            _push(("status", ""), ("busy", False))
        else:
            _push(("done",), ("busy", False), ("status", ""))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        from . import log_client

        log_client.error(detail[:500] or str(exc), component="chat")
        _push(("error", detail[:500] or str(exc)), ("busy", False))
    except Exception as exc:
        from . import log_client

        log_client.exception(str(exc)[:500], exc, component="chat")
        _push(("error", str(exc)[:500]), ("busy", False))


def start_chat(context, message: str) -> tuple[bool, str]:
    """Start a chat stream. Returns (ok, error_message). Never blocks on HTTP."""
    global _thread

    text = (message or "").strip()
    state = chat_state.get_chat(context)
    if state is None:
        return False, "Chat state unavailable"

    image_path = (state.pending_image_path or "").strip()
    if not text and not image_path:
        return False, "Enter a prompt first"
    if not text and image_path:
        text = "Please look at this viewport capture."

    if state.busy or is_streaming():
        return False, "Already generating — press Stop first"

    if getattr(context.window_manager, "blender_ai_webui_active", False):
        return False, "WebUI is open — click Back to Blender first"

    prefs = preferences.get_prefs(context)
    settings = getattr(context.window_manager, "blender_ai_settings", None)
    base = bridge_client.base_url(context)

    # Prefer N-Panel settings enums; fall back to AddonPreferences.
    if settings and settings.provider_id:
        provider_id = settings.provider_id
    else:
        provider_id = (prefs.active_provider if prefs else "ollama") or "ollama"
    if settings is not None:
        model = settings.model_id or ""
    else:
        model = (prefs.active_model if prefs else "") or ""
    skill_id = (settings.skill_id if settings else "") or ""
    workflow_id = (settings.workflow_id if settings else "") or ""

    if prefs is not None:
        prefs.active_provider = provider_id
        prefs.active_model = model

    # Non-blocking: use bridge status; kick off start without waiting for /health.
    status = bridge_client.status_text()
    if status != "online":
        bridge_client.start_sidecar_process(context)

    summary = None
    try:
        summary = scene_ctx.build_summary(context)
    except Exception:
        summary = None

    _cancel.clear()
    state.busy = True
    state.status_line = "Sending…" if status == "online" else "Starting sidecar…"
    state.prompt = ""
    state.pending_image_path = ""

    chat_id = state.chat_id
    _thread = threading.Thread(
        target=_worker,
        args=(base, text, provider_id, model, chat_id, summary, image_path, skill_id, workflow_id),
        daemon=True,
        name="BlenderAI-chat",
    )
    _thread.start()
    _ensure_timer()
    return True, ""
