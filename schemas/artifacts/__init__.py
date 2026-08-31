"""Artifact schema loading and validation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).parent
PROFILE_SCHEMA_DIR = SCHEMA_DIR.parent / "profiles"

ARTIFACT_NAMES = [
    "research_brief",
    "proposal_packet",
    "brief",
    "script",
    "character_design",
    "rig_plan",
    "pose_library",
    "scene_plan",
    "action_timeline",
    "production_project_manifest",
    "normalized_production_plan",
    "asset_manifest",
    "edit_decisions",
    "render_report",
    "publish_log",
    "review",
    "cost_log",
    "decision_log",
    "source_media_review",
    "final_review",
    "character_qa_report",
    "video_analysis_brief",
]


def load_schema(name: str) -> dict:
    """Load a JSON schema by artifact name."""
    path = SCHEMA_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _schema_registry() -> Registry:
    """Resolve shared profile schemas from every artifact schema base URI."""

    registry = Registry()
    for filename in ("composition_profiles.schema.json", "preview_export_profile.schema.json"):
        schema = json.loads((PROFILE_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(f"openmontage/profiles/{filename}", resource)
    return registry


def validate_artifact(name: str, data: dict[str, Any]) -> None:
    """Validate artifact data against its schema. Raises on failure."""
    schema = load_schema(name)
    Draft202012Validator(schema, registry=_schema_registry()).validate(data)


def list_schemas() -> list[str]:
    """List all available artifact schema names."""
    return [p.stem.replace(".schema", "") for p in SCHEMA_DIR.glob("*.schema.json")]
