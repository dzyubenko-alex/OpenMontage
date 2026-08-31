from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from schemas.artifacts import validate_artifact
from lib.production_assembly import (
    ProductionAssemblyError,
    canonical_digest,
    compile_edit_decisions,
    normalize_production_plan,
    validate_manifest,
    validate_normalized_plan,
)

ROOT = Path(__file__).resolve().parents[2]


def _profiles(mode: str) -> dict:
    editing = {"transition": "fade", "transition_seconds": 0.25, "background_color": "#000"}
    if mode in {"PHOTO", "HYBRID"}:
        editing |= {"motion": "zoom", "image_fit": "cover", "scale_from": 1,
                    "scale_to": 1.08, "pan_x": 12, "pan_y": 8}
    if mode in {"VIDEO", "HYBRID"}:
        editing["video_fit"] = "cover"
    value = {
        "voice": {"enabled": True, "volume": 1, "captions": {
            "enabled": True, "words_per_page": 6, "font_size": 42}},
        "music": {"enabled": True, "volume": 0.15, "fade_in_seconds": 1,
                  "fade_out_seconds": 2, "loop": True,
                  "ducking": {"enabled": True, "volume_multiplier": 0.4}},
        "editing": editing,
        "branding": {"enabled": True, "logo_src": "logo", "position": "top-right",
                     "opacity": 0.9, "max_width": 220, "safe_margin": 40,
                     "primary_color": "#FFF", "text_color": "#FFF",
                     "caption_background_color": "#000A", "font_family": "Inter",
                     "title_font_size": 72, "subtitle_font_size": 34},
        "export": {"media_profile": "generic_hd"},
    }
    if mode in {"VIDEO", "HYBRID"}:
        value["source_audio"] = {"default_mode": "muted", "volume": 1,
                                 "ducking": {"enabled": True, "volume_multiplier": 0.25}}
    return value


def _manifest(kind: str = "HYBRID", requested: str = "AUTO") -> dict:
    assets, scenes, narration = [], [], []
    if kind in {"PHOTO", "HYBRID"}:
        assets.append({"id": "photo", "path": "living.mp4",
                       "metadata": {"media_type": "photo", "width": 4000, "height": 3000}})
        narration.append({"id": "np", "text": "Bright living room",
                          "semantic_purpose": "show interior"})
        scenes.append({"id": "sp", "order": 0, "asset_id": "photo",
                       "narration_segment_id": "np",
                       "match": {"method": "manual", "reason": "Shows narrated room"},
                       "timing": {"duration_seconds": 4},
                       "visual": {"object_position": "center", "photo_motion": "zoom"}})
    if kind in {"VIDEO", "HYBRID"}:
        assets.append({"id": "video", "path": "exterior.jpg",
                       "metadata": {"media_type": "video", "duration_seconds": 10}})
        narration.append({"id": "nv", "text": "Exterior approach",
                          "semantic_purpose": "show exterior"})
        scenes.append({"id": "sv", "order": 1, "asset_id": "video",
                       "narration_segment_id": "nv",
                       "match": {"method": "declared", "reason": "Shows narrated exterior"},
                       "timing": {"duration_seconds": 3, "in_seconds": 1,
                                  "out_seconds": 7, "playback_rate": 2},
                       "source_audio": {"mode": "muted", "volume": 0.5}})
    return {
        "version": "1.0", "project": {"id": "property", "title": "Property"},
        "production_mode": requested,
        "target": {"platform": "generic", "aspect_ratio": "16:9"},
        "narration_segments": narration, "assets": assets, "scenes": scenes,
        "profiles": _profiles(kind), "delivery": {"cta": "Book", "contacts": {"phone": "555"}},
        "audio": {}, "variants": [
            {"id": "landscape-16x9", "target_overrides": {"platform": "youtube", "aspect_ratio": "16:9"},
             "profile_overrides": {"export": {"media_profile": "youtube_landscape"}}},
            {"id": "vertical-9x16", "base_variant": "landscape-16x9",
             "target_overrides": {"platform": "instagram", "aspect_ratio": "9:16"},
             "profile_overrides": {"export": {"media_profile": "instagram_reels"}},
             "scene_overrides": {"sp": {"visual": {"object_position": "65% 50%"}}}},
            {"id": "avito-no-contacts", "base_variant": "vertical-9x16",
             "target_overrides": {"platform": "avito"}, "policy": {"contacts": "omit"}},
        ],
    }


