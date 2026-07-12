"""Local log ring + HTTP forward to sidecar /api/logs and /api/reports."""

from __future__ import annotations

import json
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timezone
from typing import Any

import bpy

from .bridge import client as bridge_client

MAX_LOCAL = 200
_ring: deque[dict[str, Any]] = deque(maxlen=MAX_LOCAL)
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _blender_detail() -> dict[str, Any]:
    try:
        return {
            "blender_version": bpy.app.version_string,
            "blender_version_cycle": getattr(bpy.app, "version_cycle", ""),
        }
    except Exception:
        return {}


def local_entries(limit: int = 80) -> list[dict[str, Any]]:
    with _lock:
        return list(_ring)[: max(1, min(limit, MAX_LOCAL))]


def clear_local() -> None:
    with _lock:
        _ring.clear()


def log(
    level: str,
    message: str,
    *,
    component: str = "",
    detail: dict[str, Any] | None = None,
    forward: bool = True,
) -> dict[str, Any]:
    entry = {
        "ts": _now(),
        "level": (level or "info").lower(),
        "source": "extension",
        "component": component or "",
        "message": (message or "")[:4000],
        "detail": {**_blender_detail(), **(detail or {})},
    }
    with _lock:
        _ring.appendleft(entry)
    if forward:
        _post_async("/api/logs", entry)
    # Avoid per-log VIEW_3D redraw storms (chat + bridge logs were hanging Blender).
    return entry


def warning(message: str, *, component: str = "", detail: dict[str, Any] | None = None) -> None:
    log("warning", message, component=component, detail=detail)


def error(message: str, *, component: str = "", detail: dict[str, Any] | None = None) -> None:
    log("error", message, component=component, detail=detail)


def exception(
    message: str,
    exc: BaseException | None = None,
    *,
    component: str = "",
) -> None:
    detail: dict[str, Any] = {}
    if exc is not None:
        detail["traceback"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    else:
        detail["traceback"] = traceback.format_exc()
    log("error", message, component=component, detail=detail)


def _post_async(path: str, payload: dict[str, Any]) -> None:
    def _run() -> None:
        try:
            base = bridge_client.base_url()
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                base + path,
                data=data,
                headers=bridge_client.auth_headers(
                    {"Content-Type": "application/json", "Accept": "application/json"}
                ),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                resp.read()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def fetch_remote(limit: int = 100, level: str = "") -> tuple[bool, list[dict[str, Any]], str]:
    try:
        base = bridge_client.base_url()
        q = f"?limit={int(limit)}"
        if level:
            q += f"&level={urllib.parse.quote(level)}"
        req = urllib.request.Request(
            base + "/api/logs" + q,
            headers=bridge_client.auth_headers({"Accept": "application/json"}),
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return True, list(data.get("logs") or []), ""
    except Exception as exc:
        return False, [], str(exc)


def clear_remote() -> tuple[bool, str]:
    try:
        base = bridge_client.base_url()
        req = urllib.request.Request(
            base + "/api/logs",
            headers=bridge_client.auth_headers({"Accept": "application/json"}),
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            resp.read()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def send_report(
    summary: str,
    *,
    kind: str = "error",
    note: str = "",
    detail: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any] | None, str]:
    payload = {
        "kind": kind,
        "source": "extension",
        "summary": summary,
        "note": note,
        "detail": {
            **_blender_detail(),
            "local_logs": local_entries(60),
            **(detail or {}),
        },
    }
    try:
        base = bridge_client.base_url()
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            base + "/api/reports",
            data=data,
            headers=bridge_client.auth_headers(
                {"Content-Type": "application/json", "Accept": "application/json"}
            ),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        log("info", f"Report sent: {summary}", component="reports", forward=True)
        return True, body, ""
    except urllib.error.HTTPError as exc:
        try:
            detail_txt = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail_txt = str(exc)
        return False, None, detail_txt or str(exc)
    except Exception as exc:
        return False, None, str(exc)
