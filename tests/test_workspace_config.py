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
    WorkspaceInitResult,
    WorkspacePlatformCreateInput,
    add_workspace_platform,
    create_workspace,
    inspect_registered_workspace,
    list_workspace_registry,
    load_registered_workspace,
    update_workspace_platform,
)
from fsq_agent.config._user_provider import _register_workspace
from fsq_agent.config._workspace import load_workspace_config
from fsq_agent.models import ConfigurationError, WorkspaceRegistryEntry


def _android_workspace(parent: Path, name: str = "checkout") -> WorkspaceConfig:
    return WorkspaceConfig(
        version=2,
        name=name,
        root_path=(parent / name).resolve(),
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
        env={"TEST_PASSWORD": "initial-secret"},
    )


def _create_from_config(selected_path: Path, config: WorkspaceConfig, user_config_root: Path):
    if next(selected_path.iterdir(), None) is None:
        (selected_path / ".existing").write_text("keep", encoding="utf-8")
    return create_workspace(
        selected_path=selected_path,
        name=config.name,
        platforms=[
            WorkspacePlatformCreateInput(
                platform=config.platform,
                target=config.target,
                env=config.env,
            )
        ],
        user_config_root=user_config_root,
    )


def _revision(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def test_create_workspace_adopts_empty_selected_directory_and_loads_config(tmp_path: Path) -> None:
    selected = tmp_path / "workspace"
    selected.mkdir()
    user_root = tmp_path / "user"
    platform = WorkspacePlatformCreateInput(
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
        env={"TEST_PASSWORD": "initial-secret"},
    )

    created = create_workspace(
        selected_path=selected,
        name="checkout",
        platforms=[platform],
        user_config_root=user_root,
    )

    config_path = selected / ".fsq" / "config" / "config.android.yaml"
    assert created.status == "available"
    assert created.root_path == selected.resolve()
    assert [status.platform for status in created.platforms] == ["android"]
    assert config_path.is_file()
    assert (selected / "cases" / "android").is_dir()
    assert (selected / ".fsq" / "runs" / "android").is_dir()
    assert (selected / "knowledge" / "android" / "project.md").read_text(encoding="utf-8") == ""
    assert yaml.safe_load(config_path.read_text(encoding="utf-8"))["env"] == {"TEST_PASSWORD": "initial-secret"}
    assert [(entry.name, entry.root_path) for entry in list_workspace_registry(user_root)] == [("checkout", selected.resolve())]
    assert load_registered_workspace("CHECKOUT", "android", user_root).root_path == selected.resolve()
    loaded, loaded_root, loaded_path = load_workspace_config(selected, "android")
    assert loaded.name == "checkout"
    assert loaded.root_path == selected.resolve()
    assert loaded_root == selected.resolve()
    assert loaded_path == config_path


def test_workspace_init_result_normalizes_canonical_identity(tmp_path: Path) -> None:
    lexical_root = tmp_path / "nested" / ".." / "checkout"

    result = WorkspaceInitResult(
        status="unchanged",
        name=" checkout ",
        root_path=lexical_root,
        platform="android",
    )

    assert result.name == "checkout"
    assert result.root_path == (tmp_path / "checkout").resolve()


def test_update_workspace_platform_requires_current_revision_and_preserves_identity(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    candidate = _android_workspace(parent)
    _create_from_config(parent, candidate, user_root)
    config_path = candidate.root_path / ".fsq" / "config" / "config.android.yaml"
    original_revision = _revision(config_path)

    updated = update_workspace_platform(
        name="checkout",
        platform="android",
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
        update_workspace_platform(
            name="checkout",
            platform="android",
            target={"app_id": "com.example.stale"},
            env={},
            expected_revision=original_revision,
            user_config_root=user_root,
        )
    assert load_registered_workspace("checkout", "android", user_root) == updated


def test_add_workspace_platform_preserves_existing_platform_content(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    android = _android_workspace(parent)
    _create_from_config(parent, android, user_root)
    existing_project = android.root_path / "knowledge" / "macos" / "project.md"
    existing_project.parent.mkdir(parents=True)
    existing_project.write_text("keep", encoding="utf-8")

    added = add_workspace_platform(
        name="checkout",
        platform="macos",
        target={"bundle_id": "com.example.checkout"},
        env={"TEST_ACCOUNT": "local"},
        user_config_root=user_root,
    )

    assert added.version == 2
    assert added.platform == "macos"
    assert existing_project.read_text(encoding="utf-8") == "keep"
    assert (android.root_path / "cases" / "macos").is_dir()
    assert (android.root_path / ".fsq" / "runs" / "macos").is_dir()
    assert [status.platform for status in inspect_registered_workspace("checkout", user_root).platforms] == [
        "android",
        "macos",
    ]

    with pytest.raises(ConfigurationError, match="already exists"):
        add_workspace_platform(
            name="checkout",
            platform="macos",
            target={"bundle_id": "com.example.changed"},
            env={},
            user_config_root=user_root,
        )


def test_inspect_registered_workspace_reports_invalid_sibling_as_partial(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    candidate = _android_workspace(parent)
    _create_from_config(parent, candidate, user_root)
    invalid_path = candidate.root_path / ".fsq" / "config" / "config.web.yaml"
    invalid_path.write_text("version: 2\nname: [invalid]\n", encoding="utf-8")

    status = inspect_registered_workspace("checkout", user_root)

    assert status.status == "partial"
    assert [(item.platform, item.status) for item in status.platforms] == [
        ("android", "available"),
        ("web", "unavailable"),
    ]
    assert load_registered_workspace("checkout", "android", user_root) == candidate
    with pytest.raises(ConfigurationError, match="unavailable"):
        load_registered_workspace("checkout", "web", user_root)


@pytest.mark.parametrize("entry_kind", ["hidden_file", "child_directory", "symlink"])
def test_create_workspace_treats_all_selected_directory_entries_as_non_empty(
    tmp_path: Path,
    entry_kind: str,
) -> None:
    selected = tmp_path / "projects"
    selected.mkdir()
    if entry_kind == "hidden_file":
        (selected / ".hidden").write_text("keep", encoding="utf-8")
    elif entry_kind == "child_directory":
        (selected / "existing").mkdir()
    else:
        link_target = tmp_path / "link-target"
        link_target.mkdir()
        try:
            (selected / "existing-link").symlink_to(link_target, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"Symlink creation is unavailable: {exc}")
    platform = WorkspacePlatformCreateInput(
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
    )

    created = create_workspace(
        selected_path=selected,
        name="checkout",
        platforms=[platform],
        user_config_root=tmp_path / "user",
    )

    assert created.root_path == (selected / "checkout").resolve()
    assert (selected / "checkout" / ".fsq" / "config" / "config.android.yaml").is_file()


@pytest.mark.parametrize(
    "conflict_kind",
    ["file", "empty_directory", "non_empty_directory", "valid_symlink", "broken_symlink"],
)
def test_create_workspace_rejects_every_existing_derived_child(
    tmp_path: Path,
    conflict_kind: str,
) -> None:
    selected = tmp_path / "projects"
    selected.mkdir()
    final_root = selected / "checkout"
    if conflict_kind == "file":
        final_root.write_text("keep", encoding="utf-8")
    elif conflict_kind == "empty_directory":
        final_root.mkdir()
    elif conflict_kind == "non_empty_directory":
        final_root.mkdir()
        (final_root / "keep.txt").write_text("keep", encoding="utf-8")
    else:
        target = tmp_path / ("outside" if conflict_kind == "valid_symlink" else "missing")
        if conflict_kind == "valid_symlink":
            target.mkdir()
        try:
            final_root.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"Symlink creation is unavailable: {exc}")
    platform = WorkspacePlatformCreateInput(
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
    )

    with pytest.raises(ConfigurationError, match="already exists"):
        create_workspace(
            selected_path=selected,
            name="checkout",
            platforms=[platform],
            user_config_root=tmp_path / "user",
        )

    assert final_root.exists() or final_root.is_symlink()
    assert list_workspace_registry(tmp_path / "user") == []
    if conflict_kind == "non_empty_directory":
        assert (final_root / "keep.txt").read_text(encoding="utf-8") == "keep"
    if conflict_kind == "valid_symlink":
        assert list(target.iterdir()) == []


def test_create_workspace_rejects_duplicate_registered_name_independently(tmp_path: Path) -> None:
    selected = tmp_path / "selected"
    selected.mkdir()
    registered_root = tmp_path / "registered"
    registered_root.mkdir()
    user_root = tmp_path / "user"
    _register_workspace(WorkspaceRegistryEntry(name="checkout", root_path=registered_root), user_root)
    platform = WorkspacePlatformCreateInput(
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
    )

    with pytest.raises(ConfigurationError, match="name is already registered"):
        create_workspace(
            selected_path=selected,
            name="CHECKOUT",
            platforms=[platform],
            user_config_root=user_root,
        )

    assert list(selected.iterdir()) == []


def test_create_workspace_rejects_duplicate_registered_root_independently(tmp_path: Path) -> None:
    selected = tmp_path / "selected"
    selected.mkdir()
    user_root = tmp_path / "user"
    _register_workspace(WorkspaceRegistryEntry(name="existing", root_path=selected), user_root)
    platform = WorkspacePlatformCreateInput(
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
    )

    with pytest.raises(ConfigurationError, match="path is already registered"):
        create_workspace(
            selected_path=selected,
            name="checkout",
            platforms=[platform],
            user_config_root=user_root,
        )

    assert list(selected.iterdir()) == []


def test_create_workspace_rollback_preserves_user_owned_empty_selected_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "selected"
    selected.mkdir()
    user_root = tmp_path / "user"
    platform = WorkspacePlatformCreateInput(
        platform="android",
        target=AndroidWorkspaceTarget(app_id="com.example.checkout"),
    )

    def fail_write(path: Path, content: bytes) -> None:
        if path.name == "config.android.yaml":
            raise OSError("injected write failure")
        path.write_bytes(content)

    monkeypatch.setattr("fsq_agent.config._workspace._atomic_write", fail_write)

    with pytest.raises(OSError, match="injected write failure"):
        create_workspace(
            selected_path=selected,
            name="checkout",
            platforms=[platform],
            user_config_root=user_root,
        )

    assert selected.is_dir()
    assert list(selected.iterdir()) == []
    assert list_workspace_registry(user_root) == []


def test_create_workspace_rollback_removes_created_child_and_preserves_parent_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "projects"
    final_root = parent / "checkout"
    parent.mkdir()
    user_file = parent / "keep.txt"
    user_file.write_text("keep", encoding="utf-8")
    user_root = tmp_path / "user"
    candidate = _android_workspace(parent)

    def fail_write(path: Path, content: bytes) -> None:
        if path.name == "config.android.yaml":
            raise OSError("injected write failure")
        path.write_bytes(content)

    monkeypatch.setattr("fsq_agent.config._workspace._atomic_write", fail_write)

    with pytest.raises(OSError, match="injected write failure"):
        create_workspace(
            selected_path=parent,
            name=candidate.name,
            platforms=[WorkspacePlatformCreateInput(platform=candidate.platform, target=candidate.target, env=candidate.env)],
            user_config_root=user_root,
        )

    assert not final_root.exists()
    assert user_file.read_text(encoding="utf-8") == "keep"
    assert list_workspace_registry(user_root) == []


def test_add_workspace_platform_rejects_symlinked_managed_directory(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    android = _android_workspace(parent)
    _create_from_config(parent, android, user_root)
    outside = tmp_path / "outside"
    outside.mkdir()
    chrome = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.write_bytes(b"")
    chrome.chmod(0o755)
    linked_cases = android.root_path / "cases" / "web"
    try:
        linked_cases.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    with pytest.raises(ConfigurationError, match="managed directory"):
        add_workspace_platform(
            name="checkout",
            platform="web",
            target={"browser_executable_path": str(chrome)},
            env={},
            user_config_root=user_root,
        )

    assert list(outside.iterdir()) == []
    assert not (android.root_path / ".fsq" / "config" / "config.web.yaml").exists()


@pytest.mark.parametrize("linked_part", ["metadata", "config_directory", "config"])
def test_load_workspace_config_rejects_symlinked_metadata(tmp_path: Path, linked_part: str) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    config = _android_workspace(tmp_path, name="workspace")
    source = yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)
    if linked_part == "metadata":
        config_directory = outside / "config"
        config_directory.mkdir()
        (config_directory / "config.android.yaml").write_text(source, encoding="utf-8")
        link = root / ".fsq"
        target = outside
        target_is_directory = True
    elif linked_part == "config_directory":
        metadata = root / ".fsq"
        metadata.mkdir()
        target = outside / "config"
        target.mkdir()
        (target / "config.android.yaml").write_text(source, encoding="utf-8")
        link = metadata / "config"
        target_is_directory = True
    else:
        config_directory = root / ".fsq" / "config"
        config_directory.mkdir(parents=True)
        target = outside / "config.android.yaml"
        target.write_text(source, encoding="utf-8")
        link = config_directory / "config.android.yaml"
        target_is_directory = False
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    with pytest.raises(ConfigurationError, match="not an FSQ workspace"):
        load_workspace_config(root, "android")


def test_load_workspace_config_rejects_symlinked_workspace_root(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    metadata = root / ".fsq" / "config"
    metadata.mkdir(parents=True)
    config = _android_workspace(tmp_path, name="workspace")
    (metadata / "config.android.yaml").write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    link = tmp_path / "workspace-link"
    try:
        link.symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")

    with pytest.raises(ConfigurationError, match="symbolic link"):
        load_workspace_config(link, "android")


def test_workspace_validation_errors_do_not_include_secret_input_values(tmp_path: Path) -> None:
    marker = "never-echo-this-secret"
    root = tmp_path / "workspace"
    config_dir = root / ".fsq" / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.android.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": 2,
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
        load_workspace_config(root, "android")

    assert marker not in json.dumps(load_error.value.context)

    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    candidate = _android_workspace(parent)
    _create_from_config(parent, candidate, user_root)
    with pytest.raises(ConfigurationError) as update_error:
        update_workspace_platform(
            name=candidate.name,
            platform="android",
            target={"app_id": "com.example.app"},
            env={"API_KEY": [marker]},  # type: ignore[dict-item]
            expected_revision=_revision(candidate.root_path / ".fsq" / "config" / "config.android.yaml"),
            user_config_root=user_root,
        )

    assert marker not in json.dumps(update_error.value.context)


def test_create_workspace_rejects_macos_app_path_that_is_not_bundle_or_executable(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    invalid_app_path = tmp_path / "ordinary-directory"
    invalid_app_path.mkdir()
    candidate = WorkspaceConfig(
        version=2,
        name="checkout",
        root_path=(parent / "checkout").resolve(),
        platform="macos",
        target=MacOSWorkspaceTarget(app_path=invalid_app_path),
    )

    with pytest.raises(ConfigurationError, match="app bundle or executable"):
        create_workspace(
            selected_path=parent,
            name=candidate.name,
            platforms=[WorkspacePlatformCreateInput(platform=candidate.platform, target=candidate.target, env=candidate.env)],
            user_config_root=tmp_path / "user",
        )

    app_bundle = tmp_path / "Checkout.app"
    app_bundle.mkdir()
    valid_candidate = candidate.model_copy(update={"target": MacOSWorkspaceTarget(app_path=app_bundle)})

    assert (
        create_workspace(
            selected_path=parent,
            name=valid_candidate.name,
            platforms=[
                WorkspacePlatformCreateInput(
                    platform=valid_candidate.platform,
                    target=valid_candidate.target,
                    env=valid_candidate.env,
                )
            ],
            user_config_root=tmp_path / "valid-user",
        ).status
        == "available"
    )
