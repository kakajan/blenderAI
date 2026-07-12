from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from blender_ai_sidecar.config import get_settings
from blender_ai_sidecar.policy import (
    MODELING_BASE_TOOLS,
    STRICT_TOOL_SKILLS,
    resolve_skill_tools as _policy_resolve_skill_tools,
)
from blender_ai_sidecar.skills.schema import SkillValidationError, validate_skill_dict
from blender_ai_sidecar.tools import get_registry


def get_known_tools() -> list[str]:
    return sorted(get_registry().allowlist())


KNOWN_TOOLS = get_known_tools()


def resolve_skill_tools(skill: dict[str, Any] | None, *, allowlist: list[str] | None = None) -> list[str]:
    """Return effective tools for a skill (delegates to policy; allowlist ignored)."""
    del allowlist  # registry / policy is the single source of truth
    return _policy_resolve_skill_tools(skill)

_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


def normalize_skill_id(raw: str) -> str:
    text = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    text = re.sub(r"[^a-z0-9_.]", "", text)
    if "." not in text:
        text = f"user.{text}" if text else "user.custom"
    if not text.startswith("user."):
        # User-created skills always live under user.* to avoid clobbering bundled ids via API.
        text = f"user.{text.replace('.', '_')}"
    return text


normalize_preset_id = normalize_skill_id

_PRESET_CATEGORIES = ("general", "styles", "workflows", "modeling", "materials", "lighting", "custom")

