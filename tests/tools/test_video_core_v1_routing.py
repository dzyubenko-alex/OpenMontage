import json
from pathlib import Path

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

def test_canonical_trim_and_speed_are_normalized_without_mutation() -> None:
    data = {
        "renderer_family": "video-montage",
        "cuts": [{
            "id": "clip", "source": "/tmp/clip.mp4",
            "in_seconds": 2, "out_seconds": 8, "speed": 2,
        }],
    }
    adapted = VideoCompose._adapt_video_core_props(data)
    assert adapted["cuts"][0] == {
        "id": "clip", "source": "/tmp/clip.mp4",
        "trim_in_seconds": 2, "trim_out_seconds": 8, "playback_rate": 2,
    }
    assert (adapted["cuts"][0]["trim_out_seconds"] - adapted["cuts"][0]["trim_in_seconds"]) / adapted["cuts"][0]["playback_rate"] == 3
    assert data["cuts"][0]["in_seconds"] == 2
    assert "trim_in_seconds" not in data["cuts"][0]

def test_high_level_video_route_passes_normalized_props(monkeypatch, tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = json.loads((root / "tests/fixtures/video_core_v1_minimal.json").read_text())
    tool = VideoCompose()
    captured = {}
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool, "_needs_remotion", lambda cuts: True)
    monkeypatch.setattr(tool, "_run_final_review", lambda *args, **kwargs: {})

    def fake_render(inputs):
        captured.update(inputs)
        from tools.base_tool import ToolResult
        return ToolResult(success=True, data={}, artifacts=[])

    monkeypatch.setattr(tool, "_remotion_render", fake_render)
    result = tool._render({
        "edit_decisions": fixture,
        "asset_manifest": {
            "assets": [{"id": "clip-asset", "path": "/tmp/clip.mp4"}],
        },
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success
    props = captured["edit_decisions"]
    assert props["renderer_family"] == "video-montage"
    assert props["cuts"][0]["source"] == "/tmp/clip.mp4"
    assert props["cuts"][0]["trim_in_seconds"] == 0
    assert props["cuts"][0]["trim_out_seconds"] == 3
    assert props["cuts"][0]["playback_rate"] == 1
    assert "in_seconds" not in props["cuts"][0]
    assert "out_seconds" not in props["cuts"][0]
