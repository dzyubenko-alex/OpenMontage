from __future__ import annotations
import json
from pathlib import Path
from tools.video.video_compose import VideoCompose

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "tests/fixtures/hybrid_core_v1_minimal.json").read_text())

def test_hybrid_montage_routes_without_changing_existing_families() -> None:
    assert VideoCompose._get_composition_id("hybrid-montage") == "HybridCoreV1"
    assert VideoCompose._get_composition_id("photo-montage") == "PhotoCoreV1"
    assert VideoCompose._get_composition_id("video-montage") == "VideoCoreV1"
    assert VideoCompose._get_composition_id("explainer-data") == "Explainer"

def test_profile_assets_resolve_for_hybrid_without_mutation() -> None:
    data = {"profiles": {"branding": {"logo_src": "logo"}}, "audio": {
        "narration": {"segments": [{"asset_id": "voice"}]}, "music": {"asset_id": "music"}}}
    lookup = {"logo": {"path": "/logo.png"}, "voice": {"path": "/voice.wav"}, "music": {"path": "/music.mp3"}}
    resolved = VideoCompose._resolve_photo_profile_assets(data, lookup)
    assert resolved["profiles"]["branding"]["logo_src"] == "/logo.png"
    assert resolved["audio"]["narration"]["segments"][0]["src"] == "/voice.wav"
    assert resolved["audio"]["music"]["src"] == "/music.mp3"
    assert data["profiles"]["branding"]["logo_src"] == "logo"

def test_high_level_hybrid_route_passes_normalized_props(monkeypatch, tmp_path) -> None:
    tool = VideoCompose()
    captured = {}
    calls = 0
    original_adapter = VideoCompose._adapt_hybrid_core_props

    def counting_adapter(data):
        nonlocal calls
        calls += 1
        return original_adapter(data)

    monkeypatch.setattr(VideoCompose, "_adapt_hybrid_core_props", staticmethod(counting_adapter))
    monkeypatch.setattr(tool, "_pre_compose_validation", lambda *args, **kwargs: None)
    monkeypatch.setattr(tool, "_needs_remotion", lambda cuts: True)
    monkeypatch.setattr(tool, "_run_final_review", lambda *args, **kwargs: {})

    def fake_render(inputs):
        captured.update(inputs | {"edit_decisions": tool._adapt_hybrid_core_props(inputs["edit_decisions"])})
        from tools.base_tool import ToolResult
        return ToolResult(success=True, data={}, artifacts=[])

    monkeypatch.setattr(tool, "_remotion_render", fake_render)
    result = tool._render({
        "edit_decisions": FIXTURE,
        "asset_manifest": {"assets": [
            {"id": "photo-asset", "path": "/tmp/photo.svg"},
            {"id": "video-asset", "path": "/tmp/video.mp4"},
        ]},
        "output_path": str(tmp_path / "out.mp4"),
    })
    assert result.success
    assert calls == 1
    props = captured["edit_decisions"]
    assert props["renderer_family"] == "hybrid-montage"
    assert props["cuts"][0]["source"] == "/tmp/photo.svg"
    assert props["cuts"][0]["duration_seconds"] == 3
    assert props["cuts"][1]["source"] == "/tmp/video.mp4"
    assert props["cuts"][1]["trim_in_seconds"] == 1
    assert props["cuts"][1]["trim_out_seconds"] == 5
    assert props["cuts"][1]["playback_rate"] == 2

def test_preview_export_stays_shared_and_hybrid_mode_is_profile_driven() -> None:
    compose = (ROOT / "tools/video/video_compose.py").read_text()
    defaults = (ROOT / "remotion-composer/src/presets/hybrid-core-v1/defaults.ts").read_text()
    assert "result = self._apply_preview_export(result, inputs)" in compose
    assert 'mode: "HYBRID"' in defaults and "enabled: false" in defaults
