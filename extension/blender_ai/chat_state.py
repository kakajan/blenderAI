"""In-Blender chat state on WindowManager (not bound to .blend files)."""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup, UIList


MAX_MESSAGES = 80
MAX_MESSAGE_CHARS = 4000


class BLENDERAI_ChatMessage(PropertyGroup):
    role: StringProperty(name="Role", default="assistant")
    text: StringProperty(name="Text", default="", maxlen=MAX_MESSAGE_CHARS)


class BLENDERAI_UL_messages(UIList):
    bl_idname = "BLENDERAI_UL_messages"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            if item.role == "user":
                row.label(text="You", icon="USER")
            elif item.role == "error":
                row.label(text="Error", icon="ERROR")
            else:
                row.label(text="AI", icon="OUTLINER_OB_LIGHT")
            preview = (item.text or "").replace("\n", " ")
            if len(preview) > 72:
                preview = preview[:69] + "…"
            row.label(text=preview)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon="TEXT")


class BLENDERAI_ChatState(PropertyGroup):
    prompt: StringProperty(
        name="Prompt",
        description="Message to send to BlenderAI",
        default="",
        options={"TEXTEDIT_UPDATE"},
    )
    busy: BoolProperty(name="Busy", default=False)
    status_line: StringProperty(name="Status", default="")
    chat_id: StringProperty(name="Chat ID", default="")
    messages: CollectionProperty(type=BLENDERAI_ChatMessage)
    active_message: IntProperty(name="Active Message", default=0)


def get_chat(context=None) -> BLENDERAI_ChatState | None:
    context = context or bpy.context
    wm = getattr(context, "window_manager", None)
    if wm is None:
        return None
    return getattr(wm, "blender_ai_chat", None)


def append_message(state: BLENDERAI_ChatState, role: str, text: str) -> BLENDERAI_ChatMessage:
    while len(state.messages) >= MAX_MESSAGES:
        state.messages.remove(0)
    item = state.messages.add()
    item.role = role
    item.text = (text or "")[:MAX_MESSAGE_CHARS]
    state.active_message = len(state.messages) - 1
    return item


def clear_messages(state: BLENDERAI_ChatState) -> None:
    state.messages.clear()
    state.active_message = 0
    state.chat_id = ""
    state.status_line = ""
    state.busy = False


def register():
    bpy.utils.register_class(BLENDERAI_ChatMessage)
    bpy.utils.register_class(BLENDERAI_UL_messages)
    bpy.utils.register_class(BLENDERAI_ChatState)
    bpy.types.WindowManager.blender_ai_chat = bpy.props.PointerProperty(type=BLENDERAI_ChatState)


def unregister():
    if hasattr(bpy.types.WindowManager, "blender_ai_chat"):
        del bpy.types.WindowManager.blender_ai_chat
    bpy.utils.unregister_class(BLENDERAI_ChatState)
    bpy.utils.unregister_class(BLENDERAI_UL_messages)
    bpy.utils.unregister_class(BLENDERAI_ChatMessage)
