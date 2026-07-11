import bpy
from bpy.types import Panel

from ..bridge import client as bridge_client
from .. import preferences


class BLENDERAI_PT_main(Panel):
    bl_label = "BlenderAI"
    bl_idname = "BLENDERAI_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"

    def draw(self, context):
        layout = self.layout
        prefs = preferences.get_prefs(context)
        status = bridge_client.status_text()

        box = layout.box()
        row = box.row(align=True)
        row.label(text=f"Sidecar: {status}")
        row = box.row(align=True)
        row.operator("blender_ai.start_sidecar", text="Start", icon="PLAY")
        row.operator("blender_ai.stop_sidecar", text="Stop", icon="PAUSE")

        if prefs:
            col = layout.column(align=True)
            col.label(text=f"Provider: {prefs.active_provider or '-'}")
            col.label(text=f"Model: {prefs.active_model or '-'}")
        layout.operator(
            "blender_ai.open_providers",
            text="Providers (browser)",
            icon="PREFERENCES",
        )


class BLENDERAI_PT_chat(Panel):
    bl_label = "Chat"
    bl_idname = "BLENDERAI_PT_chat"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"
    bl_parent_id = "BLENDERAI_PT_main"

    def draw(self, context):
        layout = self.layout
        state = getattr(context.window_manager, "blender_ai_chat", None)
        if state is None:
            layout.label(text="Chat state unavailable")
            return

        if state.status_line:
            layout.label(text=state.status_line)

        layout.template_list(
            "BLENDERAI_UL_messages",
            "",
            state,
            "messages",
            state,
            "active_message",
            rows=6,
        )

        if state.messages and 0 <= state.active_message < len(state.messages):
            msg = state.messages[state.active_message]
            box = layout.box()
            box.label(text=f"{msg.role}:")
            text = msg.text or ""
            if not text:
                box.label(text="…")
            else:
                for i in range(0, min(len(text), 1200), 80):
                    box.label(text=text[i : i + 80])

        layout.prop(state, "prompt", text="")
        row = layout.row(align=True)
        send_row = row.row(align=True)
        send_row.enabled = not state.busy
        send_row.operator("blender_ai.chat_send", text="Send", icon="PLAY")
        row.operator("blender_ai.stop_generation", text="Stop", icon="CANCEL")
        layout.operator("blender_ai.chat_clear", text="New Chat", icon="FILE_NEW")


class BLENDERAI_PT_tools(Panel):
    bl_label = "Tools"
    bl_idname = "BLENDERAI_PT_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"
    bl_parent_id = "BLENDERAI_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("blender_ai.capture_viewport", text="Capture", icon="IMAGE_DATA")
        row.operator("blender_ai.undo_ai", text="Undo AI", icon="LOOP_BACK")
        layout.operator(
            "blender_ai.open_webui",
            text="Open in browser",
            icon="URL",
        )


def register():
    bpy.utils.register_class(BLENDERAI_PT_main)
    bpy.utils.register_class(BLENDERAI_PT_chat)
    bpy.utils.register_class(BLENDERAI_PT_tools)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_PT_tools)
    bpy.utils.unregister_class(BLENDERAI_PT_chat)
    bpy.utils.unregister_class(BLENDERAI_PT_main)
