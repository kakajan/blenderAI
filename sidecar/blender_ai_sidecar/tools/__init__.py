"""Authoritative tool registry — single source of truth for allowlist, docs, risk."""

from __future__ import annotations

from typing import Iterable

from blender_ai_sidecar.contracts import ToolSpec

# Canonical specs. Keep names stable — Blender handlers and skills depend on them.
_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(name="scene.summary", doc="Return a structured scene summary.", risk="read", domains=["scene"], tags=["read"]),
    ToolSpec(
        name="viewport.capture",
        doc='Capture viewport image(s). Pass views=["front","side","back"] for turnaround.',
        risk="read",
        domains=["viewport", "review"],
        tags=["vision", "read"],
    ),
    ToolSpec(name="viewport.set_shading", doc="Set viewport shading mode.", risk="low", domains=["viewport"], tags=["viewport"]),
    ToolSpec(name="undo", doc="Undo last Blender action.", risk="destructive", domains=["scene"], tags=["history"]),
    ToolSpec(name="redo", doc="Redo last Blender action.", risk="destructive", domains=["scene"], tags=["history"]),
    ToolSpec(
        name="scene.create_object",
        doc="Create a primitive object (cube, uv_sphere, cylinder, …).",
        risk="low",
        domains=["modeling"],
        tags=["modeling", "create"],
    ),
    ToolSpec(
        name="mesh.from_data",
        doc="Build mesh from vertices/faces parts in one call.",
        risk="medium",
        domains=["modeling"],
        tags=["modeling", "surface"],
    ),
    ToolSpec(name="selection.set", doc="Set object selection.", risk="low", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="mesh.select", doc="Select mesh elements (semantic or indices).", risk="low", domains=["modeling"], tags=["modeling", "surface"]),
    ToolSpec(name="mesh.extrude", doc="Extrude selected mesh geometry.", risk="medium", domains=["modeling"], tags=["modeling", "surface"]),
    ToolSpec(name="mesh.edge_loop", doc="Select/cut edge loops.", risk="medium", domains=["modeling"], tags=["modeling", "surface"]),
    ToolSpec(name="mesh.profile_extrude", doc="Extrude a profile curve into mesh features.", risk="medium", domains=["modeling"], tags=["modeling", "surface"]),
    ToolSpec(name="mesh.ops", doc="Apply mesh operators (bevel, inset, subdivide, …).", risk="medium", domains=["modeling"], tags=["modeling", "surface"]),
    ToolSpec(name="object.transform", doc="Translate/rotate/scale an object.", risk="low", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="object.join", doc="Join selected objects.", risk="medium", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="object.duplicate", doc="Duplicate object(s).", risk="low", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="object.delete", doc="Delete object(s).", risk="destructive", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="object.parent", doc="Parent objects.", risk="medium", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="modifier.add", doc="Add a modifier.", risk="medium", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="modifier.apply", doc="Apply a modifier (destructive).", risk="destructive", domains=["modeling"], tags=["modeling"]),
    ToolSpec(name="material.create", doc="Create a material.", risk="low", domains=["materials"], tags=["materials"]),
    ToolSpec(name="material.assign", doc="Assign material to object.", risk="low", domains=["materials"], tags=["materials"]),
    ToolSpec(name="node.set", doc="Set shader/node values.", risk="medium", domains=["materials", "nodes"], tags=["materials", "nodes"]),
    ToolSpec(name="nodes.geometry_set", doc="Create/update a geometry nodes tree.", risk="medium", domains=["nodes"], tags=["nodes"]),
    ToolSpec(name="light.set", doc="Create/update a light (AREA/POINT/SUN/SPOT, size, color, look_at).", risk="low", domains=["lighting"], tags=["lighting"]),
    ToolSpec(name="world.set", doc="Set world background/strength.", risk="low", domains=["lighting"], tags=["lighting"]),
    ToolSpec(name="world.hdri_set", doc="Load an HDRI from an approved path.", risk="medium", domains=["lighting"], tags=["lighting", "files"]),
    ToolSpec(name="collection.organize", doc="Organize objects into collections.", risk="low", domains=["scene"], tags=["scene"]),
    ToolSpec(name="sculpt.set_brush", doc="Configure sculpt brush.", risk="low", domains=["sculpt"], tags=["sculpt"]),
    ToolSpec(name="sculpt.remesh", doc="Remesh sculpt object.", risk="high", domains=["sculpt"], tags=["sculpt"]),
    ToolSpec(name="particle.fur_set", doc="Add/configure fur particle system.", risk="medium", domains=["materials"], tags=["materials"]),
    ToolSpec(name="uv.unwrap", doc="Unwrap UVs.", risk="medium", domains=["uv"], tags=["uv"]),
    ToolSpec(name="camera.set", doc="Create/update camera (look_at, track_to, lens, DOF).", risk="low", domains=["camera"], tags=["camera"]),
    ToolSpec(
        name="scene.reference_image",
        doc="Add a reference image empty from an approved path.",
        risk="medium",
        domains=["scene"],
        tags=["scene", "files"],
    ),
    ToolSpec(name="render.set", doc="Set render engine/resolution/samples/motion blur/fps.", risk="low", domains=["render"], tags=["render"]),
    ToolSpec(
        name="anim.keyframes",
        doc="Insert or clear object keyframes (location/rotation/scale/batch).",
        risk="medium",
        domains=["animation"],
        tags=["animation"],
    ),
    ToolSpec(name="anim.walk_to_camera", doc="Simple walk-cycle animation helper.", risk="medium", domains=["animation"], tags=["animation"]),
    ToolSpec(
        name="anim.throw_bounce",
        doc="Throw + ground-bounce animation with camera follow and motion blur.",
        risk="medium",
        domains=["animation", "camera", "render"],
        tags=["animation", "camera"],
    ),
    ToolSpec(name="anim.play", doc="Play/stop animation.", risk="low", domains=["animation"], tags=["animation"]),
    ToolSpec(name="anim.set_frame", doc="Set current frame.", risk="low", domains=["animation"], tags=["animation"]),
    ToolSpec(
        name="blender.introspect",
        doc="Read-only Blender version/engine/RNA/operator hints for adaptive prompting.",
        risk="read",
        domains=["scene"],
        tags=["read", "adaptive"],
    ),
]


