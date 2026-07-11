import bpy
from bpy.types import Operator

from .. import chat_http


class BLENDERAI_OT_chat_send(Operator):
    bl_idname = "blender_ai.chat_send"
    bl_label = "Send"
    bl_description = "Send the prompt to BlenderAI (sidecar)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        state = getattr(context.window_manager, "blender_ai_chat", None)
        prompt = state.prompt if state else ""
        ok, err = chat_http.start_chat(context, prompt)
        if not ok:
            self.report({"WARNING"}, err)
            return {"CANCELLED"}
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_chat_send)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_chat_send)
