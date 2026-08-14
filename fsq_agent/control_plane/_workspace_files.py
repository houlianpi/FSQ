# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from fsq_agent.config import list_workspace_registry, load_registered_workspace
from fsq_agent.models import ConfigurationError, WorkspaceConfig

_ALLOWED_ROOTS = frozenset({"cases", "knowledge"})
_MAX_DEPTH = 32
_MAX_ENTRIES = 500
_MAX_FILE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class WorkspaceFileAPIError(Exception):
    status: int
    code: str
    message: str
    action: str


def list_workspace_entries(name: str, relative_path: str, user_config_root: Path | None) -> dict[str, Any]:
    config = _load_workspace(name, user_config_root)
    workspace_root = config.root_path.resolve()
    normalized = _normalize_relative_path(relative_path, allow_root=True)
    if not normalized.parts:
        entries = [
            _managed_root_projection(workspace_root, root_name)
            for root_name in sorted(_ALLOWED_ROOTS)
        ]
        return {"path": "", "entries": entries, "truncated": False}

    managed_path = workspace_root / normalized.parts[0]
    if len(normalized.parts) == 1 and not managed_path.exists():
        if managed_path.is_symlink():
            raise WorkspaceFileAPIError(400, "invalid_workspace_path", "Workspace path escapes its managed root.", "Remove the unsafe link or select another directory.")
        return {"path": normalized.as_posix(), "entries": [], "truncated": False}
    directory = _resolve_allowed_path(workspace_root, normalized)
    managed_root = (workspace_root / normalized.parts[0]).resolve(strict=True)
    if not directory.is_dir():
        raise WorkspaceFileAPIError(400, "workspace_path_not_directory", "Workspace path is not a directory.", "Select a directory and retry.")
    try:
        children = []
        for index, child in enumerate(directory.iterdir()):
            if index >= _MAX_ENTRIES:
                break
            children.append(_entry_projection(child, workspace_root, managed_root, child.name))
        truncated = index >= _MAX_ENTRIES if "index" in locals() else False
    except WorkspaceFileAPIError:
        raise
    except OSError as exc:
        raise WorkspaceFileAPIError(409, "workspace_entries_unavailable", "Workspace directory is unavailable.", "Retry or select another directory.") from exc
    children.sort(key=lambda entry: (entry["kind"] != "directory", entry["name"].casefold(), entry["name"]))
    return {"path": normalized.as_posix(), "entries": children, "truncated": truncated}


def read_workspace_file(name: str, relative_path: str, user_config_root: Path | None) -> dict[str, Any]:
    config = _load_workspace(name, user_config_root)
    workspace_root = config.root_path.resolve()
    normalized = _normalize_relative_path(relative_path, allow_root=False)
    file_path = _resolve_allowed_path(workspace_root, normalized)
    if not file_path.is_file():
        raise WorkspaceFileAPIError(400, "workspace_path_not_file", "Workspace path is not a regular file.", "Select a file and retry.")
    try:
        stat = file_path.stat()
        if stat.st_size > _MAX_FILE_BYTES:
            raise WorkspaceFileAPIError(413, "workspace_file_too_large", "Workspace file is too large to display.", "Open the file in the local editor.")
        source = file_path.read_bytes()
    except WorkspaceFileAPIError:
        raise
    except OSError as exc:
        raise WorkspaceFileAPIError(409, "workspace_file_unavailable", "Workspace file is unavailable.", "Retry or select another file.") from exc
    if len(source) > _MAX_FILE_BYTES:
        raise WorkspaceFileAPIError(413, "workspace_file_too_large", "Workspace file is too large to display.", "Open the file in the local editor.")
    try:
        content = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceFileAPIError(415, "workspace_file_not_text", "Workspace file is not valid UTF-8 text.", "Open the file in the local editor.") from exc
    if "\0" in content:
        raise WorkspaceFileAPIError(415, "workspace_file_not_text", "Workspace file is not displayable text.", "Open the file in the local editor.")
    media_type = mimetypes.guess_type(file_path.name)[0] or "text/plain"
    return {
        "path": normalized.as_posix(),
        "name": file_path.name,
        "mediaType": media_type,
        "presentation": "markdown" if file_path.suffix.casefold() in {".md", ".markdown"} else "code",
        "size": len(source),
        "lineCount": len(content.splitlines()),
        "modifiedTime": _modified_time(stat.st_mtime),
        "content": content,
    }


