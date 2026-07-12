"""Refresh N-Panel settings catalogs and apply presets."""

from __future__ import annotations

import bpy
from bpy.types import Operator

from .. import settings_cache
from ..chat_state import get_chat


class BLENDERAI_OT_settings_refresh(Operator):
    bl_idname = "blender_ai.settings_refresh"
    bl_label = "Refresh Settings"
    bl_description = "Reload providers, models, skills, and presets from the sidecar"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from ..bridge import client as bridge_client

        if bridge_client.status_text() != "online":
            bridge_client.start_sidecar_process(context)
        ok = settings_cache.refresh_async(context)
        if ok:
            self.report({"INFO"}, "Refreshing providers / models / skills / presets…")
        else:
            self.report({"INFO"}, "Refresh already in progress")
        return {"FINISHED"}


class BLENDERAI_OT_use_preset(Operator):
    bl_idname = "blender_ai.use_preset"
    bl_label = "Use Preset"
    bl_description = "Fill the chat prompt with the selected preset"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from ..bridge import client as bridge_client

        settings = getattr(context.window_manager, "blender_ai_settings", None)
        state = get_chat(context)
        if settings is None or state is None:
            self.report({"WARNING"}, "Settings unavailable")
            return {"CANCELLED"}
        pid = settings.preset_id or ""
        if not pid:
            self.report({"WARNING"}, "Select a preset first")
            return {"CANCELLED"}

        base = bridge_client.base_url(context)
        prompt, err = settings_cache.fetch_preset_prompt(base, pid)
        if not prompt.strip():
            self.report({"WARNING"}, err or "Preset has no prompt text")
            return {"CANCELLED"}
        state.prompt = prompt
        state.typing = False
        self.report({"INFO"}, "Preset loaded into prompt")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_settings_refresh)
    bpy.utils.register_class(BLENDERAI_OT_use_preset)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_use_preset)
    bpy.utils.unregister_class(BLENDERAI_OT_settings_refresh)
