from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
from typing import get_args, get_type_hints

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from lib.production_assembly import compile_edit_decisions, normalize_production_plan, validate_manifest
from lib.production_assembly.validation import ProductionAssemblyError
from schemas.artifacts import validate_artifact
from tests.lib.test_production_assembly_v1 import _manifest

from lib.contextual_transitions import (
    CanonicalTransitionType,
    LEGACY_TRANSITION_ALIASES,
    LEGACY_TRANSITIONS,
    LegacyTransitionType,
    SUPPORTED_TRANSITIONS,
    TransitionDecision,
    TransitionMapEntry,
    TransitionType,
    canonical_transition,
    resolve_contextual_transitions,
    resolve_declared_transitions,
)

ROOT = Path(__file__).resolve().parents[2]


def scene(scene_id: str, media: str = "photo", **values):
    base = {
        "id": scene_id,
        "media_type": media,
        "timing": {"duration_seconds": 2},
        "narration_binding": {"semantic_purpose": "feature"},
    }
    base.update(values)
    return base


def test_supported_set_and_legacy_aliases_are_stable():
    assert SUPPORTED_TRANSITIONS == (
        "hard_cut", "crossfade", "subtle_zoom", "directional_push",
        "matched_motion", "section_transition",
    )
    assert LEGACY_TRANSITION_ALIASES == {"cut": "hard_cut", "fade": "crossfade"}
    assert canonical_transition("cut") == "hard_cut"
    assert canonical_transition("fade") == "crossfade"


def test_semantic_selection_uses_sections_environment_media_roles_and_motion():
    assert resolve_contextual_transitions([
        scene("a", section_id="one"), scene("b", section_id="two")
    ])[0].transition == "section_transition"
    assert resolve_contextual_transitions([
        scene("a", environment="exterior"), scene("b", environment="interior")
    ])[0].transition == "crossfade"
    assert resolve_contextual_transitions([
        scene("a", "photo"), scene("b", "video")
    ])[0].transition == "crossfade"
    assert resolve_contextual_transitions([
        scene("a", "video", motion_hint={"direction": "left"}),
        scene("b", "video", motion_hint={"direction": "left"}),
    ])[0].transition == "matched_motion"
    assert resolve_contextual_transitions([
        scene("a"), scene("b", semantic_role="outro")
    ])[0].transition == "hard_cut"


def test_repeat_limiter_caps_identical_decorative_run():
    scenes = [scene(str(i), transition={"out": "subtle_zoom"}) for i in range(4)]
    decisions = resolve_contextual_transitions(scenes)
    assert [item.transition for item in decisions] == ["subtle_zoom", "subtle_zoom", "crossfade"]
    assert "repeat limiter" in decisions[-1].reason


def test_output_is_deterministic_and_input_is_not_mutated():
    scenes = [scene("a"), scene("b"), scene("c", media_type="video")]
    before = copy.deepcopy(scenes)
    first = resolve_contextual_transitions(scenes)
    second = resolve_contextual_transitions(scenes)
    assert first == second
    assert scenes == before


@pytest.mark.parametrize(("duration", "fallback"), [(2, "crossfade"), (0.2, "hard_cut")])
def test_matched_motion_missing_data_has_deterministic_fallback(duration, fallback):
    decisions = resolve_contextual_transitions([
        scene("a", transition={"out": "matched_motion"}, timing={"duration_seconds": duration}),
        scene("b", timing={"duration_seconds": duration}),
    ])
    assert decisions[0].transition == fallback
    assert "insufficient aligned motion data" in decisions[0].reason


@pytest.mark.parametrize("pair", [("photo", "photo"), ("video", "video"), ("photo", "video"), ("video", "photo")])
def test_all_photo_video_hybrid_boundaries_resolve(pair):
    result = resolve_contextual_transitions([scene("from", pair[0]), scene("to", pair[1])])
    assert len(result) == 1 and result[0].transition in SUPPORTED_TRANSITIONS
    assert {"FROM_SCENE", "TO_SCENE", "TRANSITION", "DURATION", "REASON"} <= set(result[0].as_map_entry())


