# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from fsq_agent.config._paths import resolve_runtime_paths
from fsq_agent.config._settings import Settings
from fsq_agent.models import ConfigurationError

DEFAULT_CONFIG_PATHS = (Path("config.yaml"), Path("config.yml"))
PLATFORM_CONFIG_PATHS = {
    "android": Path("config.android.yaml"),
    "web": Path("config.web.yaml"),
    "windows": Path("config.windows.yaml"),
    "macos": Path("config.macos.yaml"),
}
DEFAULT_ENV_PATH = Path(".env")
ANDROID_APP_ID_ENV = "FSQ_ANDROID_APP_ID"
ANDROID_SERIAL_ENV = "FSQ_ANDROID_SERIAL"
WEB_BROWSER_EXECUTABLE_PATH_ENV = "FSQ_WEB_BROWSER_EXECUTABLE_PATH"
WINDOWS_APP_PATH_ENV = "FSQ_WINDOWS_APP_PATH"
WINDOWS_BACKEND_KIND_ENV = "FSQ_WINDOWS_BACKEND_KIND"
WINDOWS_WINDOW_TITLE_RE_ENV = "FSQ_WINDOWS_WINDOW_TITLE_RE"
WINDOWS_LAUNCH_ARGS_ENV = "FSQ_WINDOWS_LAUNCH_ARGS"
MACOS_APPIUM_SERVER_URL_ENV = "FSQ_MACOS_APPIUM_SERVER_URL"
MACOS_BUNDLE_ID_ENV = "FSQ_MACOS_BUNDLE_ID"
MACOS_APP_PATH_ENV = "FSQ_MACOS_APP_PATH"
LLM_PROVIDER_ENV = "FSQ_LLM_PROVIDER"
AZURE_OPENAI_BASE_URL_ENV = "AZURE_OPENAI_BASE_URL"
AZURE_OPENAI_MODEL_ENV = "AZURE_OPENAI_MODEL"
AZURE_OPENAI_API_KEY_ENV = "AZURE_OPENAI_API_KEY"
GITHUB_COPILOT_MODEL = "gpt-5.5"
SUPPORTED_LLM_PROVIDERS = ("github_copilot", "azure_openai")
CHROME_EXECUTABLE_NAMES = {"chrome", "chrome.exe", "google chrome", "google-chrome", "google-chrome-stable"}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file) or {}
    except OSError as exc:
        raise ConfigurationError("Unable to read configuration file.", context={"path": str(path)}) from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration file must contain a YAML mapping.", context={"path": str(path)})
    return data


def _find_default_config() -> Path | None:
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path
    return None


def load_settings(path: str | Path | None = None, workspace: str | Path | None = None) -> Settings:
    config_path = Path(path) if path is not None else _find_default_config()
    _load_env_files(config_path)
    data = _read_yaml(config_path) if config_path else {}
    _reject_obsolete_settings(data)
    try:
        settings = Settings.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError("Invalid configuration.", context={"errors": exc.errors()}) from exc
    if workspace is not None:
        settings.workspace.root_dir = Path(workspace)
    _apply_environment_settings(settings)
    base_dir = config_path.parent if config_path is not None else Path.cwd()
    resolve_runtime_paths(settings, base_dir)
    return settings


def resolve_platform_config_path(platform: str) -> Path:
    platform_id = platform.strip().lower()
    config_path = PLATFORM_CONFIG_PATHS.get(platform_id)
    if config_path is None:
        raise ConfigurationError(
            "Unsupported harness platform.",
            context={"platform": platform, "supported": sorted(PLATFORM_CONFIG_PATHS)},
        )
    if not config_path.is_file():
        raise ConfigurationError(
            "Platform configuration file is missing.",
            context={"platform": platform_id, "path": str(config_path)},
        )
    return config_path


def load_platform_settings(platform: str, workspace: str | Path | None = None) -> Settings:
    platform_id = platform.strip().lower()
    settings = load_settings(resolve_platform_config_path(platform_id), workspace)
    if settings.harness.platform != platform_id:
        raise ConfigurationError(
            "Platform configuration does not match requested platform.",
            context={"platform": platform_id, "configured_platform": settings.harness.platform},
        )
    return settings


