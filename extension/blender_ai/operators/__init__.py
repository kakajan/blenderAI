from . import (
    open_webui,
    open_providers,
    start_sidecar,
    stop_sidecar,
    capture_viewport,
    undo_ai,
    stop_generation,
    execute_tool,
)

MODULES = (
    open_webui,
    open_providers,
    start_sidecar,
    stop_sidecar,
    capture_viewport,
    undo_ai,
    stop_generation,
    execute_tool,
)


def register():
    for mod in MODULES:
        mod.register()


def unregister():
    for mod in reversed(MODULES):
        mod.unregister()
