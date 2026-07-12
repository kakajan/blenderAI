"""Cached sidecar catalogs for N-Panel enums (providers, models, skills, presets).

HTTP runs on a background thread — never from panel draw.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request
from typing import Any

import bpy

from .bridge import client as bridge_client

# Persistent lists for EnumProperty item callbacks (must keep identity stable-ish).
_provider_items: list[tuple[str, str, str]] = [("ollama", "Ollama", "")]
_model_items: list[tuple[str, str, str]] = [("", "(auto)", "Use provider default")]
_skill_items: list[tuple[str, str, str]] = [("", "—", "No skill")]
_preset_items: list[tuple[str, str, str]] = [("", "—", "No preset")]
_workflow_items: list[tuple[str, str, str]] = [("", "—", "No workflow")]
_preset_prompts: dict[str, str] = {}
_workflow_ids: set[str] = set()
_lock = threading.Lock()
_refreshing = False
_status = ""


def provider_items(self, context):
    with _lock:
        return list(_provider_items) or [("ollama", "Ollama", "")]


def model_items(self, context):
    with _lock:
        return list(_model_items) or [("", "(auto)", "Use provider default")]


def skill_items(self, context):
    with _lock:
        return list(_skill_items) or [("", "—", "No skill")]


def preset_items(self, context):
    with _lock:
        return list(_preset_items) or [("", "—", "No preset")]


def workflow_items(self, context):
    with _lock:
        return list(_workflow_items) or [("", "—", "No workflow")]


def is_workflow_preset(preset_id: str) -> bool:
    with _lock:
        return (preset_id or "") in _workflow_ids

def preset_prompt(preset_id: str) -> str:
    with _lock:
        return _preset_prompts.get(preset_id or "", "")


def _prompt_from_preset(preset: dict[str, Any]) -> str:
    text = str(preset.get("prompt") or "").strip()
    if text:
        return text
    steps = preset.get("steps")
    if isinstance(steps, list) and steps:
        lines: list[str] = []
        for step in steps:
            if isinstance(step, str):
                lines.append(f"- {step}")
            elif isinstance(step, dict):
                title = str(step.get("title") or step.get("name") or "").strip()
                detail = str(
                    step.get("detail") or step.get("text") or step.get("prompt") or ""
                ).strip()
                if title and detail:
                    lines.append(f"- {title}: {detail}")
                elif title or detail:
                    lines.append(f"- {title or detail}")
        return "\n".join(lines).strip()
    return str(preset.get("prompt_preview") or "").strip()


def fetch_preset_prompt(base: str, preset_id: str) -> tuple[str, str]:
    """Load full preset prompt from sidecar. Returns (prompt, error)."""
    pid = (preset_id or "").strip()
    if not pid:
        return "", "No preset selected"

    cached = preset_prompt(pid)
    try:
        enc = urllib.parse.quote(pid, safe="/")
        data = _http_json(f"{base}/api/presets/{enc}", timeout=5.0)
        preset = data.get("preset") or {}
        prompt = _prompt_from_preset(preset)
        if prompt:
            with _lock:
                _preset_prompts[pid] = prompt
            return prompt, ""
        if cached:
            return cached, ""
        return "", "Preset has no prompt text"
    except Exception as exc:
        if cached:
            return cached, ""
        return "", str(exc)


def refresh_status() -> str:
    with _lock:
        return _status


def is_refreshing() -> bool:
    with _lock:
        return _refreshing


def _http_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _set_items(
    providers: list[tuple[str, str, str]],
    models: list[tuple[str, str, str]],
    skills: list[tuple[str, str, str]],
    presets: list[tuple[str, str, str]],
    prompts: dict[str, str],
    status: str,
    workflows: list[tuple[str, str, str]] | None = None,
    workflow_ids: set[str] | None = None,
) -> None:
    global _status, _refreshing
    with _lock:
        _provider_items.clear()
        _provider_items.extend(providers or [("ollama", "Ollama", "")])
        _model_items.clear()
        _model_items.extend(models or [("", "(auto)", "Use provider default")])
        _skill_items.clear()
        _skill_items.extend(skills or [("", "—", "No skill")])
        _preset_items.clear()
        _preset_items.extend(presets or [("", "—", "No preset")])
        _workflow_items.clear()
        _workflow_items.extend(workflows or [("", "—", "No workflow")])
        _workflow_ids.clear()
        if workflow_ids:
            _workflow_ids.update(workflow_ids)
        _preset_prompts.clear()
        _preset_prompts.update(prompts)
        _status = status
        _refreshing = False


def _tag_redraw() -> None:
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:
        pass


def _fetch_all(base: str, provider_id: str) -> None:
    global _refreshing, _status
    with _lock:
        _refreshing = True
        _status = "Refreshing…"

    providers: list[tuple[str, str, str]] = []
    models: list[tuple[str, str, str]] = [("", "(auto)", "Use provider default")]
    skills: list[tuple[str, str, str]] = [("", "—", "No skill")]
    presets: list[tuple[str, str, str]] = [("", "—", "No preset")]
    workflows: list[tuple[str, str, str]] = [("", "—", "No workflow")]
    workflow_ids: set[str] = set()
    prompts: dict[str, str] = {}
    err = ""

    try:
        pdata = _http_json(f"{base}/api/providers", timeout=4.0)
        for p in pdata.get("providers") or []:
            if not p.get("enabled", True):
                continue
            pid = str(p.get("id") or "")
            if not pid:
                continue
            name = str(p.get("name") or pid)
            providers.append((pid, name, str(p.get("kind") or "")))
        if not providers:
            providers = [("ollama", "Ollama", "")]

        pid = provider_id if any(x[0] == provider_id for x in providers) else providers[0][0]
        try:
            mdata = _http_json(f"{base}/api/providers/{pid}/models", timeout=8.0)
            for m in mdata.get("models") or []:
                mid = str(m.get("id") or m.get("name") or "")
                if not mid:
                    continue
                label = str(m.get("name") or mid)
                if len(label) > 48:
                    label = label[:45] + "…"
                models.append((mid, label, mid))
        except Exception as exc:
            err = f"models: {exc}"

        try:
            sdata = _http_json(f"{base}/api/skills", timeout=4.0)
            for s in sdata.get("skills") or []:
                sid = str(s.get("id") or "")
                if not sid:
                    continue
                skills.append((sid, str(s.get("name") or sid), str(s.get("description") or "")[:80]))
        except Exception as exc:
            err = (err + f"; skills: {exc}").strip("; ")

        try:
            prdata = _http_json(f"{base}/api/presets", timeout=4.0)
            for pr in prdata.get("presets") or []:
                prid = str(pr.get("id") or "")
                if not prid:
                    continue
                presets.append(
                    (prid, str(pr.get("name") or prid), str(pr.get("description") or "")[:80])
                )
                prompts[prid] = str(pr.get("prompt") or pr.get("prompt_preview") or "")
        except Exception as exc:
            err = (err + f"; presets: {exc}").strip("; ")

        try:
            wdata = _http_json(f"{base}/api/workflows", timeout=4.0)
            for w in wdata.get("workflows") or []:
                wid = str(w.get("id") or "")
                if not wid:
                    continue
                workflows.append(
                    (wid, str(w.get("name") or wid), str(w.get("description") or "")[:80])
                )
                workflow_ids.add(wid)
        except Exception as exc:
            err = (err + f"; workflows: {exc}").strip("; ")

        status = err or f"Loaded {len(providers)} provider(s), {len(models) - 1} model(s)"
        _set_items(providers, models, skills, presets, prompts, status, workflows, workflow_ids)
    except Exception as exc:
        _set_items(
            list(_provider_items) or [("ollama", "Ollama", "")],
            list(_model_items),
            list(_skill_items),
            list(_preset_items),
            dict(_preset_prompts),
            f"Refresh failed: {exc}",
            list(_workflow_items),
            set(_workflow_ids),
        )
    finally:
        with _lock:
            _refreshing = False
        # Schedule redraw on main thread
        def _redraw_once():
            _tag_redraw()
            return None

        try:
            if not bpy.app.timers.is_registered(_redraw_once):
                bpy.app.timers.register(_redraw_once, first_interval=0.05)
        except Exception:
            pass


def refresh_async(context=None, provider_id: str | None = None) -> bool:
    """Kick off a background catalog refresh. Returns False if already running."""
    global _refreshing
    with _lock:
        if _refreshing:
            return False
        _refreshing = True

    prefs = None
    try:
        from . import preferences

        prefs = preferences.get_prefs(context)
    except Exception:
        pass

    base = bridge_client.base_url(context)
    if not provider_id:
        settings = getattr(getattr(context, "window_manager", None), "blender_ai_settings", None)
        if settings and settings.provider_id:
            provider_id = settings.provider_id
        elif prefs:
            provider_id = prefs.active_provider or "ollama"
        else:
            provider_id = "ollama"

    threading.Thread(
        target=_fetch_all,
        args=(base, provider_id or "ollama"),
        daemon=True,
        name="BlenderAI-settings-refresh",
    ).start()
    return True


def sync_selection_to_prefs(context) -> None:
    settings = getattr(context.window_manager, "blender_ai_settings", None)
    if settings is None:
        return
    from . import preferences

    prefs = preferences.get_prefs(context)
    if prefs is None:
        return
    if settings.provider_id:
        prefs.active_provider = settings.provider_id
    prefs.active_model = settings.model_id or ""
