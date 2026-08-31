from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

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


def test_schema_and_contract_gaps() -> None:
    source = _manifest(); plan = normalize_production_plan(source)
    validate_manifest(source)
    validate_normalized_plan(plan)
    for name in ("proposal_packet", "render_report"):
        text = (ROOT / f"schemas/artifacts/{name}.schema.json").read_text()
        assert all(family in text for family in ("photo-montage", "video-montage", "hybrid-montage"))
