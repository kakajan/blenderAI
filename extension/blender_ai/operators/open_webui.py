import webbrowser
import bpy
from bpy.types import Operator

from .. import preferences


class BLENDERAI_OT_open_webui(Operator):
    bl_idname = "blender_ai.open_webui"
    bl_label = "Open in browser"
    bl_description = "Open the rich WebUI in your browser (Providers, History, Skills)"
    bl_options = {"REGISTER"}

    def execute(self, context):
        prefs = preferences.get_prefs(context)
        host = prefs.sidecar_host if prefs else "127.0.0.1"
        port = prefs.sidecar_port if prefs else 8765
        webbrowser.open(f"http://{host}:{port}/")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_open_webui)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_open_webui)
