from __future__ import annotations

import keyring

SERVICE = "BlenderAI"


def get_api_key(provider_id: str) -> str:
    return keyring.get_password(SERVICE, provider_id) or ""


def set_api_key(provider_id: str, api_key: str) -> None:
    if not api_key:
        try:
            keyring.delete_password(SERVICE, provider_id)
        except keyring.errors.PasswordDeleteError:
            pass
        return
    keyring.set_password(SERVICE, provider_id, api_key)


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "••••••••"
    return f"{api_key[:3]}••••{api_key[-4:]}"
