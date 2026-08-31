# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.adapters.coding_agent import create_coding_agent_runtime
from fsq_agent.agent import FsqAgent
from fsq_agent.config import Settings


def create_case_agent(settings: Settings) -> FsqAgent:
    """Construct the SDK-neutral Agent collaborator injected into Application."""
    return FsqAgent.from_settings(settings, create_coding_agent_runtime)


__all__ = ["create_case_agent"]
