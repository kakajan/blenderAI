"""Ensure sidecar ToolRegistry and extension allowlist stay aligned."""

from __future__ import annotations

import ast
from pathlib import Path

from blender_ai_sidecar.tools import get_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PY = REPO_ROOT / "extension" / "bridge" / "allowlist.py"


def _extension_known_tools() -> set[str]:
    tree = ast.parse(ALLOWLIST_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        call = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "KNOWN_TOOLS":
                call = node.value
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "KNOWN_TOOLS":
                    call = node.value
        if isinstance(call, ast.Call) and call.args:
            elts = call.args[0]
            if isinstance(elts, (ast.Set, ast.Tuple, ast.List)):
                return {e.value for e in elts.elts if isinstance(e, ast.Constant)}
    raise AssertionError("KNOWN_TOOLS not found in allowlist.py")


def test_extension_allowlist_matches_registry():
    registry = get_registry().allowlist()
    known = _extension_known_tools()
    assert known == registry, (
        f"extension-only: {sorted(known - registry)}; "
        f"registry-only: {sorted(registry - known)}"
    )


def test_procedural_tools_present_on_both_sides():
    needed = {
        "python.run",
        "curve.create",
        "mesh.loft_profiles",
        "asset.list",
        "asset.import",
    }
    registry = get_registry().allowlist()
    known = _extension_known_tools()
    assert needed <= registry
    assert needed <= known
