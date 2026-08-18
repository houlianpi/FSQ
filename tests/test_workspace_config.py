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
    WebWorkspaceTarget,
    WorkspaceConfig,
    WorkspaceInitResult,
    add_workspace_platform,
    create_workspace,
    initialize_workspace,
    inspect_registered_workspace,
    list_workspace_registry,
    load_registered_workspace,
    update_workspace_platform,
)
from fsq_agent.config._workspace import _load_registered_workspace_snapshot, load_workspace_config
from fsq_agent.models import ConfigurationError


def _android_workspace(parent: Path, name: str = "checkout") -> WorkspaceConfig:
    return WorkspaceConfig(
        version=2,
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

    created = create_workspace(parent_path=parent, configs=[candidate], user_config_root=user_root)

    config_path = candidate.root_path / ".fsq" / "config" / "config.android.yaml"
    assert created.status == "available"
    assert [status.platform for status in created.platforms] == ["android"]
    assert config_path.is_file()
    assert (candidate.root_path / "cases" / "android").is_dir()
    assert (candidate.root_path / ".fsq" / "runs" / "android").is_dir()
    assert (candidate.root_path / "knowledge" / "android" / "project.md").read_text(encoding="utf-8") == ""
    assert yaml.safe_load(config_path.read_text(encoding="utf-8"))["env"] == {"TEST_PASSWORD": "initial-secret"}
    assert [(entry.name, entry.root_path) for entry in list_workspace_registry(user_root)] == [("checkout", candidate.root_path)]
    assert load_registered_workspace("CHECKOUT", "android", user_root) == candidate


def test_initialize_workspace_creates_adds_and_returns_unchanged(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    android = _android_workspace(parent)

    created = initialize_workspace(parent_path=parent, config=android, user_config_root=user_root)
    config_path = android.root_path / ".fsq" / "config" / "config.android.yaml"
    created_revision = _revision(config_path)
    unchanged = initialize_workspace(parent_path=parent, config=android, user_config_root=user_root)
    macos = WorkspaceConfig(
        version=2,
        name=android.name,
        root_path=android.root_path,
        platform="macos",
        target=MacOSWorkspaceTarget(bundle_id="com.example.checkout"),
    )
    added = initialize_workspace(parent_path=parent, config=macos, user_config_root=user_root)

    assert created.model_dump(mode="json") == {
        "status": "initialized",
        "name": "checkout",
        "root_path": str(android.root_path),
        "platform": "android",
    }
    assert unchanged.status == "unchanged"
    assert _revision(config_path) == created_revision
    assert added.status == "platform_added"
    assert load_registered_workspace("checkout", "macos", user_root) == macos


def test_initialize_workspace_requires_update_flag_for_differing_platform(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    original = _android_workspace(parent)
    initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)
    replacement = original.model_copy(
        update={
            "target": AndroidWorkspaceTarget(app_id="com.example.changed"),
            "env": {"TEST_PASSWORD": "replacement-secret"},
        }
    )

    with pytest.raises(ConfigurationError, match="--update-existing"):
        initialize_workspace(parent_path=parent, config=replacement, user_config_root=user_root)

    assert load_registered_workspace("checkout", "android", user_root) == original
    updated = initialize_workspace(
        parent_path=parent,
        config=replacement,
        update_existing=True,
        user_config_root=user_root,
    )
    assert updated.status == "updated"
    assert load_registered_workspace("checkout", "android", user_root) == replacement


@pytest.mark.parametrize("legacy_path", [Path(".fsq/config.yaml"), Path(".fsq-agent-workspace")])
def test_initialize_workspace_rejects_registered_legacy_layout(
    tmp_path: Path,
    legacy_path: Path,
) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    original = _android_workspace(parent)
    create_workspace(parent_path=parent, configs=[original], user_config_root=user_root)
    current_config = original.root_path / ".fsq" / "config" / "config.android.yaml"
    current_config.unlink()
    marker = original.root_path / legacy_path
    if legacy_path.name == ".fsq-agent-workspace":
        marker.mkdir()
    else:
        marker.write_text("version: 1\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Legacy workspace layout"):
        initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)

    assert not current_config.exists()


def test_initialize_workspace_does_not_retry_stale_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    original = _android_workspace(parent)
    initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)
    replacement = original.model_copy(update={"target": AndroidWorkspaceTarget(app_id="com.example.changed")})
    real_update = update_workspace_platform

    def race_update(**kwargs):
        config_path = original.root_path / ".fsq" / "config" / "config.android.yaml"
        config_path.write_bytes(config_path.read_bytes() + b"\n")
        return real_update(**kwargs)

    monkeypatch.setattr("fsq_agent.config._workspace.update_workspace_platform", race_update)

    with pytest.raises(ConfigurationError, match="changed since it was loaded"):
        initialize_workspace(
            parent_path=parent,
            config=replacement,
            update_existing=True,
            user_config_root=user_root,
        )

    assert load_registered_workspace("checkout", "android", user_root).target == original.target


