"""N-Panel settings: provider, model, skill, preset selection."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import PropertyGroup

from . import settings_cache


def _on_provider_update(self, context):
    settings_cache.sync_selection_to_prefs(context)
    # Reset model to auto, then refresh model list for the new provider
    try:
        self["model_id"] = ""
    except Exception:
        pass
    settings_cache.refresh_async(context, provider_id=self.provider_id)


def _on_model_update(self, context):
    settings_cache.sync_selection_to_prefs(context)


class BLENDERAI_SettingsState(PropertyGroup):
    provider_id: EnumProperty(
        name="Provider",
        description="AI provider for N-Panel chat",
        items=settings_cache.provider_items,
        update=_on_provider_update,
    )
    model_id: EnumProperty(
        name="Model",
        description="Model for N-Panel chat ((auto) uses provider default)",
        items=settings_cache.model_items,
        update=_on_model_update,
    )
    skill_id: EnumProperty(
        name="Skill",
        description="Optional skill for N-Panel chat",
        items=settings_cache.skill_items,
    )
    workflow_id: EnumProperty(
        name="Workflow",
        description="Multi-step specialist workflow (overrides single skill when set)",
        items=settings_cache.workflow_items,
    )
    preset_id: EnumProperty(
        name="Preset",
        description="Optional prompt preset — click Use Preset to fill the chat box",
        items=settings_cache.preset_items,
    )
    last_status: StringProperty(name="Status", default="")


def get_settings(context=None) -> BLENDERAI_SettingsState | None:
    context = context or bpy.context
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return None
    return getattr(wm, "blender_ai_settings", None)


def register():
    bpy.utils.register_class(BLENDERAI_SettingsState)
    bpy.types.WindowManager.blender_ai_settings = bpy.props.PointerProperty(
        type=BLENDERAI_SettingsState
    )


def unregister():
    if hasattr(bpy.types.WindowManager, "blender_ai_settings"):
        del bpy.types.WindowManager.blender_ai_settings
    bpy.utils.unregister_class(BLENDERAI_SettingsState)
