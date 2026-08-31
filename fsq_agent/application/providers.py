# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Callable
from pathlib import Path

from fsq_agent.application.contracts import ApplicationError, ApplicationErrorCategory, ApplicationErrorCode, ProviderConfigurationResult, ProviderStatusResult
from fsq_agent.config import Settings, load_user_provider_config, refresh_provider_settings, save_azure_openai_provider
from fsq_agent.providers import (
    GitHubCopilotModel,
    GitHubDeviceCode,
    activate_github_copilot_authorization,
    check_provider_readiness,
    complete_github_copilot_device_flow,
    list_github_copilot_models,
    request_github_copilot_device_code,
)


def configure_azure_openai(*, base_url: str, model: str, api_key: str, user_config_root: str | Path | None = None) -> ProviderConfigurationResult:
    try:
        saved = save_azure_openai_provider(base_url=base_url, model=model, api_key=api_key, user_config_root=user_config_root)
    except Exception as exc:
        raise _provider_error("Azure OpenAI configuration failed.", "Check the endpoint, model, and API key, then retry.") from exc
    return ProviderConfigurationResult(provider="azure_openai", model=saved.provider.model if saved.provider is not None else "")


def request_github_device_code() -> GitHubDeviceCode:
    try:
        return request_github_copilot_device_code()
    except Exception as exc:
        raise _provider_error("GitHub Copilot sign-in could not be started.", "Check network access and retry.") from exc


def complete_github_configuration(
    device_code: GitHubDeviceCode, *, model: str | None, select_model: Callable[[tuple[GitHubCopilotModel, ...]], str], cancel_requested: Callable[[], bool], user_config_root: str | Path | None = None
) -> ProviderConfigurationResult:
    try:
        authorization = complete_github_copilot_device_flow(device_code, cancel_requested=cancel_requested)
        models = list_github_copilot_models(authorization)
        selected = model.strip() if model else select_model(models).strip()
        _validate_selected_model(selected, models)
        saved = activate_github_copilot_authorization(authorization, model=selected, user_config_root=user_config_root)
    except Exception as exc:
        raise _provider_error("GitHub Copilot configuration failed.", "Retry sign-in and select an available model.") from exc
    return ProviderConfigurationResult(provider="github_copilot", model=saved.provider.model if saved.provider is not None else selected)


def provider_status(*, user_config_root: str | Path | None = None) -> ProviderStatusResult:
    try:
        configured = load_user_provider_config(user_config_root)
        if configured.provider is None:
            return ProviderStatusResult(status="unavailable", configured=False, authenticated=False, message="No model Provider is configured.", action="Run fsq providers configure.")
        ready, message, action = check_provider_readiness(refresh_provider_settings(Settings(), user_config_root))
        return ProviderStatusResult(
            status="ready" if ready else "unavailable", configured=True, provider=configured.provider.type, model=configured.provider.model, authenticated=ready, message=message, action=action or None
        )
    except Exception as exc:
        raise _provider_error("Provider status could not be read.", "Repair the user Provider configuration and retry.", configuration=True) from exc


def _provider_error(message: str, action: str, *, configuration: bool = False) -> ApplicationError:
    return ApplicationError(
        code=ApplicationErrorCode.CONFIGURATION_INVALID if configuration else ApplicationErrorCode.PROVIDER_UNAVAILABLE,
        category=ApplicationErrorCategory.CONFIGURATION if configuration else ApplicationErrorCategory.UNAVAILABLE,
        message=message,
        action=action,
    )


def _validate_selected_model(selected: str, models: tuple[GitHubCopilotModel, ...]) -> None:
    if selected not in {item.id for item in models}:
        raise ValueError("selected model is not offered")


__all__ = ["complete_github_configuration", "configure_azure_openai", "provider_status", "request_github_device_code"]