def _reject_obsolete_settings(data: dict[str, Any]) -> None:
    if "verification" in data:
        raise ConfigurationError(
            "Obsolete verification configuration is no longer supported.",
            context={"config_key": "verification", "removed_key": "verification.mode"},
        )
    harness = data.get("harness")
    if isinstance(harness, dict) and "strict_core" in harness:
        raise ConfigurationError(
            "Obsolete strict-core step interval configuration is no longer supported; use execution.post_action_delay_seconds instead.",
            context={"config_key": "harness.strict_core", "replacement_key": "execution.post_action_delay_seconds"},
        )
    openai_agents = data.get("openai_agents")
    if not isinstance(openai_agents, dict):
        return
    prompt = openai_agents.get("prompt")
    if not isinstance(prompt, dict):
        return
    for key in ("custom_instructions", "custom_instructions_path"):
        if key in prompt:
            raise ConfigurationError(
                "Obsolete custom instruction configuration is no longer supported; move guidance into knowledge/project.md or configured skills.",
                context={"config_key": f"openai_agents.prompt.{key}"},
            )


def _load_env_files(config_path: Path | None) -> None:
    candidates = [DEFAULT_ENV_PATH]
    if config_path is not None:
        config_env_path = config_path.parent / DEFAULT_ENV_PATH
        if config_env_path not in candidates:
            candidates.append(config_env_path)
    for env_path in candidates:
        _load_env_file(env_path)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigurationError("Unable to read .env file.", context={"path": str(path)}) from exc
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ConfigurationError(
                "Invalid .env line; expected KEY=VALUE.",
                context={"path": str(path), "line": line_number},
            )
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigurationError(
                "Invalid .env line; key cannot be empty.",
                context={"path": str(path), "line": line_number},
            )
        os.environ.setdefault(key, _strip_env_value(value.strip()))


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _apply_environment_settings(settings: Settings) -> None:
    provider = _env_value(LLM_PROVIDER_ENV)
    if provider:
        normalized_provider = provider.strip().lower()
        if normalized_provider not in SUPPORTED_LLM_PROVIDERS:
            raise ConfigurationError(
                f"LLM provider environment variable {LLM_PROVIDER_ENV} is invalid.",
                context={"provider_env": LLM_PROVIDER_ENV, "value": provider, "supported": list(SUPPORTED_LLM_PROVIDERS)},
            )
        settings.openai_agents.provider = normalized_provider  # type: ignore[assignment]

    app_id = _env_value(ANDROID_APP_ID_ENV)
    serial = _env_value(ANDROID_SERIAL_ENV)
    if app_id:
        settings.harness.android.app_id = app_id
    if serial:
        settings.harness.android.serial = serial
    browser_executable_path = _env_value(WEB_BROWSER_EXECUTABLE_PATH_ENV)
    if browser_executable_path:
        settings.harness.web.browser_executable_path = browser_executable_path
    windows_app_path = _env_value(WINDOWS_APP_PATH_ENV)
    windows_backend_kind = _env_value(WINDOWS_BACKEND_KIND_ENV)
    windows_window_title_re = _env_value(WINDOWS_WINDOW_TITLE_RE_ENV)
    windows_launch_args = _env_value(WINDOWS_LAUNCH_ARGS_ENV)
    if windows_app_path:
        settings.harness.windows.app_path = Path(windows_app_path)
    if windows_backend_kind:
        settings.harness.windows.backend_kind = _validate_windows_backend_kind(windows_backend_kind)
    if windows_window_title_re:
        settings.harness.windows.window_title_re = windows_window_title_re
    if windows_launch_args:
        settings.harness.windows.launch_args = _parse_windows_launch_args(windows_launch_args)
    macos_appium_server_url = _env_value(MACOS_APPIUM_SERVER_URL_ENV)
    macos_bundle_id = _env_value(MACOS_BUNDLE_ID_ENV)
    macos_app_path = _env_value(MACOS_APP_PATH_ENV)
    if macos_appium_server_url:
        settings.harness.macos.appium_server_url = macos_appium_server_url
    if macos_bundle_id:
        settings.harness.macos.bundle_id = macos_bundle_id
    if macos_app_path:
        settings.harness.macos.app_path = macos_app_path

    if settings.openai_agents.provider == "github_copilot":
        settings.openai_agents.model = GITHUB_COPILOT_MODEL
        settings.openai_agents.base_url = ""
        return

    settings.openai_agents.model = _env_value(AZURE_OPENAI_MODEL_ENV) or ""
    base_url = _env_value(AZURE_OPENAI_BASE_URL_ENV) or ""
    if "/openai/responses" in base_url:
        base_url = base_url.split("/openai/responses", 1)[0] + "/openai/v1/"
    elif "/openai/v1" in base_url:
        base_url = base_url.split("/openai/v1", 1)[0] + "/openai/v1/"
    elif base_url.endswith((".openai.azure.com", ".cognitiveservices.azure.com")):
        base_url = base_url.rstrip("/") + "/openai/v1/"
    settings.openai_agents.base_url = base_url


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _validate_windows_backend_kind(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"uia", "win32"}:
        return normalized
    raise ConfigurationError(
        f"Windows pywinauto backend kind environment variable {WINDOWS_BACKEND_KIND_ENV} is invalid.",
        context={"backend_kind_env": WINDOWS_BACKEND_KIND_ENV, "value": value, "supported": ["uia", "win32"]},
    )


