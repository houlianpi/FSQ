# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from fsq_agent.config import Settings, UserProviderConfig, activate_github_copilot_provider
from fsq_agent.models import ConfigurationError
from fsq_agent.providers._azure_openai import ProviderClientConfig

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

DEVICE_CODE_URL = "https://github.com/login/device/code"
# This is a public OAuth endpoint URL, not a credential or secret token.
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105
CLIENT_ID = "Iv1.b507a08c87ecfe98"
GITHUB_OAUTH_SCOPE = "read:user"
GITHUB_API_VERSION = "2022-11-28"
# This is a public Copilot service endpoint URL, not a credential or secret token.
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"  # noqa: S105
COPILOT_USER_URL = "https://api.github.com/copilot_internal/user"
COPILOT_AUTH_TIMEOUT_SECONDS = 20.0

COPILOT_BASE_URLS: dict[str, str] = {
    "individual": "https://api.githubcopilot.com",
    "business": "https://api.business.githubcopilot.com",
    "enterprise": "https://api.enterprise.githubcopilot.com",
}

COPILOT_EDITOR_HEADERS: dict[str, str] = {
    "editor-version": "vscode/1.99.0",
    "editor-plugin-version": "copilot-chat/0.38.2",
    "user-agent": "GitHubCopilotChat/0.38.2",
    "x-github-api-version": GITHUB_API_VERSION,
}

COPILOT_MODEL_HEADERS: dict[str, str] = {
    "copilot-integration-id": "vscode-chat",
    "editor-version": "vscode/1.99.0",
    "editor-plugin-version": "copilot-chat/0.38.2",
    "user-agent": "GitHubCopilotChat/0.38.2",
    "openai-intent": "conversation-agent",
}


@dataclass(frozen=True)
class CopilotToken:
    token: str
    expires_at: float


@dataclass(frozen=True)
class CachedCopilotProviderToken:
    token: str
    expires_at: float
    plan: str


@dataclass(frozen=True)
class GitHubDeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    expires_at: float
    poll_interval_seconds: int


def build_github_copilot_client_config(settings: Settings) -> ProviderClientConfig:
    cached_provider_token = _load_provider_token(settings.openai_agents.provider_token)
    if cached_provider_token:
        return _client_config_from_cached_provider_token(settings, cached_provider_token)
    return refresh_github_copilot_client_config(settings)


def refresh_github_copilot_client_config(settings: Settings) -> ProviderClientConfig:
    github_payload = settings.openai_agents.github_token
    github_token = _load_github_token(github_payload)
    if github_token is None:
        raise ConfigurationError("GitHub Copilot authentication is not configured. Authenticate in Control Plane Config.")
    user_config_root = settings.openai_agents.user_config_root
    if user_config_root is None:
        raise ConfigurationError("GitHub Copilot user configuration root is unavailable.")
    plan = _get_copilot_plan(github_token)
    copilot_token = _get_copilot_token(github_token)
    provider_payload: dict[str, object] = {
        "token": copilot_token.token,
        "expires_at": copilot_token.expires_at,
        "plan": plan,
    }
    activate_github_copilot_provider(
        model=settings.openai_agents.model,
        github_token=github_payload or {},
        provider_token=provider_payload,
        user_config_root=user_config_root,
    )
    settings.openai_agents.provider_token = provider_payload
    return _client_config_from_cached_provider_token(
        settings,
        CachedCopilotProviderToken(token=copilot_token.token, expires_at=copilot_token.expires_at, plan=plan),
    )


def _client_config_from_cached_provider_token(
    settings: Settings,
    provider_token: CachedCopilotProviderToken,
) -> ProviderClientConfig:
    model = settings.openai_agents.model.strip()
    if not model:
        raise ConfigurationError("GitHub Copilot model name is required.")
    return ProviderClientConfig(
        provider="github_copilot",
        model=model,
        api_key=provider_token.token,
        base_url=COPILOT_BASE_URLS[provider_token.plan],
        default_headers=COPILOT_MODEL_HEADERS,
        metadata={"endpoint_family": "github_copilot", "copilot_plan": provider_token.plan},
    )


def _load_github_token(data: dict[str, object] | None) -> str | None:
    if data is None:
        return None
    expires_at = data.get("expires_at")
    if isinstance(expires_at, int | float) and time.time() >= expires_at - 60:
        return None
    token = data.get("access_token")
    return token if isinstance(token, str) and token else None


def _load_provider_token(data: dict[str, object] | None) -> CachedCopilotProviderToken | None:
    if data is None:
        return None
    expires_at = data.get("expires_at")
    if not isinstance(expires_at, int | float) or time.time() >= expires_at - 60:
        return None
    token = data.get("token")
    plan = data.get("plan")
    if not isinstance(token, str) or not token or plan not in COPILOT_BASE_URLS:
        return None
    return CachedCopilotProviderToken(token=token, expires_at=expires_at, plan=plan)


