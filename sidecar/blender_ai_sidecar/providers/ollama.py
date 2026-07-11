from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from blender_ai_sidecar.providers.base import ChatRequest, ModelInfo, StreamEvent


class OllamaProvider:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", default_model: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def list_models(self) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            data = r.json()
        return [
            ModelInfo(id=m.get("name", ""), name=m.get("name"))
            for m in data.get("models", [])
            if m.get("name")
        ]

    async def test_connection(self) -> dict[str, Any]:
        try:
            models = await self.list_models()
            return {"ok": True, "message": f"Connected — {len(models)} models", "models": len(models)}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    async def chat_stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        model = req.model or self.default_model
        if not model:
            models = await self.list_models()
            if not models:
                yield StreamEvent(type="error", content="No Ollama model available")
                return
            model = models[0].id
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in req.messages],
            "stream": True,
            "options": {"temperature": req.temperature},
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    yield StreamEvent(type="error", content=body.decode("utf-8", errors="replace"))
                    return
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    import json

                    chunk = json.loads(line)
                    msg = chunk.get("message") or {}
                    token = msg.get("content") or ""
                    if token:
                        yield StreamEvent(type="token", content=token)
                    if chunk.get("done"):
                        yield StreamEvent(type="done")
                        return
        yield StreamEvent(type="done")
