"""Preview icons for viewport captures shown in the N-Panel chat."""

from __future__ import annotations

import os

import bpy
import bpy.utils.previews

_pcoll = None
_MAX = 48


def register() -> None:
    global _pcoll
    if _pcoll is None:
        _pcoll = bpy.utils.previews.new()


def unregister() -> None:
    global _pcoll
    if _pcoll is not None:
        bpy.utils.previews.remove(_pcoll)
        _pcoll = None


def _key(path: str) -> str:
    return os.path.normpath(path).replace("\\", "/").lower()


def icon_id_for(path: str) -> int:
    """Return a UI icon id for an image file, or 0 if unavailable."""
    if not path or _pcoll is None:
        return 0
    if not os.path.isfile(path):
        return 0
    key = _key(path)
    if key not in _pcoll:
        if len(_pcoll) >= _MAX:
            for old in list(_pcoll.keys())[:12]:
                try:
                    del _pcoll[old]
                except Exception:
                    pass
        try:
            _pcoll.load(key, path, "IMAGE")
        except Exception:
            return 0
    try:
        return int(_pcoll[key].icon_id)
    except Exception:
        return 0


def invalidate(path: str) -> None:
    if not path or _pcoll is None:
        return
    key = _key(path)
    if key in _pcoll:
        try:
            del _pcoll[key]
        except Exception:
            pass
