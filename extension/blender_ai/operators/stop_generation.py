import bpy
from bpy.types import Operator

from ..bridge import client as bridge_client


class BLENDERAI_OT_stop_generation(Operator):
    bl_idname = "blender_ai.stop_generation"
    bl_label = "Stop Generation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        bridge_client.send_json({"type": "stop_generation"})
        self.report({"INFO"}, "Stop requested")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_stop_generation)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_stop_generation)
