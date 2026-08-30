"""Best-effort export of completed renders to a user-facing preview folder."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Mapping


PREVIEW_MODES = {"PHOTO", "VIDEO", "HYBRID"}
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


def sanitize_windows_filename(value: str, *, fallback: str = "project") -> str:
    """Return a stable Windows-safe filename component."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = _WINDOWS_INVALID.sub("-", normalized)
    normalized = _WHITESPACE.sub("-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip(" .-")
    if not normalized:
        normalized = fallback
    if normalized.upper() in _WINDOWS_RESERVED:
        normalized = f"_{normalized}"
    return normalized[:80].rstrip(" .") or fallback


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _diagnostic(
    *,
    status: str,
    mode: str,
    source: Path,
    destination: Path | None,
    copied: bool,
    warning: str | None,
    source_preserved: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "mode": mode,
        "source_path": str(source),
        "destination_path": str(destination) if destination else None,
        "copied": copied,
        "warning": warning,
        "source_preserved": source_preserved,
    }


def _warning(
    message: str,
    *,
    mode: str,
    source: Path,
    destination: Path | None = None,
) -> dict[str, Any]:
    return _diagnostic(
        status="warning",
        mode=mode,
        source=source,
        destination=destination,
        copied=False,
        warning=message,
        source_preserved=source.exists(),
    )


def _render_filename(
    profile: Mapping[str, Any],
    *,
    project_name: str,
    mode: str,
    source: Path,
    now: datetime,
) -> str:
    template = str(
        profile.get("filename_template")
        or "{project}-{mode}-{timestamp}.{ext}"
    )
    timestamp_format = str(profile.get("timestamp_format") or "%Y%m%d-%H%M%S")
    filename = template.format(
        project=sanitize_windows_filename(project_name),
        mode=mode,
        timestamp=now.strftime(timestamp_format),
        ext=source.suffix.lstrip(".") or "mp4",
    )
    if Path(filename).name != filename or filename in {"", ".", ".."}:
        raise ValueError("filename_template must produce a filename, not a path")
    return sanitize_windows_filename(Path(filename).stem) + Path(filename).suffix


def _reserve_destination(
    destination: Path, on_conflict: str
) -> tuple[Path, BinaryIO]:
    candidate = destination
    counter = 2
    while True:
        try:
            return candidate, candidate.open("xb")
        except FileExistsError:
            if on_conflict != "increment":
                raise
            candidate = destination.with_name(
                f"{destination.stem}-{counter:02d}{destination.suffix}"
            )
            counter += 1


def export_preview(
    source_path: str | Path,
    profile: Mapping[str, Any] | None,
    *,
    project_name: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Copy a successful render according to a declarative preview profile."""

    source = Path(source_path).resolve()
    profile = profile or {}
    mode = str(profile.get("mode") or "").upper()

    if not profile.get("enabled", False):
        return _diagnostic(
            status="disabled",
            mode=mode,
            source=source,
            destination=None,
            copied=False,
            warning=None,
            source_preserved=source.exists(),
        )

    destination: Path | None = None
    destination_owned = False
    reservation: BinaryIO | None = None
    temporary: Path | None = None
    try:
        if mode not in PREVIEW_MODES:
            raise ValueError(f"Unsupported preview mode: {mode!r}")
        if not source.is_file():
            raise FileNotFoundError(f"Preview source does not exist: {source}")
        source_size = source.stat().st_size
        if source_size <= 0:
            raise ValueError(f"Preview source is empty: {source}")

        root_value = str(profile.get("root") or "").strip()
        if not root_value:
            raise ValueError("Preview root must be set when preview export is enabled")
        destination_dir = Path(root_value).expanduser() / mode
        if not destination_dir.is_dir():
            raise FileNotFoundError(
                f"Preview destination is unavailable: {destination_dir}"
            )

        filename = _render_filename(
            profile,
            project_name=project_name,
            mode=mode,
            source=source,
            now=now or datetime.now(),
        )
        destination, reservation = _reserve_destination(
            destination_dir / filename,
            str(profile.get("on_conflict") or "increment"),
        )
        reservation.close()
        reservation = None
        destination_owned = True

        temporary = destination_dir / f".{destination.name}.{uuid.uuid4().hex}.tmp"
        shutil.copyfile(source, temporary)

        source_checksum = _sha256(source)
        if temporary.stat().st_size != source_size:
            raise OSError("Preview temporary copy size does not match source")
        if _sha256(temporary) != source_checksum:
            raise OSError("Preview temporary copy checksum does not match source")

        # Atomically replace only the zero-byte reservation created above.
        os.replace(temporary, destination)
        temporary = None

        if destination.stat().st_size != source_size:
            raise OSError("Preview destination size does not match source")
        if _sha256(destination) != source_checksum:
            raise OSError("Preview destination checksum does not match source")
        if not source.is_file() or source.stat().st_size != source_size:
            raise OSError("Primary render changed during preview export")

        return _diagnostic(
            status="copied",
            mode=mode,
            source=source,
            destination=destination,
            copied=True,
            warning=None,
            source_preserved=True,
        )
    except Exception as exc:
        if reservation is not None:
            reservation.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if destination_owned and destination is not None and destination.exists():
            destination.unlink(missing_ok=True)
        return _warning(
            str(exc),
            mode=mode,
            source=source,
            destination=destination,
        )
