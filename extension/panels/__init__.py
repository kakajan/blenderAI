_needs_reload = "bpy" in locals()

from . import main_panel

if _needs_reload:
    import importlib

    main_panel = importlib.reload(main_panel)


def register():
    main_panel.register()


def unregister():
    main_panel.unregister()
