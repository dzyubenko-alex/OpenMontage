from pathlib import Path

import pytest

from lib.config_model import ObjectMapping, ObjectWorkspaceConfig, OpenMontageConfig
from lib.object_workspace import (
    ObjectWorkspaceError,
    load_object_mapping,
    resolve_openmontage_output,
    validate_canonical_root_name,
    validate_object_workspace,
)


def _config() -> OpenMontageConfig:
    return OpenMontageConfig(object_workspace=ObjectWorkspaceConfig())


def test_global_config_records_generic_object_workspace_standard() -> None:
    workspace = OpenMontageConfig.load().object_workspace
    assert workspace.standard_id == "OBJECT_WORKSPACE_STANDARD_V1"
    assert workspace.allow_automatic_root_creation is False
    assert workspace.require_explicit_existing_root is True
    assert workspace.allow_legacy_root is True
    assert "legacy_objects" not in workspace.model_dump()


@pytest.mark.parametrize("name", ["D-001_Example_10", "A1_Example_10"])
def test_canonical_names_are_accepted(name: str) -> None:
    validate_canonical_root_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "Example_10",
        "D-001 Example 10",
        "D-001_181m2",
        "D-001_Example_10$",
        "D-001_Example:10",
    ],
)
def test_noncanonical_names_are_rejected(name: str) -> None:
    with pytest.raises(ObjectWorkspaceError):
        validate_canonical_root_name(name)


def test_missing_root_stops_without_creating_it(tmp_path: Path) -> None:
    missing = tmp_path / "D-003_Example_1"
    with pytest.raises(ObjectWorkspaceError, match="automatic creation is forbidden"):
        validate_object_workspace(missing, config=_config())
    assert not missing.exists()


def test_legacy_root_requires_and_accepts_exact_mapping(tmp_path: Path) -> None:
    legacy = tmp_path / "historical root"
    legacy.mkdir()
    with pytest.raises(ObjectWorkspaceError):
        validate_object_workspace(legacy, config=_config())

    mapping = ObjectMapping(
        object_code="T-001",
        project_id="t001-example10",
        canonical_root_name="T-001_Example_10",
        actual_legacy_root=str(legacy),
    )
    assert validate_object_workspace(
        legacy, config=_config(), mapping=mapping
    ).is_legacy is True


def test_object_local_mapping_is_loaded_from_workspace(tmp_path: Path) -> None:
    legacy = tmp_path / "historical root"
    mapping_dir = legacy / "06_OpenMontage" / "01_Project"
    mapping_dir.mkdir(parents=True)
    mapping = ObjectMapping(
        object_code="T-001",
        project_id="t001-example10",
        canonical_root_name="T-001_Example_10",
        actual_legacy_root=str(legacy),
    )
    (mapping_dir / "OBJECT_MAPPING.json").write_text(
        mapping.model_dump_json(), encoding="utf-8"
    )
    assert load_object_mapping(legacy, config=_config()) == mapping
    assert validate_object_workspace(legacy, config=_config()).is_legacy is True


def test_mismatched_object_mapping_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "historical root"
    root.mkdir()
    mapping = ObjectMapping(
        object_code="T-001",
        project_id="t001-example10",
        canonical_root_name="T-001_Example_10",
        actual_legacy_root=str(tmp_path / "different root"),
    )
    with pytest.raises(ObjectWorkspaceError, match="does not match"):
        validate_object_workspace(root, config=_config(), mapping=mapping)


def test_output_resolution_is_scoped_to_openmontage(tmp_path: Path) -> None:
    root = tmp_path / "D-003_Test_1"
    root.mkdir()
    output = resolve_openmontage_output(
        root, "03_Output", "16x9", "final.mp4", config=_config()
    )
    assert output == root / "06_OpenMontage" / "03_Output" / "16x9" / "final.mp4"
    with pytest.raises(ObjectWorkspaceError, match="escapes"):
        resolve_openmontage_output(root, "..", "outside.mp4", config=_config())
