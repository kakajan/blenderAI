"""Lightweight retrieval over docs/blender-refs for adaptive prompting."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from blender_ai_sidecar.config import get_settings, repo_root


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-z0-9_]{3,}", (text or "").lower())}


def blender_refs_dir() -> Path:
    settings = get_settings()
    # Prefer installed/bundled docs next to repo; fall back to data_dir copy.
    candidates = [
        repo_root() / "docs" / "blender-refs",
        Path(__file__).resolve().parents[2] / "docs" / "blender-refs",
        settings.data_dir / "knowledge" / "blender-refs",
    ]
    for path in candidates:
        if (path / "index.json").exists():
            return path
    return candidates[0]


@lru_cache(maxsize=1)
def load_index() -> dict[str, Any]:
    path = blender_refs_dir() / "index.json"
    if not path.exists():
        return {"version": None, "chunks": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": None, "chunks": []}


def reset_knowledge_cache() -> None:
    load_index.cache_clear()


def retrieve(query: str, *, limit: int = 3, tags: list[str] | None = None) -> list[dict[str, Any]]:
    data = load_index()
    chunks = list(data.get("chunks") or [])
    if not chunks:
        return []
    q_tokens = _tokenize(query)
    tag_set = {t.lower() for t in (tags or [])}
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        text = " ".join(
            [
                str(chunk.get("title") or ""),
                str(chunk.get("text") or ""),
                " ".join(chunk.get("tags") or []),
            ]
        )
        tokens = _tokenize(text)
        score = float(len(q_tokens & tokens))
        chunk_tags = {str(t).lower() for t in (chunk.get("tags") or [])}
        if tag_set:
            score += 2.0 * len(tag_set & chunk_tags)
        if score <= 0 and not tag_set:
            continue
        if score <= 0 and tag_set and not (tag_set & chunk_tags):
            continue
        scored.append((score, chunk))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("id") or "")))
    if not scored and tag_set:
        # Fallback: any chunk sharing a tag
        for chunk in chunks:
            chunk_tags = {str(t).lower() for t in (chunk.get("tags") or [])}
            if tag_set & chunk_tags:
                scored.append((1.0, chunk))
        scored.sort(key=lambda x: (-x[0], str(x[1].get("id") or "")))
    return [c for _, c in scored[: max(1, limit)]]


def format_for_prompt(chunks: list[dict[str, Any]], *, max_chars: int = 1800) -> str:
    if not chunks:
        return ""
    lines = ["## Blender reference notes (retrieved)", ""]
    used = 0
    for chunk in chunks:
        block = f"### {chunk.get('title') or chunk.get('id')}\n{chunk.get('text') or ''}\n"
        if used + len(block) > max_chars:
            break
        lines.append(block)
        used += len(block)
    api = load_index().get("api_url")
    if api:
        lines.append(f"API: {api}")
    return "\n".join(lines).strip()
