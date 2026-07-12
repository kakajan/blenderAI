from __future__ import annotations

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE = "BlenderAI"

# Used when no OS keyring backend is available (e.g. headless CI).
_memory: dict[str, str] = {}


def get_api_key(provider_id: str) -> str:
    try:
        return keyring.get_password(SERVICE, provider_id) or ""
    except KeyringError:
        return _memory.get(provider_id, "")


def set_api_key(provider_id: str, api_key: str) -> None:
    if not api_key:
        try:
            keyring.delete_password(SERVICE, provider_id)
        except (PasswordDeleteError, KeyringError):
            pass
        _memory.pop(provider_id, None)
        return
    try:
        keyring.set_password(SERVICE, provider_id, api_key)
        _memory.pop(provider_id, None)
    except KeyringError:
        _memory[provider_id] = api_key


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "••••••••"
    return f"{api_key[:3]}••••{api_key[-4:]}"
