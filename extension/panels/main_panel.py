import bpy
from bpy.types import Panel

from ..bridge import client as bridge_client
from .. import preferences
from .. import chat_previews
from .. import settings_cache


def _draw_image_preview(layout, path: str, scale: float = 5.5) -> bool:
    icon_id = chat_previews.icon_id_for(path)
    if not icon_id:
        layout.label(text="(image unavailable)", icon="ERROR")
        return False
    row = layout.row()
    row.alignment = "CENTER"
    row.template_icon(icon_value=icon_id, scale=scale)
    return True


def _draw_pending_capture(layout, state) -> None:
    path = (state.pending_image_path or "").strip()
    if not path:
        return
    box = layout.box()
    header = box.row(align=True)
    header.label(text="Capture ready", icon="IMAGE_DATA")
    header.operator("blender_ai.clear_pending_capture", text="", icon="X", emboss=False)
    _draw_image_preview(box, path, scale=6.0)
    box.label(text="Will send with your next message")


def _draw_prompt(layout, state) -> None:
    """Prompt UI: click to type (Enter sends, Shift+Enter newline)."""
    box = layout.box()
    prompt = state.prompt or ""

    if state.typing:
        cur = max(0, min(state.typing_cursor, len(prompt)))
        shown = prompt[:cur] + "|" + prompt[cur:]
        lines = shown.split("\n") or [""]
        for line in lines[:10]:
            box.label(text=line if line else " ")
        if len(lines) > 10:
            box.label(text="…")
        box.label(text="Enter: send · Shift+Enter: new line · Esc: done")
        return

    label = "Write a message…"
    if prompt:
        first, *rest = prompt.split("\n")
        label = first if first else " "
        if len(first) > 48:
            label = first[:45] + "…"
        elif rest:
            label = label + " …"
    op_row = box.row(align=True)
    op_row.enabled = not state.busy
    op_row.operator("blender_ai.chat_prompt_modal", text=label, icon="GREASEPENCIL")
    if prompt:
        for line in prompt.split("\n")[1:6]:
            box.label(text=line if line else " ")


class BLENDERAI_PT_main(Panel):
    bl_label = "BlenderAI"
    bl_idname = "BLENDERAI_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"

    def draw(self, context):
        layout = self.layout
        status = bridge_client.status_text()
        bridge = bridge_client.bridge_text()

        box = layout.box()
        row = box.row(align=True)
        row.label(text=f"Sidecar: {status}")
        row = box.row(align=True)
        row.label(text=f"Bridge: {bridge}")
        row = box.row(align=True)
        if status in ("online", "starting"):
            row.operator("blender_ai.stop_sidecar", text="Stop", icon="PAUSE")
        else:
            row.operator("blender_ai.start_sidecar", text="Start", icon="PLAY")
            err = bridge_client.last_start_error()
            if err:
                box.label(text=err[:64], icon="ERROR")

        webui_active = bool(getattr(context.window_manager, "blender_ai_webui_active", False))
        box = layout.box()
        if webui_active:
            box.label(text="Using WebUI — N-Panel chat paused", icon="URL")
            box.operator("blender_ai.close_webui", text="Back to Blender", icon="LOOP_BACK")
        else:
            box.operator("blender_ai.open_webui", text="Open WebUI", icon="URL")
            box.label(text="Optional — settings below work in Blender")


class BLENDERAI_PT_settings(Panel):
    bl_label = "Settings"
    bl_idname = "BLENDERAI_PT_settings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"
    bl_parent_id = "BLENDERAI_PT_main"

    def draw(self, context):
        layout = self.layout
        webui_active = bool(getattr(context.window_manager, "blender_ai_webui_active", False))
        if webui_active:
            layout.label(text="Settings available after Back to Blender")
            layout.operator("blender_ai.close_webui", text="Back to Blender", icon="LOOP_BACK")
            return

        settings = getattr(context.window_manager, "blender_ai_settings", None)
        if settings is None:
            layout.label(text="Settings unavailable")
            return

        row = layout.row(align=True)
        row.operator("blender_ai.settings_refresh", text="Refresh lists", icon="FILE_REFRESH")
        if settings_cache.is_refreshing():
            layout.label(text="Loading…")
        else:
            status = settings_cache.refresh_status()
            if status:
                layout.label(text=status[:60])

        col = layout.column(align=True)
        col.prop(settings, "provider_id", text="Provider")
        col.prop(settings, "model_id", text="Model")
        col.prop(settings, "skill_id", text="Skill")
        col.prop(settings, "workflow_id", text="Workflow")

        box = layout.box()
        box.label(text="Preset")
        box.prop(settings, "preset_id", text="")
        box.operator("blender_ai.use_preset", text="Use Preset", icon="TEXT")

        prefs = preferences.get_prefs(context)
        if prefs:
            layout.prop(prefs, "autonomy", text="Autonomy")

        layout.operator(
            "blender_ai.open_providers",
            text="Advanced: Providers (browser)",
            icon="PREFERENCES",
        )


