"""Multimodal context assembly + simple attachment store."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from blender_ai_sidecar.config import get_settings
from blender_ai_sidecar.contracts import ContextBundle, ImageRef, ProviderCapabilities


def attachments_dir() -> Path:
    path = get_settings().data_dir / "attachments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resize_hint_b64(data: bytes, *, max_edge: int = 1536) -> bytes:
    """Best-effort resize via stdlib only — return original if Pillow unavailable."""
    try:
        import io

        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(data))
        img.load()
        w, h = img.size
        scale = min(1.0, max_edge / float(max(w, h) or 1))
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        out = io.BytesIO()
        fmt = "JPEG" if img.mode in {"RGB", "L"} else "PNG"
        if fmt == "JPEG" and img.mode not in {"RGB", "L"}:
            img = img.convert("RGB")
        img.save(out, format=fmt, quality=85, optimize=True)
        return out.getvalue()
    except Exception:
        return data


def store_attachment(
    data: bytes,
    *,
    chat_id: str | None = None,
    mime: str = "image/png",
    view: str | None = None,
    source: str = "viewport",
    meta: dict[str, Any] | None = None,
) -> ImageRef:
    data = _resize_hint_b64(data)
    attach_id = str(uuid.uuid4())
    folder = attachments_dir() / (chat_id or "_shared")
    folder.mkdir(parents=True, exist_ok=True)
    ext = ".jpg" if "jpeg" in mime or "jpg" in mime else ".png"
    path = folder / f"{attach_id}{ext}"
    path.write_bytes(data)
    meta_path = folder / f"{attach_id}.json"
    meta_path.write_text(
        json.dumps(
            {
                "id": attach_id,
                "mime": mime,
                "view": view,
                "source": source,
                "created_at": time.time(),
                "meta": meta or {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return ImageRef(
        id=attach_id,
        source=source,  # type: ignore[arg-type]
        mime=mime,
        data_base64=base64.b64encode(data).decode("ascii"),
        storage_id=attach_id,
        path=str(path),
        view=view,
        camera=(meta or {}).get("camera"),
        framing=(meta or {}).get("framing"),
        caption=f"View: {view}" if view else None,
    )


def read_image_b64(path: str) -> str | None:
    if not path:
        return None
    try:
        data = Path(path).read_bytes()
        if not data:
            return None
        data = _resize_hint_b64(data)
        return base64.b64encode(data).decode("ascii")
    except Exception:
        return None


def image_refs_from_capture(cap: dict[str, Any], *, chat_id: str | None = None) -> list[ImageRef]:
    refs: list[ImageRef] = []
    views = cap.get("views") or []
    if isinstance(views, list) and views:
        for item in views:
            if not isinstance(item, dict):
                continue
            path = item.get("path") or ""
            raw = Path(path).read_bytes() if path and Path(path).exists() else b""
            if not raw:
                continue
            refs.append(
                store_attachment(
                    raw,
                    chat_id=chat_id,
                    mime="image/png",
                    view=str(item.get("view") or "user"),
                    source="critique" if len(views) > 1 else "viewport",
                    meta={"camera": item.get("camera"), "framing": item.get("framing")},
                )
            )
        return refs
    path = cap.get("path") or ""
    raw = Path(path).read_bytes() if path and Path(path).exists() else b""
    if raw:
        refs.append(
            store_attachment(
                raw,
                chat_id=chat_id,
                mime="image/png",
                view="user",
                source="viewport",
            )
        )
    return refs


def build_context_bundle(
    *,
    scene_summary: dict[str, Any] | None,
    images: list[ImageRef] | None = None,
    memory: list[dict[str, Any]] | None = None,
    skill_id: str | None = None,
    connected: bool = False,
    strategy: dict[str, Any] | None = None,
    text_enrichments: list[str] | None = None,
) -> ContextBundle:
    return ContextBundle(
        scene=scene_summary,
        images=list(images or []),
        memory=list(memory or []),
        skill_id=skill_id,
        connection={"connected": connected},
        strategy=strategy,
        text_enrichments=list(text_enrichments or []),
    )


def apply_capability_gate(
    bundle: ContextBundle,
    caps: ProviderCapabilities,
) -> tuple[ContextBundle, str | None]:
    """Drop or truncate images based on provider capabilities. Returns warning if any."""
    if not bundle.images:
        return bundle, None
    if not caps.vision or caps.max_images <= 0:
        digest = {
            "note": "Provider/model does not support vision; images omitted.",
            "views": [img.view or img.source for img in bundle.images],
        }
        enrichments = list(bundle.text_enrichments)
        enrichments.append("Visual digest (no vision model):\n" + json.dumps(digest, ensure_ascii=False))
        return bundle.model_copy(update={"images": [], "text_enrichments": enrichments}), (
            "Model does not support vision; attached images were converted to a text digest."
        )
    if len(bundle.images) > caps.max_images:
        kept = bundle.images[: caps.max_images]
        return bundle.model_copy(update={"images": kept}), (
            f"Truncated images to max_images={caps.max_images}"
        )
    return bundle, None


def cleanup_attachments(*, max_age_seconds: float = 7 * 24 * 3600, max_files: int = 500) -> int:
    root = attachments_dir()
    removed = 0
    files: list[tuple[float, Path]] = []
    now = time.time()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".json":
            continue
        try:
            age = now - path.stat().st_mtime
            if age > max_age_seconds:
                path.unlink(missing_ok=True)
                path.with_suffix(".json").unlink(missing_ok=True)
                removed += 1
            else:
                files.append((path.stat().st_mtime, path))
        except Exception:
            continue
    if len(files) > max_files:
        files.sort(key=lambda x: x[0])
        for _, path in files[: len(files) - max_files]:
            path.unlink(missing_ok=True)
            path.with_suffix(".json").unlink(missing_ok=True)
            removed += 1
    return removed


def scope_key(project_path: str | None, profile_id: str | None = None) -> str:
    base = (project_path or "global").strip().lower()
    profile = (profile_id or "default").strip().lower()
    digest = hashlib.sha256(f"{profile}|{base}".encode("utf-8")).hexdigest()[:16]
    return f"{profile}:{digest}"
