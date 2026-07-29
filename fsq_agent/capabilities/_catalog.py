# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from fsq_agent.models import CapabilityExecutorKind, ExecutableStepKind, ReplayPolicy


@dataclass(frozen=True)
class CapabilityActionDefinition:
    action_name: str
    canonical_name: str
    executor_kind: CapabilityExecutorKind
    owner: str
    params_model: type[BaseModel]
    step_kind: ExecutableStepKind = "action"
    method_name: str | None = None
    replay: ReplayPolicy | None = None
    post_action_delay_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


CapabilityActionCatalog = Mapping[str, CapabilityActionDefinition]
