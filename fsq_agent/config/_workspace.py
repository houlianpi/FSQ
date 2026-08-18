# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import hashlib
import os
from collections.abc import Mapping, Sequence
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
    WorkspaceInitResult,
    WorkspacePlatformStatus,
    WorkspaceRegistryEntry,
    WorkspaceStatus,
)

SUPPORTED_PLATFORMS = ("android", "web", "windows", "macos")
WORKSPACE_CONFIG_DIRECTORY = Path(".fsq/config")
WEB_CHANNEL_EXECUTABLE_NAMES = {
    "chromium": {"chromium", "chromium.exe", "chromium-browser"},
    "chrome": {"chrome", "chrome.exe", "google chrome", "google-chrome", "google-chrome-stable"},
    "chrome-beta": {"chrome", "chrome.exe", "google chrome beta", "google-chrome-beta"},
    "chrome-dev": {"chrome", "chrome.exe", "google chrome dev", "google-chrome-unstable"},
    "chrome-canary": {"chrome", "chrome.exe", "google chrome canary"},
    "msedge": {"msedge", "msedge.exe", "microsoft edge"},
    "msedge-beta": {"msedge", "msedge.exe", "microsoft edge beta"},
    "msedge-dev": {"msedge", "msedge.exe", "microsoft edge dev"},
    "msedge-canary": {"msedge", "msedge.exe", "microsoft edge canary"},
}
WEB_CHANNEL_PATH_MARKERS = {
    "chromium": ("chromium",), "chrome": ("google/chrome", "google chrome"),
    "chrome-beta": ("chrome beta",), "chrome-dev": ("chrome dev",), "chrome-canary": ("chrome canary", "chrome sxs"),
    "msedge": ("microsoft/edge/application", "microsoft edge.app"), "msedge-beta": ("edge beta",),
    "msedge-dev": ("edge dev",), "msedge-canary": ("edge canary", "edge sxs"),
}
CHROME_EXECUTABLE_NAMES = WEB_CHANNEL_EXECUTABLE_NAMES["chrome"]


def _is_macos_app_bundle_or_executable(path: Path) -> bool:
    return (path.is_dir() and path.suffix.casefold() == ".app") or (path.is_file() and (os.name == "nt" or os.access(path, os.X_OK)))


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


def _workspace_config_path(workspace_root: Path, platform: str) -> Path:
    if platform not in SUPPORTED_PLATFORMS:
        raise ConfigurationError("Unsupported workspace platform.", context={"platform": platform})
    return workspace_root / WORKSPACE_CONFIG_DIRECTORY / f"config.{platform}.yaml"


def load_workspace_config(workspace: str | Path, platform: str) -> tuple[WorkspaceConfig, Path, Path]:
    config, workspace_root, config_path, _ = _load_workspace_config_snapshot(workspace, platform)
    return config, workspace_root, config_path


