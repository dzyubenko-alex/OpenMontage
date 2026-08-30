from __future__ import annotations

from pathlib import Path

import pytest

from tools.base_tool import ToolResult
from tools.video.video_compose import VideoCompose


def _preview(root: Path, mode: str, *, failure_policy: str = "warn") -> dict:
    return {
        "enabled": True,
        "root": str(root),
        "mode": mode,
        "filename_template": "{project}-{mode}-{timestamp}.{ext}",
        "timestamp_format": "%Y%m%d-%H%M%S",
        "on_conflict": "increment",
        "failure_policy": failure_policy,
    }


@pytest.mark.parametrize("mode", ["PHOTO", "VIDEO", "HYBRID"])
def test_all_modes_use_the_same_post_render_exporter(
    tmp_path: Path, monkeypatch, mode: str
) -> None:
    source = tmp_path / "project" / "renders" / "final.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(f"{mode}-render".encode())
    root = tmp_path / "windows-preview"
    (root / mode).mkdir(parents=True)

    tool = VideoCompose()
    monkeypatch.setattr(
        tool,
        "_render",
        lambda inputs: ToolResult(
            success=True,
            data={"output": str(source)},
            artifacts=[str(source)],
        ),
    )

    result = tool.execute(
        {
            "operation": "render",
            "project_name": f"My {mode} Project",
            "edit_decisions": {
                "profiles": {"export": {"preview": _preview(root, mode)}}
            },
        }
    )

    diagnostic = result.data["preview_export"]
    assert result.success is True
    assert diagnostic["status"] == "copied"
    assert diagnostic["mode"] == mode
    assert diagnostic["source_path"] == str(source.resolve())
    assert Path(diagnostic["destination_path"]).parent == root / mode
    assert diagnostic["copied"] is True
    assert diagnostic["warning"] is None
    assert diagnostic["source_preserved"] is True
    assert source.exists()


def test_unavailable_windows_folder_warns_without_failing_render(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "project" / "renders" / "final.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"successful-primary-render")
    tool = VideoCompose()
    monkeypatch.setattr(
        tool,
        "_render",
        lambda inputs: ToolResult(
            success=True,
            data={"output": str(source)},
            artifacts=[str(source)],
        ),
    )

    result = tool.execute(
        {
            "operation": "render",
            "project_name": "Unavailable Preview",
            "edit_decisions": {
                "profiles": {
                    "export": {
                        "preview": _preview(
                            tmp_path / "missing-windows-root",
                            "PHOTO",
                            failure_policy="warn",
                        )
                    }
                }
            },
        }
    )

    diagnostic = result.data["preview_export"]
    assert result.success is True
    assert result.error is None
    assert diagnostic["status"] == "warning"
    assert diagnostic["mode"] == "PHOTO"
    assert diagnostic["destination_path"] is None
    assert diagnostic["copied"] is False
    assert "unavailable" in diagnostic["warning"]
    assert diagnostic["source_preserved"] is True
    assert source.read_bytes() == b"successful-primary-render"
