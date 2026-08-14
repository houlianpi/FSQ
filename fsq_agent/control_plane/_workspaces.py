# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fsq_agent.config import (
    WorkspaceConfig,
    create_workspace,
    list_workspace_registry,
    load_registered_workspace,
    update_workspace,
    workspace_revision,
)
from fsq_agent.models import ConfigurationError


@dataclass(frozen=True)
class WorkspaceAPIError(Exception):
    status: int
    code: str
    message: str
    action: str


def list_workspaces(user_config_root: Path | None) -> dict[str, list[dict[str, Any]]]:
    workspaces: list[dict[str, Any]] = []
    for entry in list_workspace_registry(user_config_root):
        config_path = entry.config_path.resolve()
        root_path = config_path.parent.parent
        try:
            config = load_registered_workspace(entry.name, user_config_root)
        except (ConfigurationError, OSError):
            workspaces.append(
                {
                    "name": entry.name,
                    "configPath": str(config_path),
                    "rootPath": str(root_path),
                    "status": "unavailable",
                    "message": "Workspace configuration is unavailable.",
                    "action": "Repair the registered .fsq/config.yaml file or create a replacement workspace.",
                }
            )
            continue
        workspaces.append(
            {
                "name": config.name,
                "configPath": str(config_path),
                "rootPath": str(config.root_path.resolve()),
                "platform": config.platform,
                "status": "available",
                "message": "Workspace is available.",
            }
        )
    return {"workspaces": workspaces}


def get_workspace(name: str, user_config_root: Path | None) -> dict[str, Any]:
    config = _load_exact_workspace(name, user_config_root)
    return _detail(config)


