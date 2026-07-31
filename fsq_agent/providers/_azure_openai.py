# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from dataclasses import dataclass, field
from typing import Any

from fsq_agent.config import Settings
from fsq_agent.models import ConfigurationError

AZURE_OPENAI_API_KEY_ENV = "AZURE_OPENAI_API_KEY"


@dataclass(frozen=True)
class ProviderClientConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    default_headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_azure_openai_client_config(settings: Settings) -> ProviderClientConfig:
    openai_settings = settings.openai_agents
    api_key = os.getenv(AZURE_OPENAI_API_KEY_ENV)
    if not api_key:
        raise ConfigurationError(
            "Azure OpenAI API key environment variable is not set.",
            context={"api_key_env": AZURE_OPENAI_API_KEY_ENV},
        )
    if api_key.lower().startswith("replace-with"):
        raise ConfigurationError(
            "Azure OpenAI API key environment variable still contains a placeholder value.",
            context={"api_key_env": AZURE_OPENAI_API_KEY_ENV},
        )
    base_url = openai_settings.base_url.strip()
    if not base_url.endswith("/openai/v1/"):
        raise ConfigurationError(
            "Azure OpenAI base URL must use the /openai/v1/ form.",
            context={"base_url": base_url},
        )
    return ProviderClientConfig(
        provider="azure_openai",
        model=openai_settings.model,
        api_key=api_key,
        base_url=base_url,
        metadata={"endpoint_family": "azure_openai"},
    )
