from __future__ import annotations

import pytest

from tools.video.video_compose import VideoCompose


def _profiles(media_profile: str = "generic_hd") -> dict:
    return {
        "voice": {"enabled": False, "volume": 1, "captions": {}},
        "music": {"enabled": False, "volume": 0.1, "ducking": {}},
        "editing": {},
        "branding": {"enabled": False, "logo_src": "logo-asset"},
        "export": {"media_profile": media_profile},
    }


def test_photo_montage_routes_to_dedicated_composition() -> None:
    assert VideoCompose._get_composition_id("photo-montage") == "PhotoCoreV1"
    assert VideoCompose._get_composition_id("explainer-data") == "Explainer"


def test_export_profile_is_used_when_explicit_profile_is_absent() -> None:
    data = {"profiles": _profiles("generic_hd")}
    assert VideoCompose._resolve_output_profile({}, data) == "generic_hd"


def test_matching_explicit_export_profile_is_allowed() -> None:
    data = {"profiles": _profiles("youtube_landscape")}
    assert (
        VideoCompose._resolve_output_profile({"profile": "youtube_landscape"}, data)
        == "youtube_landscape"
    )


def test_conflicting_export_profile_is_blocked() -> None:
    data = {"profiles": _profiles("generic_hd")}
    with pytest.raises(ValueError, match="Export profile conflict"):
        VideoCompose._resolve_output_profile({"profile": "tiktok"}, data)


def test_unknown_export_profile_is_blocked() -> None:
    data = {"profiles": _profiles("not-a-profile")}
    with pytest.raises(ValueError, match="Unknown profile"):
        VideoCompose._resolve_output_profile({}, data)


def test_photo_audio_and_logo_asset_ids_are_resolved_without_mutation() -> None:
    data = {
        "profiles": _profiles(),
        "audio": {
            "narration": {
                "segments": [{"asset_id": "voice-1", "start_seconds": 0}]
            },
            "music": {"asset_id": "music-1"},
        },
    }
    lookup = {
        "logo-asset": {"path": "/tmp/logo.png"},
        "voice-1": {"path": "/tmp/voice.wav"},
        "music-1": {"path": "/tmp/music.mp3"},
    }

    resolved = VideoCompose._resolve_photo_profile_assets(data, lookup)

    assert resolved["profiles"]["branding"]["logo_src"] == "/tmp/logo.png"
    assert resolved["audio"]["narration"]["segments"] == [
        {"src": "/tmp/voice.wav", "start_seconds": 0}
    ]
    assert resolved["audio"]["music"]["src"] == "/tmp/music.mp3"
    assert data["profiles"]["branding"]["logo_src"] == "logo-asset"


def test_remotion_contract_accepts_local_browser_executable() -> None:
    browser = VideoCompose.input_schema["properties"]["browser_executable"]
    assert browser["type"] == "string"
