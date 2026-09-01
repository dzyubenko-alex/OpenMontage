"""Load named voice-generation profiles from the repository profile store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
VOICE_PROFILE_DIR = REPO_ROOT / "profiles" / "voice"
VOICE_PROFILE_SCHEMA = REPO_ROOT / "schemas" / "profiles" / "voice_generation_profile.schema.json"


def _profile_path(profile_id: str) -> Path:
    if not profile_id or Path(profile_id).name != profile_id:
        raise ValueError(f"Invalid voice profile id: {profile_id!r}")
    return VOICE_PROFILE_DIR / f"{profile_id}.json"


def load_voice_profile(profile_id: str) -> dict[str, Any]:
    """Load and validate a named profile without resolving environment references."""
    path = _profile_path(profile_id)
    if not path.is_file():
        raise KeyError(f"Unknown voice profile: {profile_id}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(VOICE_PROFILE_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(profile)
    if profile["profile_id"] != profile_id:
        raise ValueError(f"Voice profile id mismatch in {path}")
    return profile


def resolve_voice_profile(
    profile_id: str, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Resolve a profile by name and inject its private voice id in memory."""
    profile = load_voice_profile(profile_id)
    environment = os.environ if env is None else env
    variable = profile["voice_id_env"]
    voice_id = environment.get(variable, "").strip()
    if not voice_id:
        raise RuntimeError(f"Voice profile {profile_id} requires environment variable {variable}")
    resolved = dict(profile)
    resolved["voice_id"] = voice_id
    return resolved
