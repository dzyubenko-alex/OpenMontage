"""Schema and cross-reference validation for Production Assembly V1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas" / "artifacts"


class ProductionAssemblyError(ValueError):
    """Raised when a production manifest or normalized plan is unsafe to compile."""


def _validate_schema(name: str, value: dict[str, Any]) -> None:
    schema = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    profile_schema = json.loads(
        (ROOT / "schemas/profiles/composition_profiles.schema.json").read_text(encoding="utf-8")
    )
    preview_schema = json.loads(
        (ROOT / "schemas/profiles/preview_export_profile.schema.json").read_text(encoding="utf-8")
    )
    registry = (
        Registry().with_resource(profile_schema["$id"], Resource.from_contents(profile_schema))
        .with_resource("openmontage/profiles/composition_profiles.schema.json", Resource.from_contents(profile_schema))
        .with_resource(preview_schema["$id"], Resource.from_contents(preview_schema))
        .with_resource("openmontage/profiles/preview_export_profile.schema.json", Resource.from_contents(preview_schema))
    )
    errors = sorted(Draft202012Validator(schema, registry=registry).iter_errors(value), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        location = ".".join(map(str, first.absolute_path)) or "<root>"
        raise ProductionAssemblyError(f"{name} schema error at {location}: {first.message}")


def _index_unique(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item["id"]
        if item_id in index:
            raise ProductionAssemblyError(f"Duplicate {label} id: {item_id}")
        index[item_id] = item
    return index


def validate_manifest(manifest: dict[str, Any]) -> None:
    _validate_schema("production_project_manifest", manifest)
    assets = _index_unique(manifest["assets"], "asset")
    narrations = _index_unique(manifest.get("narration_segments", []), "narration segment")
    scenes = _index_unique(manifest["scenes"], "scene")
    orders = [scene["order"] for scene in scenes.values()]
    if len(orders) != len(set(orders)):
        raise ProductionAssemblyError("Scene order values must be unique")

    bound_narration: set[str] = set()
    for scene in scenes.values():
        asset_id = scene["asset_id"]
        if asset_id not in assets:
            raise ProductionAssemblyError(
                f"Scene {scene['id']} references missing asset {asset_id!r}"
            )
        media_type = (assets[asset_id].get("metadata") or {}).get("media_type")
        if media_type not in {"photo", "video"}:
            raise ProductionAssemblyError(
                f"Scene {scene['id']} asset {asset_id!r} has unknown metadata.media_type"
            )
        narration_id = scene.get("narration_segment_id")
        if narration_id is not None:
            if narration_id not in narrations:
                raise ProductionAssemblyError(
                    f"Scene {scene['id']} references missing narration segment {narration_id!r}"
                )
            bound_narration.add(narration_id)
            match = scene.get("match") or {}
            if not match.get("method") or not str(match.get("reason", "")).strip():
                raise ProductionAssemblyError(
                    f"Scene {scene['id']} requires explicit match.method and match.reason"
                )
        timing = scene["timing"]
        if timing["duration_seconds"] <= 0:
            raise ProductionAssemblyError(f"Scene {scene['id']} duration must be positive")
        if timing.get("playback_rate", 1) <= 0:
            raise ProductionAssemblyError(f"Scene {scene['id']} playback rate must be positive")
        if media_type == "photo":
            forbidden = {"in_seconds", "out_seconds", "playback_rate"}.intersection(timing)
            if "source_audio" in scene:
                forbidden.add("source_audio")
            if forbidden:
                raise ProductionAssemblyError(
                    f"Photo scene {scene['id']} has video-only fields: {sorted(forbidden)}"
                )
        else:
            if "in_seconds" not in timing or "out_seconds" not in timing:
                raise ProductionAssemblyError(
                    f"Video scene {scene['id']} requires in_seconds and out_seconds"
                )
            if timing["out_seconds"] <= timing["in_seconds"]:
                raise ProductionAssemblyError(
                    f"Video scene {scene['id']} out_seconds must exceed in_seconds"
                )
            if (scene.get("visual") or {}).get("photo_motion") is not None:
                raise ProductionAssemblyError(
                    f"Video scene {scene['id']} cannot use photo_motion"
                )

    unbound = set(narrations) - bound_narration
    if unbound:
        raise ProductionAssemblyError(
            "Narration segment(s) without scene binding: " + ", ".join(sorted(unbound))
        )
    variants = _index_unique(manifest.get("variants", []), "variant")
    for variant in variants.values():
        base = variant.get("base_variant")
        if base is not None and base not in variants:
            raise ProductionAssemblyError(
                f"Variant {variant['id']} references missing base variant {base!r}"
            )


def validate_normalized_plan(plan: dict[str, Any]) -> None:
    _validate_schema("normalized_production_plan", plan)
    mode = plan["resolved_mode"]
    media_types = {scene["media_type"] for scene in plan["scenes"]}
    if mode == "PHOTO" and media_types != {"photo"}:
        raise ProductionAssemblyError("PHOTO mode accepts photo scenes only")
    if mode == "VIDEO" and media_types != {"video"}:
        raise ProductionAssemblyError("VIDEO mode accepts video scenes only")
    if mode == "HYBRID" and not media_types <= {"photo", "video"}:
        raise ProductionAssemblyError("HYBRID mode accepts typed photo/video scenes only")
    expected = {"PHOTO": "photo-montage", "VIDEO": "video-montage", "HYBRID": "hybrid-montage"}[mode]
    if plan["renderer_family"] != expected:
        raise ProductionAssemblyError("Resolved mode and renderer_family disagree")
