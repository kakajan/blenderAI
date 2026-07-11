from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from blender_ai_sidecar.config import get_settings

KNOWN_TOOLS = [
    "scene.summary",
    "viewport.capture",
    "undo",
    "redo",
    "scene.create_object",
    "selection.set",
    "modifier.add",
    "modifier.apply",
    "material.create",
    "material.assign",
    "light.set",
    "world.set",
    "collection.organize",
    "render.set",
    "mesh.ops",
    "sculpt.set_brush",
    "node.set",
    "nodes.geometry_set",
]

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


class SkillEngine:
    def __init__(
        self,
        skills_dir: Path | None = None,
        presets_dir: Path | None = None,
        user_skills_dir: Path | None = None,
    ) -> None:
        settings = get_settings()
        self.skills_dir = skills_dir or settings.skills_dir
        self.presets_dir = presets_dir or settings.presets_dir
        self.user_skills_dir = user_skills_dir or settings.user_skills_dir
        self._skills: dict[str, dict[str, Any]] = {}

    def load(self) -> list[dict[str, Any]]:
        self._skills.clear()
        self._load_dir(self.skills_dir, source="bundled")
        self.user_skills_dir.mkdir(parents=True, exist_ok=True)
        (self.user_skills_dir / "prompts").mkdir(parents=True, exist_ok=True)
        self._load_dir(self.user_skills_dir, source="user")
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

    def list_presets(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self.presets_dir.exists():
            return out
        for path in self.presets_dir.rglob("*"):
            if path.suffix.lower() not in {".md", ".yaml", ".yml"}:
                continue
            rel = str(path.relative_to(self.presets_dir)).replace("\\", "/")
            item: dict[str, Any] = {"id": rel, "path": rel, "name": path.stem}
            if path.suffix.lower() in {".yaml", ".yml"}:
                with path.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    item.update({k: data[k] for k in ("id", "name", "prompt", "steps") if k in data})
            else:
                item["prompt"] = path.read_text(encoding="utf-8")[:500]
            out.append(item)
        return out

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
        tools = [t for t in tools if t in KNOWN_TOOLS] or ["scene.summary"]
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
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                continue
            if not data.get("id"):
                data["id"] = path.stem
            data["_path"] = str(path)
            data["source"] = source
            data["editable"] = source == "user"
            prompt = self._load_prompt(data.get("system_prompt", ""), base_dir=directory)
            if not prompt and data.get("prompt"):
                prompt = str(data.get("prompt") or "")
            data["system_prompt_text"] = prompt
            self._skills[data["id"]] = data

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
        else:
            candidates.append(path)
        for candidate in candidates:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        return ""