def test_schema_accepts_new_types_and_legacy_aliases():
    schema = json.loads((ROOT / "schemas/artifacts/production_project_manifest.schema.json").read_text())
    transition = schema["$defs"]["transition_input"]
    for value in (*SUPPORTED_TRANSITIONS, "cut", "fade"):
        Draft202012Validator(transition).validate(value)


def test_existing_boundary_layer_is_extended_without_new_render_path():
    shared = (ROOT / "remotion-composer/src/presets/contextualTransitions.ts").read_text()
    compose = (ROOT / "tools/video/video_compose.py").read_text()
    for value in SUPPORTED_TRANSITIONS:
        assert value in shared
    assert "boundaryTransitionStyle" in shared
    assert "contextual" not in " ".join(line for line in compose.splitlines() if "_render_via_" in line).lower()


def test_premium_restrained_transition_vocabulary():
    forbidden = {"flash", "glitch", "spin", "bounce", "aggressive_wipe"}
    assert not forbidden.intersection(SUPPORTED_TRANSITIONS)


def _two_photo_manifest() -> dict:
    manifest = _manifest("PHOTO")
    manifest["assets"].append({"id": "photo-2", "path": "two.jpg", "metadata": {"media_type": "photo"}})
    manifest["narration_segments"].append({"id": "n-2", "text": "Detail", "semantic_purpose": "show detail"})
    manifest["scenes"].append({
        "id": "scene-2", "order": 1, "asset_id": "photo-2", "narration_segment_id": "n-2",
        "match": {"method": "manual", "reason": "Shows detail"}, "timing": {"duration_seconds": 2},
    })
    return manifest


def test_legacy_profiles_do_not_opt_into_semantic_transitions():
    manifest = _two_photo_manifest()
    manifest["profiles"]["editing"]["transition"] = "cut"
    decisions = compile_edit_decisions(normalize_production_plan(manifest))
    assert all("transition_in" not in cut and "transition_out" not in cut for cut in decisions["cuts"])
    assert decisions["metadata"]["production_assembly"]["transition_map"][0]["TRANSITION"] == "hard_cut"


def test_legacy_explicit_cut_and_fade_are_preserved_without_migration():
    manifest = _two_photo_manifest()
    manifest["scenes"][0]["transition"] = {"out": "fade"}
    manifest["scenes"][1]["transition"] = {"in": "cut"}
    decisions = compile_edit_decisions(normalize_production_plan(manifest))
    assert decisions["cuts"][0]["transition_out"] == "fade"
    assert decisions["cuts"][1]["transition_in"] == "cut"


def test_contextual_v1_is_an_explicit_opt_in():
    manifest = _two_photo_manifest()
    manifest["profiles"]["editing"]["transition"] = "cut"
    manifest["profiles"]["editing"]["transition_mode"] = "contextual_v1"
    decisions = compile_edit_decisions(normalize_production_plan(manifest))
    assert decisions["cuts"][0]["transition_out"] == "subtle_zoom"
    assert decisions["cuts"][1]["transition_in"] == "subtle_zoom"


def test_photo_video_hybrid_share_visual_timeline_and_keep_audio_canonical():
    presets = ROOT / "remotion-composer/src/presets"
    shared = (presets / "visualBoundaryTimeline.tsx").read_text()
    assert "canonicalStartFrame" in shared
    assert "visualStartFrame: canonicalStarts[index] - incomingFrames" in shared
    assert "visualDurationInFrames: durations[index] + incomingFrames" in shared
    assert "buildVisualBoundaries" in shared
    for core in (
        presets / "photo-core-v1/PhotoCoreV1.tsx",
        presets / "video-core-v1/VideoCoreV1.tsx",
        presets / "hybrid-core-v1/HybridCoreV1.tsx",
    ):
        assert "VisualBoundary" in core.read_text()
    video = (presets / "video-core-v1/VideoCoreV1.tsx").read_text()
    hybrid = (presets / "hybrid-core-v1/HybridCoreV1.tsx").read_text()
    assert "SourceAudioTrack" in video and "from={from}" in video
    assert "SourceAudioTrack" in hybrid and "from={item.canonicalStartFrame}" in hybrid
    assert "visualOnly" in video
    assert "visualOnly={contextualEnabled}" in (presets / "hybrid-core-v1/HybridFrame.tsx").read_text()