def _load_workspace_config_snapshot(workspace: str | Path, platform: str) -> tuple[WorkspaceConfig, Path, Path, str]:
    requested_root = (Path.cwd() if workspace is None else Path(workspace)).expanduser()
    if requested_root.is_symlink():
        raise ConfigurationError(
            "Workspace root must not be a symbolic link.",
            context={"workspace": str(requested_root)},
        )
    workspace_root = requested_root.resolve()
    metadata_path = workspace_root / ".fsq"
    config_directory = workspace_root / WORKSPACE_CONFIG_DIRECTORY
    config_path = _workspace_config_path(workspace_root, platform)
    if metadata_path.is_symlink() or config_directory.is_symlink() or config_path.is_symlink() or not metadata_path.is_dir() or not config_directory.is_dir() or not config_path.is_file():
        raise ConfigurationError(
            "Directory is not an FSQ workspace. Create a workspace in Control Plane.",
            context={"workspace": str(workspace_root), "platform": platform, "config_path": str(config_path)},
        )
    try:
        source = config_path.read_bytes()
        data = yaml.load(source.decode("utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader subclass rejects duplicate keys.
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
    if config.platform != platform:
        raise ConfigurationError(
            "Workspace platform does not match its configuration filename.",
            context={"platform": platform, "configured_platform": config.platform},
        )
    return config, workspace_root, config_path, _revision(source)


def _find_registry_entry(name: str, user_config_root: str | Path | None = None) -> WorkspaceRegistryEntry:
    normalized_name = name.strip().casefold()
    entry = next(
        (candidate for candidate in list_workspace_registry(user_config_root) if candidate.name.casefold() == normalized_name),
        None,
    )
    if entry is None:
        raise ConfigurationError("Workspace is not registered.", context={"name": name})
    return entry


def inspect_registered_workspace(name: str, user_config_root: str | Path | None = None) -> WorkspaceStatus:
    entry = _find_registry_entry(name, user_config_root)
    root = entry.root_path
    if root.is_symlink() or not root.is_dir():
        return WorkspaceStatus(
            name=entry.name,
            root_path=root,
            status="unavailable",
            message="Workspace root is unavailable.",
            action="Restore the registered workspace root.",
        )
    config_directory = root / WORKSPACE_CONFIG_DIRECTORY
    if config_directory.is_symlink() or not config_directory.is_dir():
        legacy_path = root / ".fsq" / "config.yaml"
        message = "Legacy workspace configuration is unsupported." if legacy_path.is_file() else "No platform configuration is available."
        return WorkspaceStatus(
            name=entry.name,
            root_path=root,
            status="unavailable",
            message=message,
            action="Add a supported platform configuration.",
        )

    platforms: list[WorkspacePlatformStatus] = []
    available_count = 0
    unavailable_count = 0
    for platform in SUPPORTED_PLATFORMS:
        config_path = _workspace_config_path(root, platform)
        if not config_path.exists() and not config_path.is_symlink():
            continue
        try:
            config, _, loaded_path = load_workspace_config(root, platform)
            if config.name != entry.name or loaded_path.resolve() != config_path.resolve():
                raise ConfigurationError("Registered workspace identity does not match its configuration.")  # noqa: TRY301
            _validate_target_paths(config)
        except ConfigurationError:
            unavailable_count += 1
            platforms.append(
                WorkspacePlatformStatus(
                    platform=platform,
                    config_path=config_path,
                    status="unavailable",
                    message="Platform configuration is unavailable.",
                    action=f"Repair config.{platform}.yaml manually.",
                )
            )
        else:
            available_count += 1
            platforms.append(
                WorkspacePlatformStatus(
                    platform=platform,
                    config_path=config_path,
                    status="available",
                    message="Platform configuration is available.",
                )
            )

    if available_count == 0:
        return WorkspaceStatus(
            name=entry.name,
            root_path=root,
            status="unavailable",
            message="No valid platform configuration is available.",
            action="Add or repair a supported platform configuration.",
            platforms=platforms,
        )
    if unavailable_count:
        return WorkspaceStatus(
            name=entry.name,
            root_path=root,
            status="partial",
            message="Some platform configurations are unavailable.",
            action="Repair unavailable platform configurations.",
            platforms=platforms,
        )
    return WorkspaceStatus(
        name=entry.name,
        root_path=root,
        status="available",
        message="Workspace is available.",
        platforms=platforms,
    )


def load_registered_workspace(
    name: str,
    platform: str,
    user_config_root: str | Path | None = None,
) -> WorkspaceConfig:
    config, _ = _load_registered_workspace_snapshot(name, platform, user_config_root)
    return config


def _load_registered_workspace_snapshot(
    name: str,
    platform: str,
    user_config_root: str | Path | None = None,
) -> tuple[WorkspaceConfig, str]:
    entry = _find_registry_entry(name, user_config_root)
    try:
        config, workspace_root, _, revision = _load_workspace_config_snapshot(entry.root_path, platform)
    except ConfigurationError as exc:
        raise ConfigurationError(
            "Workspace platform is unavailable.",
            context={"name": entry.name, "platform": platform},
        ) from exc
    if workspace_root != entry.root_path.resolve() or config.name != entry.name:
        raise ConfigurationError("Registered workspace identity does not match its configuration.", context={"name": entry.name})
    _validate_target_paths(config)
    return config, revision


def create_workspace(
    *,
    parent_path: Path,
    configs: Sequence[WorkspaceConfig],
    user_config_root: str | Path | None = None,
) -> WorkspaceStatus:
    if not configs:
        raise ConfigurationError("Workspace requires at least one platform configuration.")
    first = configs[0]
    if len({config.platform for config in configs}) != len(configs):
        raise ConfigurationError("Workspace platform configurations must be unique.")
    if any(config.name != first.name or config.root_path.expanduser().resolve() != first.root_path.expanduser().resolve() for config in configs):
        raise ConfigurationError("Workspace platform configurations must share one name and root path.")
    parent = parent_path.expanduser().resolve()
    if not parent.exists() or not parent.is_dir():
        raise ConfigurationError("Workspace parent path must be an existing directory.", context={"parent_path": str(parent)})
    requested_root = parent / first.name
    if requested_root.is_symlink():
        raise ConfigurationError("Workspace final path must not be a symbolic link.", context={"root_path": str(requested_root)})
    final_root = requested_root.resolve()
    if first.root_path.expanduser().resolve() != final_root:
        raise ConfigurationError(
            "Workspace root_path must match parent path and name.",
            context={"root_path": str(first.root_path), "expected_root": str(final_root)},
        )
    if final_root.exists() and not final_root.is_dir():
        raise ConfigurationError("Workspace final path must be a directory.", context={"root_path": str(final_root)})
    if final_root.exists() and any(final_root.iterdir()):
        raise ConfigurationError("Workspace final directory must be empty.", context={"root_path": str(final_root)})
    for config in configs:
        _validate_target_paths(config)

    preexisting_root = final_root.exists()
    created_paths: list[Path] = []
    with _WRITE_LOCK:
        try:
            if not preexisting_root:
                final_root.mkdir()
                created_paths.append(final_root)
            for directory in (final_root / ".fsq", final_root / WORKSPACE_CONFIG_DIRECTORY, final_root / ".fsq" / "runs"):
                _ensure_managed_directory(final_root, directory, created_paths)
            _set_hidden_best_effort(final_root / ".fsq")
            for config in configs:
                for directory in (
                    final_root / "cases" / config.platform,
                    final_root / "knowledge" / config.platform,
                    final_root / ".fsq" / "runs" / config.platform,
                ):
                    _ensure_managed_directory(final_root, directory, created_paths)
                project_path = final_root / "knowledge" / config.platform / "project.md"
                _atomic_write(project_path, b"")
                created_paths.append(project_path)
                config_path = _workspace_config_path(final_root, config.platform)
                _atomic_write(config_path, _workspace_yaml_bytes(config))
                _restrict_workspace_config_permissions(config_path)
                created_paths.append(config_path)
            _register_workspace(
                WorkspaceRegistryEntry(name=first.name, root_path=final_root),
                user_config_root,
            )
        except Exception:
            _rollback_created_paths(created_paths)
            raise
    return inspect_registered_workspace(first.name, user_config_root)


def initialize_workspace(
    *,
    parent_path: Path,
    config: WorkspaceConfig,
    update_existing: bool = False,
    user_config_root: str | Path | None = None,
) -> WorkspaceInitResult:
    parent = parent_path.expanduser().resolve()
    if not parent.exists() or not parent.is_dir():
        raise ConfigurationError("Workspace parent path must be an existing directory.", context={"parent_path": str(parent)})
    expected_root = (parent / config.name).resolve()
    if config.root_path.expanduser().resolve() != expected_root:
        raise ConfigurationError(
            "Workspace root_path must match parent path and name.",
            context={"root_path": str(config.root_path), "expected_root": str(expected_root)},
        )
    _validate_target_paths(config)

    entry = next(
        (candidate for candidate in list_workspace_registry(user_config_root) if candidate.name.casefold() == config.name.casefold()),
        None,
    )
    if entry is None:
        create_workspace(parent_path=parent, configs=[config], user_config_root=user_config_root)
        return WorkspaceInitResult(status="initialized", name=config.name, root_path=expected_root, platform=config.platform)

    registered_root = entry.root_path.expanduser().resolve()
    if registered_root != expected_root:
        raise ConfigurationError(
            "Registered workspace root does not match parent path and name.",
            context={"name": entry.name, "registered_root": str(registered_root), "expected_root": str(expected_root)},
        )
    legacy_paths = (registered_root / ".fsq" / "config.yaml", registered_root / ".fsq-agent-workspace")
    if any(path.exists() or path.is_symlink() for path in legacy_paths):
        raise ConfigurationError(
            "Legacy workspace layout is incompatible with initialization.",
            context={"name": entry.name, "root_path": str(registered_root)},
        )
    config_path = _workspace_config_path(registered_root, config.platform)
    if not config_path.exists() and not config_path.is_symlink():
        added = add_workspace_platform(
            name=entry.name,
            platform=config.platform,
            target=config.target,
            env=config.env,
            user_config_root=user_config_root,
        )
        return WorkspaceInitResult(status="platform_added", name=added.name, root_path=added.root_path, platform=added.platform)

    current, expected_revision = _load_registered_workspace_snapshot(entry.name, config.platform, user_config_root)
    if current.target == config.target and current.env == config.env:
        _, current_revision = _load_registered_workspace_snapshot(entry.name, config.platform, user_config_root)
        if current_revision != expected_revision:
            raise ConfigurationError(
                "Workspace configuration changed since it was loaded.",
                context={"name": current.name, "platform": current.platform},
            )
        return WorkspaceInitResult(status="unchanged", name=current.name, root_path=current.root_path, platform=current.platform)
    if not update_existing:
        raise ConfigurationError(
            "Workspace platform configuration differs; use --update-existing to replace target and env values.",
            context={"name": current.name, "platform": current.platform},
        )
    updated = update_workspace_platform(
        name=current.name,
        platform=current.platform,
        target=config.target,
        env=config.env,
        expected_revision=expected_revision,
        user_config_root=user_config_root,
    )
    return WorkspaceInitResult(status="updated", name=updated.name, root_path=updated.root_path, platform=updated.platform)


def add_workspace_platform(
    *,
    name: str,
    platform: str,
    target: object,
    env: Mapping[str, str],
    user_config_root: str | Path | None = None,
) -> WorkspaceConfig:
    with _WRITE_LOCK:
        entry = _find_registry_entry(name, user_config_root)
        config_path = _workspace_config_path(entry.root_path, platform)
        config_directory = entry.root_path / WORKSPACE_CONFIG_DIRECTORY
        if config_path.exists() or config_path.is_symlink():
            raise ConfigurationError(
                "Workspace platform configuration already exists.",
                context={"name": entry.name, "platform": platform},
            )
        if entry.root_path.is_symlink() or not entry.root_path.is_dir() or config_directory.is_symlink():
            raise ConfigurationError("Workspace root is unavailable.", context={"name": entry.name})
        try:
            candidate = WorkspaceConfig.model_validate(
                {
                    "version": 2,
                    "name": entry.name,
                    "root_path": entry.root_path,
                    "platform": platform,
                    "target": target,
                    "env": dict(env),
                }
            )
        except ValidationError as exc:
            raise ConfigurationError("Invalid workspace platform configuration.", context={"errors": exc.errors(include_input=False)}) from exc
        _validate_target_paths(candidate)
        created_paths: list[Path] = []
        try:
            for directory in (
                entry.root_path / ".fsq",
                config_directory,
                entry.root_path / "cases" / platform,
                entry.root_path / "knowledge" / platform,
                entry.root_path / ".fsq" / "runs" / platform,
            ):
                _ensure_managed_directory(entry.root_path, directory, created_paths)
            project_path = entry.root_path / "knowledge" / platform / "project.md"
            if not project_path.exists():
                _atomic_write(project_path, b"")
                created_paths.append(project_path)
            _atomic_write(config_path, _workspace_yaml_bytes(candidate))
            _restrict_workspace_config_permissions(config_path)
            created_paths.append(config_path)
        except Exception:
            _rollback_created_paths(created_paths)
            raise
        return candidate


def update_workspace_platform(
    *,
    name: str,
    platform: str,
    target: object,
    env: Mapping[str, str],
    expected_revision: str,
    user_config_root: str | Path | None = None,
) -> WorkspaceConfig:
    with _WRITE_LOCK:
        current, current_revision = _load_registered_workspace_snapshot(name, platform, user_config_root)
        config_path = _workspace_config_path(current.root_path, platform)
        if current_revision != expected_revision:
            raise ConfigurationError(
                "Workspace configuration changed since it was loaded.",
                context={"name": current.name, "platform": platform, "error_code": "workspace_conflict"},
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
            raise ConfigurationError(
                "Unable to update workspace configuration.",
                context={"name": current.name, "platform": platform},
            ) from exc
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
    expected_names = WEB_CHANNEL_EXECUTABLE_NAMES.get(target.browser_channel, set()) if isinstance(target, WebWorkspaceTarget) else set()
    if isinstance(target, WebWorkspaceTarget) and normalized.name.casefold() not in expected_names:
        raise ConfigurationError(
            "Web browser executable path does not match the configured Web preset channel.",
            context={"path": str(normalized), "channel": target.browser_channel, "expected_file_names": sorted(expected_names)},
        )
    if os.name == "nt" and isinstance(target, WebWorkspaceTarget) and normalized.name.casefold() in {"chrome.exe", "msedge.exe"}:
        normalized_path = str(normalized).replace("\\", "/").casefold()
        if not any(marker in normalized_path for marker in WEB_CHANNEL_PATH_MARKERS[target.browser_channel]):
            raise ConfigurationError(
                "Web browser executable path does not match the configured Web preset channel.",
                context={"path": str(normalized), "channel": target.browser_channel},
            )
    if isinstance(target, WebWorkspaceTarget) and os.name != "nt" and not os.access(normalized, os.X_OK):
        raise ConfigurationError(f"{description} must be executable.", context={"path": str(normalized)})


def _restrict_workspace_config_permissions(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o600)


def _ensure_managed_directory(root: Path, directory: Path, created_paths: list[Path]) -> None:
    current = root
    if current.is_symlink() or not current.is_dir():
        raise ConfigurationError("Workspace root is unavailable.", context={"root_path": str(root)})
    for part in directory.relative_to(root).parts:
        current /= part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise ConfigurationError("Workspace managed directory is unavailable.", context={"path": str(current)})
        if not current.exists():
            current.mkdir()
            created_paths.append(current)


def _rollback_created_paths(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        except OSError:
            continue
