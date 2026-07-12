from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from blender_ai_sidecar.providers.base import ChatRequest, ModelInfo, StreamEvent, model_info_with_caps


class AnthropicProvider:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.anthropic.com",
        default_model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

    async def list_models(self) -> list[ModelInfo]:
        defaults = [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
        ]
        return [
            model_info_with_caps(model_id=m, name=m, provider_id="anthropic", provider_kind="anthropic")
            for m in defaults
        ]

    async def test_connection(self) -> dict[str, Any]:
        if not self.api_key:
            return {"ok": False, "message": "API key required"}
        try:
            payload = {
                "model": self.default_model or "claude-3-5-haiku-20241022",
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "ping"}],
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers=self._headers(),
                    json=payload,
                )
            if r.status_code >= 400:
                return {"ok": False, "message": r.text[:300]}
            return {"ok": True, "message": "Connected to Anthropic"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        model = req.model or self.default_model
        system = ""
        messages = []
        for m in req.messages:
            if m.role == "system":
                system = (system + "\n" + m.content).strip()
                continue
            if m.images:
                parts: list[dict[str, Any]] = [{"type": "text", "text": m.content or ""}]
                mime = (m.image_mime or "image/png").split("/")[-1]
                if mime == "jpg":
                    mime = "jpeg"
                for img in m.images:
                    raw = img.strip()
                    if "," in raw and raw.startswith("data:"):
                        raw = raw.split(",", 1)[1]
                    parts.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": m.image_mime or "image/png",
                                "data": raw,
                            },
                        }
                    )
                messages.append({"role": m.role, "content": parts})
            else:
                messages.append({"role": m.role, "content": m.content})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages or [{"role": "user", "content": "Hello"}],
            "max_tokens": req.max_tokens or 4096,
            "stream": True,
            "temperature": req.temperature,
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    yield StreamEvent(type="error", content=body.decode("utf-8", errors="replace"))
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    et = event.get("type")
                    if et == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            yield StreamEvent(type="token", content=delta.get("text") or "")
                    elif et == "message_stop":
                        yield StreamEvent(type="done")
                        return
        yield StreamEvent(type="done")
