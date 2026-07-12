import bpy
from bpy.types import Operator

from .. import chat_http
from ..bridge import client as bridge_client


class BLENDERAI_OT_stop_generation(Operator):
    bl_idname = "blender_ai.stop_generation"
    bl_label = "Stop Generation"
    bl_description = "Cancel the current chat generation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        chat_http.cancel_stream()
        bridge_client.send_json({"type": "stop_generation"})
        state = getattr(context.window_manager, "blender_ai_chat", None)
        if state:
            state.busy = False
            state.status_line = ""
        self.report({"INFO"}, "Stop requested")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_stop_generation)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_stop_generation)
