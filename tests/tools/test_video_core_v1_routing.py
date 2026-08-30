from tools.video.video_compose import VideoCompose

def test_video_montage_routes_to_video_core() -> None:
    assert VideoCompose._get_composition_id("video-montage") == "VideoCoreV1"
    assert VideoCompose._get_composition_id("photo-montage") == "PhotoCoreV1"
    assert VideoCompose._get_composition_id("explainer-data") == "Explainer"

def test_profile_assets_resolve_for_video_without_mutation() -> None:
    data = {
        "profiles": {"branding": {"logo_src": "logo"}},
        "audio": {"narration": {"segments": [{"asset_id": "voice"}]}, "music": {"asset_id": "music"}},
    }
    lookup = {"logo": {"path": "/logo.png"}, "voice": {"path": "/voice.wav"}, "music": {"path": "/music.mp3"}}
    resolved = VideoCompose._resolve_photo_profile_assets(data, lookup)
    assert resolved["profiles"]["branding"]["logo_src"] == "/logo.png"
    assert resolved["audio"]["narration"]["segments"][0]["src"] == "/voice.wav"
    assert resolved["audio"]["music"]["src"] == "/music.mp3"
    assert data["profiles"]["branding"]["logo_src"] == "logo"
