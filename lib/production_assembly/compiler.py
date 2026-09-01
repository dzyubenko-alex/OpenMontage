"""Compile normalized Production Assembly plans into canonical edit_decisions."""

from __future__ import annotations

import copy
from typing import Any

from lib.contextual_transitions import (
    resolve_contextual_transitions, resolve_declared_transitions,
)
from .normalizer import canonical_digest, normalized_plan_digest
from .validation import ProductionAssemblyError, validate_normalized_plan


def compile_edit_decisions(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile canonical cuts without renderer-only trim fields."""

    source = copy.deepcopy(plan)
    stored_digest = source.get("diagnostics", {}).get("normalized_plan_digest")
    actual_digest = normalized_plan_digest(source)
    if stored_digest != actual_digest:
        raise ProductionAssemblyError("Normalized production plan digest mismatch")
    validate_normalized_plan(source)
    editing = source["profiles"]['editing']
    contextual_enabled = editing.get("transition_mode") == "contextual_v1"
    resolver = resolve_contextual_transitions if contextual_enabled else resolve_declared_transitions
    transition_decisions = resolver(
        source["scenes"], default_transition=editing["transition"],
        default_duration=editing["transition_seconds"],
    )
    entering = {item.to_scene: item for item in transition_decisions}
    leaving = {item.from_scene: item for item in transition_decisions}
    cuts: list[dict[str, Any]] = []
    narration_timeline: list[dict[str, Any]] = []
    cursor = 0.0

    for scene in source["scenes"]:
        timing = scene["timing"]
        duration = float(timing["duration_seconds"])
        if scene["media_type"] == "photo":
            in_seconds = cursor
            out_seconds = cursor + duration
        else:
            in_seconds = float(timing["in_seconds"])
            out_seconds = float(timing["out_seconds"])
        cut: dict[str, Any] = {
            "id": scene["id"],
            "media_type": scene["media_type"],
            "source": scene["asset_binding"]["asset_id"],
            "in_seconds": in_seconds,
            "out_seconds": out_seconds,
            "reason": scene["match"]["reason"],
        }
        if scene["media_type"] == "video":
            rate = float(timing.get("playback_rate", 1))
            cut["clip_duration_seconds"] = duration
            if rate != 1:
                cut["playback_rate"] = rate
            source_audio = scene.get("source_audio")
            if source_audio:
                cut["source_audio"] = source_audio["mode"]
                if "volume" in source_audio:
                    cut["source_audio_volume"] = source_audio["volume"]

        visual = scene.get("visual", {})
        transform: dict[str, Any] = {}
        if "object_position" in visual:
            transform["position"] = copy.deepcopy(visual["object_position"])
        if "crop" in visual:
            transform["crop"] = copy.deepcopy(visual["crop"])
        if scene["media_type"] == "photo" and "photo_motion" in visual:
            transform["animation"] = visual["photo_motion"]
        if transform:
            cut["transform"] = transform

        if contextual_enabled:
            incoming = entering.get(scene["id"])
            outgoing = leaving.get(scene["id"])
            if incoming:
                cut["transition_in"] = incoming.transition
                cut["transition_in_duration"] = incoming.duration
                if incoming.direction is not None:
                    cut["transition_in_direction"] = incoming.direction
            if outgoing:
                cut["transition_out"] = outgoing.transition
                cut["transition_out_duration"] = outgoing.duration
                if outgoing.direction is not None:
                    cut["transition_out_direction"] = outgoing.direction
        else:
            transition = scene.get("transition", {})
            if "in" in transition:
                cut["transition_in"] = transition["in"]
            if "out" in transition:
                cut["transition_out"] = transition["out"]
            if "duration_seconds" in transition:
                cut["transition_duration"] = transition["duration_seconds"]
        cuts.append(cut)

        narration = scene.get("narration_binding")
        if narration:
            narration_timeline.append({
                "segment_id": narration["segment_id"],
                "scene_id": scene["id"],
                "start_seconds": cursor,
                "end_seconds": cursor + duration,
            })
        cursor += duration

    decisions: dict[str, Any] = {
        "version": "1.0",
        "cuts": cuts,
        "profiles": copy.deepcopy(source["profiles"]),
        "renderer_family": source["renderer_family"],
        "render_runtime": source["render_runtime"],
        "audio": copy.deepcopy(source.get("audio", {})),
        "metadata": {
            "production_assembly": {
                "version": "1.0",
                "project_id": source["project"]["id"],
                "variant_id": source["variant_id"],
                "resolved_mode": source["resolved_mode"],
                "delivery": copy.deepcopy(source.get("delivery", {})),
                "narration_bindings": narration_timeline,
                "source_manifest_digest": source["diagnostics"]["source_manifest_digest"],
                "normalized_plan_digest": source["diagnostics"]["normalized_plan_digest"],
                "transition_map": [item.as_map_entry() for item in transition_decisions],
            }
        },
    }
    assembly = decisions["metadata"]["production_assembly"]
    assembly["edit_decisions_digest"] = canonical_digest(decisions)
    return decisions
