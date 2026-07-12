"""Thin wrappers around RunRegistry for back-compat.

Prefer ``blender_ai_sidecar.orchestration.get_run_registry`` in new code.
"""

from __future__ import annotations

import asyncio

from blender_ai_sidecar.orchestration import get_run_registry

_lock = asyncio.Lock()
_current_run_id: str | None = None


async def arm() -> asyncio.Event:
    """Create a run and return its cancel event (legacy API)."""
    global _current_run_id
    handle = await get_run_registry().create(meta={"source": "chat_cancel.arm"})
    async with _lock:
        _current_run_id = handle.run_id
    return handle.cancel


async def disarm() -> None:
    global _current_run_id
    registry = get_run_registry()
    async with _lock:
        run_id = _current_run_id
        _current_run_id = None
    if run_id:
        await registry.finish(run_id, "done")


async def request_stop() -> bool:
    registry = get_run_registry()
    async with _lock:
        run_id = _current_run_id
    return await registry.request_stop(run_id)


def cancelled(event: asyncio.Event | None) -> bool:
    return event is not None and event.is_set()
