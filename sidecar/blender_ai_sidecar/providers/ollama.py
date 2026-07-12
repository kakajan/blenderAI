from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from blender_ai_sidecar.providers.base import (
    ChatRequest,
    ModelInfo,
    StreamEvent,
    message_to_ollama_dict,
    model_info_with_caps,
)


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
            model_info_with_caps(
                model_id=m.get("name", ""),
                name=m.get("name"),
                provider_id="ollama",
                provider_kind="ollama",
            )
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
        # Do NOT send think=false. On gemma4:e4b (and similar) it yields eval tokens
        # with empty content+thinking. Omit the field and fall back to `thinking`
        # when the model streams reasoning-only (common for Gemma 4 / Qwen3).
        payload = {
            "model": model,
            "messages": [message_to_ollama_dict(m) for m in req.messages],
            "stream": True,
            "options": {"temperature": req.temperature},
        }
        got_content = False
        thinking_buf: list[str] = []
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

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = chunk.get("message") or {}
                    token = msg.get("content") or ""
                    thinking = msg.get("thinking") or msg.get("reasoning") or ""
                    if token:
                        got_content = True
                        yield StreamEvent(type="token", content=token)
                    elif thinking and not got_content:
                        # Buffer only — avoid mixing reasoning with a later content reply.
                        if not thinking_buf:
                            yield StreamEvent(type="status", content="Model thinking…")
                        thinking_buf.append(thinking)
                    if chunk.get("done"):
                        if not got_content and thinking_buf:
                            yield StreamEvent(type="token", content="".join(thinking_buf))
                        elif not got_content:
                            reason = chunk.get("done_reason") or "unknown"
                            # Soft signal — avoid hard "error" so the agent can synthesize
                            # a reply after tools and the N-Panel keeps reading until done.
                            yield StreamEvent(
                                type="status",
                                content=f"empty_model_response:{reason}",
                            )
                        yield StreamEvent(type="done")
                        return
        if not got_content and thinking_buf:
            yield StreamEvent(type="token", content="".join(thinking_buf))
        elif not got_content:
            yield StreamEvent(type="status", content="empty_model_response:unknown")
        yield StreamEvent(type="done")