def _parse_windows_launch_args(value: str) -> list[str]:
    try:
        return _split_windows_command_line(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Windows launch arguments environment variable {WINDOWS_LAUNCH_ARGS_ENV} could not be parsed.",
            context={"launch_args_env": WINDOWS_LAUNCH_ARGS_ENV, "error": str(exc)},
        ) from exc


def _split_windows_command_line(value: str) -> list[str]:
    args: list[str] = []
    arg: list[str] = []
    in_quotes = False
    token_started = False
    index = 0
    length = len(value)
    while index < length:
        char = value[index]
        if char.isspace() and not in_quotes:
            if token_started:
                args.append("".join(arg))
                arg = []
                token_started = False
            index += 1
            continue
        if char == "\\":
            slash_start = index
            while index < length and value[index] == "\\":
                index += 1
            slash_count = index - slash_start
            if index < length and value[index] == '"':
                arg.extend("\\" * (slash_count // 2))
                if slash_count % 2:
                    arg.append('"')
                else:
                    in_quotes = not in_quotes
                token_started = True
                index += 1
                continue
            arg.extend("\\" * slash_count)
            token_started = True
            continue
        if char == '"':
            in_quotes = not in_quotes
            token_started = True
            index += 1
            continue
        arg.append(char)
        token_started = True
        index += 1
    if in_quotes:
        raise ValueError("No closing quotation")
    if token_started:
        args.append("".join(arg))
    return args


def validate_provider_settings(settings: Settings) -> None:
    _validate_openai_provider_settings(settings)


def validate_runtime_settings(settings: Settings) -> None:
    validate_provider_settings(settings)
    _validate_harness_settings(settings)


def validate_strict_core_settings(settings: Settings, requires_ai_assertion: bool = False) -> None:
    _validate_harness_settings(settings)
    if requires_ai_assertion:
        validate_provider_settings(settings)


def _validate_openai_provider_settings(settings: Settings) -> None:
    if settings.openai_agents.provider not in SUPPORTED_LLM_PROVIDERS:
        raise ConfigurationError(
            "OpenAI Agents SDK provider is unsupported.",
            context={"provider_env": LLM_PROVIDER_ENV, "provider": settings.openai_agents.provider, "supported": list(SUPPORTED_LLM_PROVIDERS)},
        )
    if not settings.openai_agents.model.strip():
        raise ConfigurationError(
            "OpenAI Agents SDK model deployment name is required.",
            context={"model_env": AZURE_OPENAI_MODEL_ENV if settings.openai_agents.provider == "azure_openai" else None},
        )
    if settings.openai_agents.provider == "azure_openai" and not settings.openai_agents.base_url.endswith("/openai/v1/"):
        raise ConfigurationError(
            "Azure OpenAI base URL must use the /openai/v1/ form.",
            context={"base_url_env": AZURE_OPENAI_BASE_URL_ENV, "base_url": settings.openai_agents.base_url},
        )
    api_key = os.getenv(AZURE_OPENAI_API_KEY_ENV)
    if settings.openai_agents.provider == "azure_openai" and not api_key:
        raise ConfigurationError(
            "Azure OpenAI API key environment variable is not set.",
            context={"api_key_env": AZURE_OPENAI_API_KEY_ENV},
        )
    if settings.openai_agents.provider == "azure_openai" and api_key and api_key.lower().startswith("replace-with"):
        raise ConfigurationError(
            "Azure OpenAI API key environment variable still contains a placeholder value.",
            context={"api_key_env": AZURE_OPENAI_API_KEY_ENV},
        )


def _validate_harness_settings(settings: Settings) -> None:
    if settings.harness.platform == "android":
        _validate_android_harness_settings(settings)
        return
    if settings.harness.platform == "web":
        _validate_web_harness_settings(settings)
        return
    if settings.harness.platform == "windows":
        _validate_windows_harness_settings(settings)
        return
    if settings.harness.platform == "macos":
        _validate_macos_harness_settings(settings)
        return
    raise ConfigurationError(
        "Unsupported harness platform.",
        context={"platform": settings.harness.platform, "supported": ["android", "web", "windows", "macos"]},
    )


def _validate_android_harness_settings(settings: Settings) -> None:
    if settings.harness.android.backend != "uiautomator2":
        raise ConfigurationError(
            "Unsupported Android harness backend.",
            context={"backend": settings.harness.android.backend, "supported": ["uiautomator2"]},
        )


def _validate_web_harness_settings(settings: Settings) -> None:
    if settings.harness.web.backend != "playwright":
        raise ConfigurationError(
            "Unsupported Web harness backend.",
            context={"backend": settings.harness.web.backend, "supported": ["playwright"]},
        )
    _validate_web_browser_executable_path(settings)


def _validate_web_browser_executable_path(settings: Settings) -> None:
    browser_path = settings.harness.web.browser_executable_path
    if browser_path is None:
        raise ConfigurationError(
            "Web browser executable path environment variable is not set.",
            context={"executable_path_env": WEB_BROWSER_EXECUTABLE_PATH_ENV, "channel": settings.harness.web.channel},
        )
    if not browser_path.exists():
        raise ConfigurationError(
            "Configured Web browser executable path does not exist.",
            context={"executable_path_env": WEB_BROWSER_EXECUTABLE_PATH_ENV, "path": str(browser_path)},
        )
    if not browser_path.is_file():
        raise ConfigurationError(
            "Configured Web browser executable path must point to the browser executable file.",
            context={"executable_path_env": WEB_BROWSER_EXECUTABLE_PATH_ENV, "path": str(browser_path)},
        )
    if settings.harness.web.channel == "chrome" and browser_path.name.casefold() not in CHROME_EXECUTABLE_NAMES:
        raise ConfigurationError(
            "Configured Web browser executable path does not match harness.web.channel.",
            context={
                "executable_path_env": WEB_BROWSER_EXECUTABLE_PATH_ENV,
                "path": str(browser_path),
                "channel": settings.harness.web.channel,
                "expected_file_names": sorted(CHROME_EXECUTABLE_NAMES),
            },
        )
    if os.name != "nt" and not os.access(browser_path, os.X_OK):
        raise ConfigurationError(
            "Configured Web browser executable path is not executable.",
            context={"executable_path_env": WEB_BROWSER_EXECUTABLE_PATH_ENV, "path": str(browser_path)},
        )


def _validate_windows_harness_settings(settings: Settings) -> None:
    if settings.harness.windows.backend != "pywinauto":
        raise ConfigurationError(
            "Unsupported Windows harness backend.",
            context={"backend": settings.harness.windows.backend, "supported": ["pywinauto"]},
        )
    app_path = settings.harness.windows.app_path
    if app_path is None:
        raise ConfigurationError(
            f"Windows app path environment variable {WINDOWS_APP_PATH_ENV} is not set.",
            context={"app_path_env": WINDOWS_APP_PATH_ENV, "legacy_config_key": "harness.windows.app_path"},
        )
    if not app_path.exists():
        raise ConfigurationError(
            "Configured Windows app path does not exist.",
            context={"app_path_env": WINDOWS_APP_PATH_ENV, "path": str(app_path)},
        )
    if not app_path.is_file():
        raise ConfigurationError(
            "Configured Windows app path must point to the application executable file.",
            context={"app_path_env": WINDOWS_APP_PATH_ENV, "path": str(app_path)},
        )


def _validate_macos_harness_settings(settings: Settings) -> None:
    if settings.harness.macos.backend != "appium_mac2":
        raise ConfigurationError(
            "Unsupported macOS harness backend.",
            context={"backend": settings.harness.macos.backend, "supported": ["appium_mac2"]},
        )
    if not settings.harness.macos.appium_server_url:
        raise ConfigurationError(
            "macOS Appium server URL environment variable is not set.",
            context={"server_url_env": MACOS_APPIUM_SERVER_URL_ENV},
        )
    app_path = settings.harness.macos.app_path
    bundle_id = settings.harness.macos.bundle_id
    if app_path is None and bundle_id is None:
        raise ConfigurationError(
            "macOS app identity is not configured.",
            context={"bundle_id_env": MACOS_BUNDLE_ID_ENV, "app_path_env": MACOS_APP_PATH_ENV},
        )
    if app_path is None:
        return
    if not app_path.exists():
        raise ConfigurationError(
            "Configured macOS app path does not exist.",
            context={"app_path_env": MACOS_APP_PATH_ENV, "path": str(app_path)},
        )
    if not (app_path.is_dir() or app_path.is_file()):
        raise ConfigurationError(
            "Configured macOS app path must point to an application bundle or executable.",
            context={"app_path_env": MACOS_APP_PATH_ENV, "path": str(app_path)},
        )
