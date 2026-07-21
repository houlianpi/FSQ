from typing import Any
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from fsq_agent.config import Settings
from fsq_agent.models import ConfigurationError, OpenAIAgentsSettings
from fsq_agent.providers import (
    build_ai_assertion_evaluator,
    build_model_provider_session,
    prepare_model_provider_session,
    refresh_model_provider_session,
)
from fsq_agent.providers import _github_copilot as copilot


class _AsyncOpenAI:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_build_github_copilot_client_config_uses_plan_endpoint(tmp_path) -> None:
    token_cache_path = tmp_path / "auth" / "github-copilot-provider-token.json"
    token_cache_path.parent.mkdir()
    token_cache_path.write_text(
        json.dumps(
            {
                "token": "copilot-token",
                "expires_at": time.time() + 3600,
                "plan": "business",
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(openai_agents=OpenAIAgentsSettings(provider="github_copilot"))
    settings.workspace.root_dir = tmp_path
    with patch.object(copilot, "_get_copilot_plan") as get_plan, patch.object(copilot, "_get_copilot_token") as get_token:
        config = copilot.build_github_copilot_client_config(settings)

    get_plan.assert_not_called()
    get_token.assert_not_called()
    assert config.api_key == "copilot-token"
    assert config.base_url == "https://api.business.githubcopilot.com"
    assert config.default_headers["copilot-integration-id"] == "vscode-chat"
    assert config.model == "gpt-5.5"


def test_prepare_model_provider_session_exchanges_and_caches_copilot_provider_token(tmp_path) -> None:
    oauth_cache_path = tmp_path / "auth" / "github-copilot-token.json"
    provider_cache_path = tmp_path / "auth" / "github-copilot-provider-token.json"
    oauth_cache_path.parent.mkdir()
    oauth_cache_path.write_text(json.dumps({"access_token": "ghu_test", "expires_at": time.time() + 3600}), encoding="utf-8")
    settings = Settings(openai_agents=OpenAIAgentsSettings(provider="github_copilot"))
    settings.workspace.root_dir = tmp_path

    with patch.object(copilot, "_get_copilot_plan", return_value="business") as get_plan, patch.object(
        copilot,
        "_get_copilot_token",
        return_value=copilot.CopilotToken(token="copilot-token", expires_at=time.time() + 3600),
    ) as get_token:
        session = prepare_model_provider_session(settings, interactive_auth=True)

    get_plan.assert_called_once_with("ghu_test")
    get_token.assert_called_once_with("ghu_test")
    assert session.client_config.api_key == "copilot-token"
    data = json.loads(provider_cache_path.read_text(encoding="utf-8"))
    assert data["token"] == "copilot-token"
    assert data["plan"] == "business"


def test_runtime_copilot_provider_session_requires_cached_provider_or_github_token(tmp_path) -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings(provider="github_copilot"))
    settings.workspace.root_dir = tmp_path

    with patch.object(copilot, "_authenticate") as authenticate, patch.object(copilot, "_get_copilot_token") as get_token:
        with pytest.raises(ConfigurationError, match="Run fsq-agent init"):
            build_model_provider_session(settings)

    authenticate.assert_not_called()
    get_token.assert_not_called()


def test_runtime_copilot_provider_session_refreshes_expired_provider_token_from_cached_github_token(tmp_path) -> None:
    auth_dir = tmp_path / "auth"
    oauth_cache_path = auth_dir / "github-copilot-token.json"
    provider_cache_path = auth_dir / "github-copilot-provider-token.json"
    auth_dir.mkdir()
    oauth_cache_path.write_text(json.dumps({"access_token": "ghu_test", "expires_at": time.time() + 3600}), encoding="utf-8")
    provider_cache_path.write_text(
        json.dumps({"token": "old-provider-token", "expires_at": time.time() - 1, "plan": "enterprise"}),
        encoding="utf-8",
    )
    settings = Settings(openai_agents=OpenAIAgentsSettings(provider="github_copilot"))
    settings.workspace.root_dir = tmp_path

    with patch.object(copilot, "_authenticate") as authenticate, patch.object(
        copilot,
        "_get_copilot_plan",
        return_value="enterprise",
    ) as get_plan, patch.object(
        copilot,
        "_get_copilot_token",
        return_value=copilot.CopilotToken(token="new-provider-token", expires_at=time.time() + 3600),
    ) as get_token:
        session = build_model_provider_session(settings)

    authenticate.assert_not_called()
    get_plan.assert_called_once_with("ghu_test")
    get_token.assert_called_once_with("ghu_test")
    assert session.client_config.api_key == "new-provider-token"
    data = json.loads(provider_cache_path.read_text(encoding="utf-8"))
    assert data["token"] == "new-provider-token"


def test_refresh_model_provider_session_always_refreshes_from_cached_github_token(tmp_path) -> None:
    auth_dir = tmp_path / "auth"
    oauth_cache_path = auth_dir / "github-copilot-token.json"
    provider_cache_path = auth_dir / "github-copilot-provider-token.json"
    auth_dir.mkdir()
    oauth_cache_path.write_text(json.dumps({"access_token": "ghu_test", "expires_at": time.time() + 3600}), encoding="utf-8")
    provider_cache_path.write_text(
        json.dumps({"token": "still-valid-provider-token", "expires_at": time.time() + 3600, "plan": "business"}),
        encoding="utf-8",
    )
    settings = Settings(openai_agents=OpenAIAgentsSettings(provider="github_copilot"))
    settings.workspace.root_dir = tmp_path

    with patch.object(copilot, "_authenticate") as authenticate, patch.object(
        copilot,
        "_get_copilot_plan",
        return_value="enterprise",
    ) as get_plan, patch.object(
        copilot,
        "_get_copilot_token",
        return_value=copilot.CopilotToken(token="fresh-provider-token", expires_at=time.time() + 3600),
    ) as get_token:
        session = refresh_model_provider_session(settings)

    authenticate.assert_not_called()
    get_plan.assert_called_once_with("ghu_test")
    get_token.assert_called_once_with("ghu_test")
    assert session.client_config.api_key == "fresh-provider-token"
    data = json.loads(provider_cache_path.read_text(encoding="utf-8"))
    assert data["token"] == "fresh-provider-token"
    assert data["plan"] == "enterprise"


def test_runtime_copilot_provider_session_and_ai_assertion_use_cached_provider_token(tmp_path) -> None:
    provider_cache_path = tmp_path / "auth" / "github-copilot-provider-token.json"
    provider_cache_path.parent.mkdir()
    provider_cache_path.write_text(
        json.dumps(
            {
                "token": "copilot-token",
                "expires_at": time.time() + 3600,
                "plan": "enterprise",
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(openai_agents=OpenAIAgentsSettings(provider="github_copilot"))
    settings.workspace.root_dir = tmp_path

    with patch.object(copilot, "_get_copilot_token") as get_token:
        session = build_model_provider_session(settings)
        evaluator = build_ai_assertion_evaluator(settings)

    get_token.assert_not_called()
    assert session.client_config.api_key == "copilot-token"
    assert session.client_config.base_url == "https://api.enterprise.githubcopilot.com"
    assert evaluator.session.client_config.api_key == "copilot-token"


def test_load_cached_token_returns_none_when_expired(tmp_path) -> None:
    token_cache_path = tmp_path / "auth" / "github-copilot-token.json"
    token_cache_path.parent.mkdir()
    token_cache_path.write_text(json.dumps({"access_token": "ghu_old", "expires_at": time.time() - 1}), encoding="utf-8")

    assert copilot._load_cached_token(token_cache_path) is None


def test_resolve_github_token_authenticates_when_cache_expired(tmp_path) -> None:
    token_cache_path = tmp_path / "auth" / "github-copilot-token.json"
    token_cache_path.parent.mkdir()
    token_cache_path.write_text(json.dumps({"access_token": "ghu_old", "expires_at": time.time() - 1}), encoding="utf-8")

    with patch.object(copilot, "_authenticate", return_value="ghu_new") as authenticate:
        token = copilot._resolve_github_token(token_cache_path)

    assert token == "ghu_new"
    authenticate.assert_called_once_with(token_cache_path)


def test_request_device_code_uses_explicit_copilot_scope() -> None:
    response = MagicMock()
    response.json.return_value = {"device_code": "device", "user_code": "user"}
    response.raise_for_status = MagicMock()

    with patch.object(copilot.httpx, "post", return_value=response) as post:
        copilot._request_device_code()

    assert post.call_args.kwargs["data"]["scope"] == copilot.GITHUB_OAUTH_SCOPE


def test_get_copilot_token_uses_copilot_exchange_headers() -> None:
    response = MagicMock()
    response.json.return_value = {
        "token": "copilot-token",
        "expires_at": 9999999999,
    }
    response.raise_for_status = MagicMock()

    with patch.object(copilot.httpx, "get", return_value=response) as get:
        token = copilot._get_copilot_token("ghu_test")

    headers = get.call_args.kwargs["headers"]
    assert headers["authorization"] == "token ghu_test"
    assert headers["x-github-api-version"] == copilot.GITHUB_API_VERSION
    assert get.call_args.kwargs["timeout"] == copilot.COPILOT_AUTH_TIMEOUT_SECONDS
    assert token.token == "copilot-token"


def test_prepare_model_provider_session_noninteractive_rejects_missing_provider_token(tmp_path) -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings(provider="github_copilot"))
    settings.workspace.root_dir = tmp_path

    with patch.object(copilot, "_authenticate") as authenticate, patch.object(copilot, "_get_copilot_token") as get_token:
        with pytest.raises(ConfigurationError, match="Run fsq-agent init"):
            prepare_model_provider_session(settings, interactive_auth=False)

    authenticate.assert_not_called()
    get_token.assert_not_called()


def test_get_copilot_plan_rejects_unknown_plan() -> None:
    response = MagicMock()
    response.json.return_value = {"copilot_plan": "unknown"}
    response.raise_for_status = MagicMock()

    with patch.object(copilot.httpx, "get", return_value=response):
        with pytest.raises(ConfigurationError, match="Unknown GitHub Copilot plan"):
            copilot._get_copilot_plan("ghu_test")


def test_get_copilot_token_requires_token_field() -> None:
    response = MagicMock()
    response.json.return_value = {}
    response.raise_for_status = MagicMock()

    with patch.object(copilot.httpx, "get", return_value=response):
        with pytest.raises(ConfigurationError, match="did not include a token"):
            copilot._get_copilot_token("ghu_test")

