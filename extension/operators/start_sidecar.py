import bpy
from bpy.types import Operator

from ..bridge import client as bridge_client


class BLENDERAI_OT_start_sidecar(Operator):
    bl_idname = "blender_ai.start_sidecar"
    bl_label = "Start Sidecar"
    bl_description = "Start the BlenderAI sidecar process"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok = bridge_client.start_sidecar_process(context)
        if ok:
            self.report({"INFO"}, "Sidecar start requested")
        else:
            detail = bridge_client.last_start_error() or "Could not start sidecar"
            self.report({"WARNING"}, detail[:256])
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_start_sidecar)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_start_sidecar)
