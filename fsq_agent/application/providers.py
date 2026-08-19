# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path

from fsq_agent.application.contracts import ProviderSummary, WorkspaceRequest
from fsq_agent.application.workspace import require_initialized_workspace


def configure_provider(current_directory: Path, name: str) -> ProviderSummary:
    require_initialized_workspace(WorkspaceRequest(current_directory=current_directory))
    if name not in {"github_copilot", "azure_openai"}:
        raise ValueError(f"Unsupported provider: {name}")
    env_path = current_directory / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    output = [line for line in lines if not line.lstrip().startswith("FSQ_LLM_PROVIDER=")]
    output.append(f"FSQ_LLM_PROVIDER={name}")
    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return ProviderSummary(name=name, configured=True, selected=True)


def provider_status(name: str | None = None) -> list[ProviderSummary]:
    return [item for item in list_providers() if name is None or item.name == name]


def list_providers() -> list[ProviderSummary]:
    selected = os.getenv("FSQ_LLM_PROVIDER", "github_copilot")
    return [
        ProviderSummary(name="github_copilot", configured=selected == "github_copilot", selected=selected == "github_copilot"),
        ProviderSummary(name="azure_openai", configured=selected == "azure_openai", selected=selected == "azure_openai"),
    ]


__all__ = ["configure_provider", "list_providers", "provider_status"]
