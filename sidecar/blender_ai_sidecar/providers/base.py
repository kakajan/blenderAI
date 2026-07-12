from __future__ import annotations

import re
from typing import Any, AsyncIterator, Literal, Protocol

from pydantic import BaseModel, Field

from blender_ai_sidecar.contracts import ProviderCapabilities

ToolCallingMode = Literal["none", "openai", "anthropic", "regex"]


class ModelInfo(BaseModel):
    id: str
    name: str | None = None
    provider_id: str | None = None
    supports_vision: bool = False
    tool_calling: ToolCallingMode = "regex"
    max_images: int = 0
    context_tokens: int | None = None


_VISION_OPENAI_RE = re.compile(
    r"(gpt-4o|gpt-4\.1|gpt-4-turbo|gpt-4-vision|o[13]|gemini|qwen[-_.]?vl|"
    r"llava|vision|claude-3|claude-sonnet-4|claude-opus-4|glm-4v|pixtral)",
    re.IGNORECASE,
)
_VISION_OLLAMA_RE = re.compile(
    r"(llava|bakllava|vision|moondream|minicpm-v|qwen2\.5-vl|gemma3)",
    re.IGNORECASE,
)


def infer_capabilities(provider_kind: str, model: str | None = None) -> ProviderCapabilities:
    """Infer vision / tool-calling capabilities from provider kind and model id."""
    kind = (provider_kind or "").strip().lower()
    mid = (model or "").strip().lower()

    if kind == "anthropic":
        return ProviderCapabilities(vision=True, tool_calling="anthropic", max_images=8)

    if kind == "cursor":
        return ProviderCapabilities(vision=False, tool_calling="none", max_images=0)

    if kind == "ollama":
        vision = bool(mid and _VISION_OLLAMA_RE.search(mid))
        return ProviderCapabilities(
            vision=vision,
            tool_calling="regex",
            max_images=4 if vision else 0,
        )

    # openai / openai_compatible / unknown cloud chat APIs
    if kind in {"openai", "openai_compatible"} or kind:
        vision = bool(mid and _VISION_OPENAI_RE.search(mid))
        # Strong multimodal models get a higher image budget.
        max_images = 8 if vision and re.search(r"(gpt-4o|gemini|qwen[-_.]?vl)", mid, re.I) else (4 if vision else 0)
        return ProviderCapabilities(
            vision=vision,
            tool_calling="openai",
            max_images=max_images,
        )

    return ProviderCapabilities()


def model_info_with_caps(
    *,
    model_id: str,
    name: str | None = None,
    provider_id: str | None = None,
    provider_kind: str,
) -> ModelInfo:
    caps = infer_capabilities(provider_kind, model_id)
    return ModelInfo(
        id=model_id,
        name=name or model_id,
        provider_id=provider_id,
        supports_vision=caps.vision,
        tool_calling=caps.tool_calling,
        max_images=caps.max_images,
        context_tokens=caps.context_tokens,
    )


class ChatMessage(BaseModel):
    role: str
    content: str
    # Optional vision attachments (base64 PNG/JPEG without data-URI prefix).
    images: list[str] | None = None
    # MIME for images, default image/png
    image_mime: str = "image/png"


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


def message_to_openai_dict(m: ChatMessage) -> dict[str, Any]:
    """Build OpenAI-compatible message payload, including vision content parts."""
    if not m.images:
        return {"role": m.role, "content": m.content}
    parts: list[dict[str, Any]] = [{"type": "text", "text": m.content or ""}]
    mime = m.image_mime or "image/png"
    for img in m.images:
        raw = img.strip()
        if raw.startswith("data:"):
            url = raw
        else:
            url = f"data:{mime};base64,{raw}"
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return {"role": m.role, "content": parts}


def message_to_ollama_dict(m: ChatMessage) -> dict[str, Any]:
    """Build Ollama chat message; images as raw base64 list when present."""
    out: dict[str, Any] = {"role": m.role, "content": m.content or ""}
    if m.images:
        cleaned = []
        for img in m.images:
            raw = img.strip()
            if "," in raw and raw.startswith("data:"):
                raw = raw.split(",", 1)[1]
            cleaned.append(raw)
        out["images"] = cleaned
    return out