_TOOL_JSON_RE = re.compile(
    r"```(?:json)?\s*(?:tool\s*)?(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_tool_recipes_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recipes: list[dict[str, Any]] = []
    for msg in messages:
        if str(msg.get("role") or "") != "assistant":
            continue
        content = str(msg.get("content") or "")
        for match in _TOOL_JSON_RE.finditer(content):
            try:
                call = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            tool = call.get("tool")
            if tool:
                recipes.append({"tool": tool, "args": call.get("args") or {}})
    return recipes


def _format_tool_recipes_for_preset(recipes: list[dict[str, Any]], *, limit: int = 12) -> list[str]:
    if not recipes:
        return []
    lines = ["", "## Tool recipes that worked", ""]
    for item in recipes[:limit]:
        args = json.dumps(item.get("args") or {}, ensure_ascii=False)
        if len(args) > 200:
            args = args[:197] + "…"
        lines.append(f'```json tool\n{{"tool":"{item.get("tool")}","args":{args}}}\n```')
        lines.append("")
    return lines


_TOOL_NOISE_RE = re.compile(
    r"(?m)^\s*[⚙✓⚠].*$|^\s*tool (ok|failed).*$",
    re.IGNORECASE,
)


def _clean_assistant_for_preset(text: str, limit: int = 900) -> str:
    cleaned = _TOOL_NOISE_RE.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


class SkillEngine:
    def __init__(
        self,
        skills_dir: Path | None = None,
        presets_dir: Path | None = None,
        user_skills_dir: Path | None = None,
        user_presets_dir: Path | None = None,
    ) -> None:
        settings = get_settings()
        self.skills_dir = skills_dir or settings.skills_dir
        self.presets_dir = presets_dir or settings.presets_dir
        self.user_skills_dir = user_skills_dir or settings.user_skills_dir
        self.user_presets_dir = user_presets_dir or settings.user_presets_dir
        self.skills_user_dir = getattr(settings, "skills_user_dir", None) or (
            settings.data_dir / "skills_user"
        )
        self._skills: dict[str, dict[str, Any]] = {}
        self._presets: dict[str, dict[str, Any]] = {}
        self.load_warnings: list[str] = []

    def load(self) -> list[dict[str, Any]]:
        self._skills.clear()
        self.load_warnings = []
        self._load_dir(self.skills_dir, source="bundled")
        self.user_skills_dir.mkdir(parents=True, exist_ok=True)
        (self.user_skills_dir / "prompts").mkdir(parents=True, exist_ok=True)
        self._load_dir(self.user_skills_dir, source="user")
        try:
            self.skills_user_dir.mkdir(parents=True, exist_ok=True)
            (self.skills_user_dir / "prompts").mkdir(parents=True, exist_ok=True)
            if self.skills_user_dir.resolve() != self.user_skills_dir.resolve():
                self._load_dir(self.skills_user_dir, source="user")
        except Exception as exc:
            self.load_warnings.append(f"skills_user_dir: {exc}")
        return list(self._skills.values())

    def reload(self) -> list[dict[str, Any]]:
        return self.load()

    def list(self) -> list[dict[str, Any]]:
        if not self._skills:
            self.load()
        return list(self._skills.values())

    def get(self, skill_id: str) -> dict[str, Any] | None:
        if not self._skills:
            self.load()
        return self._skills.get(skill_id)

    def load_presets(self) -> list[dict[str, Any]]:
        self._presets.clear()
        self._load_presets_dir(self.presets_dir, source="bundled")
        self.user_presets_dir.mkdir(parents=True, exist_ok=True)
        self._load_presets_dir(self.user_presets_dir, source="user", flat=True)
        return list(self._presets.values())

    def reload_presets(self) -> list[dict[str, Any]]:
        return self.load_presets()

    def list_presets(self) -> list[dict[str, Any]]:
        if not self._presets:
            self.load_presets()
        return list(self._presets.values())

    def get_preset(self, preset_id: str) -> dict[str, Any] | None:
        if not self._presets:
            self.load_presets()
        return self._presets.get(preset_id)

    def save_user_preset(self, payload: dict[str, Any]) -> dict[str, Any]:
        preset_id = normalize_preset_id(str(payload.get("id") or payload.get("name") or "custom"))
        existing = self.get_preset(preset_id)
        if existing and existing.get("source") == "bundled":
            raise ValueError("Cannot overwrite a bundled preset. Use a user.* id.")

        name = (payload.get("name") or preset_id).strip()
        description = (payload.get("description") or "").strip()
        category = (payload.get("category") or "custom").strip().lower() or "custom"
        category = re.sub(r"[^a-z0-9_]", "", category) or "custom"
        if category not in _PRESET_CATEGORIES:
            category = "custom"

        prompt_text = (payload.get("prompt") or "").strip()
        if not prompt_text:
            prompt_text = f"Preset “{name}”: follow this style/workflow guidance carefully."

        steps = payload.get("steps")
        if isinstance(steps, str):
            steps = steps.strip()
            if steps:
                try:
                    steps = yaml.safe_load(steps)
                except yaml.YAMLError as exc:
                    raise ValueError(f"Invalid steps YAML: {exc}") from exc
            else:
                steps = None
        if steps is not None and not isinstance(steps, list):
            raise ValueError("steps must be a list")

        data: dict[str, Any] = {
            "id": preset_id,
            "name": name,
            "category": category,
            "description": description,
            "prompt": prompt_text,
        }
        if steps:
            data["steps"] = steps

        self.user_presets_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = self.user_presets_dir / f"{preset_id}.yaml"
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

        self.load_presets()
        preset = self.get_preset(preset_id)
        if not preset:
            raise RuntimeError("Failed to reload saved preset")
        return preset

    def delete_user_preset(self, preset_id: str) -> bool:
        preset = self.get_preset(preset_id)
        if not preset:
            return False
        if preset.get("source") != "user":
            raise ValueError("Only user presets can be deleted")
        path = Path(preset.get("_path") or "")
        if path.exists():
            path.unlink()
        self.load_presets()
        return True

    def draft_preset_from_messages(
        self,
        title: str,
        messages: list[dict[str, Any]],
        *,
        name: str | None = None,
        description: str | None = None,
        category: str = "workflows",
    ) -> dict[str, Any]:
        user_parts: list[str] = []
        assistant_parts: list[str] = []
        for msg in messages:
            role = str(msg.get("role") or "")
            content = str(msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                user_parts.append(content)
            elif role == "assistant":
                cleaned = _clean_assistant_for_preset(content)
                if cleaned:
                    assistant_parts.append(cleaned)

        if not user_parts and not assistant_parts:
            raise ValueError("Chat has no usable messages to build a preset")

        chat_title = (title or "").strip() or "Chat preset"
        preset_name = (name or "").strip() or chat_title
        if len(preset_name) > 80:
            preset_name = preset_name[:77] + "…"
        desc = (description or "").strip() or f"Created from chat: {chat_title}"

        lines = [
            f"# Preset from chat: {preset_name}",
            "",
            "Reuse this as a BlenderAI workflow/style guide.",
            "",
            "## User goals",
        ]
        for i, part in enumerate(user_parts[:16], 1):
            lines.append(f"{i}. {part}")
        if assistant_parts:
            lines.extend(["", "## Guidance from the session"])
            for part in assistant_parts[:8]:
                lines.append(part)
                lines.append("")

        recipes = _extract_tool_recipes_from_messages(messages)
        lines.extend(_format_tool_recipes_for_preset(recipes))

        lines.append(
            "Follow the goals above. Prefer the same structure, naming, and tool sequence that worked in the original chat."
        )

        return {
            "name": preset_name,
            "description": desc[:240],
            "category": category if category in _PRESET_CATEGORIES else "workflows",
            "prompt": "\n".join(lines).strip(),
            "id": "",
        }

    def save_user_skill(self, payload: dict[str, Any]) -> dict[str, Any]:
        skill_id = normalize_skill_id(str(payload.get("id") or payload.get("name") or "custom"))
        existing = self.get(skill_id)
        if existing and existing.get("source") == "bundled":
            raise ValueError("Cannot overwrite a bundled skill. Use a user.* id.")

        name = (payload.get("name") or skill_id).strip()
        description = (payload.get("description") or "").strip()
        domains = payload.get("domains") or ["custom"]
        if isinstance(domains, str):
            domains = [d.strip() for d in domains.split(",") if d.strip()]
        tools = payload.get("tools") or []
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]
        tools = [t for t in tools if t in get_known_tools()] or ["scene.summary"]
        risk = payload.get("risk") or "medium"
        if risk not in {"low", "medium", "high"}:
            risk = "medium"
        requires_confirmation = bool(payload.get("requires_confirmation", False))
        viewport_capture = payload.get("viewport_capture") or "optional"
        if viewport_capture not in {"false", "optional", "required", False, True}:
            viewport_capture = "optional"
        if viewport_capture is True:
            viewport_capture = "required"
        if viewport_capture is False:
            viewport_capture = "false"

        prompt_text = (payload.get("prompt") or payload.get("system_prompt_text") or "").strip()
        if not prompt_text:
            prompt_text = (
                f"You are a BlenderAI skill helper for “{name}”. "
                "Use only allowlisted tools. Be concise and confirm risky actions when needed."
            )

        self.user_skills_dir.mkdir(parents=True, exist_ok=True)
        prompts_dir = self.user_skills_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompt_rel = f"prompts/{skill_id}.md"
        prompt_path = self.user_skills_dir / prompt_rel
        prompt_path.write_text(prompt_text, encoding="utf-8")

        data = {
            "id": skill_id,
            "version": int(payload.get("version") or 1),
            "name": name,
            "domains": domains,
            "tools": tools,
            "system_prompt": prompt_rel,
            "risk": risk,
            "requires_confirmation": requires_confirmation,
            "viewport_capture": viewport_capture,
            "description": description,
        }
        method = (payload.get("method") or "").strip()
        if method:
            data["method"] = method
        yaml_path = self.user_skills_dir / f"{skill_id}.yaml"
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

        self.load()
        skill = self.get(skill_id)
        if not skill:
            raise RuntimeError("Failed to reload saved skill")
        return skill

    def delete_user_skill(self, skill_id: str) -> bool:
        skill = self.get(skill_id)
        if not skill:
            return False
        if skill.get("source") != "user":
            raise ValueError("Only user skills can be deleted")
        yaml_path = Path(skill.get("_path") or "")
        if yaml_path.exists():
            yaml_path.unlink()
        prompt_path = self.user_skills_dir / "prompts" / f"{skill_id}.md"
        prompt_path.unlink(missing_ok=True)
        self.load()
        return True

    def _load_dir(self, directory: Path, *, source: str) -> None:
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.yaml")):
            try:
                with path.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as exc:
                self.load_warnings.append(f"skip {path.name}: read error: {exc}")
                continue
            if not isinstance(data, dict):
                self.load_warnings.append(f"skip {path.name}: not a mapping")
                continue
            if not data.get("id"):
                data["id"] = path.stem
            try:
                data, warnings = validate_skill_dict(data)
            except SkillValidationError as exc:
                self.load_warnings.append(f"skip {path.name}: {exc}")
                continue
            self.load_warnings.extend(warnings)
            data["_path"] = str(path)
            data["source"] = source
            data["editable"] = source == "user"
            prompt = self._load_prompt(data.get("system_prompt", ""), base_dir=directory)
            if not prompt and data.get("prompt"):
                prompt = str(data.get("prompt") or "")
            data["system_prompt_text"] = prompt
            self._skills[data["id"]] = data

    def _load_presets_dir(self, directory: Path, *, source: str, flat: bool = False) -> None:
        if not directory.exists():
            return
        paths = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
        if not flat:
            paths = sorted(
                p
                for p in directory.rglob("*")
                if p.is_file() and p.suffix.lower() in {".md", ".yaml", ".yml"}
            )
        for path in paths:
            item = self._parse_preset_file(path, directory, source=source, flat=flat)
            if item:
                self._presets[item["id"]] = item

    def _parse_preset_file(
        self,
        path: Path,
        root: Path,
        *,
        source: str,
        flat: bool,
    ) -> dict[str, Any] | None:
        rel = str(path.relative_to(root)).replace("\\", "/")
        category = path.parent.name if path.parent != root else "custom"
        if category == root.name:
            category = "custom"

        item: dict[str, Any] = {
            "path": rel,
            "name": path.stem,
            "category": category,
            "description": "",
            "source": source,
            "editable": source == "user",
            "_path": str(path),
        }

        if path.suffix.lower() in {".yaml", ".yml"}:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return None
            for key in ("id", "name", "prompt", "steps", "description", "category"):
                if key in data and data[key] is not None:
                    item[key] = data[key]
            if flat or source == "user":
                item["id"] = str(data.get("id") or path.stem)
            else:
                # Bundled: stable path id; keep yaml id as alias field when present.
                item["id"] = rel
                if data.get("id"):
                    item["alias"] = data["id"]
        else:
            prompt = path.read_text(encoding="utf-8")
            item["id"] = rel
            item["prompt"] = prompt
            item["name"] = path.stem.replace("_", " ").title()

        if not item.get("prompt") and not item.get("steps"):
            item["prompt"] = ""
        if source == "user" and not str(item["id"]).startswith("user."):
            item["id"] = normalize_preset_id(str(item["id"]))
        return item

    def _load_prompt(self, ref: str, base_dir: Path | None = None) -> str:
        if not ref:
            return ""
        path = Path(ref)
        candidates: list[Path] = []
        if base_dir is not None and not path.is_absolute():
            candidates.append(base_dir / ref)
        if not path.is_absolute():
            candidates.append(self.presets_dir.parent / ref)
            candidates.append(self.presets_dir / ref)
            candidates.append(self.user_skills_dir / ref)
            candidates.append(self.user_presets_dir / ref)
        else:
            candidates.append(path)
        for candidate in candidates:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        return ""
