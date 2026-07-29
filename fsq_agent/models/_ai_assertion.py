# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models._core import HarnessArtifactRef, HarnessPlatform


AIAssertionStatus = Literal["passed", "failed", "error"]


class AIAssertionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: HarnessPlatform
    prompt: str
    screenshot_path: Path | str | None = None
    screenshot_artifact_ref: HarnessArtifactRef | None = None
    ui_context: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None
    step_id: str | None = None
    action_name: str | None = None
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIAssertionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AIAssertionStatus
    passed: bool
    explanation: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    token_usage: dict[str, int] = Field(default_factory=dict)
    artifact_refs: list[HarnessArtifactRef] = Field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)