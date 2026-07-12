"""Path sandbox for file-loading Blender tools."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import bpy


def _blenderai_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", "")) / "BlenderAI"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BlenderAI"
    xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(xdg) / "BlenderAI"


def allowed_roots() -> list[Path]:
    """Approved roots for HDRI / reference / material image loads."""
    roots: list[Path] = []

    try:
        tempdir = getattr(bpy.app, "tempdir", None) or ""
        if tempdir:
            roots.append(Path(tempdir).resolve())
    except Exception:
        pass

    try:
        roots.append(_blenderai_data_dir().resolve())
    except Exception:
        pass

    try:
        blend = bpy.data.filepath or ""
        if blend:
            roots.append(Path(blend).resolve().parent)
    except Exception:
        pass

    try:
        pictures = Path.home() / "Pictures"
        if pictures.exists():
            roots.append(pictures.resolve())
    except Exception:
        pass

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def resolve_allowed_path(path: str | os.PathLike[str]) -> tuple[Path | None, str]:
    """Resolve ``path`` and ensure it stays under an allowed root.

    Returns ``(resolved_path, "")`` on success, or ``(None, error)`` on failure.
    """
    raw = str(path or "").strip()
    if not raw:
        return None, "Path required"

    try:
        candidate = Path(raw).expanduser()
        # Resolve symlinks / .. so traversal cannot escape roots.
        candidate = candidate.resolve(strict=False)
    except Exception as exc:
        return None, f"Invalid path: {exc}"

    for root in allowed_roots():
        try:
            candidate.relative_to(root)
            return candidate, ""
        except ValueError:
            continue

    return None, f"Path not allowed (outside approved roots): {raw}"


def require_allowed_file(path: str | os.PathLike[str]) -> tuple[str | None, dict | None]:
    """Return ``(resolved_str, None)`` or ``(None, {"ok": False, "error": ...})``."""
    resolved, err = resolve_allowed_path(path)
    if err:
        return None, {"ok": False, "error": err}
    assert resolved is not None
    if not resolved.is_file():
        return None, {"ok": False, "error": f"File not found: {path}"}
    return str(resolved), None
