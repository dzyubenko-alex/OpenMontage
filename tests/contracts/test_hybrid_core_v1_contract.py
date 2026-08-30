from __future__ import annotations
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
PRESET = ROOT / "remotion-composer/src/presets/hybrid-core-v1"
FIXTURE = json.loads((ROOT / "tests/fixtures/hybrid_core_v1_minimal.json").read_text())

def validator() -> Draft202012Validator:
    edit_schema = json.loads((ROOT / "schemas/artifacts/edit_decisions.schema.json").read_text())
    profiles_schema = json.loads((ROOT / "schemas/profiles/composition_profiles.schema.json").read_text())
    profile_resource = Resource.from_contents(profiles_schema)
    registry = (
        Registry()
        .with_resource("openmontage/profiles/composition_profiles.schema.json", profile_resource)
        .with_resource("openmontage/artifacts/openmontage/profiles/composition_profiles.schema.json", profile_resource)
    )
    return Draft202012Validator(edit_schema, registry=registry)

def test_hybrid_artifact_validates_with_media_type_as_discriminator() -> None:
    artifact = json.loads(json.dumps(FIXTURE))
    artifact.pop("captions")
    validator().validate(artifact)
    missing = json.loads(json.dumps(artifact))
    missing["cuts"][0].pop("media_type")
    with pytest.raises(ValidationError):
        validator().validate(missing)

def test_media_specific_fields_are_strict() -> None:
    photo_with_audio = json.loads(json.dumps(FIXTURE))
    photo_with_audio["cuts"][0]["source_audio"] = "original"
    with pytest.raises(ValidationError):
        validator().validate(photo_with_audio)
    video_with_motion = json.loads(json.dumps(FIXTURE))
    video_with_motion["cuts"][1]["transform"]["animation"] = "zoom"
    with pytest.raises(ValidationError):
        validator().validate(video_with_motion)

def test_hybrid_adapter_normalizes_photo_and_video_without_mutation() -> None:
    from tools.video.video_compose import VideoCompose
    adapted = VideoCompose._adapt_hybrid_core_props(FIXTURE)
    photo, video = adapted["cuts"]
    assert photo["media_type"] == "photo" and photo["duration_seconds"] == 3
    assert video["media_type"] == "video"
    assert video["trim_in_seconds"] == 1 and video["trim_out_seconds"] == 5
    assert video["playback_rate"] == 2
    assert "in_seconds" not in photo and "out_seconds" not in video and "speed" not in video
    assert "duration_seconds" not in FIXTURE["cuts"][0]
    assert "trim_in_seconds" not in FIXTURE["cuts"][1]
    assert VideoCompose._adapt_hybrid_core_props(adapted) == adapted


@pytest.mark.parametrize("transition", ["cut", "fade"])
def test_supported_hybrid_transitions_validate(transition: str) -> None:
    artifact = json.loads(json.dumps(FIXTURE))
    artifact.pop("captions")
    artifact["cuts"][0]["transition_out"] = transition
    artifact["cuts"][1]["transition_in"] = transition
    validator().validate(artifact)


def test_unsupported_hybrid_transition_is_rejected_before_renderer() -> None:
    artifact = json.loads(json.dumps(FIXTURE))
    artifact.pop("captions")
    artifact["cuts"][0]["transition_out"] = "wipe"
    with pytest.raises(ValidationError):
        validator().validate(artifact)

def test_hybrid_timeline_and_metadata_share_frame_builder() -> None:
    timeline = (PRESET / "timeline.ts").read_text()
    metadata = (PRESET / "metadata.ts").read_text()
    assert 'cut.media_type === "photo"' in timeline
    assert "cut.duration_seconds * fps" in timeline
    assert "(cut.trim_out_seconds - cut.trim_in_seconds) / rate" in timeline
    assert "Math.min(cut.clip_duration_seconds, available)" in timeline
    assert "buildHybridTimeline(cuts, fps, editing)" in timeline
    assert "hybridTimelineDurationInFrames(props.cuts, fps, props.profiles.editing)" in metadata

def test_all_mixed_boundaries_use_one_transition_owner() -> None:
    timeline = (PRESET / "timeline.ts").read_text()
    frame = (PRESET / "HybridFrame.tsx").read_text()
    assert "boundaryTransition(previous.cut, cut, editing)" in timeline
    assert 'transition_in: "cut", transition_out: "cut"' in frame
    assert "<PhotoFrame" in frame and "<VideoFrame" in frame
    pairs = [("photo", "photo"), ("video", "video"), ("photo", "video"), ("video", "photo")]
    assert len(pairs) == 4

def test_ken_burns_is_photo_only_and_source_audio_is_video_only() -> None:
    frame = (PRESET / "HybridFrame.tsx").read_text()
    types = (PRESET / "types.ts").read_text()
    assert 'item.cut.media_type === "photo"' in frame
    photo_decl = types.split("export type HybridVideoCut")[0]
    video_decl = types.split("export type HybridVideoCut")[1].split("export type HybridCut")[0]
    assert "animation?: string" in photo_decl and "source_audio" not in photo_decl
    assert "source_audio" in video_decl and "animation?: string" not in video_decl

def test_profiles_preview_and_domain_neutrality() -> None:
    source = "\n".join(p.read_text().lower() for p in PRESET.glob("*.ts*"))
    assert 'mode: "hybrid"' in source
    assert "enabled: false" in source
    assert "source_audio: {default_mode: \"muted\"" in source
    forbidden = {"real_estate", "real-estate", "property", "listing", "realtor", "elevenlabs", "spotify"}
    assert not {token for token in forbidden if token in source}

def test_photo_and_video_renderer_contracts_remain_strict() -> None:
    photo = json.loads((ROOT / "tests/fixtures/photo_core_v1_minimal.json").read_text())
    video = json.loads((ROOT / "tests/fixtures/video_core_v1_minimal.json").read_text())
    profiles_schema = json.loads((ROOT / "schemas/profiles/composition_profiles.schema.json").read_text())
    profile_validator = Draft202012Validator(profiles_schema)
    profile_validator.validate(photo["profiles"])
    profile_validator.validate(video["profiles"])
    broken_photo = json.loads(json.dumps(photo["profiles"]))
    broken_photo["editing"].pop("motion")
    with pytest.raises(ValidationError):
        profile_validator.validate(broken_photo)
    broken_video = json.loads(json.dumps(video["profiles"]))
    broken_video["editing"].pop("video_fit")
    with pytest.raises(ValidationError):
        profile_validator.validate(broken_video)
