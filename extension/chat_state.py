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
    image_path: StringProperty(name="Image Path", default="", subtype="FILE_PATH")


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
            if getattr(item, "image_path", ""):
                row.label(text="", icon="IMAGE_DATA")
            preview = (item.text or "").replace("\n", " ")
            if not preview and getattr(item, "image_path", ""):
                preview = "Viewport capture"
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
    typing: BoolProperty(name="Typing", default=False)
    typing_cursor: IntProperty(name="Typing Cursor", default=0, min=0)
    busy: BoolProperty(name="Busy", default=False)
    status_line: StringProperty(name="Status", default="")
    chat_id: StringProperty(name="Chat ID", default="")
    messages: CollectionProperty(type=BLENDERAI_ChatMessage)
    active_message: IntProperty(name="Active Message", default=0)
    pending_image_path: StringProperty(
        name="Pending Capture",
        description="Viewport capture attached to the next message",
        default="",
        subtype="FILE_PATH",
    )


def get_chat(context=None) -> BLENDERAI_ChatState | None:
    """Return chat state. Safe for bpy.app.timers (context may lack window_manager)."""
    if context is not None:
        wm = getattr(context, "window_manager", None)
        if wm is not None:
            chat = getattr(wm, "blender_ai_chat", None)
            if chat is not None:
                return chat
    # Timer / restricted context fallback
    try:
        for wm in bpy.data.window_managers:
            chat = getattr(wm, "blender_ai_chat", None)
            if chat is not None:
                return chat
    except Exception:
        pass
    try:
        wm = bpy.context.window_manager
        if wm is not None:
            return getattr(wm, "blender_ai_chat", None)
    except Exception:
        pass
    return None


def append_message(
    state: BLENDERAI_ChatState,
    role: str,
    text: str,
    image_path: str = "",
) -> BLENDERAI_ChatMessage:
    while len(state.messages) >= MAX_MESSAGES:
        state.messages.remove(0)
    item = state.messages.add()
    item.role = role
    item.text = (text or "")[:MAX_MESSAGE_CHARS]
    item.image_path = image_path or ""
    state.active_message = len(state.messages) - 1
    return item


def clear_messages(state: BLENDERAI_ChatState) -> None:
    state.messages.clear()
    state.active_message = 0
    state.chat_id = ""
    state.status_line = ""
    state.busy = False
    state.typing = False
    state.typing_cursor = 0
    state.prompt = ""
    state.pending_image_path = ""


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
