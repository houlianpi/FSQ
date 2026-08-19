# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

from pydantic import ValidationError

from fsq_agent.application._contracts import ApplicationError, ApplicationErrorCategory, ApplicationErrorCode, WorkspaceInitializeRequest, WorkspaceInitializeResult
from fsq_agent.config import add_workspace_platform as persist_workspace_platform
from fsq_agent.config import create_workspace as persist_workspace
from fsq_agent.config import initialize_workspace_root
from fsq_agent.config import update_workspace_platform as persist_workspace_platform_update
from fsq_agent.core import PlatformRuntimeService
from fsq_agent.models import AndroidWorkspaceTarget, ConfigurationError, MacOSWorkspaceTarget, WebWorkspaceTarget, WindowsWorkspaceTarget, WorkspaceConfig


def initialize_workspace(request: WorkspaceInitializeRequest) -> WorkspaceInitializeResult:
    root = request.current_directory.expanduser().resolve()
    target, installed = resolve_workspace_target(request)
    try:
        config = WorkspaceConfig(version=2, name=request.name or root.name, root_path=root, platform=request.platform, target=target, env=request.env)
        result = initialize_workspace_root(root_path=root, config=config, update_existing=request.update_existing, user_config_root=request.user_config_root)
    except (ConfigurationError, ValidationError, ValueError) as exc:
        raise _configuration_error(exc) from exc
    browser_path = target.browser_executable_path if isinstance(target, WebWorkspaceTarget) else None
    return WorkspaceInitializeResult(
        status=result.status, name=result.name, root_path=result.root_path, platform=result.platform, driver_status="installed" if installed else "ready", browser_executable_path=browser_path
    )


def resolve_workspace_target(request: WorkspaceInitializeRequest):
    """Check platform readiness and return one complete persistence-ready target."""
    runtime = PlatformRuntimeService()
    try:
        target = _target(request, runtime)
    except (ConfigurationError, ValidationError, ValueError) as exc:
        raise _configuration_error(exc) from exc
    check = runtime.check(request.platform)
    installed = False
    if check.status == "missing" and request.install_driver:
        check = runtime.install(request.platform)
        installed = check.ready
    if not check.ready:
        raise ApplicationError(
            code=ApplicationErrorCode.ENVIRONMENT_UNAVAILABLE, category=ApplicationErrorCategory.UNAVAILABLE, message=check.message, action=check.action, details={"platform": request.platform}
        )
    return target, installed


def create_workspace(*, parent_path: Path, configs: list[WorkspaceConfig | dict[str, object]], user_config_root: Path | None = None):
    resolved = [_resolve_config_target(config) for config in configs]
    return persist_workspace(parent_path=parent_path, configs=resolved, user_config_root=user_config_root)


def add_workspace_platform(*, name: str, root_path: Path, platform: str, target: dict[str, object], env: dict[str, str], user_config_root: Path | None = None):
    resolved, _ = resolve_workspace_target(_request_from_target(root_path, platform, target, env))
    return persist_workspace_platform(name=name, platform=platform, target=resolved, env=env, user_config_root=user_config_root)


def update_workspace_platform(
    *, name: str, root_path: Path, platform: str, target: dict[str, object], env: dict[str, str], expected_revision: str, user_config_root: Path | None = None
):
    resolved, _ = resolve_workspace_target(_request_from_target(root_path, platform, target, env))
    return persist_workspace_platform_update(
        name=name, platform=platform, target=resolved, env=env, expected_revision=expected_revision, user_config_root=user_config_root
    )


def _resolve_config_target(config: WorkspaceConfig | dict[str, object]) -> WorkspaceConfig:
    if not isinstance(config, WorkspaceConfig):
        root_path = Path(str(config["root_path"]))
        platform = str(config["platform"])
        target = config["target"]
        env = config["env"]
        if not isinstance(target, dict) or not isinstance(env, dict):
            raise TypeError("Workspace target and environment must be objects.")
        request = _request_from_target(root_path, platform, target, env)  # type: ignore[arg-type]
        resolved, _ = resolve_workspace_target(request)
        return WorkspaceConfig.model_validate({**config, "target": resolved})
    request = _request_from_target(config.root_path, config.platform, config.target.model_dump(), dict(config.env))
    resolved, _ = resolve_workspace_target(request)
    return config.model_copy(update={"target": resolved})


