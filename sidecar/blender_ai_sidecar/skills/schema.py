"""Skill YAML validation against registry allowlist."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from blender_ai_sidecar.contracts import SkillSpec as ContractSkillSpec
from blender_ai_sidecar.tools import get_registry

SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


class SkillValidationError(ValueError):
    """Raised when a skill YAML fails hard validation."""


class SkillSpec(BaseModel):
    """Validated skill document (wraps / mirrors contracts.SkillSpec)."""

    id: str
    version: str = "1"
    schema_version: int = 1
    name: str = ""
    description: str = ""
    domains: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    requested_tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    system_prompt_text: str = ""
    risk: str | None = None
    requires_confirmation: bool = False
    viewport_capture: str = "optional"
    max_steps: int | None = None
    method: str | None = None
    evals: list[str] = Field(default_factory=list)
    source: str = "bundled"
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        text = (v or "").strip()
        if not SKILL_ID_RE.match(text):
            raise ValueError(
                f"skill id must match {SKILL_ID_RE.pattern!r}, got {text!r}"
            )
        return text

    @field_validator("version", mode="before")
    @classmethod
    def _coerce_version(cls, v: Any) -> str:
        if v is None or v == "":
            raise ValueError("version is required")
        return str(v)

    def to_contract(self) -> ContractSkillSpec:
        tools = self.tools or self.requested_tools
        return ContractSkillSpec(
            id=self.id,
            version=self.version,
            schema_version=self.schema_version,
            name=self.name,
            description=self.description,
            domains=list(self.domains),
            requested_tools=list(tools),
            system_prompt=self.system_prompt,
            system_prompt_text=self.system_prompt_text,
            risk=self.risk,  # type: ignore[arg-type]
            requires_confirmation=self.requires_confirmation,
            viewport_capture=self.viewport_capture,  # type: ignore[arg-type]
            max_steps=self.max_steps,
            method=self.method,
            evals=list(self.evals),
            source=self.source,  # type: ignore[arg-type]
            provenance=dict(self.provenance),
        )


def validate_skill_dict(
    data: dict[str, Any],
    *,
    allowlist: set[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Validate and normalize a skill dict.

    Returns (normalized_dict, warnings).
    Unknown tools are stripped with a warning (soft).
    Hard failures raise SkillValidationError.
    """
    warnings: list[str] = []
    known = allowlist if allowlist is not None else get_registry().allowlist()

    raw = dict(data)
    if "version" not in raw or raw.get("version") in (None, ""):
        raise SkillValidationError(f"skill {raw.get('id')!r}: version is required")

    tools_key = "tools" if "tools" in raw else "requested_tools"
    raw_tools = list(raw.get(tools_key) or raw.get("tools") or raw.get("requested_tools") or [])
    kept: list[str] = []
    unknown: list[str] = []
    for tool in raw_tools:
        name = str(tool).strip()
        if not name:
            continue
        if name in known:
            kept.append(name)
        else:
            unknown.append(name)
    if unknown:
        sid = raw.get("id") or "?"
        warnings.append(
            f"skill {sid}: unknown tools stripped: {', '.join(unknown)}"
        )
    raw["tools"] = kept
    raw["requested_tools"] = kept
    raw["version"] = str(raw["version"])

    vc = raw.get("viewport_capture", "optional")
    if vc is True:
        raw["viewport_capture"] = "required"
    elif vc is False:
        raw["viewport_capture"] = "false"
    elif vc is None:
        raw["viewport_capture"] = "optional"
    else:
        raw["viewport_capture"] = str(vc)

    try:
        spec = SkillSpec.model_validate(
            {
                **raw,
                "tools": kept,
                "requested_tools": kept,
            }
        )
    except Exception as exc:
        raise SkillValidationError(str(exc)) from exc

    out = dict(raw)
    out["id"] = spec.id
    out["version"] = spec.version
    out["tools"] = list(spec.tools)
    out["requested_tools"] = list(spec.requested_tools)
    return out, warnings
