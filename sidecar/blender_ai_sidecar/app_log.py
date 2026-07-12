"""Central log + crash-report helpers for the sidecar."""

from __future__ import annotations

import traceback
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from blender_ai_sidecar import __version__

_LEVELS = frozenset({"debug", "info", "warning", "error", "crash"})
_ring: deque[dict[str, Any]] = deque(maxlen=300)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_level(level: str) -> str:
    lv = (level or "info").strip().lower()
    if lv in ("warn", "warning"):
        return "warning"
    if lv in _LEVELS:
        return lv
    return "info"


def make_entry(
    level: str,
    source: str,
    message: str,
    *,
    component: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = {
        "id": str(uuid.uuid4()),
        "ts": _now(),
        "level": _normalize_level(level),
        "source": (source or "sidecar").strip() or "sidecar",
        "component": (component or "")[:128],
        "message": (message or "")[:4000],
        "detail": detail or {},
    }
    _ring.appendleft(entry)
    return entry


def ring_tail(limit: int = 50) -> list[dict[str, Any]]:
    return list(_ring)[: max(1, min(limit, 300))]


async def emit(
    db: Any,
    level: str,
    source: str,
    message: str,
    *,
    component: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry = make_entry(level, source, message, component=component, detail=detail)
    if db is not None:
        await db.insert_log(entry)
    return entry


async def create_report(
    db: Any,
    data_dir: Path,
    *,
    kind: str,
    source: str,
    summary: str,
    detail: dict[str, Any] | None = None,
    include_logs: int = 80,
) -> dict[str, Any]:
    kind_n = (kind or "error").strip().lower()
    if kind_n not in ("error", "crash", "feedback"):
        kind_n = "error"
    detail = dict(detail or {})
    detail.setdefault("sidecar_version", __version__)
    if "logs_tail" not in detail:
        if db is not None:
            detail["logs_tail"] = await db.list_logs(limit=include_logs)
        else:
            detail["logs_tail"] = ring_tail(include_logs)

    report_id = str(uuid.uuid4())
    ts = _now()
    reports_dir = Path(data_dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    file_path = reports_dir / f"report-{report_id[:8]}-{ts[:10]}.txt"

    lines = [
        f"BlenderAI report ({kind_n})",
        f"id: {report_id}",
        f"ts: {ts}",
        f"source: {source}",
        f"sidecar: {__version__}",
        f"summary: {summary}",
        "",
        "--- detail ---",
        str(detail.get("traceback") or detail.get("stack") or ""),
        "",
        "--- context ---",
    ]
    for key, val in detail.items():
        if key in ("logs_tail", "traceback", "stack"):
            continue
        lines.append(f"{key}: {val}")
    lines.append("")
    lines.append("--- recent logs ---")
    for log in detail.get("logs_tail") or []:
        lines.append(
            f"[{log.get('ts', '')}] {log.get('level', '')} "
            f"{log.get('source', '')}/{log.get('component', '')}: {log.get('message', '')}"
        )
    file_path.write_text("\n".join(lines), encoding="utf-8")

    entry = {
        "id": report_id,
        "ts": ts,
        "kind": kind_n,
        "source": (source or "unknown").strip() or "unknown",
        "summary": (summary or "")[:2000],
        "detail": detail,
        "file_path": str(file_path),
    }
    if db is not None:
        await db.insert_report(entry)

    await emit(
        db,
        "crash" if kind_n == "crash" else "error",
        source,
        f"Report filed: {summary}",
        component="reports",
        detail={"report_id": report_id, "file_path": str(file_path)},
    )
    return entry


def format_exception(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
