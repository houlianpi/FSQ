# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from fsq_agent.config import (
    AndroidWorkspaceTarget,
    MacOSWorkspaceTarget,
    WorkspaceConfig,
    create_workspace,
    list_workspace_registry,
    load_registered_workspace,
    update_workspace,
)
from fsq_agent.config._workspace import load_workspace_config
from fsq_agent.models import ConfigurationError


def _android_workspace(parent: Path, name: str = "checkout") -> WorkspaceConfig:
    return WorkspaceConfig(
        version=1,
        name=name,
        root_path=(parent / name).resolve(),
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
        env={"TEST_PASSWORD": "initial-secret"},
    )


def _revision(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def test_create_workspace_commits_minimal_layout_and_registry(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    candidate = _android_workspace(parent)

    created = create_workspace(parent_path=parent, config=candidate, user_config_root=user_root)

    config_path = candidate.root_path / ".fsq" / "config.yaml"
    assert created == candidate
    assert config_path.is_file()
    assert (candidate.root_path / "cases").is_dir()
    assert (candidate.root_path / "knowledge" / "project.md").read_text(encoding="utf-8") == ""
    assert yaml.safe_load(config_path.read_text(encoding="utf-8"))["env"] == {
        "TEST_PASSWORD": "initial-secret"
    }
    assert [(entry.name, entry.config_path) for entry in list_workspace_registry(user_root)] == [
        ("checkout", config_path.resolve())
    ]
    assert load_registered_workspace("CHECKOUT", user_root) == candidate


def test_update_workspace_requires_current_revision_and_preserves_identity(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    candidate = _android_workspace(parent)
    create_workspace(parent_path=parent, config=candidate, user_config_root=user_root)
    config_path = candidate.root_path / ".fsq" / "config.yaml"
    original_revision = _revision(config_path)

    updated = update_workspace(
        name="checkout",
        target={"app_id": "com.example.changed"},
        env={"TEST_PASSWORD": "replacement-secret"},
        expected_revision=original_revision,
        user_config_root=user_root,
    )

    assert updated.name == candidate.name
    assert updated.root_path == candidate.root_path
    assert updated.platform == candidate.platform
    assert updated.target == AndroidWorkspaceTarget(app_id="com.example.changed")
    assert updated.env == {"TEST_PASSWORD": "replacement-secret"}
    with pytest.raises(ConfigurationError, match="changed since it was loaded"):
        update_workspace(
            name="checkout",
            target={"app_id": "com.example.stale"},
            env={},
            expected_revision=original_revision,
            user_config_root=user_root,
        )
    assert load_registered_workspace("checkout", user_root) == updated


def test_create_workspace_rejects_non_empty_final_root_without_changes(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    final_root = parent / "checkout"
    final_root.mkdir(parents=True)
    user_file = final_root / "keep.txt"
    user_file.write_text("keep", encoding="utf-8")
    user_root = tmp_path / "user"

    with pytest.raises(ConfigurationError, match="empty"):
        create_workspace(parent_path=parent, config=_android_workspace(parent), user_config_root=user_root)

    assert user_file.read_text(encoding="utf-8") == "keep"
    assert list_workspace_registry(user_root) == []


def test_create_workspace_rejects_symlinked_final_root_without_changes(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    final_root = parent / "checkout"
    try:
        final_root.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")
    user_root = tmp_path / "user"

    with pytest.raises(ConfigurationError, match="symbolic link"):
        create_workspace(parent_path=parent, config=_android_workspace(parent), user_config_root=user_root)

    assert list(outside.iterdir()) == []
    assert list_workspace_registry(user_root) == []


@pytest.mark.parametrize("linked_part", ["metadata", "config"])
def test_load_workspace_config_rejects_symlinked_metadata(tmp_path: Path, linked_part: str) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    config = _android_workspace(tmp_path, name="workspace")
    source = yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)
    if linked_part == "metadata":
        (outside / "config.yaml").write_text(source, encoding="utf-8")
        link = root / ".fsq"
        target = outside
        target_is_directory = True
    else:
        metadata = root / ".fsq"
        metadata.mkdir()
        target = outside / "config.yaml"
        target.write_text(source, encoding="utf-8")
        link = metadata / "config.yaml"
        target_is_directory = False
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    with pytest.raises(ConfigurationError, match="not an FSQ workspace"):
        load_workspace_config(root)


def test_load_workspace_config_rejects_symlinked_workspace_root(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    metadata = root / ".fsq"
    metadata.mkdir(parents=True)
    config = _android_workspace(tmp_path, name="workspace")
    (metadata / "config.yaml").write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    link = tmp_path / "workspace-link"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    with pytest.raises(ConfigurationError, match="symbolic link"):
        load_workspace_config(link)


def test_workspace_validation_errors_do_not_include_secret_input_values(tmp_path: Path) -> None:
    marker = "never-echo-this-secret"
    root = tmp_path / "workspace"
    config_dir = root / ".fsq"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "name": "workspace",
                "root_path": str(root),
                "platform": "android",
                "target": {"app_id": "com.example.app"},
                "env": {"API_KEY": [marker]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError) as load_error:
        load_workspace_config(root)

    assert marker not in json.dumps(load_error.value.context)

    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    candidate = _android_workspace(parent)
    create_workspace(parent_path=parent, config=candidate, user_config_root=user_root)
    with pytest.raises(ConfigurationError) as update_error:
        update_workspace(
            name=candidate.name,
            target={"app_id": "com.example.app"},
            env={"API_KEY": [marker]},  # type: ignore[dict-item]
            expected_revision=_revision(candidate.root_path / ".fsq" / "config.yaml"),
            user_config_root=user_root,
        )

    assert marker not in json.dumps(update_error.value.context)


def test_create_workspace_rejects_macos_app_path_that_is_not_bundle_or_executable(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    invalid_app_path = tmp_path / "ordinary-directory"
    invalid_app_path.mkdir()
    candidate = WorkspaceConfig(
        version=1,
        name="checkout",
        root_path=(parent / "checkout").resolve(),
        platform="macos",
        target=MacOSWorkspaceTarget(app_path=invalid_app_path),
    )

    with pytest.raises(ConfigurationError, match="app bundle or executable"):
        create_workspace(parent_path=parent, config=candidate, user_config_root=tmp_path / "user")

    app_bundle = tmp_path / "Checkout.app"
    app_bundle.mkdir()
    valid_candidate = candidate.model_copy(update={"target": MacOSWorkspaceTarget(app_path=app_bundle)})

    assert create_workspace(
        parent_path=parent,
        config=valid_candidate,
        user_config_root=tmp_path / "valid-user",
    ) == valid_candidate