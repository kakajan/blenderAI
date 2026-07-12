"""Log entry PropertyGroup stored on WindowManager for the Logs panel."""

from __future__ import annotations

import bpy
from bpy.props import CollectionProperty, StringProperty
from bpy.types import PropertyGroup


class BLENDERAI_LogEntry(PropertyGroup):
    level: StringProperty(name="Level", default="")
    source: StringProperty(name="Source", default="")
    component: StringProperty(name="Component", default="")
    message: StringProperty(name="Message", default="")
    ts: StringProperty(name="Time", default="")


def register():
    bpy.utils.register_class(BLENDERAI_LogEntry)
    bpy.types.WindowManager.blender_ai_log_cache = CollectionProperty(type=BLENDERAI_LogEntry)


def unregister():
    if hasattr(bpy.types.WindowManager, "blender_ai_log_cache"):
        del bpy.types.WindowManager.blender_ai_log_cache
    bpy.utils.unregister_class(BLENDERAI_LogEntry)
