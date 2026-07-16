"""Sandboxed Python validation for the python.run tool.

No bpy import — this module is unit-testable outside Blender.
Keep in sync with sidecar/blender_ai_sidecar/bridge/python_guard.py.
"""

from __future__ import annotations

import ast
import io
from typing import Any

MAX_CODE_BYTES = 20_480
MAX_STDOUT_CHARS = 10_240
DEFAULT_TIMEOUT_SEC = 20.0

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

# Attribute chains that must never appear (module-level escapes).
FORBIDDEN_ATTR_CHAINS = frozenset(
    {
        ("bpy", "ops", "wm"),
        ("bpy", "app"),
        ("bpy", "path"),
        ("bpy", "utils", "script"),
    }
)

SAFE_BUILTIN_NAMES = (
    "abs",
    "all",
    "any",
    "bool",
    "bytes",
    "callable",
    "chr",
    "complex",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "format",
    "frozenset",
    "hash",
    "hex",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "oct",
    "ord",
    "pow",
    "print",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    "True",
    "False",
    "None",
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
            # Block builtins.call-style via Name
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_NAMES:
                raise SandboxError(f"Forbidden call: {node.func.id}")

    return text


def _check_import(node: ast.Import | ast.ImportFrom) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            root = (alias.name or "").split(".", 1)[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                raise SandboxError(f"Import not allowed: {alias.name}")
        return
    # ImportFrom
    if node.level and node.level > 0:
        raise SandboxError("Relative imports are not allowed")
    mod = node.module or ""
    root = mod.split(".", 1)[0] if mod else ""
    if root not in ALLOWED_IMPORT_ROOTS:
        raise SandboxError(f"Import not allowed: {mod or '*'}")


def build_safe_builtins() -> dict[str, Any]:
    """Subset of builtins safe for modeling scripts."""
    import builtins as _builtins

    out: dict[str, Any] = {}
    for name in SAFE_BUILTIN_NAMES:
        if name in {"True", "False", "None"}:
            out[name] = getattr(_builtins, name, None) if name != "None" else None
            if name == "True":
                out[name] = True
            elif name == "False":
                out[name] = False
            else:
                out[name] = None
            continue
        if hasattr(_builtins, name):
            out[name] = getattr(_builtins, name)
    return out


class _StdoutCapture(io.StringIO):
    def write(self, s: str) -> int:  # type: ignore[override]
        if self.tell() >= MAX_STDOUT_CHARS:
            return 0
        remaining = MAX_STDOUT_CHARS - self.tell()
        if len(s) > remaining:
            s = s[:remaining]
        return super().write(s)


def run_sandboxed(
    code: str,
    *,
    globals_dict: dict[str, Any],
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any]:
    """Execute validated code with a line-level timeout via sys.settrace.

    *globals_dict* must already include allowed modules and ``__builtins__``.
    Returns ``{"ok": True, "stdout": ..., "result": ...}`` or raises.
    """
    import sys
    import time

    validated = validate_code(code)
    timeout = max(0.5, float(timeout_sec))
    start = time.monotonic()
    stdout = _StdoutCapture()

    def _tracer(frame, event, arg):  # noqa: ANN001
        if event == "line" and (time.monotonic() - start) > timeout:
            raise TimeoutError(f"python.run exceeded {timeout:.1f}s")
        return _tracer

    # Redirect print
    old_stdout = sys.stdout
    old_trace = sys.gettrace()
    result_value: Any = None
    try:
        sys.stdout = stdout
        sys.settrace(_tracer)
        exec(compile(validated, "<blenderai_python_run>", "exec"), globals_dict, globals_dict)
        result_value = globals_dict.get("result")
    finally:
        sys.settrace(old_trace)
        sys.stdout = old_stdout

    out: dict[str, Any] = {
        "ok": True,
        "stdout": stdout.getvalue(),
        "elapsed_sec": round(time.monotonic() - start, 3),
    }
    if result_value is not None:
        try:
            # Prefer JSON-friendly values
            if isinstance(result_value, (str, int, float, bool, list, dict)) or result_value is None:
                out["result"] = result_value
            else:
                out["result"] = repr(result_value)[:2000]
        except Exception:
            out["result"] = "<unserializable>"
    return out
