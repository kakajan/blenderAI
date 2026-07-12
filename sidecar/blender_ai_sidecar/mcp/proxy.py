from __future__ import annotations

import json
from typing import Any

import httpx

from blender_ai_sidecar.auth import TOKEN_HEADER, read_auth_file
from blender_ai_sidecar.config import get_settings


def _base_url() -> str:
    settings = get_settings()
    return f"http://{settings.host}:{settings.port}"


def _auth_headers() -> dict[str, str]:
    token = read_auth_file().strip()
    if not token:
        token = (get_settings().mcp_token or "").strip()
    if not token:
        return {}
    return {TOKEN_HEADER: token}


def resolve_mcp_provider(provider_id: str | None) -> str:
    """MCP chat/execute_skill default to the Cursor delegated provider."""
    pid = (provider_id or "").strip()
    if not pid or pid in {"cursor", "cursor-agent", "default", "auto"}:
        return "cursor"
    return pid


async def sidecar_reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{_base_url()}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def get_status() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_base_url()}/health")
            resp.raise_for_status()
            data = resp.json()
            return {
                "sidecar_online": True,
                "connected": bool(data.get("blender_connected")),
                "bridge_transport": data.get("bridge_transport", "none"),
                "version": data.get("version"),
                "summary": data.get("scene_summary") or {},
            }
    except httpx.ConnectError:
        return {
            "sidecar_online": False,
            "connected": False,
            "error": "Sidecar not running. Open Blender with BlenderAI enabled (N-Panel).",
        }
    except Exception as exc:
        return {"sidecar_online": False, "connected": False, "error": str(exc)}


async def invoke_tool(
    tool: str,
    args: dict[str, Any] | None = None,
    timeout: float = 30.0,
    *,
    confirmed: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"tool": tool, "args": args or {}, "timeout": timeout}
    if confirmed:
        payload["confirmed"] = True
    try:
        async with httpx.AsyncClient(timeout=timeout + 5.0) as client:
            resp = await client.post(
                f"{_base_url()}/api/bridge/invoke",
                json=payload,
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"ok": False, "error": "Sidecar not running. Open Blender with BlenderAI enabled."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def prepare_delegate(
    message: str,
    *,
    skill_id: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": message}
    if skill_id:
        payload["skill_id"] = skill_id
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{_base_url()}/api/mcp/prepare",
                json=payload,
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"ok": False, "error": "Sidecar not running. Open Blender with BlenderAI enabled."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def chat_turn(
    message: str,
    *,
    skill_id: str | None = None,
    provider_id: str | None = None,
    timeout: float = 300.0,
) -> dict[str, Any]:
    provider_id = resolve_mcp_provider(provider_id)
    if provider_id == "cursor":
        return await prepare_delegate(message, skill_id=skill_id, timeout=min(timeout, 60.0))

    payload: dict[str, Any] = {"message": message, "provider_id": provider_id}
    if skill_id:
        payload["skill_id"] = skill_id
    text_parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{_base_url()}/api/chat/stream",
                json=payload,
                headers=_auth_headers(),
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    return {"ok": False, "error": body.decode("utf-8", errors="replace")[:500]}
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        for line in block.splitlines():
                            if not line.startswith("data:"):
                                continue
                            raw = line[5:].strip()
                            if not raw:
                                continue
                            try:
                                event = json.loads(raw)
                            except json.JSONDecodeError:
                                continue
                            etype = event.get("type")
                            if etype == "token":
                                text_parts.append(event.get("content") or "")
                            elif etype == "error":
                                return {"ok": False, "error": event.get("content") or "Chat error"}
        return {"ok": True, "text": "".join(text_parts)}
    except httpx.ConnectError:
        return {"ok": False, "error": "Sidecar not running. Open Blender with BlenderAI enabled."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
