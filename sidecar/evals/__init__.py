"""Minimal skill-policy eval harness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from blender_ai_sidecar.policy import resolve_skill_tools


@dataclass
class EvalCase:
    id: str
    prompt: str
    skill_id: str
    forbidden_tools: list[str]
    required_tool_substring: str | None = None


@dataclass
class EvalResult:
    case_id: str
    ok: bool
    allowed: list[str]
    errors: list[str]


def cases_path() -> Path:
    return Path(__file__).resolve().parent / "cases.yaml"


def load_cases(path: Path | None = None) -> list[EvalCase]:
    p = path or cases_path()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cases = raw.get("cases") or raw
    out: list[EvalCase] = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        out.append(
            EvalCase(
                id=str(item.get("id") or item.get("skill_id") or "case"),
                prompt=str(item.get("prompt") or ""),
                skill_id=str(item["skill_id"]),
                forbidden_tools=[str(t) for t in (item.get("forbidden_tools") or [])],
                required_tool_substring=(
                    str(item["required_tool_substring"])
                    if item.get("required_tool_substring")
                    else None
                ),
            )
        )
    return out


def run_case(case: EvalCase, skill: dict[str, Any] | None) -> EvalResult:
    errors: list[str] = []
    if skill is None:
        return EvalResult(case_id=case.id, ok=False, allowed=[], errors=[f"unknown skill {case.skill_id}"])

    allowed = resolve_skill_tools(skill)
    allowed_set = set(allowed)

    for tool in case.forbidden_tools:
        if tool in allowed_set:
            errors.append(f"forbidden tool present: {tool}")

    if case.required_tool_substring:
        needle = case.required_tool_substring
        if not any(needle in t for t in allowed):
            errors.append(f"required tool substring missing: {needle!r}")

    return EvalResult(case_id=case.id, ok=not errors, allowed=allowed, errors=errors)


def run_evals(skills: dict[str, dict[str, Any]], path: Path | None = None) -> list[EvalResult]:
    return [run_case(c, skills.get(c.skill_id)) for c in load_cases(path)]
