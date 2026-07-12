from __future__ import annotations

from typing import Any, AsyncIterator

from blender_ai_sidecar.providers.base import ChatRequest, ModelInfo, StreamEvent, model_info_with_caps


CURSOR_MODELS = [
    model_info_with_caps(
        model_id="cursor-agent",
        name="Cursor Agent (MCP)",
        provider_id="cursor",
        provider_kind="cursor",
    ),
    model_info_with_caps(
        model_id="composer-2.5",
        name="Composer 2.5",
        provider_id="cursor",
        provider_kind="cursor",
    ),
]


class CursorProvider:
    """Delegated provider — the connected MCP client (Cursor) is the reasoning agent."""

    def __init__(self, *, provider_id: str = "cursor", default_model: str = "cursor-agent") -> None:
        self.provider_id = provider_id
        self.default_model = default_model

    async def list_models(self) -> list[ModelInfo]:
        return list(CURSOR_MODELS)

    async def test_connection(self) -> dict[str, Any]:
        return {
            "ok": True,
            "message": "Cursor Agent — reasoning runs in the connected MCP client (e.g. Cursor IDE).",
        }

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
        yield StreamEvent(
            type="error",
            content=(
                "Cursor Agent provider is for MCP clients. "
                "Call chat/execute_skill from Cursor with provider_id=cursor, "
                "then use invoke_tool to run Blender tools. "
                f"Last user message: {user[:200]}"
            ),
        )
        yield StreamEvent(type="done")
