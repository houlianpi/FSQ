# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.agent._core import FsqAgent
from fsq_agent.agent._policy import CodingAgentPolicy
from fsq_agent.agent._runtime import CodingAgentRuntime, CodingAgentRuntimeFactory
from fsq_agent.agent._verifier import Verifier

__all__ = ["CodingAgentPolicy", "CodingAgentRuntime", "CodingAgentRuntimeFactory", "FsqAgent", "OpenAIAgentsRuntime", "Verifier"]


def __getattr__(name: str):
    if name == "OpenAIAgentsRuntime":
        from fsq_agent.adapters.coding_agent import OpenAIAgentsRuntime

        return OpenAIAgentsRuntime
    raise AttributeError(name)
