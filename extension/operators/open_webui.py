"""Open/close BlenderAI WebUI with N-Panel handoff.

Opens Chromium/Edge in --app mode so we can close that window when returning
to the Blender N-Panel. Stops in-progress N-Panel generation on open.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

import bpy
from bpy.types import Operator

from .. import chat_http
from .. import preferences
from ..bridge import client as bridge_client

_webui_proc: subprocess.Popen | None = None


def _webui_url(context=None) -> str:
    prefs = preferences.get_prefs(context)
    host = prefs.sidecar_host if prefs else "127.0.0.1"
    port = prefs.sidecar_port if prefs else 8765
    return f"http://{host}:{port}/"


def _chromium_app_cmd(url: str) -> list[str] | None:
    """Prefer Edge/Chrome/Brave app window so we can terminate it later."""
    env_paths = [
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("PROGRAMFILES", ""),
        os.environ.get("PROGRAMFILES(X86)", ""),
    ]
    rels = [
        Path("Microsoft") / "Edge" / "Application" / "msedge.exe",
        Path("Google") / "Chrome" / "Application" / "chrome.exe",
        Path("BraveSoftware") / "Brave-Browser" / "Application" / "brave.exe",
    ]
    for base in env_paths:
        if not base:
            continue
        root = Path(base)
        for rel in rels:
            exe = root / rel
            if exe.is_file():
                return [str(exe), f"--app={url}", "--new-window"]
    if sys.platform == "darwin":
        for name in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ):
            if Path(name).is_file():
                return [name, f"--app={url}", "--new-window"]
    return None


def is_webui_active(context=None) -> bool:
    context = context or bpy.context
    wm = getattr(context, "window_manager", None)
    return bool(wm and getattr(wm, "blender_ai_webui_active", False))


def set_webui_active(context, active: bool) -> None:
    wm = context.window_manager
    if hasattr(wm, "blender_ai_webui_active"):
        wm.blender_ai_webui_active = active
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _stop_npanel_chat(context) -> None:
    chat_http.cancel_stream()
    bridge_client.send_json({"type": "stop_generation"})
    state = getattr(context.window_manager, "blender_ai_chat", None)
    if state is not None:
        state.busy = False
        state.typing = False
        state.status_line = ""


def _terminate_webui_proc() -> bool:
    global _webui_proc
    proc = _webui_proc
    _webui_proc = None
    if proc is None:
        return False
    if proc.poll() is not None:
        return True
    try:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            proc.kill()
        return True
    except Exception:
        return False


def open_webui_session(context) -> tuple[bool, str]:
    """Stop N-Panel chat, ensure sidecar, open WebUI, mark handoff active."""
    global _webui_proc

    _stop_npanel_chat(context)

    if bridge_client.status_text() != "online":
        bridge_client.start_sidecar_process(context)

    url = _webui_url(context)
    # Replace previous app window if any
    _terminate_webui_proc()

    cmd = _chromium_app_cmd(url)
    if cmd:
        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            _webui_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            set_webui_active(context, True)
            return True, "WebUI opened — N-Panel chat paused"
        except Exception as exc:
            _webui_proc = None
            webbrowser.open(url)
            set_webui_active(context, True)
            return True, f"WebUI opened in default browser ({exc})"

    webbrowser.open(url)
    set_webui_active(context, True)
    return True, "WebUI opened in default browser (close the tab manually when done)"


def close_webui_session(context) -> tuple[bool, str]:
    """Close tracked WebUI window and restore N-Panel chat."""
    closed = _terminate_webui_proc()
    set_webui_active(context, False)
    if closed:
        return True, "WebUI closed — back to Blender N-Panel"
    return True, "Back to Blender N-Panel (close the browser tab if still open)"


class BLENDERAI_OT_open_webui(Operator):
    bl_idname = "blender_ai.open_webui"
    bl_label = "Open WebUI"
    bl_description = (
        "Stop N-Panel chat generation, open the rich WebUI, and pause the Blender chat panel"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return not is_webui_active(context)

    def execute(self, context):
        ok, msg = open_webui_session(context)
        self.report({"INFO"} if ok else {"WARNING"}, msg)
        return {"FINISHED"}


class BLENDERAI_OT_close_webui(Operator):
    bl_idname = "blender_ai.close_webui"
    bl_label = "Back to Blender"
    bl_description = "Close the WebUI window and restore the Blender N-Panel chat"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return is_webui_active(context)

    def execute(self, context):
        ok, msg = close_webui_session(context)
        self.report({"INFO"} if ok else {"WARNING"}, msg)
        return {"FINISHED"}


def register():
    bpy.types.WindowManager.blender_ai_webui_active = bpy.props.BoolProperty(
        name="WebUI Active",
        description="True while chat is handed off to the browser WebUI",
        default=False,
    )
    bpy.utils.register_class(BLENDERAI_OT_open_webui)
    bpy.utils.register_class(BLENDERAI_OT_close_webui)


def unregister():
    _terminate_webui_proc()
    bpy.utils.unregister_class(BLENDERAI_OT_close_webui)
    bpy.utils.unregister_class(BLENDERAI_OT_open_webui)
    if hasattr(bpy.types.WindowManager, "blender_ai_webui_active"):
        del bpy.types.WindowManager.blender_ai_webui_active
