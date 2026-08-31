"""Deterministic production-manifest assembly for the montage Core V1 renderers."""

from .compiler import compile_edit_decisions
from .mode_router import MODE_TO_RENDERER, resolve_production_mode
from .normalizer import canonical_digest, canonical_json, normalize_production_plan
from .validation import ProductionAssemblyError, validate_manifest, validate_normalized_plan

__all__ = [
    "MODE_TO_RENDERER",
    "ProductionAssemblyError",
    "canonical_digest",
    "canonical_json",
    "compile_edit_decisions",
    "normalize_production_plan",
    "resolve_production_mode",
    "validate_manifest",
    "validate_normalized_plan",
]
