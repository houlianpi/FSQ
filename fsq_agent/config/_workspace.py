# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from fsq_agent.config._paths import _set_hidden_best_effort
from fsq_agent.config._user_provider import _WRITE_LOCK, _atomic_write, _register_workspace, list_workspace_registry
from fsq_agent.models import (
    ConfigurationError,
    MacOSWorkspaceTarget,
    WebWorkspaceTarget,
    WindowsWorkspaceTarget,
    WorkspaceConfig,
    WorkspaceRegistryEntry,
)

WORKSPACE_CONFIG_RELATIVE_PATH = Path(".fsq/config.yaml")
CHROME_EXECUTABLE_NAMES = {"chrome", "chrome.exe", "google chrome", "google-chrome", "google-chrome-stable"}


def _is_macos_app_bundle_or_executable(path: Path) -> bool:
    return (path.is_dir() and path.suffix.casefold() == ".app") or (
        path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))
    )


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigurationError("Workspace configuration contains a duplicate YAML key.", context={"key": str(key)})
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def load_workspace_config(workspace: str | Path | None = None) -> tuple[WorkspaceConfig, Path, Path]:
    requested_root = (Path.cwd() if workspace is None else Path(workspace)).expanduser()
    if requested_root.is_symlink():
        raise ConfigurationError(
            "Workspace root must not be a symbolic link.",
            context={"workspace": str(requested_root)},
        )
    workspace_root = requested_root.resolve()
    metadata_path = workspace_root / ".fsq"
    config_path = workspace_root / WORKSPACE_CONFIG_RELATIVE_PATH
    if metadata_path.is_symlink() or config_path.is_symlink() or not metadata_path.is_dir() or not config_path.is_file():
        raise ConfigurationError(
            "Directory is not an FSQ workspace. Create a workspace in Control Plane.",
            context={"workspace": str(workspace_root), "config_path": str(config_path)},
        )
    try:
        data = yaml.load(config_path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except ConfigurationError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigurationError("Unable to read workspace configuration.", context={"path": str(config_path)}) from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Workspace configuration must contain a YAML mapping.", context={"path": str(config_path)})
    try:
        config = WorkspaceConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError("Invalid workspace configuration.", context={"errors": exc.errors(include_input=False)}) from exc
    configured_root = config.root_path.expanduser().resolve()
    if configured_root != workspace_root:
        raise ConfigurationError(
            "Workspace root_path does not identify the containing workspace.",
            context={"workspace": str(workspace_root), "configured_root": str(configured_root)},
        )
    return config, workspace_root, config_path


def load_registered_workspace(name: str, user_config_root: str | Path | None = None) -> WorkspaceConfig:
    normalized_name = name.strip().casefold()
    entry = next(
        (candidate for candidate in list_workspace_registry(user_config_root) if candidate.name.casefold() == normalized_name),
        None,
    )
    if entry is None:
        raise ConfigurationError("Workspace is not registered.", context={"name": name})
    workspace_root = entry.config_path.parent.parent
    expected_path = workspace_root / WORKSPACE_CONFIG_RELATIVE_PATH
    if entry.config_path.resolve() != expected_path.resolve():
        raise ConfigurationError("Registered workspace path is invalid.", context={"name": entry.name})
    config, _, config_path = load_workspace_config(workspace_root)
    if config_path.resolve() != entry.config_path.resolve() or config.name != entry.name:
        raise ConfigurationError("Registered workspace identity does not match its configuration.", context={"name": entry.name})
    _validate_target_paths(config)
    return config


def create_workspace(
    *,
    parent_path: Path,
    config: WorkspaceConfig,
    user_config_root: str | Path | None = None,
) -> WorkspaceConfig:
    parent = parent_path.expanduser().resolve()
    if not parent.exists() or not parent.is_dir():
        raise ConfigurationError("Workspace parent path must be an existing directory.", context={"parent_path": str(parent)})
    requested_root = parent / config.name
    if requested_root.is_symlink():
        raise ConfigurationError("Workspace final path must not be a symbolic link.", context={"root_path": str(requested_root)})
    final_root = requested_root.resolve()
    if config.root_path.expanduser().resolve() != final_root:
        raise ConfigurationError(
            "Workspace root_path must match parent path and name.",
            context={"root_path": str(config.root_path), "expected_root": str(final_root)},
        )
    if final_root.exists() and not final_root.is_dir():
        raise ConfigurationError("Workspace final path must be a directory.", context={"root_path": str(final_root)})
    if final_root.exists() and any(final_root.iterdir()):
        raise ConfigurationError("Workspace final directory must be empty.", context={"root_path": str(final_root)})
    _validate_target_paths(config)

    config_path = final_root / WORKSPACE_CONFIG_RELATIVE_PATH
    preexisting_root = final_root.exists()
    created_paths: list[Path] = []
    with _WRITE_LOCK:
        try:
            if not preexisting_root:
                final_root.mkdir()
                created_paths.append(final_root)
            for directory in (final_root / ".fsq", final_root / "cases", final_root / "knowledge"):
                directory.mkdir()
                created_paths.append(directory)
            _set_hidden_best_effort(final_root / ".fsq")
            project_path = final_root / "knowledge" / "project.md"
            _atomic_write(project_path, b"")
            created_paths.append(project_path)
            _atomic_write(config_path, _workspace_yaml_bytes(config))
            _restrict_workspace_config_permissions(config_path)
            created_paths.append(config_path)
            _register_workspace(
                WorkspaceRegistryEntry(name=config.name, config_path=config_path.resolve()),
                user_config_root,
            )
        except Exception:
            _rollback_created_paths(created_paths)
            raise
    return config


def update_workspace(
    *,
    name: str,
    target: object,
    env: Mapping[str, str],
    expected_revision: str,
    user_config_root: str | Path | None = None,
) -> WorkspaceConfig:
    with _WRITE_LOCK:
        current = load_registered_workspace(name, user_config_root)
        config_path = current.root_path / WORKSPACE_CONFIG_RELATIVE_PATH
        try:
            source = config_path.read_bytes()
        except OSError as exc:
            raise ConfigurationError("Unable to read workspace configuration.", context={"name": current.name}) from exc
        if _revision(source) != expected_revision:
            raise ConfigurationError(
                "Workspace configuration changed since it was loaded.",
                context={"name": current.name, "error_code": "workspace_conflict"},
            )
        candidate_data = current.model_dump(mode="python")
        candidate_data["target"] = target
        candidate_data["env"] = dict(env)
        try:
            candidate = WorkspaceConfig.model_validate(candidate_data)
        except ValidationError as exc:
            raise ConfigurationError("Invalid workspace configuration update.", context={"errors": exc.errors(include_input=False)}) from exc
        _validate_target_paths(candidate)
        try:
            _atomic_write(config_path, _workspace_yaml_bytes(candidate))
            _restrict_workspace_config_permissions(config_path)
        except OSError as exc:
            raise ConfigurationError("Unable to update workspace configuration.", context={"name": current.name}) from exc
        return candidate


def workspace_revision(config_path: Path) -> str:
    try:
        return _revision(config_path.read_bytes())
    except OSError as exc:
        raise ConfigurationError("Unable to read workspace configuration.", context={"path": str(config_path)}) from exc


def _revision(source: bytes) -> str:
    return f"sha256:{hashlib.sha256(source).hexdigest()}"


def _workspace_yaml_bytes(config: WorkspaceConfig) -> bytes:
    return yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False).encode("utf-8")


