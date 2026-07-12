from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from blender_ai_sidecar.providers.base import (
    ChatRequest,
    ModelInfo,
    StreamEvent,
    message_to_openai_dict,
    model_info_with_caps,
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        default_model: str = "",
        provider_id: str = "openai",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.provider_id = provider_id

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def list_models(self) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(f"{self.base_url}/models", headers=self._headers())
            r.raise_for_status()
            data = r.json()
        items = data.get("data") or data.get("models") or []
        kind = "openai" if self.provider_id == "openai" else "openai_compatible"
        out: list[ModelInfo] = []
        for m in items:
            mid = m.get("id") or m.get("name") or ""
            if mid:
                out.append(
                    model_info_with_caps(
                        model_id=mid,
                        name=mid,
                        provider_id=self.provider_id,
                        provider_kind=kind,
                    )
                )
        return out

    async def test_connection(self) -> dict[str, Any]:
        try:
            if not self.api_key and "127.0.0.1" not in self.base_url and "localhost" not in self.base_url:
                return {"ok": False, "message": "API key required"}
            models = await self.list_models()
            return {"ok": True, "message": f"Connected — {len(models)} models", "models": len(models)}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        model = req.model or self.default_model
        if not model:
            yield StreamEvent(type="error", content="No model selected")
            return
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message_to_openai_dict(m) for m in req.messages],
            "stream": True,
            "temperature": req.temperature,
        }
        if req.max_tokens:
            payload["max_tokens"] = req.max_tokens
        if req.tools:
            payload["tools"] = req.tools
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
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
                    if data == "[DONE]":
                        yield StreamEvent(type="done")
                        return
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    token = delta.get("content") or ""
                    if token:
                        yield StreamEvent(type="token", content=token)
                    tool_calls = delta.get("tool_calls")
                    if tool_calls:
                        yield StreamEvent(type="tool_call", data={"tool_calls": tool_calls})
        yield StreamEvent(type="done")
