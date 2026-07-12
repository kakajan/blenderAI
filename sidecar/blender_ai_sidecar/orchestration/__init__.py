"""Per-run cancellation and lightweight run registry."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

RunState = Literal[
    "created",
    "planning",
    "generating",
    "tool_proposed",
    "confirm_wait",
    "tool_executing",
    "observing",
    "critique",
    "summarizing",
    "done",
    "cancelled",
    "failed",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunHandle:
    run_id: str
    session_id: str | None = None
    chat_id: str | None = None
    state: RunState = "created"
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    meta: dict[str, Any] = field(default_factory=dict)
    pending_confirm: dict[str, Any] | None = None
    confirm_event: asyncio.Event = field(default_factory=asyncio.Event)
    confirm_approved: bool = False

    def set_state(self, state: RunState) -> None:
        self.state = state
        self.updated_at = _now()


class RunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, RunHandle] = {}
        self._lock = asyncio.Lock()
        self._latest_by_session: dict[str, str] = {}

    async def create(
        self,
        *,
        session_id: str | None = None,
        chat_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> RunHandle:
        run_id = str(uuid.uuid4())
        handle = RunHandle(
            run_id=run_id,
            session_id=session_id,
            chat_id=chat_id,
            meta=meta or {},
        )
        async with self._lock:
            self._runs[run_id] = handle
            key = session_id or chat_id or "default"
            self._latest_by_session[key] = run_id
        return handle

    async def get(self, run_id: str) -> RunHandle | None:
        return self._runs.get(run_id)

    async def latest(self, session_id: str | None = None, chat_id: str | None = None) -> RunHandle | None:
        key = session_id or chat_id or "default"
        run_id = self._latest_by_session.get(key)
        if not run_id:
            # Fall back to most recently updated active run.
            active = [r for r in self._runs.values() if r.state not in {"done", "cancelled", "failed"}]
            if not active:
                return None
            active.sort(key=lambda r: r.updated_at, reverse=True)
            return active[0]
        return self._runs.get(run_id)

    async def request_stop(self, run_id: str | None = None) -> bool:
        async with self._lock:
            if run_id:
                handle = self._runs.get(run_id)
            else:
                handle = None
                for candidate in sorted(self._runs.values(), key=lambda r: r.updated_at, reverse=True):
                    if candidate.state not in {"done", "cancelled", "failed"}:
                        handle = candidate
                        break
            if handle is None or handle.cancel.is_set():
                return False
            handle.cancel.set()
            handle.set_state("cancelled")
            return True

    async def confirm(self, run_id: str, *, approved: bool = True) -> bool:
        handle = self._runs.get(run_id)
        if handle is None:
            return False
        handle.confirm_approved = approved
        handle.confirm_event.set()
        if not approved:
            handle.cancel.set()
            handle.set_state("cancelled")
        return True

    async def finish(self, run_id: str, state: RunState = "done") -> None:
        handle = self._runs.get(run_id)
        if handle:
            handle.set_state(state)

    def cancelled(self, handle: RunHandle | None) -> bool:
        return handle is not None and handle.cancel.is_set()


_REGISTRY: RunRegistry | None = None


def get_run_registry() -> RunRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = RunRegistry()
    return _REGISTRY


def reset_run_registry_for_tests() -> RunRegistry:
    global _REGISTRY
    _REGISTRY = RunRegistry()
    return _REGISTRY
