import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty
from bpy.types import AddonPreferences


class BlenderAIPreferences(AddonPreferences):
    # Must match the extension module package (bl_ext.<repo>.blender_ai when installed).
    bl_idname = __package__

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
        layout.label(text="Chat + Settings are in the N-Panel (View3D → Sidebar → BlenderAI).")
        layout.operator("blender_ai.settings_refresh", text="Refresh provider/model lists")
        layout.operator("blender_ai.open_webui", text="Open WebUI")
        layout.operator("blender_ai.close_webui", text="Back to Blender")
        layout.operator("blender_ai.open_providers", text="Advanced: Providers (browser)")


def get_prefs(context=None):
    context = context or bpy.context
    pkg = __package__ or "blender_ai"
    addon = context.preferences.addons.get(pkg)
    if addon:
        return addon.preferences
    # Fallbacks for legacy / alternate repo module keys
    for key, addon in context.preferences.addons.items():
        if key == "blender_ai" or key.endswith(".blender_ai") or "blender_ai" in key:
            return addon.preferences
    return None


def register():
    bpy.utils.register_class(BlenderAIPreferences)


def unregister():
    bpy.utils.unregister_class(BlenderAIPreferences)