@pytest.mark.parametrize(("kind", "mode", "family"), [
    ("PHOTO", "PHOTO", "photo-montage"), ("VIDEO", "VIDEO", "video-montage"),
    ("HYBRID", "HYBRID", "hybrid-montage")])
def test_auto_routes(kind: str, mode: str, family: str) -> None:
    plan = normalize_production_plan(_manifest(kind))
    assert (plan["resolved_mode"], plan["renderer_family"]) == (mode, family)


def test_explicit_override_and_incompatible_mode() -> None:
    value = _manifest("PHOTO", "HYBRID")
    value["profiles"] = _profiles("HYBRID")
    assert normalize_production_plan(value)["resolved_mode"] == "HYBRID"
    value = _manifest("VIDEO", "PHOTO")
    value["profiles"] = _profiles("PHOTO")
    with pytest.raises(ProductionAssemblyError, match="PHOTO mode"):
        normalize_production_plan(value)


def test_missing_unknown_and_extension_independence() -> None:
    value = _manifest("PHOTO"); value["scenes"][0]["asset_id"] = "missing"
    with pytest.raises(ProductionAssemblyError, match="missing asset"): validate_manifest(value)
    value = _manifest("PHOTO"); value["assets"][0]["metadata"]["media_type"] = "unknown"
    with pytest.raises(ProductionAssemblyError, match="unknown metadata"): validate_manifest(value)
    plan = normalize_production_plan(_manifest())
    assert [s["media_type"] for s in plan["scenes"]] == ["photo", "video"]
    assert plan["scenes"][0]["asset_binding"]["path"].endswith(".mp4")
    assert plan["scenes"][1]["asset_binding"]["path"].endswith(".jpg")


@pytest.mark.parametrize(("kind", "area", "key", "setting", "message"), [
    ("PHOTO", "timing", "in_seconds", 1, "video-only"),
    ("PHOTO", "scene", "source_audio", {"mode": "muted"}, "video-only"),
    ("VIDEO", "visual", "photo_motion", "zoom", "photo_motion"),
    ("PHOTO", "timing", "duration_seconds", 0, "duration"),
    ("VIDEO", "timing", "playback_rate", 0, "playback rate")])
def test_invalid_fields(kind, area, key, setting, message) -> None:
    value = _manifest(kind); scene = value["scenes"][0]
    if area == "scene":
        scene[key] = setting
    else:
        scene.setdefault(area, {})[key] = setting
    with pytest.raises(ProductionAssemblyError, match=message): validate_manifest(value)


def test_narration_binding_and_match_required() -> None:
    value = _manifest("PHOTO"); value["scenes"][0].pop("narration_segment_id")
    with pytest.raises(ProductionAssemblyError, match="without scene binding"): validate_manifest(value)
    value = _manifest("PHOTO"); value["scenes"][0]["match"]["reason"] = ""
    with pytest.raises(ProductionAssemblyError, match="schema error"): validate_manifest(value)


def test_determinism_profiles_and_canonical_trim() -> None:
    source = _manifest(); before = copy.deepcopy(source)
    a = normalize_production_plan(source, variant_id="vertical-9x16")
    b = normalize_production_plan(source, variant_id="vertical-9x16")
    assert a == b and canonical_digest(a) == canonical_digest(b) and source == before
    edit_a, edit_b = compile_edit_decisions(a), compile_edit_decisions(b)
    assert edit_a == edit_b and canonical_digest(edit_a) == canonical_digest(edit_b)
    assert edit_a["profiles"] == a["profiles"]
    assert "trim_in_seconds" not in json.dumps(edit_a) and "trim_out_seconds" not in json.dumps(edit_a)


def test_video_declared_duration_caps_renderer_and_narration_together() -> None:
    source = _manifest("VIDEO")
    source["scenes"][0]["timing"]["duration_seconds"] = 2
    plan = normalize_production_plan(source)
    decisions = compile_edit_decisions(plan)
    cut = decisions["cuts"][0]
    narration = decisions["metadata"]["production_assembly"]["narration_bindings"][0]
    assert (cut["out_seconds"] - cut["in_seconds"]) / cut["playback_rate"] == 3
    assert cut["clip_duration_seconds"] == 2
    assert narration["end_seconds"] - narration["start_seconds"] == 2


