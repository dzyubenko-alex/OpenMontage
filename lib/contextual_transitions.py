"""Deterministic semantic boundary transition resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, NotRequired, TypeAlias, TypedDict, cast, get_args

CanonicalTransitionType: TypeAlias = Literal[
    "hard_cut", "crossfade", "subtle_zoom", "directional_push",
    "matched_motion", "section_transition",
]
LegacyTransitionType: TypeAlias = Literal["cut", "fade"]
TransitionType: TypeAlias = CanonicalTransitionType | LegacyTransitionType

SUPPORTED_TRANSITIONS: tuple[CanonicalTransitionType, ...] = get_args(CanonicalTransitionType)
LEGACY_TRANSITIONS: tuple[LegacyTransitionType, ...] = get_args(LegacyTransitionType)
LEGACY_TRANSITION_ALIASES: dict[LegacyTransitionType, CanonicalTransitionType] = {
    "cut": "hard_cut", "fade": "crossfade",
}
DECORATIVE_TRANSITIONS: set[CanonicalTransitionType] = {
    "subtle_zoom", "directional_push", "matched_motion", "section_transition",
}
DEFAULT_DURATIONS: dict[CanonicalTransitionType, float] = {
    "hard_cut": 0.0, "crossfade": 0.32, "subtle_zoom": 0.36,
    "directional_push": 0.34, "matched_motion": 0.28,
    "section_transition": 0.42,
}
MAX_DECORATIVE_RUN = 2
RENDER_DIRECTIONS = {"left", "right", "up", "down"}


def canonical_transition(
    value: TransitionType | None,
) -> CanonicalTransitionType | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    normalized = LEGACY_TRANSITION_ALIASES.get(
        cast(LegacyTransitionType, raw), raw,
    )
    if normalized not in SUPPORTED_TRANSITIONS:
        raise ValueError(f"Unsupported transition type: {value!r}")
    return cast(CanonicalTransitionType, normalized)


def _semantic_role(scene: dict[str, Any]) -> str:
    explicit = scene.get("semantic_role")
    if explicit:
        return str(explicit).strip().lower()
    narration = scene.get("narration_binding") or {}
    return str(narration.get("semantic_purpose", "unspecified")).strip().lower()


def _environment(scene: dict[str, Any]) -> str:
    return str(scene.get("environment", "unknown")).strip().lower()


def _motion_direction(scene: dict[str, Any]) -> str | None:
    hint = scene.get("motion_hint") or {}
    direction = str(hint.get("direction", "")).lower() if isinstance(hint, dict) else ""
    return direction if direction in RENDER_DIRECTIONS else None


def _explicit_boundary(
    left: dict[str, Any], right: dict[str, Any],
) -> CanonicalTransitionType | None:
    incoming = (right.get("transition") or {}).get("in")
    outgoing = (left.get("transition") or {}).get("out")
    return canonical_transition(incoming if incoming is not None else outgoing)


def _matched_motion_has_data(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_direction = _motion_direction(left)
    return left_direction is not None and left_direction == _motion_direction(right)


def _matched_motion_fallback(
    left: dict[str, Any], right: dict[str, Any],
) -> CanonicalTransitionType:
    shortest = min(float((left.get("timing") or {}).get("duration_seconds", 0)), float((right.get("timing") or {}).get("duration_seconds", 0)))
    return "hard_cut" if shortest < 0.4 else "crossfade"


def _semantic_choice(
    left: dict[str, Any], right: dict[str, Any],
) -> tuple[CanonicalTransitionType, str]:
    left_section, right_section = left.get("section_id"), right.get("section_id")
    if left_section is not None and right_section is not None and left_section != right_section:
        return "section_transition", "section boundary"
    if {_environment(left), _environment(right)} == {"exterior", "interior"}:
        return "crossfade", "exterior/interior boundary"
    if _matched_motion_has_data(left, right):
        return "matched_motion", "aligned motion hints"
    left_role, right_role = _semantic_role(left), _semantic_role(right)
    if any(token in right_role for token in ("outro", "cta", "closing", "end")):
        return "hard_cut", "closing semantic role"
    left_media, right_media = left.get("media_type"), right.get("media_type")
    if left_media != right_media:
        return "crossfade", f"media boundary {left_media}->{right_media}"
    right_direction = _motion_direction(right)
    if left_media == "video" and right_direction:
        return "directional_push", f"video motion direction {right_direction}"
    if left_media == "photo" and (left_role == right_role or any(token in right_role for token in ("detail", "feature", "support", "evidence", "interior"))):
        return "subtle_zoom", "photo semantic continuity"
    return "crossfade", f"semantic role {left_role}->{right_role}"


class TransitionMapEntry(TypedDict):
    FROM_SCENE: str
    TO_SCENE: str
    TRANSITION: CanonicalTransitionType
    DURATION: float
    REASON: str
    DIRECTION: NotRequired[str]


@dataclass(frozen=True)
class TransitionDecision:
    from_scene: str
    to_scene: str
    transition: CanonicalTransitionType
    duration: float
    reason: str
    direction: str | None = None

    def as_map_entry(self) -> TransitionMapEntry:
        entry: TransitionMapEntry = {"FROM_SCENE": self.from_scene, "TO_SCENE": self.to_scene, "TRANSITION": self.transition, "DURATION": self.duration, "REASON": self.reason}
        if self.direction is not None:
            entry["DIRECTION"] = self.direction
        return entry



def resolve_declared_transitions(
    scenes: Iterable[dict[str, Any]],
    *,
    default_transition: TransitionType = "crossfade",
    default_duration: float | None = None,
) -> list[TransitionDecision]:
    """Build an audit map without semantic selection for legacy manifests."""

    ordered = list(scenes)
    fallback = canonical_transition(default_transition) or "crossfade"
    decisions: list[TransitionDecision] = []
    for left, right in zip(ordered, ordered[1:]):
        transition = _explicit_boundary(left, right) or fallback
        right_transition = right.get("transition") or {}
        left_transition = left.get("transition") or {}
        configured_duration = right_transition.get("in_duration_seconds")
        if configured_duration is None:
            configured_duration = left_transition.get("out_duration_seconds")
        if configured_duration is None:
            configured_duration = right_transition.get("duration_seconds")
        if configured_duration is None:
            configured_duration = left_transition.get("duration_seconds")
        duration = 0.0 if transition == "hard_cut" else max(
            0.0,
            float(configured_duration if configured_duration is not None else (default_duration or 0.0)),
        )
        decisions.append(TransitionDecision(
            str(left["id"]), str(right["id"]), transition,
            round(duration, 3), "legacy declared transition",
        ))
    return decisions

def resolve_contextual_transitions(scenes: Iterable[dict[str, Any]], *, default_transition: TransitionType = "crossfade", default_duration: float | None = None) -> list[TransitionDecision]:
    ordered = list(scenes)
    profile_default = canonical_transition(default_transition) or "crossfade"
    decisions: list[TransitionDecision] = []
    decorative_run = 0
    previous_type: CanonicalTransitionType | None = None
    for left, right in zip(ordered, ordered[1:]):
        explicit = _explicit_boundary(left, right)
        transition, reason = (explicit, "explicit scene transition") if explicit else _semantic_choice(left, right)
        if transition == "matched_motion" and not _matched_motion_has_data(left, right):
            transition = _matched_motion_fallback(left, right)
            reason = f"matched_motion fallback: insufficient aligned motion data -> {transition}"
        next_run = decorative_run + 1 if transition in DECORATIVE_TRANSITIONS else 0
        if transition == previous_type and next_run > MAX_DECORATIVE_RUN:
            transition = "crossfade" if profile_default != "hard_cut" else "hard_cut"
            reason = f"repeat limiter after {MAX_DECORATIVE_RUN} decorative transitions"
            next_run = 0
        right_transition = right.get("transition") or {}
        left_transition = left.get("transition") or {}
        configured_duration = right_transition.get("in_duration_seconds")
        if configured_duration is None:
            configured_duration = left_transition.get("out_duration_seconds")
        if configured_duration is None:
            configured_duration = right_transition.get("duration_seconds")
        if configured_duration is None:
            configured_duration = left_transition.get("duration_seconds")
        duration = DEFAULT_DURATIONS[transition]
        if configured_duration is not None:
            duration = max(0.0, float(configured_duration))
        elif default_duration is not None and transition != "hard_cut":
            duration = max(0.0, float(default_duration))
        if transition == "hard_cut":
            duration = 0.0
        direction = None
        if transition in {"directional_push", "matched_motion"}:
            right_transition = right.get("transition") or {}
            left_transition = left.get("transition") or {}
            explicit_direction = right_transition.get("in_direction") or left_transition.get("out_direction")
            direction = str(explicit_direction).lower() if explicit_direction in RENDER_DIRECTIONS else _motion_direction(right) or _motion_direction(left)
        decisions.append(TransitionDecision(str(left["id"]), str(right["id"]), transition, round(duration, 3), reason, direction))
        previous_type, decorative_run = transition, next_run
    return decisions
