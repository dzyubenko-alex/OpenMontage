from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from lib.preview_export import export_preview, sanitize_windows_filename


def _profile(root: Path, mode: str = "PHOTO") -> dict:
    return {
        "enabled": True,
        "root": str(root),
        "mode": mode,
        "filename_template": "{project}-{mode}-{timestamp}.{ext}",
        "timestamp_format": "%Y%m%d-%H%M%S",
        "on_conflict": "increment",
        "failure_policy": "warn",
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('  My: Project / "Preview"?  ', "My-Project-Preview"),
        ("CON", "_CON"),
        ("...", "project"),
        ("Проект 01", "Проект-01"),
    ],
)
def test_sanitize_windows_filename(raw: str, expected: str) -> None:
    assert sanitize_windows_filename(raw) == expected


def test_copy_verifies_content_and_preserves_primary_render(tmp_path: Path) -> None:
    source = tmp_path / "primary.mp4"
    payload = b"rendered-video-content"
    source.write_bytes(payload)
    root = tmp_path / "preview"
    (root / "PHOTO").mkdir(parents=True)

    result = export_preview(
        source,
        _profile(root),
        project_name='Demo: Project / "One"',
        now=datetime(2026, 8, 30, 15, 4, 5),
    )

    destination = Path(result["destination_path"])
    assert result == {
        "status": "copied",
        "mode": "PHOTO",
        "source_path": str(source.resolve()),
        "destination_path": str(destination),
        "copied": True,
        "warning": None,
        "source_preserved": True,
    }
    assert destination.name == "Demo-Project-One-PHOTO-20260830-150405.mp4"
    assert source.read_bytes() == payload
    assert destination.stat().st_size == source.stat().st_size
    assert hashlib.sha256(destination.read_bytes()).digest() == hashlib.sha256(payload).digest()
    assert not list((root / "PHOTO").glob("*.tmp"))


def test_collision_increment_never_overwrites_existing_preview(tmp_path: Path) -> None:
    source = tmp_path / "primary.mp4"
    source.write_bytes(b"new-render")
    root = tmp_path / "preview"
    destination_dir = root / "VIDEO"
    destination_dir.mkdir(parents=True)
    existing = destination_dir / "demo-VIDEO-20260830-150405.mp4"
    existing.write_bytes(b"existing-preview")

    result = export_preview(
        source,
        _profile(root, "VIDEO"),
        project_name="demo",
        now=datetime(2026, 8, 30, 15, 4, 5),
    )

    assert existing.read_bytes() == b"existing-preview"
    assert Path(result["destination_path"]).name == "demo-VIDEO-20260830-150405-02.mp4"
    assert Path(result["destination_path"]).read_bytes() == b"new-render"


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_source_must_exist_and_be_nonempty(tmp_path: Path, kind: str) -> None:
    source = tmp_path / "primary.mp4"
    if kind == "empty":
        source.touch()
    root = tmp_path / "preview"
    (root / "HYBRID").mkdir(parents=True)

    result = export_preview(source, _profile(root, "HYBRID"), project_name="demo")

    assert result["status"] == "warning"
    assert result["copied"] is False
    assert result["destination_path"] is None
    assert ("does not exist" if kind == "missing" else "empty") in result["warning"]


def test_disabled_profile_is_non_mutating(tmp_path: Path) -> None:
    source = tmp_path / "primary.mp4"
    source.write_bytes(b"render")

    result = export_preview(
        source,
        {"enabled": False, "mode": "PHOTO"},
        project_name="demo",
    )

    assert result["status"] == "disabled"
    assert result["copied"] is False
    assert result["source_preserved"] is True
