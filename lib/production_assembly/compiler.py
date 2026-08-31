"""Compile normalized Production Assembly plans into canonical edit_decisions."""

from __future__ import annotations

import copy
from typing import Any

from .normalizer import canonical_digest
from .validation import validate_normalized_plan


def compile_edit_decisions(plan: dict[str, Any]) -> dict[str, Any]:
    """Compile canonical cuts without renderer-only trim fields."""

    source = copy.deepcopy(plan)
    validate_normalized_plan(source)
    cuts: list[dict[str, Any]] = []
    narration_timeline: list[dict[str, Any]] = []
    cursor = 0.0

    for scene in source["scenes"]:
        timing = scene["timing"]
        duration = float(timing["duration_seconds"])
        cut: dict[str, Any] = {
            "id": scene["id"],
            "media_type": scene["media_type"],
            "source": scene["asset_binding"]["asset_id"],
            "in_seconds": float(timing.get("in_seconds", 0)),
            "out_seconds": float(timing.get("out_seconds", duration)),
            "reason": scene["match"]["reason"],
        }
        if scene["media_type"] == "video":
            rate = float(timing.get("playback_rate", 1))
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

        transition = scene.get("transition", {})
        if "in" in transition:
            cut["transition_in"] = transition["in"]
        if "out" in transition:
            cut["transition_out"] = transition["out"]
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
            }
        },
    }
    assembly = decisions["metadata"]["production_assembly"]
    assembly["edit_decisions_digest"] = canonical_digest(decisions)
    return decisions
