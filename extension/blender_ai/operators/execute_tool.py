import json
import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from ..bridge import tools as tool_exec


class BLENDERAI_OT_execute_tool(Operator):
    bl_idname = "blender_ai.execute_tool"
    bl_label = "Execute AI Tool"
    bl_options = {"REGISTER", "UNDO"}

    tool: StringProperty(name="Tool")
    args_json: StringProperty(name="Args JSON", default="{}")
    request_id: StringProperty(name="Request ID", default="")

    def execute(self, context):
        try:
            args = json.loads(self.args_json or "{}")
        except json.JSONDecodeError:
            args = {}
        bpy.ops.ed.undo_push(message=f"BlenderAI: {self.tool}")
        result = tool_exec.run_tool(self.tool, args, context)
        from ..bridge import client as bridge_client

        bridge_client.send_json(
            {"type": "tool_result", "id": self.request_id, "result": result}
        )
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_execute_tool)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_execute_tool)
