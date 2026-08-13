# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.config import Settings
from fsq_agent.providers._ai_assertion import AIAssertionEvaluator
from fsq_agent.providers._azure_openai import build_azure_openai_client_config
from fsq_agent.providers._github_copilot import build_github_copilot_client_config, refresh_github_copilot_client_config
from fsq_agent.providers._session import ModelProviderSession


class ModelProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_session(self) -> ModelProviderSession:
        provider = self.settings.openai_agents.provider
        if provider == "github_copilot":
            return ModelProviderSession(build_github_copilot_client_config(self.settings))
        if provider == "azure_openai":
            return ModelProviderSession(build_azure_openai_client_config(self.settings))
        from fsq_agent.models import ConfigurationError

        raise ConfigurationError("Model Provider is not configured. Add a Provider in Control Plane Config.")

    def refresh_session(self) -> ModelProviderSession:
        provider = self.settings.openai_agents.provider
        if provider == "github_copilot":
            return ModelProviderSession(refresh_github_copilot_client_config(self.settings))
        return ModelProviderSession(build_azure_openai_client_config(self.settings))

    def build_ai_assertion_evaluator(self) -> AIAssertionEvaluator:
        return AIAssertionEvaluator(self.build_session())


def build_model_provider_session(settings: Settings) -> ModelProviderSession:
    return ModelProviderFactory(settings).build_session()


def prepare_model_provider_session(settings: Settings) -> ModelProviderSession:
    return ModelProviderFactory(settings).build_session()


def refresh_model_provider_session(settings: Settings) -> ModelProviderSession:
    return ModelProviderFactory(settings).refresh_session()


def build_ai_assertion_evaluator(settings: Settings) -> AIAssertionEvaluator:
    return ModelProviderFactory(settings).build_ai_assertion_evaluator()
