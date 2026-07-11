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
        layout.label(text=f"Sidecar: {status}")
        if prefs:
            layout.label(text=f"Provider: {prefs.active_provider or '-'}")
            layout.label(text=f"Model: {prefs.active_model or '-'}")
        col = layout.column(align=True)
        col.operator("blender_ai.open_webui", text="Open Chat", icon="URL")
        col.operator("blender_ai.open_providers", text="Open Providers Settings", icon="PREFERENCES")
        layout.separator()
        row = layout.row(align=True)
        row.operator("blender_ai.capture_viewport", text="Capture", icon="IMAGE_DATA")
        row.operator("blender_ai.stop_generation", text="Stop", icon="CANCEL")
        layout.operator("blender_ai.undo_ai", text="Undo AI", icon="LOOP_BACK")
        layout.separator()
        row = layout.row(align=True)
        row.operator("blender_ai.start_sidecar", text="Start", icon="PLAY")
        row.operator("blender_ai.stop_sidecar", text="Stop Sidecar", icon="PAUSE")


def register():
    bpy.utils.register_class(BLENDERAI_PT_main)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_PT_main)
