from __future__ import annotations
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from referencing import Registry, Resource
ROOT = Path(__file__).resolve().parents[2]
PRESET = ROOT / "remotion-composer/src/presets/video-core-v1"
FIXTURE = json.loads((ROOT / "tests/fixtures/video_core_v1_minimal.json").read_text())

def test_video_core_fixture_and_profile_bundle_validate() -> None:
    edit_schema = json.loads((ROOT / "schemas/artifacts/edit_decisions.schema.json").read_text())
    profiles_schema = json.loads((ROOT / "schemas/profiles/composition_profiles.schema.json").read_text())
    profile_resource = Resource.from_contents(profiles_schema)
    registry = (
        Registry()
        .with_resource("openmontage/profiles/composition_profiles.schema.json", profile_resource)
        .with_resource(
            "openmontage/artifacts/openmontage/profiles/composition_profiles.schema.json",
            profile_resource,
        )
    )
    artifact = json.loads(json.dumps(FIXTURE))
    artifact.pop("captions")
    Draft202012Validator(edit_schema, registry=registry).validate(artifact)
    Draft202012Validator(profiles_schema).validate(FIXTURE["profiles"])
    assert profiles_schema["required"] == ["voice", "music", "editing", "branding", "export"]

def test_old_photo_profile_remains_valid_and_strict() -> None:
    profiles_schema = json.loads((ROOT / "schemas/profiles/composition_profiles.schema.json").read_text())
    photo = json.loads((ROOT / "tests/fixtures/photo_core_v1_minimal.json").read_text())
    validator = Draft202012Validator(profiles_schema)
    validator.validate(photo["profiles"])

    incomplete = json.loads(json.dumps(photo["profiles"]))
    incomplete["editing"].pop("motion")
    with pytest.raises(ValidationError):
        validator.validate(incomplete)

def test_video_profile_does_not_require_photo_only_editing_fields() -> None:
    profiles_schema = json.loads((ROOT / "schemas/profiles/composition_profiles.schema.json").read_text())
    editing = FIXTURE["profiles"]["editing"]
    assert set(editing) == {"transition", "transition_seconds", "video_fit", "background_color"}
    Draft202012Validator(profiles_schema).validate(FIXTURE["profiles"])

def test_canonical_artifact_has_one_trim_source_and_adapts_for_zod() -> None:
    cut_schema = json.loads((ROOT / "schemas/artifacts/edit_decisions.schema.json").read_text())[
        "properties"
    ]["cuts"]["items"]["properties"]
    assert "in_seconds" in cut_schema and "out_seconds" in cut_schema
    assert "trim_in_seconds" not in cut_schema and "trim_out_seconds" not in cut_schema
    adapted = __import__(
        "tools.video.video_compose", fromlist=["VideoCompose"]
    ).VideoCompose._adapt_video_core_props(FIXTURE)
    cut = adapted["cuts"][0]
    assert cut["trim_in_seconds"] == 0
    assert cut["trim_out_seconds"] == 3
    assert cut["playback_rate"] == 1
    assert "in_seconds" not in cut and "out_seconds" not in cut
    assert "speed" not in cut

def test_video_core_is_registered_and_domain_neutral() -> None:
    root = (ROOT / "remotion-composer/src/Root.tsx").read_text()
    source = "\n".join(p.read_text().lower() for p in PRESET.glob("*.ts*"))
    assert 'id="VideoCoreV1"' in root
    assert "calculateMetadata={calculateVideoCoreV1Metadata}" in root
    forbidden = {"real_estate", "real-estate", "property", "listing", "realtor", "elevenlabs", "spotify"}
    assert not {token for token in forbidden if token in source}

def test_timeline_trim_rate_duration_and_metadata_contract() -> None:
    timeline = (PRESET / "timeline.ts").read_text()
    frame = (PRESET / "VideoFrame.tsx").read_text()
    metadata = (PRESET / "metadata.ts").read_text()
    assert "trim_out_seconds - cut.trim_in_seconds" in timeline
    assert "sourceDurationSeconds(cut) / playbackRate" in timeline
    assert "Math.min(cut.clip_duration_seconds, available)" in timeline
    assert "startFrom={trimBefore}" in frame and "endAt={" in frame
    assert "playbackRate={cut.playback_rate ?? 1}" in frame
    assert "videoTimelineDurationSeconds(props.cuts)" in metadata
    assert "props.profiles.export.fps" in metadata

def test_crop_position_transition_and_original_audio_contract() -> None:
    frame = (PRESET / "VideoFrame.tsx").read_text()
    assert "cropViewportStyle(cut.transform?.crop)" in frame
    assert "objectPosition" in frame
    assert "fadeInEnabled" in frame and "fadeOutEnabled" in frame
    assert 'cut.source_audio ?? profile.default_mode' in frame
    assert '=== "muted"' in frame
    assert "cut.source_audio_volume ?? profile.volume" in frame
    assert "profile.ducking.enabled && narrationActive" in frame

def test_audio_profiles_are_segment_driven_and_music_volume_is_not_hardcoded() -> None:
    composition = (PRESET / "VideoCoreV1.tsx").read_text()
    defaults = (PRESET / "defaults.ts").read_text()
    assert "narrationIsActiveAtFrame(frame, fps, narration)" in composition
    assert "profiles.music.volume * duck" in composition
    assert "profiles.music.enabled && audio?.music?.src" in composition
    assert "source_audio: {default_mode: \"muted\"" in defaults
    assert "music: {" in defaults and "enabled: false, volume: 1" in defaults
    assert "0.15" not in "\n".join(p.read_text() for p in PRESET.glob("*.ts*"))

def test_photo_core_regression_contract_is_unchanged() -> None:
    photo = ROOT / "remotion-composer/src/presets/photo-core-v1"
    composition = (photo / "PhotoCoreV1.tsx").read_text()
    frame = (photo / "PhotoFrame.tsx").read_text()
    assert "narrationIsActiveAtFrame" in composition
    assert "profiles.music.volume" in composition
    assert "cropViewportStyle(cut.transform?.crop)" in frame
    assert "translate3d(${x}px, ${y}px, 0) scale(${scale})" in frame
    assert "<Img" in frame

def test_preview_export_remains_renderer_independent() -> None:
    compose = (ROOT / "tools/video/video_compose.py").read_text()
    assert "result = self._apply_preview_export(result, inputs)" in compose
    assert '"video-montage": "VideoCoreV1"' in compose
