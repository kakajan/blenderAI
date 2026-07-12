import bpy
from bpy.types import Operator


class BLENDERAI_OT_undo_ai(Operator):
    bl_idname = "blender_ai.undo_ai"
    bl_label = "Undo AI"
    bl_description = "Undo the last BlenderAI scene change"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.ed.undo()
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_undo_ai)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_undo_ai)