def request_github_copilot_device_code() -> GitHubDeviceCode:
    try:
        response = httpx.post(
            DEVICE_CODE_URL,
            data={"client_id": CLIENT_ID, "scope": GITHUB_OAUTH_SCOPE},
            headers={"Accept": "application/json"},
            timeout=COPILOT_AUTH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ConfigurationError("GitHub device-code request failed.", context={"error": str(exc)}) from exc
    try:
        data = response.json()
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("GitHub device-code response was invalid.") from exc
    return _parse_device_code(data)


def _parse_device_code(data: object) -> GitHubDeviceCode:
    if not isinstance(data, dict):
        raise ConfigurationError("GitHub device-code response was invalid.")
    device_code = data.get("device_code")
    user_code = data.get("user_code")
    verification_uri = data.get("verification_uri")
    interval = data.get("interval", 5)
    expires_in = data.get("expires_in", 900)
    if not all(isinstance(value, str) and value for value in (device_code, user_code, verification_uri)):
        raise ConfigurationError("GitHub device-code response was invalid.")
    if not isinstance(interval, int | float) or interval <= 0:
        raise ConfigurationError("GitHub device-code response was invalid.")
    if not isinstance(expires_in, int | float) or expires_in <= 0:
        raise ConfigurationError("GitHub device-code response was invalid.")
    return GitHubDeviceCode(
        device_code=device_code,
        user_code=user_code,
        verification_uri=verification_uri,
        expires_at=time.time() + float(expires_in),
        poll_interval_seconds=max(1, int(interval)),
    )


def complete_github_copilot_device_flow(
    device_code: GitHubDeviceCode,
    *,
    model: str,
    cancel_requested: Callable[[], bool],
    user_config_root: str | Path | None = None,
) -> UserProviderConfig:
    normalized_model = model.strip()
    if not normalized_model:
        raise ConfigurationError("GitHub Copilot model name is required.")
    wait = device_code.poll_interval_seconds
    while time.time() < device_code.expires_at:
        _raise_if_device_flow_cancelled(cancel_requested)
        time.sleep(wait)
        _raise_if_device_flow_cancelled(cancel_requested)
        try:
            response = httpx.post(
                ACCESS_TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "device_code": device_code.device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
                timeout=COPILOT_AUTH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConfigurationError("GitHub device-code polling failed.", context={"error": str(exc)}) from exc
        _raise_if_device_flow_cancelled(cancel_requested)
        data = response.json()
        github_token = data.get("access_token")
        if isinstance(github_token, str) and github_token:
            github_payload: dict[str, object] = {"access_token": github_token}
            expires_in = data.get("expires_in")
            if isinstance(expires_in, int | float):
                github_payload["expires_at"] = time.time() + float(expires_in)
            plan = _get_copilot_plan(github_token)
            _raise_if_device_flow_cancelled(cancel_requested)
            copilot_token = _get_copilot_token(github_token)
            _raise_if_device_flow_cancelled(cancel_requested)
            return activate_github_copilot_provider(
                model=normalized_model,
                github_token=github_payload,
                provider_token={"token": copilot_token.token, "expires_at": copilot_token.expires_at, "plan": plan},
                user_config_root=user_config_root,
            )
        error = data.get("error", "")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            updated_wait = data.get("interval", wait + 5)
            wait = int(updated_wait) if isinstance(updated_wait, int | float) and updated_wait > 0 else wait + 5
            continue
        if error == "expired_token":
            raise ConfigurationError("GitHub device code expired. Please try again.")
        if error == "access_denied":
            raise ConfigurationError("GitHub device-code authorization was denied.")
        raise ConfigurationError("GitHub device-code OAuth failed.", context={"error": error})
    raise ConfigurationError("GitHub device code expired. Please try again.")


def _raise_if_device_flow_cancelled(cancel_requested: Callable[[], bool]) -> None:
    if cancel_requested():
        raise ConfigurationError("GitHub device-code authentication was cancelled.")


def _get_copilot_token(github_token: str) -> CopilotToken:
    try:
        response = httpx.get(
            COPILOT_TOKEN_URL,
            headers={
                "authorization": f"token {github_token}",
                "accept": "application/json",
                **COPILOT_EDITOR_HEADERS,
            },
            timeout=COPILOT_AUTH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ConfigurationError(
            "GitHub Copilot token exchange failed. Confirm the signed-in account has Copilot access.",
            context={"status_code": exc.response.status_code},
        ) from exc
    except httpx.HTTPError as exc:
        raise ConfigurationError("GitHub Copilot token exchange failed.", context={"error": str(exc)}) from exc
    data = response.json()
    token = data.get("token")
    if not token:
        raise ConfigurationError("GitHub Copilot token response did not include a token.")
    return CopilotToken(token=token, expires_at=data.get("expires_at", time.time() + 600))


def _get_copilot_plan(github_token: str) -> str:
    try:
        response = httpx.get(
            COPILOT_USER_URL,
            headers={
                "authorization": f"token {github_token}",
                "accept": "application/json",
                **COPILOT_EDITOR_HEADERS,
            },
            timeout=COPILOT_AUTH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ConfigurationError(
            "GitHub Copilot plan detection failed. Confirm the signed-in account has Copilot access.",
            context={"status_code": exc.response.status_code},
        ) from exc
    except httpx.HTTPError as exc:
        raise ConfigurationError("GitHub Copilot plan detection failed.", context={"error": str(exc)}) from exc
    data = response.json()
    plan = data.get("copilot_plan")
    if plan not in COPILOT_BASE_URLS:
        raise ConfigurationError("Unknown GitHub Copilot plan.", context={"plan": plan})
    return plan
