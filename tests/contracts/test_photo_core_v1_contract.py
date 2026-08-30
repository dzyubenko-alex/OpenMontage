from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
PRESET_DIR = REPO_ROOT / "remotion-composer" / "src" / "presets" / "photo-core-v1"
FIXTURE = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "photo_core_v1_minimal.json").read_text(
        encoding="utf-8"
    )
)


def test_profile_bundle_requires_all_five_profile_families() -> None:
    schema = json.loads(
        (REPO_ROOT / "schemas" / "profiles" / "composition_profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(FIXTURE["profiles"])
    assert schema["required"] == ["voice", "music", "editing", "branding", "export"]


def test_edit_decisions_exposes_photo_montage_and_profiles() -> None:
    schema = json.loads(
        (REPO_ROOT / "schemas" / "artifacts" / "edit_decisions.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "photo-montage" in schema["properties"]["renderer_family"]["enum"]
    assert schema["properties"]["profiles"]["$ref"].endswith(
        "profiles/composition_profiles.schema.json"
    )


def test_root_registers_photo_core_without_replacing_explainer() -> None:
    root = (REPO_ROOT / "remotion-composer" / "src" / "Root.tsx").read_text(
        encoding="utf-8"
    )
    assert 'id="Explainer"' in root
    assert 'id="PhotoCoreV1"' in root
    assert "schema={photoCoreV1Schema}" in root
    assert "calculateMetadata={calculatePhotoCoreV1Metadata}" in root


def test_export_profile_drives_remotion_metadata() -> None:
    metadata = (PRESET_DIR / "metadata.ts").read_text(encoding="utf-8")
    assert "exportProfile.fps" in metadata
    assert "width: exportProfile.width" in metadata
    assert "height: exportProfile.height" in metadata


def test_photo_core_source_is_domain_neutral_and_profile_driven() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(PRESET_DIR.glob("*.ts*"))
    ).lower()
    forbidden = {
        "real_estate", "real-estate", "property", "listing", "bedroom",
        "realtor", "estate agent", "elevenlabs", "spotify",
    }
    assert not {token for token in forbidden if token in source}
    for family in ("profiles.voice", "profiles.music", "profiles.editing", "profiles.branding"):
        assert family in source
    assert "media_profile" in source


def test_photo_core_uses_frame_driven_remotion_primitives() -> None:
    frame = (PRESET_DIR / "PhotoFrame.tsx").read_text(encoding="utf-8")
    composition = (PRESET_DIR / "PhotoCoreV1.tsx").read_text(encoding="utf-8")
    assert "useCurrentFrame" in frame
    assert "extrapolateLeft: \"clamp\"" in frame
    assert "<Img" in frame
    assert "premountFor={fps}" in composition
    assert "<Audio" in composition


def test_photo_core_applies_declarative_crop_as_a_motion_viewport() -> None:
    frame = (PRESET_DIR / "PhotoFrame.tsx").read_text(encoding="utf-8")

    assert "cropViewportStyle(cut.transform?.crop)" in frame
    assert "left: crop.x" in frame
    assert "top: crop.y" in frame
    assert "width: crop.width" in frame
    assert "height: crop.height" in frame
    assert 'overflow: "hidden"' in frame

    # Positioning and frame-driven motion stay on the image inside the viewport.
    assert "objectPosition," in frame
    assert "translate3d(${x}px, ${y}px, 0) scale(${scale})" in frame


def test_edit_decisions_crop_is_a_complete_composition_viewport() -> None:
    schema = json.loads(
        (REPO_ROOT / "schemas" / "artifacts" / "edit_decisions.schema.json").read_text(
            encoding="utf-8"
        )
    )
    crop = schema["properties"]["cuts"]["items"]["properties"]["transform"][
        "properties"
    ]["crop"]

    assert crop["required"] == ["x", "y", "width", "height"]
    assert "composition pixels" in crop["description"]
    assert crop["additionalProperties"] is False