def _validate_target_paths(config: WorkspaceConfig) -> None:
    target = config.target
    path: Path | None = None
    description = "target path"
    if isinstance(target, WebWorkspaceTarget):
        path = target.browser_executable_path
        description = "Web browser executable path"
    elif isinstance(target, WindowsWorkspaceTarget):
        path = target.app_path
        description = "Windows application path"
    elif isinstance(target, MacOSWorkspaceTarget) and target.app_path is not None:
        path = target.app_path
        description = "macOS application path"
    if path is None:
        return
    normalized = path.expanduser().resolve()
    if not normalized.exists():
        raise ConfigurationError(f"{description} does not exist.", context={"path": str(normalized)})
    if isinstance(target, (WebWorkspaceTarget, WindowsWorkspaceTarget)) and not normalized.is_file():
        raise ConfigurationError(f"{description} must be a file.", context={"path": str(normalized)})
    if isinstance(target, MacOSWorkspaceTarget) and not _is_macos_app_bundle_or_executable(normalized):
        raise ConfigurationError(
            "macOS application path must identify an existing app bundle or executable.",
            context={"path": str(normalized)},
        )
    if isinstance(target, WebWorkspaceTarget) and normalized.name.casefold() not in CHROME_EXECUTABLE_NAMES:
        raise ConfigurationError(
            "Web browser executable path does not match the configured Web preset channel.",
            context={"path": str(normalized), "channel": "chrome", "expected_file_names": sorted(CHROME_EXECUTABLE_NAMES)},
        )
    if isinstance(target, WebWorkspaceTarget) and os.name != "nt" and not os.access(normalized, os.X_OK):
        raise ConfigurationError(f"{description} must be executable.", context={"path": str(normalized)})


def _restrict_workspace_config_permissions(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o600)


def _rollback_created_paths(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        except OSError:
            continue