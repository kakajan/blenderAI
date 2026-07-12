from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any

import bpy

from .. import preferences

TOKEN_HEADER = "X-BlenderAI-Token"

_status = "offline"
_bridge = "disconnected"  # connected | disconnected
_ws_thread: threading.Thread | None = None
_send_queue: queue.Queue = queue.Queue()
_stop_event = threading.Event()
_process = None
_spawn_lock = threading.Lock()
_deferred_timer_registered = False
_http_owner: str | None = None
_use_http = False
_cached_auth_token: str | None = None


def status_text() -> str:
    return _status


def bridge_text() -> str:
    return _bridge


def _online_access_ok() -> bool:
    """Blender guidelines: honor Preferences → System → Allow Online Access."""
    return bool(getattr(bpy.app, "online_access", True))


def _is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower().split("%", 1)[0]
    return h in {"127.0.0.1", "localhost", "::1"}


def _appdata_blenderai() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", "")) / "BlenderAI"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BlenderAI"
    xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(xdg) / "BlenderAI"


def _auth_token() -> str:
    """Load and cache token from ``%APPDATA%/BlenderAI/auth.json`` (mcp_token|token)."""
    global _cached_auth_token
    if _cached_auth_token:
        return _cached_auth_token
    path = _appdata_blenderai() / "auth.json"
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    token = str(data.get("mcp_token") or data.get("token") or "").strip()
    if token:
        _cached_auth_token = token
    return token


def auth_token() -> str:
    """Public accessor for the cached BlenderAI auth token."""
    return _auth_token()


def auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = dict(extra or {})
    token = auth_token()
    if token:
        headers[TOKEN_HEADER] = token
    return headers


def _resolve_host_port(context=None) -> tuple[str, int] | None:
    """Return (host, port) only when online_access + localhost are OK; else None."""
    global _status, _bridge
    if not _online_access_ok():
        _status = "offline"
        _bridge = "disconnected"
        return None
    prefs = preferences.get_prefs(context)
    host = prefs.sidecar_host if prefs else "127.0.0.1"
    port = int(prefs.sidecar_port if prefs else 8765)
    if not _is_loopback_host(host):
        _status = "blocked: non-localhost host"
        _bridge = "disconnected"
        return None
    return host, port


def base_url(context=None) -> str:
    resolved = _resolve_host_port(context)
    if resolved is None:
        # Prefer loopback default for callers that only need a URL string;
        # connection attempts still gate via _resolve_host_port / start_bridge.
        prefs = preferences.get_prefs(context)
        host = prefs.sidecar_host if prefs else "127.0.0.1"
        port = prefs.sidecar_port if prefs else 8765
        if not _is_loopback_host(str(host)):
            host, port = "127.0.0.1", 8765
        return f"http://{host}:{port}"
    host, port = resolved
    return f"http://{host}:{port}"


def health_ok(context=None) -> bool:
    """Non-blocking-ish health probe (short timeout). Prefer bridge thread for status."""
    global _status
    resolved = _resolve_host_port(context)
    if resolved is None:
        return False
    host, port = resolved
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/health",
            headers=auth_headers({"Accept": "application/json"}),
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=0.4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            _status = "online" if data.get("ok") else "error"
            return bool(data.get("ok"))
    except Exception:
        if _status not in ("online", "error", "offline", "starting"):
            _status = "offline"
        return False