class ToolRegistry:
    def __init__(self, specs: Iterable[ToolSpec] | None = None) -> None:
        self._by_name: dict[str, ToolSpec] = {}
        for spec in specs or _TOOL_SPECS:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        self._by_name[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._by_name.get(name)

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def allowlist(self) -> set[str]:
        return set(self._by_name)

    def specs(self) -> list[ToolSpec]:
        return [self._by_name[n] for n in self.names()]

    def docs_for(self, names: list[str] | None = None) -> str:
        wanted = set(names or self.names())
        lines = [
            "To change the Blender scene you MUST call a tool. Emit a fenced JSON block:",
            '```json tool\n{"tool":"TOOL_NAME","args":{...}}\n```',
            "Key tools:",
        ]
        for name in sorted(wanted):
            spec = self.get(name)
            if not spec:
                continue
            lines.append(f"- {spec.name} — {spec.doc}")
        lines.append('Never claim success unless the latest tool result has "ok": true.')
        return "\n".join(lines)

    def mcp_tool_schemas(self) -> list[dict]:
        """Curated high-level MCP surface plus invoke_tool."""
        return [
            {
                "name": "blender_status",
                "description": "Check sidecar + Blender bridge status.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "scene_summary",
                "description": "Get the live Blender scene summary.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "viewport_capture",
                "description": "Capture viewport image(s).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "views": {"type": "array", "items": {"type": "string"}},
                        "shading": {"type": "string"},
                        "target": {"type": "string"},
                    },
                },
            },
            {
                "name": "invoke_tool",
                "description": "Invoke an allowlisted Blender tool by name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string", "enum": self.names()},
                        "args": {"type": "object"},
                        "confirmed": {"type": "boolean"},
                    },
                    "required": ["tool"],
                },
            },
            {
                "name": "execute_skill",
                "description": "Prepare a skill-scoped prompt for the Cursor agent.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "chat",
                "description": "Chat / prepare a BlenderAI turn.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "skill_id": {"type": "string"},
                        "provider_id": {"type": "string"},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "list_objects",
                "description": "List object names from the scene summary.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "undo",
                "description": "Undo last Blender action (may require confirmation).",
                "inputSchema": {"type": "object", "properties": {"confirmed": {"type": "boolean"}}},
            },
            {
                "name": "redo",
                "description": "Redo last Blender action (may require confirmation).",
                "inputSchema": {"type": "object", "properties": {"confirmed": {"type": "boolean"}}},
            },
        ]


_REGISTRY: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ToolRegistry()
    return _REGISTRY


def reset_registry_for_tests(registry: ToolRegistry | None = None) -> ToolRegistry:
    global _REGISTRY
    _REGISTRY = registry if registry is not None else ToolRegistry()
    return _REGISTRY
