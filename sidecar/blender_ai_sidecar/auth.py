"""Loopback auth for the sidecar HTTP/WS API.

Token is stored in SQLite settings and mirrored to ``%APPDATA%/BlenderAI/auth.json``
so the Blender extension and local MCP proxy can pick it up without a UI bootstrap.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, WebSocket
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from blender_ai_sidecar.config import get_settings

TOKEN_HEADER = "X-BlenderAI-Token"
TOKEN_QUERY = "token"
AUTH_FILE_NAME = "auth.json"


def auth_file_path() -> Path:
    return get_settings().data_dir / AUTH_FILE_NAME


def write_auth_file(token: str) -> None:
    path = auth_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"mcp_token": token, "token": token}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except Exception:
        pass


def read_auth_file() -> str:
    path = auth_file_path()
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(data.get("mcp_token") or data.get("token") or "").strip()


async def ensure_token(db: Any) -> str:
    """Ensure a durable token exists in DB + auth.json. Returns the plaintext token."""
    token = (await db.get_setting("mcp_token", "")).strip()
    if not token:
        token = read_auth_file()
    if not token:
        token = secrets.token_urlsafe(24)
    await db.set_setting("mcp_token", token)
    write_auth_file(token)
    return token


async def get_expected_token(db: Any | None = None) -> str:
    if db is not None:
        token = (await db.get_setting("mcp_token", "")).strip()
        if token:
            return token
    return read_auth_file() or (get_settings().mcp_token or "").strip()


def extract_token_from_headers(headers: Any) -> str:
    raw = headers.get(TOKEN_HEADER) or headers.get(TOKEN_HEADER.lower()) or ""
    if raw:
        return str(raw).strip()
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    auth = str(auth).strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def extract_token_from_request(request: Request) -> str:
    token = extract_token_from_headers(request.headers)
    if token:
        return token
    return str(request.query_params.get(TOKEN_QUERY) or "").strip()


def extract_token_from_ws(ws: WebSocket, hello: dict[str, Any] | None = None) -> str:
    token = extract_token_from_headers(ws.headers)
    if token:
        return token
    if hello:
        return str(hello.get("token") or hello.get("mcp_token") or "").strip()
    return str(ws.query_params.get(TOKEN_QUERY) or "").strip()


def is_loopback(host: str | None) -> bool:
    if not host:
        return False
    h = host.split("%", 1)[0].lower()
    return h in {"127.0.0.1", "::1", "localhost", "testclient"}


async def require_http_token(request: Request) -> str:
    """FastAPI dependency: require a valid local token for protected routes."""
    path = request.url.path
    if path == "/health" or path.startswith("/assets") or path in {"/", "/favicon.ico"}:
        return ""
    # Localhost-only bootstrap so same-origin WebUI can obtain the token once.
    if path == "/api/auth/session":
        return ""

    db = getattr(request.app.state, "db", None)
    expected = await get_expected_token(db)
    if not expected:
        # Fail closed once the control plane is up without a token.
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Auth token not configured")

    provided = extract_token_from_request(request)
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or missing BlenderAI token")
    return provided


async def require_ws_token(ws: WebSocket, hello: dict[str, Any] | None = None) -> str:
    db = getattr(ws.app.state, "db", None)
    expected = await get_expected_token(db)
    if not expected:
        await ws.close(code=4401)
        raise PermissionError("Auth token not configured")
    provided = extract_token_from_ws(ws, hello)
    if not provided or not secrets.compare_digest(provided, expected):
        await ws.close(code=4401)
        raise PermissionError("Invalid or missing BlenderAI token")
    return provided


def require_loopback_client(request: Request) -> None:
    client = request.client.host if request.client else None
    if not is_loopback(client):
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Loopback clients only")
