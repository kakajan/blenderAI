import bpy
from bpy.types import Operator

from .. import chat_state
from ..bridge import client as bridge_client
from ..context import scene as scene_ctx


class BLENDERAI_OT_capture_viewport(Operator):
    bl_idname = "blender_ai.capture_viewport"
    bl_label = "Capture Viewport"
    bl_description = "Capture the active 3D viewport and attach it to the chat"
    bl_options = {"REGISTER"}

    def execute(self, context):
        path = scene_ctx.capture_viewport(context)
        if not path:
            self.report({"WARNING"}, "Viewport capture failed")
            return {"CANCELLED"}

        state = chat_state.get_chat(context)
        if state is not None:
            state.pending_image_path = path
            state.status_line = "Capture attached — send with your message"

        bridge_client.send_json({"type": "viewport_capture", "path": path})
        self.report({"INFO"}, "Capture attached to chat")
        return {"FINISHED"}


class BLENDERAI_OT_clear_pending_capture(Operator):
    bl_idname = "blender_ai.clear_pending_capture"
    bl_label = "Remove Capture"
    bl_description = "Remove the pending viewport capture from the next message"
    bl_options = {"REGISTER"}

    def execute(self, context):
        state = chat_state.get_chat(context)
        if state is not None:
            state.pending_image_path = ""
            if state.status_line.startswith("Capture attached"):
                state.status_line = ""
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_capture_viewport)
    bpy.utils.register_class(BLENDERAI_OT_clear_pending_capture)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_clear_pending_capture)
    bpy.utils.unregister_class(BLENDERAI_OT_capture_viewport)
