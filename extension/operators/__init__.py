_needs_reload = "bpy" in locals()

from . import (
    open_webui,
    open_providers,
    start_sidecar,
    stop_sidecar,
    capture_viewport,
    undo_ai,
    stop_generation,
    execute_tool,
    chat_send,
    chat_prompt_modal,
    chat_clear,
    logs,
    settings_ops,
)

if _needs_reload:
    import importlib

    open_webui = importlib.reload(open_webui)
    open_providers = importlib.reload(open_providers)
    start_sidecar = importlib.reload(start_sidecar)
    stop_sidecar = importlib.reload(stop_sidecar)
    capture_viewport = importlib.reload(capture_viewport)
    undo_ai = importlib.reload(undo_ai)
    stop_generation = importlib.reload(stop_generation)
    execute_tool = importlib.reload(execute_tool)
    chat_send = importlib.reload(chat_send)
    chat_prompt_modal = importlib.reload(chat_prompt_modal)
    chat_clear = importlib.reload(chat_clear)
    logs = importlib.reload(logs)
    settings_ops = importlib.reload(settings_ops)

MODULES = (
    open_webui,
    open_providers,
    start_sidecar,
    stop_sidecar,
    capture_viewport,
    undo_ai,
    stop_generation,
    execute_tool,
    chat_send,
    chat_prompt_modal,
    chat_clear,
    logs,
    settings_ops,
)


def register():
    for mod in MODULES:
        mod.register()


def unregister():
    for mod in reversed(MODULES):
        mod.unregister()
