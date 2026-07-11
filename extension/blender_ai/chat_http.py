"""Sidecar chat HTTP/SSE client for the N-Panel (background thread + UI timer)."""

from __future__ import annotations

import json
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


def cancel_stream() -> None:
    _cancel.set()
    with _lock:
        _queue.append(("status", "Stopping…"))
        _queue.append(("busy", False))
    _ensure_timer()


def is_streaming() -> bool:
    return _thread is not None and _thread.is_alive()


def _push(*events: tuple) -> None:
    with _lock:
        _queue.extend(events)
    _ensure_timer()


def _ensure_timer() -> None:
    global _timer_registered
    if _timer_registered:
        return
    if not bpy.app.timers.is_registered(_flush_timer):
        bpy.app.timers.register(_flush_timer, first_interval=0.05)
    _timer_registered = True


def _tag_redraw() -> None:
    wm = bpy.context.window_manager
    if wm is None:
        return
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
        _timer_registered = False
        return None

    for ev in events:
        kind = ev[0]
        if kind == "busy":
            state.busy = bool(ev[1])
        elif kind == "status":
            state.status_line = str(ev[1])[:256]
        elif kind == "chat_id":
            state.chat_id = str(ev[1])
        elif kind == "user":
            chat_state.append_message(state, "user", str(ev[1]))
        elif kind == "assistant_start":
            chat_state.append_message(state, "assistant", "")
        elif kind == "token":
            if state.messages:
                last = state.messages[-1]
                if last.role == "assistant":
                    last.text = (last.text + str(ev[1]))[: chat_state.MAX_MESSAGE_CHARS]
        elif kind == "error":
            chat_state.append_message(state, "error", str(ev[1]))
            state.busy = False
            state.status_line = "Error"
        elif kind == "done":
            state.busy = False
            state.status_line = "Ready"

    _tag_redraw()

    if state.busy or is_streaming() or events:
        return 0.1

    _timer_registered = False
    return None


def _http_json(url: str, payload: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
    )
    return str(chat.get("id") or "")


def _stream_sse(url: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        # Prefer short socket timeouts so cancel can interrupt between chunks.
        try:
            sock = resp.fp.raw._sock  # type: ignore[attr-defined]
            sock.settimeout(0.5)
        except Exception:
            pass

        buffer = ""
        while not _cancel.is_set():
            try:
                chunk = resp.read(512)
            except TimeoutError:
                continue
            except Exception as exc:
                # Some platforms raise socket.timeout
                if "timed out" in str(exc).lower():
                    continue
                raise
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buffer:
                part, buffer = buffer.split("\n\n", 1)
                line = part.strip()
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                et = event.get("type")
                if et == "token":
                    _push(("token", event.get("content") or ""))
                elif et == "error":
                    _push(("error", event.get("content") or "Stream error"))
                    return
                elif et == "status":
                    _push(("status", event.get("content") or ""))
                elif et == "done":
                    return


def _worker(base: str, message: str, provider_id: str, model: str, chat_id: str, summary: dict[str, Any] | None) -> None:
    try:
        if not bridge_client.health_ok():
            # health_ok needs context sometimes — try URL directly
            try:
                with urllib.request.urlopen(base + "/health", timeout=2.0) as resp:
                    if resp.status != 200:
                        raise RuntimeError("Sidecar offline")
            except Exception:
                _push(("error", "Sidecar is offline. Click Start in the N-Panel."), ("busy", False))
                return

        new_id = _ensure_chat_id(base, chat_id, provider_id, model)
        if new_id and new_id != chat_id:
            _push(("chat_id", new_id))

        _push(("user", message), ("assistant_start",), ("status", "Generating…"))
        _stream_sse(
            f"{base}/api/chat/stream",
            {
                "message": message,
                "provider_id": provider_id or "ollama",
                "model": model or None,
                "chat_id": new_id or None,
                "scene_summary": summary,
            },
        )
        if _cancel.is_set():
            _push(("status", "Stopped"), ("busy", False))
        else:
            _push(("done",), ("busy", False), ("status", "Ready"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(exc)
        _push(("error", detail[:500] or str(exc)), ("busy", False))
    except Exception as exc:
        _push(("error", str(exc)[:500]), ("busy", False))


def start_chat(context, message: str) -> tuple[bool, str]:
    """Start a chat stream. Returns (ok, error_message)."""
    global _thread

    text = (message or "").strip()
    if not text:
        return False, "Enter a prompt first"

    state = chat_state.get_chat(context)
    if state is None:
        return False, "Chat state unavailable"
    if state.busy or is_streaming():
        return False, "Already generating"

    prefs = preferences.get_prefs(context)
    base = bridge_client.base_url(context)
    provider_id = (prefs.active_provider if prefs else "ollama") or "ollama"
    model = (prefs.active_model if prefs else "") or ""

    if not bridge_client.health_ok(context):
        bridge_client.start_sidecar_process(context)
        if not bridge_client.health_ok(context):
            return False, "Sidecar offline — click Start"

    summary = None
    try:
        summary = scene_ctx.build_summary(context)
    except Exception:
        summary = None

    _cancel.clear()
    state.busy = True
    state.status_line = "Sending…"
    state.prompt = ""

    chat_id = state.chat_id
    _thread = threading.Thread(
        target=_worker,
        args=(base, text, provider_id, model, chat_id, summary),
        daemon=True,
    )
    _thread.start()
    _ensure_timer()
    return True, ""
