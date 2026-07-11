bl_info = {
    "name": "BlenderAI",
    "author": "BlenderAI",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > BlenderAI",
    "description": "Professional multi-provider AI assistant for Blender",
    "category": "Interface",
}

from . import preferences
from . import chat_state
from . import panels
from . import operators
from .bridge import client as bridge_client
from .bridge import queue as tool_queue


MODULES = (preferences, chat_state, operators, panels)


def register():
    for mod in MODULES:
        mod.register()
    tool_queue.register()
    bridge_client.register()


def unregister():
    from . import chat_http

    chat_http.cancel_stream()
    bridge_client.unregister()
    tool_queue.unregister()
    for mod in reversed(MODULES):
        mod.unregister()
