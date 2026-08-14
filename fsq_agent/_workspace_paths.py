# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

from fsq_agent.models import ConfigurationError


def resolve_discovered_case_path(path: str | Path, discovery_root: Path) -> Path:
    root = discovery_root.expanduser().resolve()
    resolved = Path(path).expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ConfigurationError(
            "Discovered case path must stay within the case directory.",
            context={"path": str(path)},
        ) from exc
    return resolved


def resolve_workspace_cases_path(path: str | Path, cases_dir: Path) -> Path:
    root = cases_dir.expanduser().resolve()
    requested = Path(path).expanduser()
    candidate = requested if requested.is_absolute() else root / requested
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ConfigurationError(
            "Case path must stay within the workspace cases directory.",
            context={"path": str(requested)},
        ) from exc
    return resolved
