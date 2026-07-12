"""CI-friendly checks for the flat Blender extension layout."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSION = REPO_ROOT / "extension"
MANIFEST = EXTENSION / "blender_manifest.toml"
INIT = EXTENSION / "__init__.py"
NESTED_INIT = EXTENSION / "blender_ai" / "__init__.py"


def test_extension_flat_layout_exists():
    assert MANIFEST.is_file(), f"missing manifest: {MANIFEST}"
    assert INIT.is_file(), f"missing flat package init: {INIT}"
    # Flat layout must not require the legacy nested package.
    assert not NESTED_INIT.is_file(), (
        "legacy nested extension/blender_ai/__init__.py must not be required "
        f"(found {NESTED_INIT})"
    )


def test_extension_manifest_parses_id_version():
    text = MANIFEST.read_text(encoding="utf-8")
    # Prefer tomllib when available (3.11+); fall back to simple regex for CI.
    try:
        import tomllib

        data = tomllib.loads(text)
        ext_id = data.get("id")
        version = data.get("version")
    except Exception:
        id_m = re.search(r'(?m)^id\s*=\s*"([^"]+)"', text)
        ver_m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
        ext_id = id_m.group(1) if id_m else None
        version = ver_m.group(1) if ver_m else None

    assert ext_id == "blender_ai"
    assert version and re.match(r"^\d+\.\d+\.\d+", str(version))