def test_contextual_hybrid_duration_is_sum_of_semantic_scene_durations():
    timeline = (ROOT / "remotion-composer/src/presets/hybrid-core-v1/timeline.ts").read_text()
    assert 'editing.transition_mode === "contextual_v1"' in timeline
    assert "cuts.reduce((sum, cut) => sum + hybridCutDurationInFrames(cut, fps), 0)" in timeline



def test_contextual_compiler_keeps_incoming_and_outgoing_boundary_durations_separate():
    manifest = _two_photo_manifest()
    manifest["assets"].append({"id": "photo-3", "path": "three.jpg", "metadata": {"media_type": "photo"}})
    manifest["narration_segments"].append({"id": "n-3", "text": "More", "semantic_purpose": "show detail"})
    manifest["scenes"].append({
        "id": "scene-3", "order": 2, "asset_id": "photo-3", "narration_segment_id": "n-3",
        "match": {"method": "manual", "reason": "More detail"}, "timing": {"duration_seconds": 2},
        "transition": {"in_duration_seconds": 0.7},
    })
    manifest["scenes"][0]["transition"] = {"out": "crossfade", "out_duration_seconds": 0.2}
    manifest["scenes"][1]["transition"] = {"in": "crossfade", "in_duration_seconds": 0.2, "out": "crossfade", "out_duration_seconds": 0.7}
    manifest["profiles"]["editing"]["transition_mode"] = "contextual_v1"
    cuts = compile_edit_decisions(normalize_production_plan(manifest))["cuts"]
    assert "transition_in_duration" not in cuts[0]
    assert cuts[0]["transition_out_duration"] == 0.2
    assert cuts[1]["transition_in_duration"] == 0.2
    assert cuts[1]["transition_out_duration"] == 0.7
    assert cuts[2]["transition_in_duration"] == 0.7
    assert "transition_out_duration" not in cuts[2]
    assert all("transition_duration" not in cut for cut in cuts)


@pytest.mark.parametrize("direction", ["left", "right", "up", "down"])
def test_direction_is_resolved_and_compiled_with_one_python_typescript_convention(direction):
    decision = resolve_contextual_transitions([
        scene("a", "video", motion_hint={"direction": direction}),
        scene("b", "video", motion_hint={"direction": direction}),
    ])[0]
    assert decision.transition == "matched_motion"
    assert decision.direction == direction
    assert decision.as_map_entry()["DIRECTION"] == direction


def test_visual_boundaries_are_single_source_and_clamped_for_short_first_last_scenes():
    shared = (ROOT / "remotion-composer/src/presets/visualBoundaryTimeline.tsx").read_text()
    assert "incomingBoundary?: VisualBoundaryDecision" in shared
    assert "outgoingBoundary?: VisualBoundaryDecision" in shared
    assert "index === 0 ? undefined" in shared
    assert "index === cuts.length - 1 ? undefined" in shared
    assert "Math.floor(durations[index] / 2)" in shared
    assert "Math.floor(durations[index + 1] / 2)" in shared
    assert "right.transition_in_duration" in shared
    assert "left.transition_out_duration" in shared


def test_transition_transforms_have_disjoint_phases_and_deterministic_overlap_precedence():
    transitions = (ROOT / "remotion-composer/src/presets/contextualTransitions.ts").read_text()
    boundary = (ROOT / "remotion-composer/src/presets/visualBoundaryTimeline.tsx").read_text()
    assert 'frame < transitionFrames' in transitions
    assert 'frame >= durationInFrames - transitionFrames' in transitions
    assert 'outgoingActive ? outgoingStyle : incomingActive ? incomingStyle : {}' in boundary
    for transition in ("subtle_zoom", "directional_push", "matched_motion", "section_transition"):
        assert transition in transitions


def test_directional_rendering_uses_both_axes_and_matched_motion_keeps_fallback():
    transitions = (ROOT / "remotion-composer/src/presets/contextualTransitions.ts").read_text()
    assert 'direction === "right"' in transitions
    assert 'direction === "up"' in transitions
    assert 'direction === "down"' in transitions
    assert "vector.x * signedProgress" in transitions
    assert "vector.y * signedProgress" in transitions
    fallback = resolve_contextual_transitions([
        scene("a", "video", transition={"out": "matched_motion"}),
        scene("b", "video"),
    ])[0]
    assert fallback.transition in {"crossfade", "hard_cut"}
    assert fallback.direction is None



