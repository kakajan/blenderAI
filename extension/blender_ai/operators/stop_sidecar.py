import bpy
from bpy.types import Operator

from ..bridge import client as bridge_client


class BLENDERAI_OT_stop_sidecar(Operator):
    bl_idname = "blender_ai.stop_sidecar"
    bl_label = "Stop Sidecar"
    bl_options = {"REGISTER"}

    def execute(self, context):
        bridge_client.stop_sidecar_process()
        self.report({"INFO"}, "Sidecar stop requested")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_stop_sidecar)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_stop_sidecar)