def _request_from_target(root: Path, platform: str, target: dict[str, object], env: dict[str, str]) -> WorkspaceInitializeRequest:
    return WorkspaceInitializeRequest.model_validate({"current_directory": root, "platform": platform, "env": env, **target})


def _configuration_error(exc: ConfigurationError | ValidationError | ValueError) -> ApplicationError:
    details = exc.context if isinstance(exc, ConfigurationError) else {}
    return ApplicationError(
        code=ApplicationErrorCode.CONFIGURATION_INVALID,
        category=ApplicationErrorCategory.CONFIGURATION,
        message=str(exc).splitlines()[0],
        action="Correct the workspace target and retry.",
        details=details,
    )


def _target(request: WorkspaceInitializeRequest, runtime: PlatformRuntimeService):
    _validate_platform_options(request)
    if request.platform == "android":
        return AndroidWorkspaceTarget(app_id=request.app_id)
    if request.platform == "web":
        if request.browser_channel is None:
            raise ValueError("Web workspace initialization requires --browser-channel.")
        path = request.browser_executable_path
        if path is None:
            candidates = runtime.discover_web_executables(request.browser_channel)
            if not candidates:
                raise ValueError("No compatible Web browser executable was found; install the selected channel or pass --browser-executable-path.")
            if len(candidates) != 1:
                raise ValueError("Multiple compatible Web browser executables were found; pass --browser-executable-path.")
            path = candidates[0]
        resolved = Path(path).expanduser().resolve()
        _validate_local_file(resolved, "Web browser executable path", executable=True)
        if not runtime.web_executable_matches_channel(request.browser_channel, resolved):
            raise ValueError("Web browser executable path does not match the selected channel.")
        return WebWorkspaceTarget(browser_channel=request.browser_channel, browser_executable_path=resolved)
    if request.platform == "windows":
        target = WindowsWorkspaceTarget(app_path=request.app_path, window_title_re=request.window_title_re, launch_args=request.launch_args or "")
        resolved = target.app_path.expanduser().resolve()
        _validate_local_file(resolved, "Windows application path", executable=True)
        return target.model_copy(update={"app_path": resolved})
    target = MacOSWorkspaceTarget(bundle_id=request.bundle_id, app_path=request.app_path)
    if target.app_path is not None:
        resolved = target.app_path.expanduser().resolve()
        if not resolved.exists() or not ((resolved.is_dir() and resolved.suffix.casefold() == ".app") or resolved.is_file()):
            raise ValueError("macOS application path must identify an existing app bundle or executable.")
        target = target.model_copy(update={"app_path": resolved})
    return target


def _validate_local_file(path: Path, description: str, *, executable: bool) -> None:
    if not path.exists():
        raise ValueError(f"{description} does not exist.")
    if not path.is_file():
        raise ValueError(f"{description} must be a file.")
    if executable and not __import__("os").access(path, __import__("os").X_OK):
        raise ValueError(f"{description} must be executable.")


def _validate_platform_options(request: WorkspaceInitializeRequest) -> None:
    supplied = {
        "app_id": request.app_id,
        "browser_channel": request.browser_channel,
        "browser_executable_path": request.browser_executable_path,
        "app_path": request.app_path,
        "window_title_re": request.window_title_re,
        "launch_args": request.launch_args,
        "bundle_id": request.bundle_id,
    }
    allowed = {
        "android": {"app_id"},
        "web": {"browser_channel", "browser_executable_path"},
        "windows": {"app_path", "window_title_re", "launch_args"},
        "macos": {"app_path", "bundle_id"},
    }[request.platform]
    invalid = sorted(name for name, value in supplied.items() if value is not None and name not in allowed)
    if invalid:
        options = ", ".join(f"--{name.replace('_', '-')}" for name in invalid)
        raise ValueError(f"{options} cannot be used with --platform {request.platform}.")
