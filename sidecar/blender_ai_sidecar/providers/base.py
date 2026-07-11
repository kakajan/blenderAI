from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    id: str
    name: str | None = None
    provider_id: str | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None


class StreamEvent(BaseModel):
    type: str  # token | tool_call | error | done | status
    content: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class ChatProvider(Protocol):
    async def list_models(self) -> list[ModelInfo]: ...

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]: ...

    async def test_connection(self) -> dict[str, Any]: ...
