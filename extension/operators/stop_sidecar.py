import bpy
from bpy.types import Operator

from ..bridge import client as bridge_client


class BLENDERAI_OT_stop_sidecar(Operator):
    bl_idname = "blender_ai.stop_sidecar"
    bl_label = "Stop Sidecar"
    bl_description = "Stop the BlenderAI sidecar process"
    bl_options = {"REGISTER"}

    def execute(self, context):
        bridge_client.stop_sidecar_process()
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
        self.report({"INFO"}, "Sidecar stopped")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_stop_sidecar)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_stop_sidecar)