def test_photo_timeline_uses_cumulative_non_overlapping_bounds() -> None:
    source = _manifest("PHOTO")
    source["assets"].extend([
        {"id": "photo-2", "path": "kitchen.jpg",
         "metadata": {"media_type": "photo"}},
        {"id": "photo-3", "path": "garden.jpg",
         "metadata": {"media_type": "photo"}},
    ])
    source["narration_segments"].extend([
        {"id": "np-2", "text": "Kitchen", "semantic_purpose": "show kitchen"},
        {"id": "np-3", "text": "Garden", "semantic_purpose": "show garden"},
    ])
    source["scenes"].extend([
        {"id": "sp-2", "order": 1, "asset_id": "photo-2",
         "narration_segment_id": "np-2",
         "match": {"method": "manual", "reason": "Shows narrated kitchen"},
         "timing": {"duration_seconds": 2.5}},
        {"id": "sp-3", "order": 2, "asset_id": "photo-3",
         "narration_segment_id": "np-3",
         "match": {"method": "manual", "reason": "Shows narrated garden"},
         "timing": {"duration_seconds": 5}},
    ])

    decisions = compile_edit_decisions(normalize_production_plan(source))
    bounds = [
        (cut["in_seconds"], cut["out_seconds"]) for cut in decisions["cuts"]
    ]
    narration = decisions["metadata"]["production_assembly"]["narration_bindings"]

    assert bounds == [(0, 4), (4, 6.5), (6.5, 11.5)]
    assert all(
        current[1] == following[0]
        for current, following in zip(bounds, bounds[1:])
    )
    assert [
        (item["start_seconds"], item["end_seconds"]) for item in narration
    ] == bounds
    assert max(cut["out_seconds"] for cut in decisions["cuts"]) == 11.5


def test_video_declared_duration_cannot_exceed_trimmed_playback() -> None:
    source = _manifest("VIDEO")
    source["scenes"][0]["timing"]["duration_seconds"] = 3.01
    with pytest.raises(ProductionAssemblyError, match="duration cap exceeds"):
        normalize_production_plan(source)


@pytest.mark.parametrize(("override", "message"), [
    ({"duration_seconds": 0}, "duration must be positive"),
    ({"in_seconds": 7}, "out_seconds must exceed"),
    ({"playback_rate": 0}, "playback rate must be positive"),
    ({"duration_seconds": -1}, "duration must be positive"),
])
def test_variant_scene_overrides_revalidate_video_timing(override, message) -> None:
    source = _manifest("VIDEO")
    source["variants"].append({
        "id": "invalid-timing",
        "scene_overrides": {"sv": {"timing": override}},
    })
    with pytest.raises(ProductionAssemblyError, match=message):
        normalize_production_plan(source, variant_id="invalid-timing")


def test_variant_scene_override_revalidates_photo_duration() -> None:
    source = _manifest("PHOTO")
    source["variants"].append({
        "id": "invalid-photo-duration",
        "scene_overrides": {"sp": {"timing": {"duration_seconds": 0}}},
    })
    with pytest.raises(ProductionAssemblyError, match="duration must be positive"):
        normalize_production_plan(source, variant_id="invalid-photo-duration")


@pytest.mark.parametrize(("kind", "profile_kind"), [
    ("PHOTO", "VIDEO"),
    ("PHOTO", "HYBRID"),
    ("VIDEO", "PHOTO"),
    ("VIDEO", "HYBRID"),
    ("HYBRID", "PHOTO"),
    ("HYBRID", "VIDEO"),
])
def test_resolved_mode_rejects_incompatible_editing_profile(kind, profile_kind) -> None:
    source = _manifest(kind)
    source["profiles"] = _profiles(profile_kind)
    with pytest.raises(ProductionAssemblyError, match=f"{kind} mode requires"):
        normalize_production_plan(source)


@pytest.mark.parametrize("kind", ["VIDEO", "HYBRID"])
def test_video_modes_require_source_audio_profile(kind: str) -> None:
    source = _manifest(kind)
    source["profiles"].pop("source_audio")
    with pytest.raises(
        ProductionAssemblyError, match="complete compatible profile bundle"
    ):
        normalize_production_plan(source)


