# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Backward-compatible AgentTool aliases for legacy CommonTool imports."""

from fsq_agent.tools._agent_tools import (
    AgentToolExecutor as CommonToolExecutor,
)
from fsq_agent.tools._agent_tools import (
    AgentToolProvider as CommonToolProvider,
)
from fsq_agent.tools._agent_tools import (
    AgentToolRegistry as CommonToolRegistry,
)
from fsq_agent.tools._agent_tools import (
    DefaultAgentToolProvider as DefaultCommonToolProvider,
)

__all__ = [
    "CommonToolExecutor",
    "CommonToolProvider",
    "CommonToolRegistry",
    "DefaultCommonToolProvider",
]
