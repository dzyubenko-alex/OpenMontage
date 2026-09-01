"""Validation for external object workspaces.

This module never creates an object root. Callers must receive OBJECT_ROOT
explicitly and validate it before writing any derived OpenMontage artifact.
Object-specific legacy mappings stay inside the object workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from lib.config_model import ObjectMapping, OpenMontageConfig


class ObjectWorkspaceError(ValueError):
    """Raised when an object workspace is unsafe or non-canonical."""


@dataclass(frozen=True)
class WorkspaceValidation:
    object_root: Path
    openmontage_root: Path
    is_legacy: bool
    missing_directories: tuple[str, ...]


VOLATILE_ROOT_TOKEN_RE = re.compile(
    r"(?:\d+(?:[.,]\d+)?(?:м2|m2|sqm)|"
    r"(?:тыс|млн|руб|usd|eur)|"
    r"(?:реклама|advertising)|"
    r"(?:19|20)\d{2})",
    re.IGNORECASE,
)


def validate_canonical_root_name(name: str) -> None:
    """Validate <OBJECT_CODE>_<SHORT_ADDRESS> without volatile attributes."""
    if "_" not in name:
        raise ObjectWorkspaceError(
            "Canonical object root must match <OBJECT_CODE>_<SHORT_ADDRESS>"
        )
    object_code, short_address = name.split("_", 1)
    if not object_code or not short_address:
        raise ObjectWorkspaceError("OBJECT_CODE and SHORT_ADDRESS are required")
    if not all(char.isalnum() or char in "-_" for char in name):
        raise ObjectWorkspaceError(
            "Object root may contain only letters, digits, hyphen, and underscore"
        )
    if VOLATILE_ROOT_TOKEN_RE.search(short_address):
        raise ObjectWorkspaceError(
            "Object root must not contain area, price, date, or advertising attributes"
        )
    if not re.fullmatch(
        r"(?=.*[0-9])[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*",
        object_code,
    ):
        raise ObjectWorkspaceError("OBJECT_CODE is invalid")


def _portable_path(value: str | Path) -> str:
    normalized = str(value).replace("\\", "/").rstrip("/")
    windows_drive = re.fullmatch(r"([A-Za-z]):/(.*)", normalized)
    if windows_drive:
        normalized = f"/mnt/{windows_drive.group(1).lower()}/{windows_drive.group(2)}"
    return normalized.casefold()


def load_object_mapping(
    object_root: str | Path,
    *,
    config: OpenMontageConfig | None = None,
) -> ObjectMapping | None:
    """Load an object-specific mapping from its object-local project directory."""
    root = Path(object_root).expanduser()
    settings = config or OpenMontageConfig.load()
    mapping_path = (
        root
        / settings.object_workspace.openmontage_directory
        / "01_Project"
        / "OBJECT_MAPPING.json"
    )
    if not mapping_path.is_file():
        return None
    try:
        return ObjectMapping.model_validate_json(mapping_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ObjectWorkspaceError(f"Invalid object-local mapping: {mapping_path}") from exc


def validate_object_workspace(
    object_root: str | Path,
    *,
    config: OpenMontageConfig | None = None,
    mapping: ObjectMapping | None = None,
    require_standard_tree: bool = False,
) -> WorkspaceValidation:
    """Validate an explicit root without creating it.

    Canonical roots are accepted directly. Historical roots require an exact
    object-local mapping, supplied explicitly or loaded from OBJECT_MAPPING.json.
    """
    if object_root is None or not str(object_root).strip():
        raise ObjectWorkspaceError("OBJECT_ROOT must be provided explicitly")
    root = Path(object_root).expanduser()
    if not root.is_dir():
        raise ObjectWorkspaceError(
            f"OBJECT_ROOT does not exist; automatic creation is forbidden: {root}"
        )

    settings = config or OpenMontageConfig.load()
    workspace = settings.object_workspace
    object_mapping = mapping or load_object_mapping(root, config=settings)
    is_legacy = object_mapping is not None and (
        _portable_path(object_mapping.actual_legacy_root) == _portable_path(root)
    )
    if object_mapping is not None and not is_legacy:
        raise ObjectWorkspaceError("Object mapping does not match OBJECT_ROOT")
    if is_legacy and not workspace.allow_legacy_root:
        raise ObjectWorkspaceError("Legacy object roots are disabled by global policy")
    if not is_legacy:
        validate_canonical_root_name(root.name)

    missing = tuple(
        relative
        for relative in workspace.required_directories
        if not (root / Path(relative)).is_dir()
    )
    if require_standard_tree and missing:
        raise ObjectWorkspaceError(
            "Object workspace is incomplete: " + ", ".join(missing)
        )

    return WorkspaceValidation(
        object_root=root,
        openmontage_root=root / workspace.openmontage_directory,
        is_legacy=is_legacy,
        missing_directories=missing,
    )


def resolve_openmontage_output(
    object_root: str | Path,
    *relative_parts: str,
    config: OpenMontageConfig | None = None,
    mapping: ObjectMapping | None = None,
) -> Path:
    """Return a safe path under 06_OpenMontage after validating OBJECT_ROOT."""
    validation = validate_object_workspace(
        object_root, config=config, mapping=mapping
    )
    base = validation.openmontage_root.resolve(strict=False)
    candidate = base.joinpath(*relative_parts).resolve(strict=False)
    if candidate != base and base not in candidate.parents:
        raise ObjectWorkspaceError("Output path escapes 06_OpenMontage")
    return candidate
