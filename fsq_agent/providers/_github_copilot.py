from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from fsq_agent.config import Settings
from fsq_agent.models import ConfigurationError
from fsq_agent.providers._azure_openai import ProviderClientConfig


DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
CLIENT_ID = "Iv1.b507a08c87ecfe98"
GITHUB_OAUTH_SCOPE = "read:user"
GITHUB_API_VERSION = "2022-11-28"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
COPILOT_USER_URL = "https://api.github.com/copilot_internal/user"
TOKEN_CACHE_RELATIVE_PATH = Path("auth") / "github-copilot-token.json"
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


def build_github_copilot_client_config(settings: Settings, *, interactive_auth: bool = True) -> ProviderClientConfig:
    workspace_root = settings.workspace.root_dir
    if workspace_root is None:
        raise ConfigurationError("GitHub Copilot provider requires a resolved fsq-agent workspace.")
    token_cache_path = workspace_root / TOKEN_CACHE_RELATIVE_PATH
    github_token = _resolve_github_token(token_cache_path, interactive_auth=interactive_auth)
    plan = _get_copilot_plan(github_token)
    copilot_token = _get_copilot_token(github_token)
    return ProviderClientConfig(
        provider="github_copilot",
        model=settings.openai_agents.model or "gpt-5.5",
        api_key=copilot_token.token,
        base_url=COPILOT_BASE_URLS[plan],
        default_headers=COPILOT_MODEL_HEADERS,
        metadata={"endpoint_family": "github_copilot", "copilot_plan": plan},
    )


def _resolve_github_token(token_cache_path: Path, *, interactive_auth: bool = True) -> str:
    cached = _load_cached_token(token_cache_path)
    if cached:
        return cached
    if not interactive_auth:
        raise ConfigurationError(
            "GitHub Copilot authentication is not configured. Run fsq-agent init --platform <platform> --provider github_copilot.",
            context={"token_cache_path": str(token_cache_path)},
        )
    return _authenticate(token_cache_path)


def _load_cached_token(token_cache_path: Path) -> str | None:
    try:
        data = json.loads(token_cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    expires_at = data.get("expires_at")
    if isinstance(expires_at, int | float) and time.time() >= expires_at - 60:
        return None
    token = data.get("access_token")
    return token if isinstance(token, str) and token else None


def _save_token(token_cache_path: Path, token_data: dict) -> None:
    token_cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"access_token": token_data["access_token"]}
    expires_in = token_data.get("expires_in")
    if isinstance(expires_in, int | float):
        payload["expires_at"] = time.time() + expires_in
    token_cache_path.write_text(json.dumps(payload), encoding="utf-8")


def _authenticate(token_cache_path: Path) -> str:
    data = _request_device_code()
    print(f"\nPlease visit: {data['verification_uri']}")
    print(f"Enter code:   {data['user_code']}\n")
    print("Waiting for GitHub Copilot authorization...", flush=True)
    token_data = _poll_for_token(
        data["device_code"],
        interval=data.get("interval", 5),
        expires_in=data.get("expires_in", 900),
    )
    _save_token(token_cache_path, token_data)
    print("GitHub Copilot authorization successful.")
    return token_data["access_token"]


def _request_device_code() -> dict:
    try:
        response = httpx.post(
            DEVICE_CODE_URL,
            data={"client_id": CLIENT_ID, "scope": GITHUB_OAUTH_SCOPE},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ConfigurationError("GitHub device-code request failed.", context={"error": str(exc)}) from exc
    return response.json()


def _poll_for_token(device_code: str, interval: int, expires_in: int) -> dict:
    deadline = time.time() + expires_in
    wait = interval
    while time.time() < deadline:
        time.sleep(wait)
        try:
            response = httpx.post(
                ACCESS_TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConfigurationError("GitHub device-code polling failed.", context={"error": str(exc)}) from exc
        data = response.json()
        if "access_token" in data:
            return data
        error = data.get("error", "")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            wait = data.get("interval", wait + 5)
            continue
        if error == "expired_token":
            raise ConfigurationError("GitHub device code expired. Please try again.")
        raise ConfigurationError("GitHub device-code OAuth failed.", context={"error": error})
    raise ConfigurationError("Timed out waiting for GitHub device-code authorization.")


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
