import bpy
from bpy.types import Operator

from .. import chat_http
from .. import chat_state


class BLENDERAI_OT_chat_clear(Operator):
    bl_idname = "blender_ai.chat_clear"
    bl_label = "New Chat"
    bl_description = "Clear the N-Panel chat history and start a new conversation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        chat_http.cancel_stream()
        state = chat_state.get_chat(context)
        if state:
            chat_state.clear_messages(state)
            state.status_line = "New chat"
        self.report({"INFO"}, "Chat cleared")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_chat_clear)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_chat_clear)