def _load_workspace(name: str, user_config_root: Path | None) -> WorkspaceConfig:
    normalized_name = name.casefold()
    entry = next(
        (candidate for candidate in list_workspace_registry(user_config_root) if candidate.name.casefold() == normalized_name),
        None,
    )
    if entry is None:
        raise WorkspaceFileAPIError(404, "workspace_not_found", "Workspace is not registered.", "Refresh the workspace list.")
    try:
        return load_registered_workspace(entry.name, user_config_root)
    except ConfigurationError as exc:
        raise WorkspaceFileAPIError(409, "workspace_unavailable", "Workspace configuration is unavailable.", "Repair the registered workspace configuration.") from exc


def _normalize_relative_path(value: str, *, allow_root: bool) -> PurePosixPath:
    if not isinstance(value, str) or "\\" in value:
        raise WorkspaceFileAPIError(400, "invalid_workspace_path", "Workspace path must be relative.", "Select a workspace path and retry.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", "..", ".fsq"} for part in path.parts):
        raise WorkspaceFileAPIError(400, "invalid_workspace_path", "Workspace path must remain below cases or knowledge.", "Select a workspace path and retry.")
    if len(path.parts) > _MAX_DEPTH:
        raise WorkspaceFileAPIError(400, "workspace_path_too_deep", "Workspace path is too deep to browse.", "Select a shallower path.")
    if not path.parts:
        if allow_root:
            return path
        raise WorkspaceFileAPIError(400, "invalid_workspace_path", "A workspace file path is required.", "Select a file and retry.")
    if path.parts[0] not in _ALLOWED_ROOTS:
        raise WorkspaceFileAPIError(400, "invalid_workspace_path", "Workspace path must remain below cases or knowledge.", "Select a workspace path and retry.")
    return path


def _resolve_allowed_path(workspace_root: Path, relative_path: PurePosixPath) -> Path:
    allowed_root = workspace_root / relative_path.parts[0]
    candidate = workspace_root.joinpath(*relative_path.parts)
    try:
        resolved_root = allowed_root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise WorkspaceFileAPIError(404, "workspace_path_not_found", "Workspace path is unavailable.", "Refresh the workspace browser.") from exc
    if not resolved_root.is_relative_to(workspace_root) or not resolved.is_relative_to(resolved_root):
        raise WorkspaceFileAPIError(400, "invalid_workspace_path", "Workspace path escapes its managed root.", "Select a contained workspace path.")
    return resolved


def _entry_projection(path: Path, workspace_root: Path, managed_root: Path, fallback_name: str) -> dict[str, Any]:
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(managed_root):
            raise WorkspaceFileAPIError(400, "invalid_workspace_path", "Workspace entry escapes its managed root.", "Remove the unsafe link or select another directory.")
        stat = resolved.stat()
    except WorkspaceFileAPIError:
        raise
    except (OSError, RuntimeError) as exc:
        raise WorkspaceFileAPIError(409, "workspace_entry_unavailable", "Workspace entry is unavailable.", "Refresh the workspace browser.") from exc
    if resolved.is_dir():
        kind = "directory"
        size: int | None = None
    elif resolved.is_file():
        kind = "file"
        size = stat.st_size
    else:
        raise WorkspaceFileAPIError(409, "workspace_entry_unavailable", "Workspace entry type is unsupported.", "Open the workspace in the local editor.")
    return {
        "path": path.relative_to(workspace_root).as_posix(),
        "name": fallback_name,
        "kind": kind,
        "size": size,
        "modifiedTime": _modified_time(stat.st_mtime),
    }


def _managed_root_projection(workspace_root: Path, root_name: str) -> dict[str, Any]:
    path = workspace_root / root_name
    if path.exists():
        return _entry_projection(path, workspace_root, path, root_name)
    if path.is_symlink():
        raise WorkspaceFileAPIError(400, "invalid_workspace_path", "Workspace entry escapes its managed root.", "Remove the unsafe link or select another directory.")
    try:
        modified_time = _modified_time(workspace_root.stat().st_mtime)
    except OSError as exc:
        raise WorkspaceFileAPIError(409, "workspace_entry_unavailable", "Workspace entry is unavailable.", "Refresh the workspace browser.") from exc
    return {
        "path": root_name,
        "name": root_name,
        "kind": "directory",
        "size": None,
        "modifiedTime": modified_time,
    }


def _modified_time(value: float) -> str:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["WorkspaceFileAPIError", "list_workspace_entries", "read_workspace_file"]