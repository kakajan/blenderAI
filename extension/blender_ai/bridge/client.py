from __future__ import annotations

import json
import queue
import threading
import urllib.request
from typing import Any

import bpy

from .. import preferences
from . import tools as tool_exec

_status = "offline"
_ws_thread: threading.Thread | None = None
_send_queue: queue.Queue = queue.Queue()
_stop_event = threading.Event()
_process = None


def status_text() -> str:
    return _status


def base_url(context=None) -> str:
    prefs = preferences.get_prefs(context)
    host = prefs.sidecar_host if prefs else "127.0.0.1"
    port = prefs.sidecar_port if prefs else 8765
    return f"http://{host}:{port}"


def health_ok(context=None) -> bool:
    global _status
    try:
        with urllib.request.urlopen(base_url(context) + "/health", timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            _status = "online" if data.get("ok") else "error"
            return bool(data.get("ok"))
    except Exception:
        _status = "offline"
        return False


def send_json(msg: dict[str, Any]) -> None:
    _send_queue.put(msg)


def _ws_loop(host: str, port: int):
    global _status
    try:
        import websocket  # optional
    except ImportError:
        # Fallback: poll HTTP only
        while not _stop_event.is_set():
            try:
                with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1.5) as resp:
                    _status = "online" if resp.status == 200 else "error"
            except Exception:
                _status = "offline"
            _stop_event.wait(2.0)
        return

    url = f"ws://{host}:{port}/ws"
    while not _stop_event.is_set():
        try:
            ws = websocket.create_connection(url, timeout=5)
            _status = "online"
            ws.send(json.dumps({"type": "hello", "role": "blender"}))
            ws.settimeout(0.5)
            while not _stop_event.is_set():
                while not _send_queue.empty():
                    ws.send(json.dumps(_send_queue.get()))
                try:
                    raw = ws.recv()
                except Exception:
                    continue
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "tool_request":
                    from .queue import enqueue_tool

                    enqueue_tool(msg.get("id", ""), msg.get("tool", ""), msg.get("args") or {})
            ws.close()
        except Exception:
            _status = "offline"
            _stop_event.wait(2.0)


def start_bridge(context=None):
    global _ws_thread
    prefs = preferences.get_prefs(context)
    host = prefs.sidecar_host if prefs else "127.0.0.1"
    port = prefs.sidecar_port if prefs else 8765
    if _ws_thread and _ws_thread.is_alive():
        return
    _stop_event.clear()
    _ws_thread = threading.Thread(target=_ws_loop, args=(host, port), daemon=True)
    _ws_thread.start()


def stop_bridge():
    _stop_event.set()


def start_sidecar_process(context=None) -> bool:
    global _process
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    if health_ok(context):
        start_bridge(context)
        return True

    here = Path(__file__).resolve()
    candidates: list[Path] = []

    # 1) install_info.json next to addon (written by installer)
    info_path = here.parents[1] / "install_info.json"
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            if info.get("sidecar_dir"):
                candidates.append(Path(info["sidecar_dir"]))
        except Exception:
            pass

    # 2) Platform data dir BlenderAI install
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA", "")) / "BlenderAI" / "sidecar"
    elif sys.platform == "darwin":
        appdata = Path.home() / "Library" / "Application Support" / "BlenderAI" / "sidecar"
    else:
        xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        appdata = Path(xdg) / "BlenderAI" / "sidecar"
    if appdata.exists():
        candidates.append(appdata)

    # 3) Dev repo layout
    for parents_up in (3, 4, 2):
        try:
            root = here.parents[parents_up]
            candidates.append(root / "sidecar")
            candidates.append(root.parent / "sidecar")
        except IndexError:
            pass

    sidecar = next((p for p in candidates if (p / "blender_ai_sidecar").exists() or (p / "pyproject.toml").exists()), None)
    if not sidecar:
        return False

    env = os.environ.copy()
    env["PYTHONPATH"] = str(sidecar) + os.pathsep + env.get("PYTHONPATH", "")

    # Prefer venv python from installed sidecar
    if os.name == "nt":
        venv_py = sidecar / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = sidecar / ".venv" / "bin" / "python"
    python_exe = str(venv_py) if venv_py.exists() else sys.executable

    try:
        _process = subprocess.Popen(
            [python_exe, "-m", "blender_ai_sidecar.main", "serve"],
            cwd=str(sidecar),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        start_bridge(context)
        return True
    except Exception:
        return False


def stop_sidecar_process():
    global _process
    stop_bridge()
    if _process and _process.poll() is None:
        _process.terminate()
        _process = None


def _timer_health():
    health_ok()
    return 3.0


def register():
    bpy.app.timers.register(_timer_health, first_interval=1.0, persistent=True)
    prefs = preferences.get_prefs()
    if prefs and prefs.auto_start_sidecar:
        start_sidecar_process()
    else:
        start_bridge()


def unregister():
    stop_sidecar_process()
    if bpy.app.timers.is_registered(_timer_health):
        bpy.app.timers.unregister(_timer_health)
