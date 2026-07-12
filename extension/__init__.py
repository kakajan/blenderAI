# SPDX-License-Identifier: MIT
"""BlenderAI — View3D sidebar chat + live scene tools via local sidecar."""

from __future__ import annotations

_needs_reload = "bpy" in locals()

import bpy

from . import preferences
from . import chat_state
from . import settings_state
from . import chat_previews
from . import log_state
from . import panels
from . import operators
from .bridge import client as bridge_client
from .bridge import queue as tool_queue

if _needs_reload:
    import importlib

    preferences = importlib.reload(preferences)
    chat_state = importlib.reload(chat_state)
    settings_state = importlib.reload(settings_state)
    chat_previews = importlib.reload(chat_previews)
    log_state = importlib.reload(log_state)
    panels = importlib.reload(panels)
    operators = importlib.reload(operators)
    bridge_client = importlib.reload(bridge_client)
    tool_queue = importlib.reload(tool_queue)

MODULES = (preferences, chat_state, settings_state, chat_previews, log_state, operators, panels)


def register():
    for mod in MODULES:
        mod.register()
    tool_queue.register()
    bridge_client.register()


def unregister():
    from . import chat_http

    chat_http.cancel_stream()
    chat_http.unregister_timers()
    bridge_client.unregister()
    tool_queue.unregister()
    for mod in reversed(MODULES):
        mod.unregister()
