"""Domain-neutral AUTO/explicit routing for montage production plans."""

from __future__ import annotations

from collections.abc import Iterable

from .validation import ProductionAssemblyError

MODES = frozenset({"AUTO", "PHOTO", "VIDEO", "HYBRID"})
MEDIA_TYPES = frozenset({"photo", "video"})
MODE_TO_RENDERER = {
    "PHOTO": "photo-montage",
    "VIDEO": "video-montage",
    "HYBRID": "hybrid-montage",
}


def resolve_production_mode(requested_mode: str, media_types: Iterable[str]) -> str:
    """Resolve a production mode without inspecting file names or extensions."""

    requested = str(requested_mode).upper()
    if requested not in MODES:
        raise ProductionAssemblyError(f"Unknown production mode: {requested_mode!r}")
    observed = set(media_types)
    unknown = observed - MEDIA_TYPES
    if unknown:
        raise ProductionAssemblyError(
            "Unknown visual media type(s): " + ", ".join(sorted(map(str, unknown)))
        )
    if requested != "AUTO":
        return requested
    if observed == {"photo"}:
        return "PHOTO"
    if observed == {"video"}:
        return "VIDEO"
    if observed == {"photo", "video"}:
        return "HYBRID"
    raise ProductionAssemblyError("AUTO mode requires at least one typed visual scene asset")
