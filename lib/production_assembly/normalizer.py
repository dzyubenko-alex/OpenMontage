"""Pure, deterministic manifest-to-plan normalization."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .mode_router import MODE_TO_RENDERER, resolve_production_mode
from .validation import ProductionAssemblyError, validate_manifest, validate_normalized_plan


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalized_plan_digest(plan: dict[str, Any]) -> str:
    """Digest canonical plan content without recursively hashing its digest field."""

    content = copy.deepcopy(plan)
    content.get("diagnostics", {}).pop("normalized_plan_digest", None)
    return canonical_digest(content)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _resolve_variant(manifest: dict[str, Any], variant_id: str | None) -> dict[str, Any]:
    if variant_id is None:
        return {}
    variants = {variant["id"]: variant for variant in manifest.get("variants", [])}
    if variant_id not in variants:
        raise ProductionAssemblyError(f"Unknown variant: {variant_id!r}")
    visiting: set[str] = set()

    def visit(current_id: str) -> dict[str, Any]:
        if current_id in visiting:
            raise ProductionAssemblyError(f"Variant inheritance cycle at {current_id!r}")
        visiting.add(current_id)
        current = variants[current_id]
        inherited = visit(current["base_variant"]) if current.get("base_variant") else {}
        visiting.remove(current_id)
        own = {key: value for key, value in current.items() if key not in {"id", "base_variant"}}
        return _deep_merge(inherited, own)

    return visit(variant_id)


def normalize_production_plan(
    manifest: dict[str, Any], *, variant_id: str | None = None
) -> dict[str, Any]:
    """Return new canonical content; never mutate the manifest or inspect the filesystem."""

    source = copy.deepcopy(manifest)
    validate_manifest(source)
    variant = _resolve_variant(source, variant_id)
    assets = {asset["id"]: asset for asset in source["assets"]}
    narrations = {item["id"]: item for item in source.get("narration_segments", [])}

    profiles = _deep_merge(source["profiles"], variant.get("profile_overrides", {}))
    delivery = _deep_merge(source.get("delivery", {}), variant.get("delivery_overrides", {}))
    policy = variant.get("policy", {})
    if policy.get("contacts") == "omit":
        delivery.pop("contacts", None)
    if policy.get("cta") == "omit":
        delivery.pop("cta", None)

    scene_overrides = variant.get("scene_overrides", {})
    scene_ids = {scene["id"] for scene in source["scenes"]}
    unknown_override_ids = set(scene_overrides) - scene_ids
    if unknown_override_ids:
        raise ProductionAssemblyError(
            "Unknown scene override id(s): " + ", ".join(sorted(unknown_override_ids))
        )
    normalized_scenes: list[dict[str, Any]] = []
    for raw_scene in sorted(source["scenes"], key=lambda item: (item["order"], item["id"])):
        scene = _deep_merge(raw_scene, scene_overrides.get(raw_scene["id"], {}))
        asset = assets[scene["asset_id"]]
        narration_id = scene.get("narration_segment_id")
        asset_binding = {"asset_id": scene["asset_id"], "path": asset["path"]}
        if "duration_seconds" in asset["metadata"]:
            asset_binding["source_duration_seconds"] = asset["metadata"]["duration_seconds"]
        normalized: dict[str, Any] = {
            "id": scene["id"],
            "order": scene["order"],
            "asset_binding": asset_binding,
            "media_type": asset["metadata"]["media_type"],
            "timing": copy.deepcopy(scene["timing"]),
            "match": copy.deepcopy(scene["match"]),
        }
        if narration_id is not None:
            normalized["narration_binding"] = {
                "segment_id": narration_id,
                "text": narrations[narration_id]["text"],
                "semantic_purpose": narrations[narration_id]["semantic_purpose"],
            }
        for optional in ("visual", "transition", "source_audio", "captions", "branding"):
            if optional in scene:
                normalized[optional] = copy.deepcopy(scene[optional])
        normalized_scenes.append(normalized)

    resolved_mode = resolve_production_mode(
        source["production_mode"], [scene["media_type"] for scene in normalized_scenes]
    )
    plan: dict[str, Any] = {
        "version": "1.0",
        "project": copy.deepcopy(source["project"]),
        "variant_id": variant_id or "default",
        "requested_mode": source["production_mode"],
        "resolved_mode": resolved_mode,
        "renderer_family": MODE_TO_RENDERER[resolved_mode],
        "render_runtime": "remotion",
        "target": _deep_merge(source["target"], variant.get("target_overrides", {})),
        "scenes": normalized_scenes,
        "profiles": profiles,
        "variants": copy.deepcopy(source.get("variants", [])),
        "delivery": delivery,
        "audio": copy.deepcopy(source.get("audio", {})),
        "diagnostics": {
            "warnings": [],
            "media_type_source": "asset.metadata.media_type",
            "semantic_matching": "explicit-bindings-only",
            "source_manifest_digest": canonical_digest(source),
        },
    }
    validate_normalized_plan(plan)
    plan["diagnostics"]["normalized_plan_digest"] = normalized_plan_digest(plan)
    return plan
