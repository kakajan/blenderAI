"""Tests for sandboxed python.run validation (sidecar + extension mirror)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from blender_ai_sidecar.bridge.python_guard import SandboxError, validate_code

# Also exercise the extension copy (no bpy) so the two stay aligned.
REPO_ROOT = Path(__file__).resolve().parents[2]
EXT_BRIDGE = REPO_ROOT / "extension" / "bridge"
if str(EXT_BRIDGE) not in sys.path:
    sys.path.insert(0, str(EXT_BRIDGE.parent))


def test_allows_bmesh_modeling_script():
    code = """
import bpy
import bmesh
import math
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
result = {'verts': len(bm.verts)}
bm.free()
"""
    out = validate_code(code)
    assert "bmesh" in out


def test_rejects_os_import():
    with pytest.raises(SandboxError, match="Import not allowed"):
        validate_code("import os\n")


def test_rejects_open_call():
    with pytest.raises(SandboxError, match="Forbidden"):
        validate_code("open('/tmp/x', 'w')\n")


def test_rejects_eval():
    with pytest.raises(SandboxError, match="Forbidden"):
        validate_code("eval('1+1')\n")


def test_rejects_dunder_attr():
    with pytest.raises(SandboxError, match="Forbidden attribute"):
        validate_code("x = ().__class__\n")


def test_rejects_bpy_app():
    with pytest.raises(SandboxError, match="Forbidden attribute chain"):
        validate_code("import bpy\nx = bpy.app.version\n")


def test_rejects_empty():
    with pytest.raises(SandboxError, match="empty"):
        validate_code("   \n")


def test_rejects_oversized():
    with pytest.raises(SandboxError, match="exceeds"):
        validate_code("x = 1\n" + ("y = 1\n" * 20000))


def test_extension_py_sandbox_mirrors_rules():
    from bridge import py_sandbox  # type: ignore

    assert py_sandbox.MAX_CODE_BYTES == 20_480
    py_sandbox.validate_code("import math\nresult = math.pi\n")
    with pytest.raises(py_sandbox.SandboxError):
        py_sandbox.validate_code("import subprocess\n")
