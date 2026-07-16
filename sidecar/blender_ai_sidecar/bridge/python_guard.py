"""Sandboxed Python validation for python.run (sidecar pre-check).

Keep in sync with extension/bridge/py_sandbox.py — same AST rules so the model
gets precise errors before a Blender round-trip.
"""

from __future__ import annotations

import ast

MAX_CODE_BYTES = 20_480

ALLOWED_IMPORT_ROOTS = frozenset({"bpy", "bmesh", "math", "mathutils", "random"})

FORBIDDEN_NAMES = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "help",
        "memoryview",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "type",
        "classmethod",
        "staticmethod",
        "property",
        "super",
        "object",
        "__builtins__",
        "__loader__",
        "__spec__",
    }
)

FORBIDDEN_ATTR_PARTS = frozenset(
    {
        "__globals__",
        "__builtins__",
        "__code__",
        "__class__",
        "__subclasses__",
        "__mro__",
        "__bases__",
        "__dict__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
        "__reduce__",
        "__reduce_ex__",
        "__getstate__",
        "__setstate__",
        "__module__",
        "__qualname__",
        "__annotations__",
        "__closure__",
        "__func__",
        "__self__",
        "__wrapped__",
        "__import__",
    }
)

FORBIDDEN_ATTR_CHAINS = frozenset(
    {
        ("bpy", "ops", "wm"),
        ("bpy", "app"),
        ("bpy", "path"),
        ("bpy", "utils", "script"),
    }
)


class SandboxError(ValueError):
    """Raised when code fails sandbox validation."""


def _attr_chain(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return parts
    return None


def _check_import(node: ast.Import | ast.ImportFrom) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            root = (alias.name or "").split(".", 1)[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                raise SandboxError(f"Import not allowed: {alias.name}")
        return
    if node.level and node.level > 0:
        raise SandboxError("Relative imports are not allowed")
    mod = node.module or ""
    root = mod.split(".", 1)[0] if mod else ""
    if root not in ALLOWED_IMPORT_ROOTS:
        raise SandboxError(f"Import not allowed: {mod or '*'}")


def validate_code(code: str) -> str:
    """Validate *code* for sandboxed execution. Returns stripped code or raises SandboxError."""
    if not isinstance(code, str):
        raise SandboxError("python.run requires a string 'code' argument")
    text = code.strip()
    if not text:
        raise SandboxError("python.run code is empty")
    if len(text.encode("utf-8", errors="replace")) > MAX_CODE_BYTES:
        raise SandboxError(f"python.run code exceeds {MAX_CODE_BYTES} bytes")

    try:
        tree = ast.parse(text, mode="exec")
    except SyntaxError as exc:
        raise SandboxError(f"Syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _check_import(node)
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                raise SandboxError(f"Forbidden name: {node.id}")
            if node.id.startswith("__") and node.id.endswith("__"):
                raise SandboxError(f"Forbidden dunder name: {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTR_PARTS or (
                node.attr.startswith("__") and node.attr.endswith("__")
            ):
                raise SandboxError(f"Forbidden attribute: {node.attr}")
            chain = _attr_chain(node)
            if chain:
                for banned in FORBIDDEN_ATTR_CHAINS:
                    if tuple(chain[: len(banned)]) == banned:
                        raise SandboxError(f"Forbidden attribute chain: {'.'.join(banned)}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
                raise SandboxError(f"Forbidden call: {node.func.id}")

    return text
