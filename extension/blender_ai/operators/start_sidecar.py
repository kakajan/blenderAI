import bpy
from bpy.types import Operator

from ..bridge import client as bridge_client


class BLENDERAI_OT_start_sidecar(Operator):
    bl_idname = "blender_ai.start_sidecar"
    bl_label = "Start Sidecar"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok = bridge_client.start_sidecar_process(context)
        self.report({"INFO"} if ok else {"WARNING"}, "Sidecar start requested" if ok else "Could not start sidecar")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_start_sidecar)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_start_sidecar)
