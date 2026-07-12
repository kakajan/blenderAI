"""Policy engine — single decision point for tool execution."""

from __future__ import annotations

from typing import Any, Literal

from blender_ai_sidecar.contracts import AutonomyMode, InvokePath, PolicyDecision, RiskLevel
from blender_ai_sidecar.tools import ToolRegistry, get_registry

# Skills that must keep their explicit tool list only (no modeling base merge).
STRICT_TOOL_SKILLS = frozenset(
    {
        "review.critique",
        "modeling.primitives",
        "modeling.low_poly",
        "render.optimize",
        "scene.organize",
        "materials.create_pbr",
        "materials.from_description",
        "lighting.hdri_setup",
        "lighting.three_point",
        "nodes.geometry_basic",
        "sculpt.brush_assist",
    }
)

MODELING_BASE_TOOLS = [
    "scene.create_object",
    "selection.set",
    "mesh.select",
    "mesh.ops",
    "object.transform",
    "object.join",
    "object.duplicate",
    "object.delete",
    "object.parent",
    "modifier.add",
    "modifier.apply",
    "collection.organize",
]


def normalize_autonomy(raw: str | None) -> AutonomyMode:
    value = (raw or "ask").strip().lower()
    if value in {"ask", "auto_safe", "auto_full", "readonly"}:
        return value  # type: ignore[return-value]
    if value in {"auto", "full"}:
        return "auto_full"
    if value in {"safe", "auto-safe"}:
        return "auto_safe"
    if value in {"read", "read_only", "read-only"}:
        return "readonly"
    return "ask"


def resolve_skill_tools(
    skill: dict[str, Any] | None,
    *,
    registry: ToolRegistry | None = None,
) -> list[str]:
    reg = registry or get_registry()
    known = reg.allowlist()
    if not skill:
        # No skill selected → read-only safe defaults for unscoped invokes.
        return sorted(n for n in known if (reg.get(n) and reg.get(n).risk == "read"))

    explicit = [t for t in (skill.get("tools") or skill.get("requested_tools") or []) if t in known]
    if not explicit:
        return sorted(n for n in known if (reg.get(n) and reg.get(n).risk in {"read", "low"}))

    sid = str(skill.get("id") or "")
    if sid in STRICT_TOOL_SKILLS:
        return explicit

    domains = set(skill.get("domains") or [])
    if domains & {"modeling"} or sid.startswith("modeling."):
        merged: list[str] = []
        for tool in explicit + MODELING_BASE_TOOLS:
            if tool in known and tool not in merged:
                merged.append(tool)
        return merged

    if sid == "review.iterate":
        merged = []
        for tool in explicit + MODELING_BASE_TOOLS + ["viewport.capture", "viewport.set_shading"]:
            if tool in known and tool not in merged:
                merged.append(tool)
        return merged

    return explicit


class PolicyEngine:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or get_registry()

    def decide(
        self,
        *,
        tool: str,
        skill: dict[str, Any] | None = None,
        autonomy: str | None = "ask",
        path: InvokePath = "chat",
        confirmed: bool = False,
        blender_connected: bool = True,
        skill_requires_confirmation: bool | None = None,
    ) -> PolicyDecision:
        spec = self.registry.get(tool)
        if spec is None:
            return PolicyDecision(action="deny", reason=f"Tool not allowlisted: {tool}", tool=tool)

        if not blender_connected and spec.risk != "read":
            return PolicyDecision(
                action="deny",
                reason="Blender is not connected",
                tool=tool,
                risk=spec.risk,
            )

        mode = normalize_autonomy(autonomy)
        if mode == "readonly" and spec.risk != "read":
            return PolicyDecision(
                action="deny",
                reason="Autonomy is readonly; only read tools are allowed",
                tool=tool,
                risk=spec.risk,
            )

        allowed = set(resolve_skill_tools(skill, registry=self.registry))
        # Direct bridge/MCP without a skill: still enforce risk via autonomy, but allow allowlisted tools.
        if skill is not None and tool not in allowed:
            sid = (skill or {}).get("id") or "unknown"
            return PolicyDecision(
                action="deny",
                reason=f"Tool not allowed for skill {sid}: {tool}",
                tool=tool,
                risk=spec.risk,
            )

        needs_confirm = bool(skill_requires_confirmation)
        if skill is None and path in {"mcp", "bridge"} and skill_requires_confirmation is None:
            needs_confirm = False
        if skill and skill.get("requires_confirmation"):
            needs_confirm = True
        if spec.risk in {"high", "destructive"}:
            needs_confirm = True

        if needs_confirm and mode == "ask" and not confirmed:
            return PolicyDecision(
                action="confirm",
                reason=f"Confirmation required for {tool} (risk={spec.risk}, autonomy=ask)",
                tool=tool,
                risk=spec.risk,
                requires_confirmation=True,
            )

        if mode == "auto_safe" and spec.risk in {"high", "destructive"} and not confirmed:
            return PolicyDecision(
                action="confirm",
                reason=f"auto_safe blocks {spec.risk} tools without confirmation",
                tool=tool,
                risk=spec.risk,
                requires_confirmation=True,
            )

        return PolicyDecision(action="allow", reason="allowed", tool=tool, risk=spec.risk)


_ENGINE: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = PolicyEngine()
    return _ENGINE
