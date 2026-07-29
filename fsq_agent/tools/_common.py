# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Backward-compatible AgentTool aliases for legacy CommonTool imports."""

from fsq_agent.tools._agent_tools import (
    AgentToolExecutor as CommonToolExecutor,
    AgentToolProvider as CommonToolProvider,
    AgentToolRegistry as CommonToolRegistry,
    DefaultAgentToolProvider as DefaultCommonToolProvider,
)

__all__ = [
    "CommonToolExecutor",
    "CommonToolProvider",
    "CommonToolRegistry",
    "DefaultCommonToolProvider",
]