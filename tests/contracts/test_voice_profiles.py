import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from lib.voice_profiles import load_voice_profile, resolve_voice_profile

ROOT = Path(__file__).resolve().parents[2]
PROFILE_ID = "REAL_ESTATE_VOICE_PROFILE_V1"


def test_real_estate_voice_profile_matches_schema_and_approved_settings() -> None:
    profile_path = ROOT / "profiles" / "voice" / f"{PROFILE_ID}.json"
    schema_path = ROOT / "schemas" / "profiles" / "voice_generation_profile.schema.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(profile)
    assert profile["provider"] == "elevenlabs_tts"
    assert profile["model_id"] == "eleven_multilingual_v2"
    assert profile["voice_settings"] == {
        "stability": 0.55,
        "similarity_boost": 0.88,
        "style": 0.03,
        "speed": 0.88,
        "use_speaker_boost": False,
    }
    assert profile["volume"] == 1.0
    assert "voice_id" not in profile
    assert "api_key" not in profile


def test_profile_resolves_by_name_and_keeps_voice_id_environment_backed() -> None:
    stored = load_voice_profile(PROFILE_ID)
    resolved = resolve_voice_profile(
        PROFILE_ID, {stored["voice_id_env"]: "private-voice-id"}
    )
    assert stored["profile_id"] == PROFILE_ID
    assert "voice_id" not in stored
    assert resolved["voice_id"] == "private-voice-id"


def test_profile_resolution_requires_configured_voice_id() -> None:
    with pytest.raises(RuntimeError, match="ELEVENLABS_REAL_ESTATE_VOICE_ID"):
        resolve_voice_profile(PROFILE_ID, {})
