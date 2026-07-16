from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable

# Pending tool calls waiting for Blender addon response
_pending: dict[str, asyncio.Future] = {}
_blender_send: Callable[[dict[str, Any]], Awaitable[None]] | None = None
_blender_owner: int | None = None
_scene_cache: dict[str, Any] = {"connected": False, "summary": {}}

# HTTP long-poll fallback (no websocket-client required in Blender)
_http_owner: str | None = None
_http_last_seen: float = 0.0
_http_ttl: float = 12.0
_outbound: asyncio.Queue[dict[str, Any]] | None = None


def _get_outbound() -> asyncio.Queue[dict[str, Any]]:
    global _outbound
    if _outbound is None:
        _outbound = asyncio.Queue()
    return _outbound


def set_blender_sender(
    sender: Callable[[dict[str, Any]], Awaitable[None]] | None,
    *,
    owner: int | None = None,
) -> None:
    """Register the Blender WS sender. Pass owner=id(ws) so disconnects are scoped."""
    global _blender_send, _blender_owner
    _blender_send = sender
    _blender_owner = owner if sender is not None else None


def clear_blender_sender_if(owner: int) -> bool:
    """Clear sender/cache only if this connection still owns the bridge."""
    global _blender_send, _blender_owner
    if _blender_owner != owner:
        return False
    _blender_send = None
    _blender_owner = None
    # Keep connected=True if HTTP poll mode is still alive
    if not http_bridge_alive():
        _scene_cache["connected"] = False
    return True


def set_scene_cache(**kwargs: Any) -> None:
    _scene_cache.update(kwargs)


def get_scene_cache() -> dict[str, Any]:
    # Lazy expiry for HTTP bridge (poller stopped)
    if _http_owner and not http_bridge_alive() and _blender_send is None:
        _scene_cache["connected"] = False
    return dict(_scene_cache)


def http_bridge_alive() -> bool:
    if not _http_owner:
        return False
    return (time.monotonic() - _http_last_seen) < _http_ttl


def register_http_blender(owner: str) -> str:
    """Mark Blender as connected via HTTP poll. Returns owner token."""
    global _http_owner, _http_last_seen
    _http_owner = owner or str(uuid.uuid4())
    _http_last_seen = time.monotonic()
    _scene_cache["connected"] = True
    return _http_owner


def touch_http_blender(owner: str | None = None) -> bool:
    """Refresh HTTP poll heartbeat. False if owner mismatch / expired."""
    global _http_last_seen
    if not _http_owner:
        return False
    if owner and owner != _http_owner:
        return False
    if not http_bridge_alive() and owner != _http_owner:
        return False
    _http_last_seen = time.monotonic()
    _scene_cache["connected"] = True
    return True


def clear_http_blender(owner: str | None = None) -> bool:
    global _http_owner, _http_last_seen
    if owner and _http_owner and owner != _http_owner:
        return False
    _http_owner = None
    _http_last_seen = 0.0
    if _blender_send is None:
        _scene_cache["connected"] = False
    return True


def blender_transport_ready() -> bool:
    return _blender_send is not None or http_bridge_alive()


def bridge_transport() -> str:
    """Return active transport: ws | http | none."""
    if _blender_send is not None:
        return "ws"
    if http_bridge_alive():
        return "http"
    return "none"


# Per-tool round-trip timeouts (seconds). Default remains 30s.
TOOL_TIMEOUTS: dict[str, float] = {
    "python.run": 120.0,
    "asset.import": 60.0,
    "mesh.from_data": 60.0,
    "sculpt.remesh": 60.0,
    "mesh.loft_profiles": 60.0,
}


def timeout_for_tool(tool: str, override: float | None = None) -> float:
    if override is not None and override > 0:
        return float(override)
    return float(TOOL_TIMEOUTS.get(tool, 30.0))


async def request_tool(tool: str, args: dict[str, Any] | None = None, timeout: float | None = None) -> dict[str, Any]:
    if not blender_transport_ready():
        return {"ok": False, "error": "Blender not connected"}
    from blender_ai_sidecar.bridge.tool_args import normalize_tool_args

    raw_args = args or {}
    try:
        raw_args = normalize_tool_args(tool, raw_args)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    wait = timeout_for_tool(tool, timeout)
    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _pending[req_id] = fut
    msg = {"type": "tool_request", "id": req_id, "tool": tool, "args": raw_args}
    try:
        if _blender_send is not None:
            await _blender_send(msg)
        else:
            await _get_outbound().put(msg)
        return await asyncio.wait_for(fut, timeout=wait)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Tool timeout"}
    finally:
        _pending.pop(req_id, None)


async def poll_outbound(timeout: float = 2.0) -> dict[str, Any] | None:
    """HTTP long-poll: wait for the next outbound message for Blender."""
    try:
        return await asyncio.wait_for(_get_outbound().get(), timeout=max(0.1, timeout))
    except asyncio.TimeoutError:
        return None


def resolve_tool(req_id: str, result: dict[str, Any]) -> None:
    fut = _pending.get(req_id)
    if fut and not fut.done():
        fut.set_result(result)


def _allowlist_from_registry() -> set[str]:
    try:
        from blender_ai_sidecar.tools import get_registry

        return get_registry().allowlist()
    except Exception:
        # Minimal fallback if registry import fails during early bootstrap.
        return {
            "scene.summary",
            "viewport.capture",
            "undo",
            "redo",
            "scene.create_object",
            "mesh.from_data",
            "mesh.ops",
            "object.delete",
            "modifier.apply",
        }


# Back-compat alias — always derived from ToolRegistry.
ALLOWLIST = _allowlist_from_registry()