@pytest.mark.parametrize(("kind", "path"), [
    ("VIDEO", ("editing", "video_fit")),
    ("HYBRID", ("editing", "image_fit")),
    ("HYBRID", ("source_audio", "ducking")),
])
def test_mode_profiles_reject_other_missing_required_fields(kind, path) -> None:
    source = _manifest(kind)
    source["profiles"][path[0]].pop(path[1])
    with pytest.raises(ProductionAssemblyError):
        normalize_production_plan(source)


def test_photo_profile_rejects_video_source_audio_shape() -> None:
    source = _manifest("PHOTO")
    source["profiles"]["source_audio"] = _profiles("VIDEO")["source_audio"]
    with pytest.raises(
        ProductionAssemblyError, match="complete compatible profile bundle"
    ):
        normalize_production_plan(source)


def test_variants_and_avito_contacts_omission() -> None:
    source = _manifest()
    landscape = normalize_production_plan(source, variant_id="landscape-16x9")
    vertical = normalize_production_plan(source, variant_id="vertical-9x16")
    avito = normalize_production_plan(source, variant_id="avito-no-contacts")
    assert landscape["target"]["aspect_ratio"] == "16:9"
    assert vertical["target"]["aspect_ratio"] == "9:16"
    assert vertical["profiles"]["export"]["media_profile"] == "instagram_reels"
    assert vertical["scenes"][0]["visual"]["object_position"] == "65% 50%"
    assert avito["target"] == {"platform": "avito", "aspect_ratio": "9:16"}
    assert "contacts" not in avito["delivery"]
    edits = [compile_edit_decisions(p) for p in (landscape, vertical, avito)]
    assert [e["metadata"]["production_assembly"]["variant_id"] for e in edits] == [
        "landscape-16x9", "vertical-9x16", "avito-no-contacts"]


def test_general_artifact_validator_resolves_production_profile_refs() -> None:
    source = _manifest()
    plan = normalize_production_plan(source)
    validate_artifact("production_project_manifest", source)
    validate_artifact("normalized_production_plan", plan)


def test_unknown_scene_override_id_is_rejected() -> None:
    source = _manifest("PHOTO")
    source["variants"].append({
        "id": "stale-scene",
        "scene_overrides": {"removed-scene": {"timing": {"duration_seconds": 2}}},
    })
    with pytest.raises(ProductionAssemblyError, match="Unknown scene override"):
        normalize_production_plan(source, variant_id="stale-scene")


def test_scene_order_overrides_are_applied_before_deterministic_sorting() -> None:
    source = _manifest("HYBRID")
    source["variants"].append({
        "id": "reverse-order",
        "scene_overrides": {"sp": {"order": 2}, "sv": {"order": 0}},
    })
    plan = normalize_production_plan(source, variant_id="reverse-order")
    assert [(scene["id"], scene["order"]) for scene in plan["scenes"]] == [
        ("sv", 0), ("sp", 2)
    ]


def test_tampered_normalized_plan_digest_is_rejected_before_compilation() -> None:
    plan = normalize_production_plan(_manifest("PHOTO"))
    plan["project"]["title"] = "Tampered after normalization"
    with pytest.raises(ProductionAssemblyError, match="digest mismatch"):
        compile_edit_decisions(plan)


@pytest.mark.parametrize(("variant_override", "message"), [
    (None, "trim exceeds declared source duration"),
    ({"out_seconds": 10.1}, "trim exceeds declared source duration"),
    ({"in_seconds": -0.1}, "in_seconds must be within source duration"),
])
def test_video_trim_cannot_exceed_declared_source_duration(
    variant_override, message
) -> None:
    source = _manifest("VIDEO")
    if variant_override is None:
        source["scenes"][0]["timing"]["out_seconds"] = 10.1
        with pytest.raises(ProductionAssemblyError, match=message):
            validate_manifest(source)
        return
    source["variants"].append({
        "id": "source-overflow",
        "scene_overrides": {"sv": {"timing": variant_override}},
    })
    with pytest.raises(ProductionAssemblyError, match=message):
        normalize_production_plan(source, variant_id="source-overflow")


def test_schema_and_contract_gaps() -> None:
    source = _manifest(); plan = normalize_production_plan(source)
    validate_manifest(source)
    validate_normalized_plan(plan)
    for name in ("proposal_packet", "render_report"):
        text = (ROOT / f"schemas/artifacts/{name}.schema.json").read_text()
        assert all(family in text for family in ("photo-montage", "video-montage", "hybrid-montage"))