def create_workspace_request(body: dict[str, Any], user_config_root: Path | None) -> dict[str, Any]:
    _require_exact_fields(body, {"name", "parentPath", "platform", "target", "env"})
    name = body["name"]
    parent_path = body["parentPath"]
    platform = body["platform"]
    if not isinstance(name, str) or not isinstance(parent_path, str) or not isinstance(platform, str):
        raise WorkspaceAPIError(
            400,
            "invalid_workspace",
            "name, parentPath, and platform must be strings.",
            "Correct the workspace fields and retry.",
        )
    parent = Path(parent_path).expanduser().resolve()
    try:
        config = WorkspaceConfig.model_validate(
            {
                "version": 1,
                "name": name,
                "root_path": parent / name,
                "platform": platform,
                "target": _target_input(body["target"]),
                "env": body["env"],
            }
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise WorkspaceAPIError(
            400,
            "invalid_workspace",
            "Workspace configuration is invalid.",
            "Correct the workspace fields and retry.",
        ) from exc
    created = create_workspace(parent_path=parent, config=config, user_config_root=user_config_root)
    return _detail(created)


def update_workspace_request(name: str, body: dict[str, Any], user_config_root: Path | None) -> dict[str, Any]:
    _require_exact_fields(body, {"target", "env", "expectedRevision"})
    expected_revision = body["expectedRevision"]
    if not isinstance(expected_revision, str) or not expected_revision:
        raise WorkspaceAPIError(
            400,
            "invalid_workspace",
            "expectedRevision must be a non-empty string.",
            "Reload the workspace and retry.",
        )
    target = body["target"]
    env = body["env"]
    if not isinstance(target, dict) or not isinstance(env, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in env.items()
    ):
        raise WorkspaceAPIError(
            400,
            "invalid_workspace",
            "target must be an object and env must contain string names and values.",
            "Correct the workspace fields and retry.",
        )
    _load_exact_workspace(name, user_config_root)
    updated = update_workspace(
        name=name,
        target=_target_input(target),
        env=env,
        expected_revision=expected_revision,
        user_config_root=user_config_root,
    )
    return _detail(updated)


def map_workspace_exception(exc: BaseException) -> WorkspaceAPIError:
    if isinstance(exc, WorkspaceAPIError):
        return exc
    if isinstance(exc, ConfigurationError):
        if exc.context.get("error_code") == "workspace_conflict":
            return WorkspaceAPIError(
                409,
                "workspace_conflict",
                "Workspace configuration changed since it was loaded.",
                "Reload the latest workspace before saving again.",
            )
        message = str(exc).splitlines()[0]
        lowered = message.casefold()
        if "not registered" in lowered:
            return WorkspaceAPIError(404, "workspace_not_found", "Workspace is not registered.", "Refresh the workspace list.")
        if "already registered" in lowered or "must be empty" in lowered or "must be a directory" in lowered:
            return WorkspaceAPIError(409, "workspace_conflict", message, "Choose a different workspace name or parent path.")
        if "unable to read" in lowered or "identity does not match" in lowered or "registered workspace path" in lowered:
            return WorkspaceAPIError(409, "workspace_unavailable", "Workspace configuration is unavailable.", "Repair the registered workspace configuration.")
        return WorkspaceAPIError(400, "invalid_workspace", message, "Correct the workspace configuration and retry.")
    if isinstance(exc, OSError):
        return WorkspaceAPIError(503, "workspace_storage_unavailable", "Unable to access workspace storage.", "Check local file permissions and retry.")
    return WorkspaceAPIError(500, "workspace_internal_error", "An unexpected workspace error occurred.", "Retry or inspect the local server logs.")


def _load_exact_workspace(name: str, user_config_root: Path | None) -> WorkspaceConfig:
    if not isinstance(name, str) or not name:
        raise WorkspaceAPIError(404, "workspace_not_found", "Workspace is not registered.", "Refresh the workspace list.")
    normalized_name = name.casefold()
    entry = next(
        (candidate for candidate in list_workspace_registry(user_config_root) if candidate.name.casefold() == normalized_name),
        None,
    )
    if entry is None:
        raise WorkspaceAPIError(404, "workspace_not_found", "Workspace is not registered.", "Refresh the workspace list.")
    try:
        return load_registered_workspace(entry.name, user_config_root)
    except ConfigurationError as exc:
        raise WorkspaceAPIError(
            409,
            "workspace_unavailable",
            "Workspace configuration is unavailable.",
            "Repair the registered workspace configuration.",
        ) from exc
    except OSError as exc:
        raise WorkspaceAPIError(
            503,
            "workspace_storage_unavailable",
            "Unable to access workspace storage.",
            "Check local file permissions and retry.",
        ) from exc


def _detail(config: WorkspaceConfig) -> dict[str, Any]:
    config_path = config.root_path.resolve() / ".fsq" / "config.yaml"
    return {
        "name": config.name,
        "rootPath": str(config.root_path.resolve()),
        "configPath": str(config_path),
        "platform": config.platform,
        "target": _target_projection(config),
        "env": dict(config.env),
        "revision": workspace_revision(config_path),
    }


def _target_projection(config: WorkspaceConfig) -> dict[str, Any]:
    target = config.target.model_dump(mode="json", exclude_none=True)
    aliases = {
        "app_id": "appId",
        "browser_executable_path": "browserExecutablePath",
        "app_path": "appPath",
        "window_title_re": "windowTitleRe",
        "launch_args": "launchArgs",
        "bundle_id": "bundleId",
    }
    return {aliases.get(key, key): value for key, value in target.items()}


def _target_input(target: object) -> object:
    if not isinstance(target, dict):
        return target
    aliases = {
        "appId": "app_id",
        "browserExecutablePath": "browser_executable_path",
        "appPath": "app_path",
        "windowTitleRe": "window_title_re",
        "launchArgs": "launch_args",
        "bundleId": "bundle_id",
    }
    return {aliases.get(key, key): value for key, value in target.items()}


def _require_exact_fields(body: dict[str, Any], expected: set[str]) -> None:
    if set(body) != expected:
        names = ", ".join(sorted(expected))
        raise WorkspaceAPIError(
            400,
            "invalid_request",
            f"Request body must contain exactly {names}.",
            "Correct the request body and retry.",
        )


__all__ = [
    "WorkspaceAPIError",
    "create_workspace_request",
    "get_workspace",
    "list_workspaces",
    "map_workspace_exception",
    "update_workspace_request",
]