from __future__ import annotations

import os
import tempfile
from typing import Any

import bpy


def build_summary(context=None) -> dict[str, Any]:
    context = context or bpy.context
    scene = context.scene
    obj = context.active_object
    selected = [o.name for o in context.selected_objects]
    materials = [m.name for m in bpy.data.materials[:30]]
    collections = [c.name for c in bpy.data.collections[:40]]
    objects = []
    for o in scene.objects[:80]:
        objects.append(
            {
                "name": o.name,
                "type": o.type,
                "location": [round(v, 4) for v in o.location],
                "dimensions": [round(v, 4) for v in o.dimensions] if hasattr(o, "dimensions") else None,
            }
        )
    summary: dict[str, Any] = {
        "blend_file": bpy.data.filepath or "",
        "mode": context.mode,
        "render_engine": scene.render.engine,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "active_object": None,
        "selection_count": len(selected),
        "selected": selected,
        "collections": collections,
        "materials": materials,
        "objects": objects,
        "object_names": [o["name"] for o in objects],
    }
    if obj:
        mods = [m.name + ":" + m.type for m in getattr(obj, "modifiers", [])]
        summary["active_object"] = {
            "name": obj.name,
            "type": obj.type,
            "location": [round(v, 4) for v in obj.location],
            "dimensions": [round(v, 4) for v in obj.dimensions] if hasattr(obj, "dimensions") else None,
            "modifiers": mods,
        }
    return summary


def capture_viewport(context=None) -> str | None:
    context = context or bpy.context
    try:
        tmp = tempfile.gettempdir()
        path = os.path.join(tmp, "blender_ai_viewport.png")
        # Best effort OpenGL render of viewport
        scene = context.scene
        prev = scene.render.filepath
        scene.render.filepath = path
        try:
            bpy.ops.render.opengl(write_still=True)
        finally:
            scene.render.filepath = prev
        return path if os.path.exists(path) else None
    except Exception:
        return None