TRANSITION_INPUTS = (*SUPPORTED_TRANSITIONS, "cut", "fade")


def test_real_typescript_timeline_and_render_math_runtime():
    node_modules = ROOT / "remotion-composer" / "node_modules"
    assert node_modules.is_dir(), "run npm ci in this worktree''s remotion-composer"
    env = dict(os.environ)
    env["NODE_PATH"] = str(node_modules)
    result = subprocess.run(
        ["node", str(ROOT / "tests/remotion/contextual_transitions_runtime.test.cjs")],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_real_remotion_render_harness_is_worktree_local_and_available():
    source = (ROOT / "tests/remotion/run_contextual_render_harness.py").read_text()
    assert "C/\"node_modules/.bin/remotion\"" in source
    assert "ROOT.parent" not in source
    assert "OpenMontage/remotion-composer/node_modules" not in source
    assert "CONTEXTUAL_REMOTION_RENDER_HARNESS=PASS" in source
    assert "analysis.returncode" in source
    assert "analysis.stdout+analysis.stderr" in source
    assert '"crop":{"x":-20' in source
    assert "REMOTION_BROWSER_EXECUTABLE" in source
    assert "/usr/bin/google-chrome" not in source


def test_public_types_reject_arbitrary_transition_strings_at_compile_time():
    tsc = ROOT / "remotion-composer/node_modules/.bin/tsc"
    result = subprocess.run([
        str(tsc), "--noEmit", "--strict", "--skipLibCheck",
        "--jsx", "react-jsx", "--module", "ESNext",
        "--moduleResolution", "bundler", "--target", "ES2020",
        str(ROOT / "tests/remotion/contextual_transition_types.test.ts"),
    ], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    sources = "\n".join(
        path.read_text() for path in (ROOT / "remotion-composer/src").rglob("*.ts*")
    )
    assert "transition_in?: string" not in sources
    assert "transition_out?: string" not in sources



@pytest.mark.parametrize("fixture_name", [
    "photo_core_v1_minimal.json", "video_core_v1_minimal.json", "hybrid_core_v1_minimal.json",
])
def test_all_core_schemas_share_strict_transition_vocabulary(fixture_name):
    fixture = json.loads((ROOT / "tests/fixtures" / fixture_name).read_text())
    fixture.pop("captions", None)
    for transition in TRANSITION_INPUTS:
        candidate = copy.deepcopy(fixture)
        candidate["cuts"][0]["transition_in"] = transition
        candidate["cuts"][0]["transition_out"] = transition
        validate_artifact("edit_decisions", candidate)
    invalid = copy.deepcopy(fixture)
    invalid["cuts"][0]["transition_in"] = "wipe"
    with pytest.raises(ValidationError):
        validate_artifact("edit_decisions", invalid)


def test_typescript_cores_import_one_transition_schema_source():
    presets = ROOT / "remotion-composer/src/presets"
    common = (presets / "transitionSchema.ts").read_text()
    assert "transitionInputSchema = z.enum(TRANSITION_INPUTS)" in common
    assert "motionHintSchema" in common and ".strict()" in common
    for core in ("photo-core-v1", "video-core-v1", "hybrid-core-v1"):
        schema = (presets / core / "schema.ts").read_text()
        assert 'from "../transitionSchema"' in schema
        assert "transitionInputSchema" in schema
        assert 'z.string().optional()' not in "\n".join(
            line for line in schema.splitlines() if "transition_" in line
        )


def test_motion_hint_contract_rejects_extra_fields_and_variant_override_drift():
    valid = _two_photo_manifest()
    valid["scenes"][0]["motion_hint"] = {"direction": "up"}
    validate_manifest(valid)

    invalid = copy.deepcopy(valid)
    invalid["scenes"][0]["motion_hint"]["kind"] = "pan"
    with pytest.raises(ProductionAssemblyError):
        validate_manifest(invalid)

    invalid_direction = copy.deepcopy(valid)
    invalid_direction["scenes"][0]["motion_hint"]["direction"] = "in"
    with pytest.raises(ProductionAssemblyError):
        validate_manifest(invalid_direction)

    variant = copy.deepcopy(valid)
    variant["variants"] = [{
        "id": "motion", "scene_overrides": {
            "scene-1": {"motion_hint": {"direction": "left", "strength": 0.8}},
        },
    }]
    with pytest.raises(ProductionAssemblyError):
        validate_manifest(variant)


def test_valid_variant_motion_hint_is_preserved_by_normalization():
    manifest = _two_photo_manifest()
    manifest["variants"] = [{
        "id": "motion", "scene_overrides": {
            "sp": {"motion_hint": {"direction": "down"}},
        },
    }]
    plan = normalize_production_plan(manifest, variant_id="motion")
    assert plan["scenes"][0]["motion_hint"] == {"direction": "down"}
    validate_artifact("normalized_production_plan", plan)


def test_contextual_visual_timeline_does_not_change_audio_or_crop_contracts():
    manifest = _two_photo_manifest()
    manifest["profiles"]["editing"]["transition_mode"] = "contextual_v1"
    manifest["audio"] = {
        "narration": {"src": "voice.wav"},
        "music": {"src": "music.wav", "offset_seconds": 0.5},
    }
    manifest["scenes"][0]["visual"] = {
        "object_position": "65% 50%",
        "crop": {"x": 0, "y": 0, "width": 1080, "height": 1920},
    }
    plan = normalize_production_plan(manifest)
    decisions = compile_edit_decisions(plan)
    assert decisions["audio"] == manifest["audio"]
    assert decisions["metadata"]["production_assembly"]["narration_bindings"] == [
        {"segment_id": "np", "scene_id": "sp", "start_seconds": 0.0, "end_seconds": 4.0},
        {"segment_id": "n-2", "scene_id": "scene-2", "start_seconds": 4.0, "end_seconds": 6.0},
    ]
    assert decisions["cuts"][0]["transform"] == {
        "position": "65% 50%",
        "crop": {"x": 0, "y": 0, "width": 1080, "height": 1920},
    }
    photo_frame = (ROOT / "remotion-composer/src/presets/photo-core-v1/PhotoFrame.tsx").read_text()
    assert "objectFit: editing.image_fit" in photo_frame
    assert "objectPosition," in photo_frame
    assert 'overflow: "hidden"' in photo_frame


def test_video_source_audio_timing_stays_on_canonical_scene_range():
    manifest = _manifest("VIDEO")
    manifest["profiles"]["editing"]["transition_mode"] = "contextual_v1"
    manifest["profiles"]["source_audio"]["default_mode"] = "original"
    manifest["scenes"][0]["source_audio"] = {"mode": "original", "volume": 0.5}
    plan = normalize_production_plan(manifest)
    decisions = compile_edit_decisions(plan)
    cut = decisions["cuts"][0]
    assert (cut["in_seconds"], cut["out_seconds"], cut["clip_duration_seconds"]) == (1.0, 7.0, 3.0)
    assert (cut["source_audio"], cut["source_audio_volume"]) == ("original", 0.5)
    video_core = (ROOT / "remotion-composer/src/presets/video-core-v1/VideoCoreV1.tsx").read_text()
    assert 'from={from} durationInFrames={duration}' in video_core
    assert "<SourceAudioTrack" in video_core


def test_vertical_hybrid_crop_and_object_position_survive_contextual_compilation():
    manifest = _manifest("HYBRID")
    manifest["profiles"]["editing"]["transition_mode"] = "contextual_v1"
    manifest["scenes"][0]["visual"]["crop"] = {"x": 0, "y": 0, "width": 1080, "height": 1920}
    plan = normalize_production_plan(manifest, variant_id="vertical-9x16")
    decisions = compile_edit_decisions(plan)
    assert plan["target"]["aspect_ratio"] == "9:16"
    assert decisions["cuts"][0]["transform"]["position"] == "65% 50%"
    assert decisions["cuts"][0]["transform"]["crop"]["height"] == 1920
    assert decisions["profiles"]["editing"]["image_fit"] == "cover"
    assert decisions["profiles"]["editing"]["video_fit"] == "cover"


def test_contextual_schemas_are_valid_draft_2020_12_meta_schemas():
    for relative in (
        "schemas/artifacts/production_project_manifest.schema.json",
        "schemas/artifacts/normalized_production_plan.schema.json",
        "schemas/artifacts/edit_decisions.schema.json",
        "schemas/profiles/composition_profiles.schema.json",
    ):
        Draft202012Validator.check_schema(json.loads((ROOT / relative).read_text()))



def test_legacy_photo_cut_profile_scene_fade_fixture_preserves_baseline_precedence():
    fixture = json.loads((
        ROOT / "tests/fixtures/contextual_transitions_v1/legacy_photo_profile_cut_scene_fade.json"
    ).read_text())
    validate_artifact("edit_decisions", fixture)
    assert fixture["profiles"]["editing"]["transition"] == "cut"
    assert fixture["cuts"][0]["transition_in"] == "fade"
    resolver = (ROOT / "remotion-composer/src/presets/photo-core-v1/legacyTransition.ts").read_text()
    frame = (ROOT / "remotion-composer/src/presets/photo-core-v1/PhotoFrame.tsx").read_text()
    assert 'if (profileTransition === "cut") return "cut"' in resolver
    assert "resolvePhotoBoundaryTransition" in frame


@pytest.mark.parametrize("invalid_transition", ["wipe", "zoom_fast", "random_transition"])
def test_arbitrary_transitions_are_rejected_at_every_public_and_normalized_ingress(invalid_transition):
    base = _two_photo_manifest()
    base["scenes"][0]["transition"] = {"out": invalid_transition}
    with pytest.raises(ProductionAssemblyError):
        validate_manifest(base)

    variant = _two_photo_manifest()
    variant["variants"] = [{
        "id": "invalid-transition",
        "scene_overrides": {"sp": {"transition": {"out": invalid_transition}}},
    }]
    with pytest.raises(ProductionAssemblyError):
        validate_manifest(variant)

    normalized = normalize_production_plan(_two_photo_manifest())
    normalized["scenes"][0]["transition"] = {"out": invalid_transition}
    with pytest.raises(ValidationError):
        validate_artifact("normalized_production_plan", normalized)

    edit = json.loads((ROOT / "tests/fixtures/photo_core_v1_minimal.json").read_text())
    edit["transitions"] = [{
        "type": invalid_transition, "at_seconds": 1, "duration_seconds": 0.2,
    }]
    with pytest.raises(ValidationError):
        validate_artifact("edit_decisions", edit)


def test_typescript_transition_public_api_has_no_raw_string_escape_hatch():
    presets = ROOT / "remotion-composer/src/presets"
    contextual = (presets / "contextualTransitions.ts").read_text()
    boundary = (presets / "visualBoundaryTimeline.tsx").read_text()
    assert "TransitionInput | string" not in contextual
    assert "TransitionInput | string" not in boundary
    assert "transition_in?: string" not in boundary
    assert "transition_out?: string" not in boundary


def test_python_public_transition_contract_uses_one_strict_type_source():
    assert SUPPORTED_TRANSITIONS == get_args(CanonicalTransitionType)
    assert LEGACY_TRANSITIONS == get_args(LegacyTransitionType)
    transition_values = {
        value
        for member in get_args(TransitionType)
        for value in get_args(member)
    }
    assert transition_values == {
        "hard_cut", "crossfade", "subtle_zoom", "directional_push",
        "matched_motion", "section_transition", "cut", "fade",
    }

    canonical_hints = get_type_hints(canonical_transition)
    assert canonical_hints["value"] == TransitionType | None
    assert canonical_hints["return"] == CanonicalTransitionType | None
    assert get_type_hints(resolve_contextual_transitions)["default_transition"] == TransitionType
    assert get_type_hints(resolve_declared_transitions)["default_transition"] == TransitionType
    assert get_type_hints(TransitionDecision)["transition"] == CanonicalTransitionType
    assert get_type_hints(TransitionMapEntry)["TRANSITION"] == CanonicalTransitionType

    for invalid in ("wipe", "zoom_fast", "random_transition"):
        with pytest.raises(ValueError):
            canonical_transition(invalid)