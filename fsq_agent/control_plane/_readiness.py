# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from pathlib import Path
from typing import Any

from fsq_agent.config import Settings, load_platform_settings, validate_strict_core_settings
from fsq_agent.providers import prepare_model_provider_session

from ._evidence import safe_exception_message
from ._targets import target_readiness


def load_control_plane_settings(platform: str, workspace_path: Path) -> Settings:
    return load_platform_settings(platform, workspace_path)


def readiness(platform: str, workspace_path: Path) -> dict[str, Any]:
    try:
        settings = load_control_plane_settings(platform, workspace_path)
    except Exception as exc:  # noqa: BLE001
        record = _record("error", safe_exception_message(exc), "Fix the committed platform preset or workspace configuration.")
        return {"platform": platform, "workspace": record, "provider": record, "target": record, "strict": record}

    workspace_ready = settings.workspace.root_dir is not None and Path(settings.workspace.root_dir).is_dir()
    workspace = _record(
        "ready" if workspace_ready else "unavailable",
        "Workspace is ready." if workspace_ready else "Workspace is unavailable.",
        "Initialize the configured workspace directory." if not workspace_ready else "",
    )
    provider = provider_readiness(settings)
    target_ready, target_message, target_action = target_readiness(settings)
    target = _record("ready" if target_ready else "unavailable", target_message, target_action)
    try:
        validate_strict_core_settings(settings)
    except Exception as exc:  # noqa: BLE001
        strict = _record("unavailable", safe_exception_message(exc, settings=settings), "Configure the selected platform for strict execution.")
    else:
        strict = _record("ready", "Provider-free strict execution is ready.", "")
    return {"platform": platform, "workspace": workspace, "provider": provider, "target": target, "strict": strict}


def provider_readiness(settings: Settings) -> dict[str, str]:
    session = None
    try:
        session = prepare_model_provider_session(settings, interactive_auth=False)
        return _record("ready", "Model provider is configured for non-interactive use.", "")
    except Exception as exc:  # noqa: BLE001
        return _record("unavailable", safe_exception_message(exc, settings=settings), "Run fsq-agent init with a provider to complete local authentication.")
    finally:
        if session is not None:
            session.close_sync()


def require_provider(settings: Settings) -> None:
    session = prepare_model_provider_session(settings, interactive_auth=False)
    session.close_sync()


def _record(status: str, message: str, action: str) -> dict[str, str]:
    return {"status": status, "message": message, "action": action}


__all__ = ["load_control_plane_settings", "provider_readiness", "readiness", "require_provider"]
