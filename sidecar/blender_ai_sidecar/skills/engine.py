from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from blender_ai_sidecar.config import get_settings


class SkillEngine:
    def __init__(self, skills_dir: Path | None = None, presets_dir: Path | None = None) -> None:
        settings = get_settings()
        self.skills_dir = skills_dir or settings.skills_dir
        self.presets_dir = presets_dir or settings.presets_dir
        self._skills: dict[str, dict[str, Any]] = {}

    def load(self) -> list[dict[str, Any]]:
        self._skills.clear()
        if not self.skills_dir.exists():
            return []
        for path in sorted(self.skills_dir.glob("*.yaml")):
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not data.get("id"):
                data["id"] = path.stem
            data["_path"] = str(path)
            data["system_prompt_text"] = self._load_prompt(data.get("system_prompt", ""))
            self._skills[data["id"]] = data
        return list(self._skills.values())

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

    def _load_prompt(self, ref: str) -> str:
        if not ref:
            return ""
        path = Path(ref)
        if not path.is_absolute():
            # try repo-relative from presets path parent (repo root)
            candidate = self.presets_dir.parent / ref
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
            candidate = self.presets_dir / ref
            if candidate.exists():
                return candidate.read_text(encoding="utf-8")
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""