class BLENDERAI_PT_chat(Panel):
    bl_label = "Chat"
    bl_idname = "BLENDERAI_PT_chat"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"
    bl_parent_id = "BLENDERAI_PT_main"

    def draw(self, context):
        layout = self.layout
        state = getattr(context.window_manager, "blender_ai_chat", None)
        if state is None:
            layout.label(text="Chat state unavailable")
            return

        webui_active = bool(getattr(context.window_manager, "blender_ai_webui_active", False))
        if webui_active:
            box = layout.box()
            box.label(text="Chat moved to WebUI", icon="INFO")
            box.label(text="Use the browser window for chat.")
            box.operator("blender_ai.close_webui", text="Back to Blender", icon="LOOP_BACK")
            return

        # Status only while active (busy) or for transient hints — not idle leftovers
        if state.busy and state.status_line:
            layout.label(text=state.status_line)
        elif state.status_line.startswith("Capture"):
            layout.label(text=state.status_line)

        if state.messages:
            layout.template_list(
                "BLENDERAI_UL_messages",
                "",
                state,
                "messages",
                state,
                "active_message",
                rows=min(6, max(2, len(state.messages))),
            )

            if 0 <= state.active_message < len(state.messages):
                msg = state.messages[state.active_message]
                box = layout.box()
                box.label(text=f"{msg.role}:")
                img = (getattr(msg, "image_path", None) or "").strip()
                if img:
                    _draw_image_preview(box, img, scale=5.0)
                text = msg.text or ""
                if not text and not img:
                    box.label(text="…")
                else:
                    for i in range(0, min(len(text), 1200), 80):
                        box.label(text=text[i : i + 80])

        _draw_pending_capture(layout, state)
        _draw_prompt(layout, state)
        row = layout.row(align=True)
        row.operator("blender_ai.capture_viewport", text="", icon="IMAGE_DATA")
        if state.busy:
            row.operator("blender_ai.stop_generation", text="Stop", icon="CANCEL")
        else:
            row.operator("blender_ai.chat_send", text="Send", icon="PLAY")
        row = layout.row(align=True)
        row.operator("blender_ai.chat_clear", text="New Chat", icon="FILE_NEW")
        row.operator("blender_ai.history_clear", text="Clear History", icon="TRASH")


class BLENDERAI_PT_logs(Panel):
    bl_label = "Logs"
    bl_idname = "BLENDERAI_PT_logs"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"
    bl_parent_id = "BLENDERAI_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("blender_ai.logs_refresh", text="Refresh", icon="FILE_REFRESH")
        row.operator("blender_ai.logs_clear", text="Clear", icon="TRASH")
        layout.operator("blender_ai.send_report", text="Send Report", icon="URL")

        store = getattr(context.window_manager, "blender_ai_log_cache", None)
        if store is None:
            layout.label(text="Log cache unavailable")
            return
        if len(store) == 0:
            layout.label(text="No logs yet — click Refresh")
            return

        box = layout.box()
        for item in list(store)[:40]:
            level = (item.level or "info").lower()
            icon = "INFO"
            if level in ("error", "crash"):
                icon = "ERROR"
            elif level == "warning":
                icon = "ERROR"
            row = box.row(align=True)
            src = item.source or "?"
            comp = f"/{item.component}" if item.component else ""
            prefix = f"[{level}] {src}{comp}"
            row.label(text=prefix[:28], icon=icon)
            msg = (item.message or "").replace("\n", " ")
            if len(msg) > 56:
                msg = msg[:53] + "…"
            row.label(text=msg)


class BLENDERAI_PT_tools(Panel):
    bl_label = "Tools"
    bl_idname = "BLENDERAI_PT_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderAI"
    bl_parent_id = "BLENDERAI_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("blender_ai.capture_viewport", text="Capture", icon="IMAGE_DATA")
        row.operator("blender_ai.undo_ai", text="Undo AI", icon="LOOP_BACK")
        webui_active = bool(getattr(context.window_manager, "blender_ai_webui_active", False))
        if webui_active:
            layout.operator("blender_ai.close_webui", text="Back to Blender", icon="LOOP_BACK")
        else:
            layout.operator("blender_ai.open_webui", text="Open WebUI", icon="URL")


def register():
    bpy.utils.register_class(BLENDERAI_PT_main)
    bpy.utils.register_class(BLENDERAI_PT_settings)
    bpy.utils.register_class(BLENDERAI_PT_chat)
    bpy.utils.register_class(BLENDERAI_PT_logs)
    bpy.utils.register_class(BLENDERAI_PT_tools)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_PT_tools)
    bpy.utils.unregister_class(BLENDERAI_PT_logs)
    bpy.utils.unregister_class(BLENDERAI_PT_chat)
    bpy.utils.unregister_class(BLENDERAI_PT_settings)
    bpy.utils.unregister_class(BLENDERAI_PT_main)