def _http_json(url: str, payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        headers=auth_headers({"Content-Type": "application/json"}),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def send_json(msg: dict[str, Any]) -> None:
    """Send a message to the sidecar (WS queue or HTTP POST)."""
    global _http_owner
    if _use_http:
        try:
            payload = dict(msg)
            if _http_owner:
                payload["owner"] = _http_owner
            host_port = base_url()
            _http_json(f"{host_port}/api/bridge/message", payload, timeout=3.0)
        except Exception:
            pass
        return
    _send_queue.put(msg)


def _http_loop(host: str, port: int) -> None:
    """Stdlib HTTP long-poll bridge — works without websocket-client."""
    global _status, _bridge, _http_owner, _use_http
    if not _online_access_ok() or not _is_loopback_host(host):
        _status = "offline" if not _online_access_ok() else "blocked: non-localhost host"
        _bridge = "disconnected"
        return

    _use_http = True
    base = f"http://{host}:{port}"
    owner: str | None = None

    while not _stop_event.is_set():
        if not _online_access_ok():
            _status = "offline"
            _bridge = "disconnected"
            break
        try:
            if owner is None:
                hello = _http_json(
                    f"{base}/api/bridge/hello",
                    {"owner": None},
                    timeout=3.0,
                )
                owner = hello.get("owner")
                _http_owner = owner
                _status = "online"
                _bridge = "connected"
                _schedule_scene_push()

            poll = _http_json(
                f"{base}/api/bridge/poll",
                {"owner": owner, "timeout": 2.0},
                timeout=8.0,
            )
            _status = "online"
            _bridge = "connected"
            owner = poll.get("owner") or owner
            _http_owner = owner

            if poll.get("type") == "tool_request":
                from .queue import enqueue_tool

                enqueue_tool(poll.get("id", ""), poll.get("tool", ""), poll.get("args") or {})
        except Exception:
            _bridge = "disconnected"
            owner = None
            _http_owner = None
            try:
                req = urllib.request.Request(
                    f"{base}/health",
                    headers=auth_headers({"Accept": "application/json"}),
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    _status = "online" if resp.status == 200 else "error"
            except Exception:
                _status = "offline"
            _stop_event.wait(2.0)


def _ws_loop(host: str, port: int):
    global _status, _bridge, _use_http
    if not _online_access_ok() or not _is_loopback_host(host):
        _status = "offline" if not _online_access_ok() else "blocked: non-localhost host"
        _bridge = "disconnected"
        return

    try:
        import websocket  # from bundled wheel when available
    except ImportError:
        _http_loop(host, port)
        return

    _use_http = False
    url = f"ws://{host}:{port}/ws"
    while not _stop_event.is_set():
        if not _online_access_ok():
            _status = "offline"
            _bridge = "disconnected"
            break
        try:
            ws = websocket.create_connection(url, timeout=5)
            _status = "online"
            hello = {"type": "hello", "role": "blender", "token": auth_token()}
            ws.send(json.dumps(hello))
            ws.settimeout(0.5)
            while not _stop_event.is_set():
                if not _online_access_ok():
                    break
                while not _send_queue.empty():
                    ws.send(json.dumps(_send_queue.get()))
                try:
                    raw = ws.recv()
                except Exception as exc:
                    # Periodic read timeouts are normal; connection errors must reconnect.
                    err = str(exc).lower()
                    if "timed out" in err or "timeout" in err:
                        continue
                    break
                if not raw:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "hello_ack":
                    _bridge = "connected"
                    _schedule_scene_push()
                elif msg.get("type") == "tool_request":
                    from .queue import enqueue_tool

                    enqueue_tool(msg.get("id", ""), msg.get("tool", ""), msg.get("args") or {})
            try:
                ws.close()
            except Exception:
                pass
        except Exception:
            _status = "offline"
        _bridge = "disconnected"
        if _stop_event.is_set():
            break
        _stop_event.wait(2.0)


def _schedule_scene_push() -> None:
    """Push scene summary from the main thread (bpy is not thread-safe)."""

    def _push():
        try:
            from ..context import scene as scene_ctx

            summary = scene_ctx.build_summary(bpy.context)
            send_json({"type": "scene_summary", "summary": summary})
        except Exception:
            pass
        return None

    try:
        if not bpy.app.timers.is_registered(_push):
            bpy.app.timers.register(_push, first_interval=0.1, persistent=False)
    except Exception:
        pass


def start_bridge(context=None):
    global _ws_thread, _status, _bridge
    resolved = _resolve_host_port(context)
    if resolved is None:
        return
    host, port = resolved
    if _ws_thread and _ws_thread.is_alive():
        if _bridge == "connected":
            return
        # Sidecar may have restarted under us — tear down the dead loop and reconnect.
        stop_bridge()
        try:
            _ws_thread.join(timeout=2.5)
        except Exception:
            pass
    _stop_event.clear()
    _ws_thread = threading.Thread(target=_ws_loop, args=(host, port), daemon=True, name="BlenderAI-bridge")
    _ws_thread.start()


def stop_bridge():
    global _http_owner, _bridge, _use_http
    if _use_http and _http_owner:
        try:
            _http_json(
                f"{base_url()}/api/bridge/message",
                {"type": "goodbye", "owner": _http_owner},
                timeout=1.0,
            )
        except Exception:
            pass
    _stop_event.set()
    _bridge = "disconnected"
    _http_owner = None


def _appdata_sidecar() -> Path:
    return _appdata_blenderai() / "sidecar"


def _install_info_candidates() -> list[Path]:
    """Locate install_info.json (prefer user data dirs over the extension package)."""
    here = Path(__file__).resolve()
    paths: list[Path] = [
        here.parents[1] / "install_info.json",  # package root (installer convenience)
        _appdata_sidecar().parent / "install_info.json",
    ]
    pkg = preferences.__package__ or "blender_ai"
    try:
        user_dir = Path(bpy.utils.extension_path_user(pkg, path="", create=False))
        paths.insert(0, user_dir / "install_info.json")
    except Exception:
        pass
    return paths


def _resolve_sidecar_dir() -> Path | None:
    here = Path(__file__).resolve()
    candidates: list[Path] = []

    for info_path in _install_info_candidates():
        if not info_path.exists():
            continue
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            if info.get("sidecar_dir"):
                candidates.append(Path(info["sidecar_dir"]))
        except Exception:
            pass

    appdata = _appdata_sidecar()
    if appdata.exists():
        candidates.append(appdata)

    # Dev repo: extension/bridge/client.py → repo root is parents[2]
    for parents_up in (2, 3, 4):
        try:
            root = here.parents[parents_up]
            candidates.append(root / "sidecar")
        except IndexError:
            pass

    return next(
        (p for p in candidates if (p / "blender_ai_sidecar").exists() or (p / "pyproject.toml").exists()),
        None,
    )


def start_sidecar_process(context=None) -> bool:
    """Spawn sidecar if needed and start the bridge. Never blocks the UI thread.

    Returns True only if the sidecar is already online, an existing child is still
    alive, or a new process was spawned and is still running. Does not wait for
    /health — bridge thread updates status asynchronously.
    """
    global _process, _status
    with _spawn_lock:
        if not _online_access_ok():
            _status = "offline"
            return False
        if _resolve_host_port(context) is None:
            return False

        # Prefer bridge-thread status — do not poll /health on the main thread.
        if _status == "online":
            start_bridge(context)
            return True

        # Reuse our own child if still alive (avoid a second listener on :8765)
        if _process is not None and _process.poll() is None:
            if _status != "starting":
                _status = "starting"
            start_bridge(context)
            return True

        sidecar = _resolve_sidecar_dir()
        if not sidecar:
            _status = "offline"
            start_bridge(context)
            return False

        _status = "starting"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(sidecar) + os.pathsep + env.get("PYTHONPATH", "")

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
        except Exception:
            _process = None
            _status = "offline"
            start_bridge(context)
            return False

        # Honest check: process must still be alive (immediate crash → False)
        if _process.poll() is not None:
            _process = None
            _status = "offline"
            start_bridge(context)
            return False

        start_bridge(context)
        return True


def stop_sidecar_process():
    global _process, _status, _ws_thread
    with _spawn_lock:
        stop_bridge()
        if _ws_thread and _ws_thread.is_alive():
            try:
                _ws_thread.join(timeout=2.5)
            except Exception:
                pass
        if _process and _process.poll() is None:
            try:
                _process.terminate()
                try:
                    _process.wait(timeout=3.0)
                except Exception:
                    try:
                        _process.kill()
                    except Exception:
                        pass
            except Exception:
                pass
            _process = None
        # After the bridge thread exits so it cannot flip status back to online.
        _status = "offline"


def _deferred_boot():
    """Run after register() so enable stays fast (Blender extension guidelines)."""
    global _deferred_timer_registered, _status, _bridge
    _deferred_timer_registered = False
    if not _online_access_ok():
        _status = "offline"
        _bridge = "disconnected"
        return None
    prefs = preferences.get_prefs()
    if prefs and prefs.auto_start_sidecar:
        start_sidecar_process()
    else:
        start_bridge()
    return None


def register():
    global _deferred_timer_registered
    # Defer subprocess / FS scan so Preferences → Enable does not stall
    if not bpy.app.timers.is_registered(_deferred_boot):
        bpy.app.timers.register(_deferred_boot, first_interval=0.35, persistent=False)
        _deferred_timer_registered = True


def unregister():
    global _deferred_timer_registered
    if bpy.app.timers.is_registered(_deferred_boot):
        bpy.app.timers.unregister(_deferred_boot)
    _deferred_timer_registered = False
    stop_sidecar_process()
