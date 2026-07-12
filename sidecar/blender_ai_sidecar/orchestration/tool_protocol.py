"""Tool call parsing — native tool_calls preferred, resilient JSON fence fallback."""

from __future__ import annotations

import json
import re
from typing import Any

# Non-greedy single-object match is insufficient for nested args; use balanced scan.
_FENCE_RE = re.compile(r"```(?:json)?\s*(?:tool\s*)?", re.IGNORECASE)


def _extract_balanced_object(text: str, start: int) -> tuple[dict[str, Any] | None, int]:
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                raw = text[start : i + 1]
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    return None, i + 1
                if isinstance(data, dict):
                    return data, i + 1
                return None, i + 1
    return None, start


def parse_tool_calls_from_text(text: str) -> list[dict[str, Any]]:
    """Parse one or more ```json tool {…}``` blocks with nested-object support."""
    calls: list[dict[str, Any]] = []
    pos = 0
    while True:
        match = _FENCE_RE.search(text, pos)
        if not match:
            break
        cursor = match.end()
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        obj, next_pos = _extract_balanced_object(text, cursor)
        if obj and obj.get("tool"):
            calls.append({"tool": obj.get("tool"), "args": obj.get("args") or {}})
            pos = next_pos
            continue
        pos = match.end() + 1
    return calls


def parse_first_tool_call(text: str) -> dict[str, Any] | None:
    calls = parse_tool_calls_from_text(text)
    return calls[0] if calls else None


def parse_native_tool_calls(event_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Normalize provider-native tool_call payloads into {tool, args} list."""
    if not event_data:
        return []
    raw = event_data.get("tool_calls") or event_data.get("tools") or []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        # OpenAI shape: {function: {name, arguments}}
        fn = item.get("function") if isinstance(item.get("function"), dict) else None
        if fn:
            name = fn.get("name")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if name:
                out.append({"tool": name, "args": args if isinstance(args, dict) else {}})
            continue
        # Anthropic / simplified
        name = item.get("name") or item.get("tool")
        args = item.get("input") or item.get("args") or {}
        if name:
            out.append({"tool": name, "args": args if isinstance(args, dict) else {}})
    return out
