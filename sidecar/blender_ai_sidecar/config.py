from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "BlenderAI"
    path.mkdir(parents=True, exist_ok=True)
    return path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_install_json() -> dict:
    path = _default_data_dir() / "install.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _path_from_install(key: str, fallback: Path) -> Path:
    env_map = {
        "skills_dir": "BLENDERAI_SKILLS_DIR",
        "presets_dir": "BLENDERAI_PRESETS_DIR",
        "webui_dist": "BLENDERAI_WEBUI_DIST",
    }
    env_key = env_map.get(key)
    if env_key and os.environ.get(env_key):
        return Path(os.environ[env_key])
    info = _load_install_json()
    if info.get(key):
        return Path(info[key])
    return fallback


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path = Field(default_factory=_default_data_dir)
    skills_dir: Path = Field(default_factory=lambda: _path_from_install("skills_dir", repo_root() / "skills"))
    presets_dir: Path = Field(default_factory=lambda: _path_from_install("presets_dir", repo_root() / "presets"))
    user_skills_dir: Path = Field(default_factory=lambda: _default_data_dir() / "user_skills")
    user_presets_dir: Path = Field(default_factory=lambda: _default_data_dir() / "user_presets")
    # Alias path from product docs (`skills_user/`); also scanned by SkillEngine.
    skills_user_dir: Path = Field(default_factory=lambda: _default_data_dir() / "skills_user")
    knowledge_dir: Path = Field(default_factory=lambda: _default_data_dir() / "knowledge")
    webui_dist: Path = Field(
        default_factory=lambda: _path_from_install("webui_dist", repo_root() / "webui" / "dist")
    )
    db_path: Path | None = None
    mcp_token: str = ""
    local_only: bool = False

    def resolved_db(self) -> Path:
        return self.db_path or (self.data_dir / "blender_ai.sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
