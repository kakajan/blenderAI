---
name: blender-addon-api
description: >-
  Write Blender Python add-ons/extensions with correct bpy register/unregister,
  AddonPreferences via __package__, relative imports, timers, online_access, and
  extension guidelines. Use when editing Blender operators, panels, PropertyGroups,
  preferences, bpy.app.timers, or converting legacy bl_info add-ons to extensions.
---

# Blender Add-on Python API

Sources: [Extensions add-ons manual](https://docs.blender.org/manual/en/latest/advanced/extensions/addons.html) · [Guidelines](https://developer.blender.org/docs/handbook/addons/guidelines/) · [Dev setup](https://developer.blender.org/docs/handbook/extensions/addon_dev_setup/)

## Namespace (extensions)

Installed module id is **`bl_ext.<repo>.<id>`**, not bare `id`.

Always use `__package__` — never hardcode the module string.

```python
class MyPrefs(bpy.types.AddonPreferences):
    bl_idname = __package__

prefs = bpy.context.preferences.addons[__package__].preferences
```

From a **subpackage**, import the top package:

```python
from .. import __package__ as base_package
# use base_package for bl_idname / prefs lookup
```

## Imports

- Use **relative** imports inside the extension (`from . import utils`).
- Do not mutate `sys.path` or inject into `sys.modules` (guidelines).
- Bundle third-party code as **wheels** in the extension, or as vendored submodules — do not `pip install` into Blender at runtime.

## Register / reload

Keep `register()` / `unregister()` symmetric. Defer heavy work (subprocess, network, FS scans) with `bpy.app.timers` so Enable stays fast.

Reload-friendly `__init__.py`:

```python
_needs_reload = "bpy" in locals()
import bpy
from . import module1, module2
if _needs_reload:
    import importlib
    module1 = importlib.reload(module1)
    module2 = importlib.reload(module2)
```

Repeat the pattern in subpackage `__init__.py` files that re-export modules.

## Preferences & storage

- Do **not** write into the extension install directory (System repos may be read-only; upgrades wipe files).
- User data:

```python
path = bpy.utils.extension_path_user(__package__, path="", create=True)
```

## Internet

Before any outbound network:

```python
if not bpy.app.online_access:
    # fail gracefully; respect Preferences → System → Allow Online Access
    return
```

Localhost sidecar still benefits from declaring `[permissions] network` in the manifest.

## UI / operators

| Type | Notes |
|------|--------|
| `Operator` | Unique `bl_idname` (`addon.op_name`); undo via `bl_options = {'REGISTER', 'UNDO'}` when mutating data |
| `Panel` | `bl_space_type='VIEW_3D'`, `bl_region_type='UI'`, `bl_category` = N-Panel tab |
| `PropertyGroup` | Attach to `WindowManager` / `Scene` carefully; remove on unregister |
| Timers | `bpy.app.timers.register(fn, first_interval=…, persistent=…)`; return `None` to stop, float seconds to reschedule; always unregister on disable |

Main-thread rule: only touch `bpy` data from the main thread (operators / timers). Background threads may queue work for a timer.

## Guidelines (extensions.blender.org + recommended everywhere)

1. Honor `bpy.app.online_access`.
2. Do not install/remove/modify other add-ons.
3. Self-contained — no runtime pip into Blender.
4. Load only into the add-on’s package namespace.
5. Support read-only System installs via `extension_path_user`.

## Legacy → extension

1. Add `blender_manifest.toml`.
2. Remove `bl_info`.
3. `bl_idname = __package__` for preferences.
4. Relative imports.
5. Wheels for deps.
6. Test with **Install from Disk**, then Enable in **Add-ons**.

## IDE

- Blender ships its own Python; IDE Python is for editing only.
- For stubs: `pip install fake-bpy-module` (community).
