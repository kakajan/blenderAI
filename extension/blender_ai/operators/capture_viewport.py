import bpy
from bpy.types import Operator

from ..bridge import client as bridge_client
from ..context import scene as scene_ctx


class BLENDERAI_OT_capture_viewport(Operator):
    bl_idname = "blender_ai.capture_viewport"
    bl_label = "Capture Viewport"
    bl_options = {"REGISTER"}

    def execute(self, context):
        path = scene_ctx.capture_viewport(context)
        bridge_client.send_json({"type": "viewport_capture", "path": path})
        self.report({"INFO"}, f"Captured: {path or 'failed'}")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_capture_viewport)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_capture_viewport)
