from __future__ import annotations

import json
from typing import Any, AsyncIterator

from blender_ai_sidecar.providers.anthropic import AnthropicProvider
from blender_ai_sidecar.providers.base import ChatRequest, StreamEvent
from blender_ai_sidecar.providers.ollama import OllamaProvider
from blender_ai_sidecar.providers.openai_compatible import OpenAICompatibleProvider
from blender_ai_sidecar.store import secrets
from blender_ai_sidecar.store.db import Database


class ProviderRouter:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def build(self, provider_id: str):
        cfg = await self.db.get_provider(provider_id)
        if not cfg:
            raise KeyError(f"Unknown provider: {provider_id}")
        api_key = secrets.get_api_key(provider_id)
        kind = cfg["kind"]
        base_url = cfg.get("base_url") or ""
        model = cfg.get("default_model") or ""
        if kind == "ollama":
            return OllamaProvider(base_url=base_url or "http://127.0.0.1:11434", default_model=model)
        if kind == "anthropic":
            return AnthropicProvider(api_key=api_key, base_url=base_url or "https://api.anthropic.com", default_model=model)
        return OpenAICompatibleProvider(
            base_url=base_url or "https://api.openai.com/v1",
            api_key=api_key,
            default_model=model,
            provider_id=provider_id,
        )

    async def test(self, provider_id: str) -> dict[str, Any]:
        provider = await self.build(provider_id)
        return await provider.test_connection()

    async def list_models(self, provider_id: str):
        provider = await self.build(provider_id)
        models = await provider.list_models()
        for m in models:
            m.provider_id = provider_id
        return models

    async def fallback_ids(self) -> list[str]:
        raw = await self.db.get_setting("fallback_chain", "[]")
        try:
            data = json.loads(raw)
            return [str(x) for x in data]
        except json.JSONDecodeError:
            return []

    async def chat_stream(
        self,
        provider_id: str,
        req: ChatRequest,
        *,
        local_only: bool = False,
    ) -> AsyncIterator[StreamEvent]:
        chain = [provider_id] + [p for p in await self.fallback_ids() if p != provider_id]
        last_error = ""
        for pid in chain:
            cfg = await self.db.get_provider(pid)
            if not cfg or not cfg.get("enabled"):
                continue
            if local_only and cfg["kind"] != "ollama":
                continue
            try:
                provider = await self.build(pid)
                async for event in provider.chat_stream(req):
                    if event.type == "error":
                        last_error = event.content
                        break
                    yield event
                    if event.type == "done":
                        return
            except Exception as e:
                last_error = str(e)
                continue
        yield StreamEvent(type="error", content=last_error or "All providers failed")
        yield StreamEvent(type="done")
