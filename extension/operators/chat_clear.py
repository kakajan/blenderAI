import bpy
from bpy.types import Operator

from .. import chat_http
from .. import chat_state
from ..bridge import client as bridge_client


def _clear_remote_history() -> tuple[bool, str]:
    try:
        import json
        import urllib.request

        base = bridge_client.base_url()
        req = urllib.request.Request(base + "/api/chats", method="DELETE")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        deleted = data.get("deleted", 0)
        return True, str(deleted)
    except Exception as exc:
        return False, str(exc)


class BLENDERAI_OT_chat_clear(Operator):
    bl_idname = "blender_ai.chat_clear"
    bl_label = "New Chat"
    bl_description = "Clear the N-Panel chat and start a new conversation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        chat_http.cancel_stream()
        state = chat_state.get_chat(context)
        if state:
            chat_state.clear_messages(state)
        self.report({"INFO"}, "Chat cleared")
        return {"FINISHED"}


class BLENDERAI_OT_history_clear(Operator):
    bl_idname = "blender_ai.history_clear"
    bl_label = "Clear History"
    bl_description = "Clear N-Panel chat and delete all saved conversations on the sidecar"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        chat_http.cancel_stream()
        state = chat_state.get_chat(context)
        if state:
            chat_state.clear_messages(state)
        ok, info = _clear_remote_history()
        if ok:
            self.report({"INFO"}, f"History cleared ({info} chat(s))")
        else:
            self.report({"WARNING"}, f"Local cleared; sidecar: {info}")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_chat_clear)
    bpy.utils.register_class(BLENDERAI_OT_history_clear)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_history_clear)
    bpy.utils.unregister_class(BLENDERAI_OT_chat_clear)
