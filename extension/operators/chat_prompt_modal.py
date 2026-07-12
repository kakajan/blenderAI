"""Modal chat prompt: Enter sends, Shift+Enter inserts a newline."""

from __future__ import annotations

import bpy
from bpy.types import Operator

from .. import chat_http
from ..chat_state import get_chat


def _redraw(context) -> None:
    area = getattr(context, "area", None)
    if area is not None:
        area.tag_redraw()
        return
    window = getattr(context, "window", None)
    if window is None:
        return
    for area in window.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


class BLENDERAI_OT_chat_prompt_modal(Operator):
    bl_idname = "blender_ai.chat_prompt_modal"
    bl_label = "Type Message"
    bl_description = "Type a message. Enter: send · Shift+Enter: new line · Esc: done"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        state = get_chat(context)
        if state is None:
            self.report({"WARNING"}, "Chat state unavailable")
            return {"CANCELLED"}
        if state.busy:
            self.report({"WARNING"}, "Already generating — press Stop first")
            return {"CANCELLED"}
        if getattr(context.window_manager, "blender_ai_webui_active", False):
            self.report({"WARNING"}, "WebUI is open — click Back to Blender first")
            return {"CANCELLED"}

        state.typing = True
        state.typing_cursor = len(state.prompt or "")
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(
            "BlenderAI: Enter = send · Shift+Enter = new line · Esc = done"
        )
        _redraw(context)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        state = get_chat(context)
        if state is None:
            return self._stop(context, cancel=True)

        # Let mouse / navigation / timers through so the viewport stays usable.
        if event.value != "PRESS":
            return {"PASS_THROUGH"}

        if event.type == "ESC":
            return self._stop(context)

        if event.type == "RET":
            if event.shift:
                self._insert(state, "\n")
                _redraw(context)
                return {"RUNNING_MODAL"}
            return self._send(context, state)

        if event.type == "BACK_SPACE":
            self._backspace(state, word=event.ctrl)
            _redraw(context)
            return {"RUNNING_MODAL"}

        if event.type == "DEL":
            self._delete(state)
            _redraw(context)
            return {"RUNNING_MODAL"}

        if event.type == "LEFT_ARROW":
            state.typing_cursor = max(0, state.typing_cursor - 1)
            _redraw(context)
            return {"RUNNING_MODAL"}

        if event.type == "RIGHT_ARROW":
            state.typing_cursor = min(len(state.prompt or ""), state.typing_cursor + 1)
            _redraw(context)
            return {"RUNNING_MODAL"}

        if event.type == "HOME":
            state.typing_cursor = 0
            _redraw(context)
            return {"RUNNING_MODAL"}

        if event.type == "END":
            state.typing_cursor = len(state.prompt or "")
            _redraw(context)
            return {"RUNNING_MODAL"}

        if event.type == "V" and (event.ctrl or event.oskey):
            clip = context.window_manager.clipboard or ""
            if clip:
                self._insert(state, clip.replace("\r\n", "\n").replace("\r", "\n"))
                _redraw(context)
            return {"RUNNING_MODAL"}

        if event.unicode and event.type not in {"RET", "TAB"}:
            self._insert(state, event.unicode)
            _redraw(context)
            return {"RUNNING_MODAL"}

        # Mouse buttons, wheel, NDOF, unhandled keys → viewport / navigation.
        return {"PASS_THROUGH"}

    def _send(self, context, state):
        text = state.prompt or ""
        context.workspace.status_text_set(None)
        state.typing = False
        ok, err = chat_http.start_chat(context, text)
        if not ok:
            # Restore draft so the user can fix and retry
            state.prompt = text
            state.typing_cursor = len(text)
            self.report({"WARNING"}, err)
            _redraw(context)
            return {"CANCELLED"}
        state.typing_cursor = 0
        _redraw(context)
        return {"FINISHED"}

    def _stop(self, context, cancel: bool = False):
        context.workspace.status_text_set(None)
        state = get_chat(context)
        if state is not None:
            state.typing = False
        _redraw(context)
        return {"CANCELLED"} if cancel else {"FINISHED"}

    @staticmethod
    def _insert(state, text: str) -> None:
        prompt = state.prompt or ""
        cur = max(0, min(state.typing_cursor, len(prompt)))
        state.prompt = prompt[:cur] + text + prompt[cur:]
        state.typing_cursor = cur + len(text)

    @staticmethod
    def _backspace(state, word: bool = False) -> None:
        prompt = state.prompt or ""
        cur = max(0, min(state.typing_cursor, len(prompt)))
        if cur <= 0:
            return
        if word:
            i = cur
            while i > 0 and prompt[i - 1].isspace():
                i -= 1
            while i > 0 and not prompt[i - 1].isspace():
                i -= 1
            state.prompt = prompt[:i] + prompt[cur:]
            state.typing_cursor = i
        else:
            state.prompt = prompt[: cur - 1] + prompt[cur:]
            state.typing_cursor = cur - 1

    @staticmethod
    def _delete(state) -> None:
        prompt = state.prompt or ""
        cur = max(0, min(state.typing_cursor, len(prompt)))
        if cur >= len(prompt):
            return
        state.prompt = prompt[:cur] + prompt[cur + 1 :]


def register():
    bpy.utils.register_class(BLENDERAI_OT_chat_prompt_modal)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_chat_prompt_modal)