def test_initialize_workspace_uses_revision_from_compared_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    original = _android_workspace(parent)
    initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)
    replacement = original.model_copy(update={"target": AndroidWorkspaceTarget(app_id="com.example.requested")})
    concurrent = original.model_copy(update={"target": AndroidWorkspaceTarget(app_id="com.example.concurrent")})
    config_path = original.root_path / ".fsq" / "config" / "config.android.yaml"

    def race_snapshot(name: str, platform: str, user_config_root: Path | None = None):
        del name, user_config_root
        current, _, _ = load_workspace_config(original.root_path, platform)
        source = config_path.read_bytes()
        config_path.write_text(yaml.safe_dump(concurrent.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        return current, f"sha256:{hashlib.sha256(source).hexdigest()}"

    monkeypatch.setattr("fsq_agent.config._workspace._load_registered_workspace_snapshot", race_snapshot, raising=False)

    with pytest.raises(ConfigurationError, match="changed since it was loaded"):
        initialize_workspace(
            parent_path=parent,
            config=replacement,
            update_existing=True,
            user_config_root=user_root,
        )

    assert load_registered_workspace("checkout", "android", user_root).target == concurrent.target


def test_initialize_workspace_rejects_stale_unchanged_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    original = _android_workspace(parent)
    initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)
    concurrent = original.model_copy(update={"target": AndroidWorkspaceTarget(app_id="com.example.concurrent")})
    config_path = original.root_path / ".fsq" / "config" / "config.android.yaml"

    def race_snapshot(name: str, platform: str, user_config_root: Path | None = None):
        del name, user_config_root
        current, _, _ = load_workspace_config(original.root_path, platform)
        source = config_path.read_bytes()
        config_path.write_text(yaml.safe_dump(concurrent.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        return current, f"sha256:{hashlib.sha256(source).hexdigest()}"

    monkeypatch.setattr("fsq_agent.config._workspace._load_registered_workspace_snapshot", race_snapshot)

    with pytest.raises(ConfigurationError, match="changed since it was loaded"):
        initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)

    assert load_registered_workspace("checkout", "android", user_root).target == concurrent.target


def test_initialize_workspace_validates_target_before_user_store_mutation(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    candidate = WorkspaceConfig(
        version=2,
        name="checkout",
        root_path=(parent / "checkout").resolve(),
        platform="web",
        target=WebWorkspaceTarget(browser_executable_path=tmp_path / "missing" / "chrome.exe"),
    )

    with pytest.raises(ConfigurationError, match="does not exist"):
        initialize_workspace(parent_path=parent, config=candidate, user_config_root=user_root)

    assert not user_root.exists()
    assert not candidate.root_path.exists()


def test_initialize_workspace_rejects_equal_byte_symlink_swap_for_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    original = _android_workspace(parent)
    initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)
    config_path = original.root_path / ".fsq" / "config" / "config.android.yaml"
    linked_config = tmp_path / "linked-config.android.yaml"
    swapped = False

    def race_snapshot(name: str, platform: str, user_config_root: Path | None = None):
        nonlocal swapped
        result = _load_registered_workspace_snapshot(name, platform, user_config_root)
        if not swapped:
            source = config_path.read_bytes()
            linked_config.write_bytes(source)
            config_path.unlink()
            try:
                config_path.symlink_to(linked_config)
            except OSError as exc:
                config_path.write_bytes(source)
                pytest.skip(f"Symlink creation is unavailable: {exc}")
            swapped = True
        return result

    monkeypatch.setattr("fsq_agent.config._workspace._load_registered_workspace_snapshot", race_snapshot)

    with pytest.raises(ConfigurationError, match="unavailable"):
        initialize_workspace(parent_path=parent, config=original, user_config_root=user_root)


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
    create_workspace(parent_path=parent, configs=[candidate], user_config_root=user_root)
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
    create_workspace(parent_path=parent, configs=[android], user_config_root=user_root)
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
    create_workspace(parent_path=parent, configs=[candidate], user_config_root=user_root)
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


def test_create_workspace_rejects_non_empty_final_root_without_changes(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    final_root = parent / "checkout"
    final_root.mkdir(parents=True)
    user_file = final_root / "keep.txt"
    user_file.write_text("keep", encoding="utf-8")
    user_root = tmp_path / "user"

    with pytest.raises(ConfigurationError, match="empty"):
        create_workspace(parent_path=parent, configs=[_android_workspace(parent)], user_config_root=user_root)

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
        create_workspace(parent_path=parent, configs=[_android_workspace(parent)], user_config_root=user_root)

    assert list(outside.iterdir()) == []
    assert list_workspace_registry(user_root) == []


def test_create_workspace_rolls_back_implicitly_created_parent_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "projects"
    final_root = parent / "checkout"
    final_root.mkdir(parents=True)
    user_root = tmp_path / "user"

    def fail_write(path: Path, content: bytes) -> None:
        if path.name == "config.android.yaml":
            raise OSError("injected write failure")
        path.write_bytes(content)

    monkeypatch.setattr("fsq_agent.config._workspace._atomic_write", fail_write)

    with pytest.raises(OSError, match="injected write failure"):
        create_workspace(parent_path=parent, configs=[_android_workspace(parent)], user_config_root=user_root)

    assert list(final_root.iterdir()) == []
    assert list_workspace_registry(user_root) == []


def test_add_workspace_platform_rejects_symlinked_managed_directory(tmp_path: Path) -> None:
    parent = tmp_path / "projects"
    parent.mkdir()
    user_root = tmp_path / "user"
    android = _android_workspace(parent)
    create_workspace(parent_path=parent, configs=[android], user_config_root=user_root)
    outside = tmp_path / "outside"
    outside.mkdir()
    chrome = tmp_path / "chrome.exe"
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
    create_workspace(parent_path=parent, configs=[candidate], user_config_root=user_root)
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
        create_workspace(parent_path=parent, configs=[candidate], user_config_root=tmp_path / "user")

    app_bundle = tmp_path / "Checkout.app"
    app_bundle.mkdir()
    valid_candidate = candidate.model_copy(update={"target": MacOSWorkspaceTarget(app_path=app_bundle)})

    assert (
        create_workspace(
            parent_path=parent,
            configs=[valid_candidate],
            user_config_root=tmp_path / "valid-user",
        ).status
        == "available"
    )
