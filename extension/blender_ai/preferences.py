import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
from bpy.types import AddonPreferences


class BlenderAIPreferences(AddonPreferences):
    bl_idname = "blender_ai"

    sidecar_host: StringProperty(name="Sidecar Host", default="127.0.0.1")
    sidecar_port: IntProperty(name="Sidecar Port", default=8765, min=1, max=65535)
    auto_start_sidecar: BoolProperty(name="Auto-start Sidecar", default=True)
    active_model: StringProperty(name="Active Model", default="")
    active_provider: StringProperty(name="Active Provider", default="ollama")
    autonomy: EnumProperty(
        name="Autonomy",
        items=[
            ("ask", "Ask", "Confirm risky actions"),
            ("auto_safe", "Auto-safe", "Auto-run safe tools"),
            ("auto_full", "Auto-full", "Auto-run allowlisted tools"),
        ],
        default="ask",
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="BlenderAI panel UI is English. Change WebUI language & RTL in Settings.")
        layout.prop(self, "sidecar_host")
        layout.prop(self, "sidecar_port")
        layout.prop(self, "auto_start_sidecar")
        layout.prop(self, "autonomy")
        layout.separator()
        layout.operator("blender_ai.open_webui", text="Open BlenderAI Chat")
        layout.operator("blender_ai.open_providers", text="Open Providers Settings")


def get_prefs(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get("blender_ai")
    if addon:
        return addon.preferences
    for key, addon in context.preferences.addons.items():
        if key.endswith("blender_ai") or "blender_ai" in key:
            return addon.preferences
    return None


def register():
    bpy.utils.register_class(BlenderAIPreferences)


def unregister():
    bpy.utils.unregister_class(BlenderAIPreferences)
