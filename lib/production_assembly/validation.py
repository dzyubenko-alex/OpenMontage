"""Schema and cross-reference validation for Production Assembly V1."""

from __future__ import annotations

from typing import Any

from jsonschema.exceptions import ValidationError
from schemas.artifacts import validate_artifact


class ProductionAssemblyError(ValueError):
    """Raised when a production manifest or normalized plan is unsafe to compile."""


def _validate_scene_timing(
    scene: dict[str, Any],
    media_type: str,
    source_duration_seconds: float | None = None,
) -> None:
    """Validate effective scene timing after every source/variant merge."""

    timing = scene["timing"]
    duration = float(timing["duration_seconds"])
    if duration <= 0:
        raise ProductionAssemblyError(f"Scene {scene['id']} duration must be positive")
    rate = float(timing.get("playback_rate", 1))
    if rate <= 0:
        raise ProductionAssemblyError(f"Scene {scene['id']} playback rate must be positive")
    if media_type == "photo":
        forbidden = {"in_seconds", "out_seconds", "playback_rate"}.intersection(timing)
        if "source_audio" in scene:
            forbidden.add("source_audio")
        if forbidden:
            raise ProductionAssemblyError(
                f"Photo scene {scene['id']} has video-only fields: {sorted(forbidden)}"
            )
        return

    if "in_seconds" not in timing or "out_seconds" not in timing:
        raise ProductionAssemblyError(
            f"Video scene {scene['id']} requires in_seconds and out_seconds"
        )
    source_in = float(timing["in_seconds"])
    source_out = float(timing["out_seconds"])
    if source_in < 0:
        raise ProductionAssemblyError(
            f"Video scene {scene['id']} in_seconds must be within source duration"
        )
    source_duration = source_out - source_in
    if source_duration <= 0:
        raise ProductionAssemblyError(
            f"Video scene {scene['id']} out_seconds must exceed in_seconds"
        )
    if source_duration_seconds is not None:
        declared_source_duration = float(source_duration_seconds)
        if source_in >= declared_source_duration or source_out > declared_source_duration:
            raise ProductionAssemblyError(
                f"Video scene {scene['id']} trim exceeds declared source duration"
            )
    available_duration = source_duration / rate
    if duration > available_duration + 1e-9:
        raise ProductionAssemblyError(
            f"Video scene {scene['id']} duration cap exceeds trimmed playback duration"
        )


def _validate_profiles_for_mode(profiles: dict[str, Any], mode: str) -> None:
    """Validate the complete bundle through the selected Core's artifact contract."""

    renderer_family = {
        "PHOTO": "photo-montage",
        "VIDEO": "video-montage",
        "HYBRID": "hybrid-montage",
    }[mode]
    contract_probe = {
        "version": "1.0",
        "cuts": [],
        "renderer_family": renderer_family,
        "render_runtime": "remotion",
        "profiles": profiles,
    }
    try:
        validate_artifact("edit_decisions", contract_probe)
    except ValidationError as exc:
        raise ProductionAssemblyError(
            f"{mode} mode requires a complete compatible profile bundle: {exc.message}"
        ) from exc


def _validate_schema(name: str, value: dict[str, Any]) -> None:
    try:
        validate_artifact(name, value)
    except ValidationError as exc:
        location = ".".join(map(str, exc.absolute_path)) or "<root>"
        raise ProductionAssemblyError(
            f"{name} schema error at {location}: {exc.message}"
        ) from exc


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
        _validate_scene_timing(
            scene, media_type, (assets[asset_id].get("metadata") or {}).get("duration_seconds")
        )
        if media_type == "video":
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
    _validate_profiles_for_mode(plan["profiles"], mode)
    for scene in plan["scenes"]:
        _validate_scene_timing(
            scene,
            scene["media_type"],
            scene["asset_binding"].get("source_duration_seconds"),
        )
        if scene["media_type"] == "video" and (
            scene.get("visual") or {}
        ).get("photo_motion") is not None:
            raise ProductionAssemblyError(
                f"Video scene {scene['id']} cannot use photo_motion"
            )
