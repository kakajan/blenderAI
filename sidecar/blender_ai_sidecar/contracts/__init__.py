"""Shared Pydantic contracts for BlenderAI control plane."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["read", "low", "medium", "high", "destructive"]
PolicyAction = Literal["allow", "deny", "confirm"]
AutonomyMode = Literal["ask", "auto_safe", "auto_full", "readonly"]
InvokePath = Literal["chat", "mcp", "bridge", "workflow", "ws"]
ToolCallingMode = Literal["none", "openai", "anthropic", "regex"]


class ToolSpec(BaseModel):
    name: str
    doc: str = ""
    risk: RiskLevel = "medium"
    domains: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    # Logical tags used by skills to request capabilities without hardcoding every tool.
    tags: list[str] = Field(default_factory=list)


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None
    step: int | None = None
    request_id: str | None = None
    confirmed: bool = False


class ToolResult(BaseModel):
    ok: bool
    tool: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None
    request_id: str | None = None

    def as_bridge_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok}
        if self.error:
            out["error"] = self.error
        if self.error_code:
            out["error_code"] = self.error_code
        out.update(self.data)
        return out


class PolicyDecision(BaseModel):
    action: PolicyAction
    reason: str = ""
    tool: str | None = None
    risk: RiskLevel | None = None
    requires_confirmation: bool = False


class ProviderCapabilities(BaseModel):
    vision: bool = False
    tool_calling: ToolCallingMode = "regex"
    max_images: int = 0
    context_tokens: int | None = None


class ImageRef(BaseModel):
    id: str
    source: Literal["viewport", "upload", "reference", "critique", "user"] = "viewport"
    mime: str = "image/png"
    data_base64: str | None = None
    storage_id: str | None = None
    path: str | None = None
    view: str | None = None
    camera: dict[str, Any] | None = None
    framing: dict[str, Any] | None = None
    caption: str | None = None


class ContextBundle(BaseModel):
    scene: dict[str, Any] | None = None
    images: list[ImageRef] = Field(default_factory=list)
    memory: list[dict[str, Any]] = Field(default_factory=list)
    skill_id: str | None = None
    connection: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] | None = None
    text_enrichments: list[str] = Field(default_factory=list)


class SkillSpec(BaseModel):
    id: str
    version: str = "1"
    schema_version: int = 1
    name: str = ""
    description: str = ""
    domains: list[str] = Field(default_factory=list)
    requested_tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    system_prompt_text: str = ""
    risk: RiskLevel | None = None
    requires_confirmation: bool = False
    viewport_capture: Literal["false", "optional", "required"] = "optional"
    max_steps: int | None = None
    method: str | None = None
    evals: list[str] = Field(default_factory=list)
    source: Literal["bundled", "user", "promoted"] = "bundled"
    provenance: dict[str, Any] = Field(default_factory=dict)


class RunEvent(BaseModel):
    type: str
    content: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None
    session_id: str | None = None
    step: int | None = None
