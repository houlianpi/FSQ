# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

DetailStatus = Literal["ready", "unavailable", "error", "not_applicable"]
SummaryStatus = Literal["ready", "partial", "unavailable"]


class DoctorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path


class DoctorStatusDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: DetailStatus
    code: str | None = None
    message: str | None = None
    action: str | None = None


class DoctorChecks(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    configuration: DoctorStatusDetail
    runtime: DoctorStatusDetail
    target_configuration: DoctorStatusDetail
    target_availability: DoctorStatusDetail
    strict_core: DoctorStatusDetail
    provider: DoctorStatusDetail
    suggestion_analyzer: DoctorStatusDetail
    dynamic_agent: DoctorStatusDetail


class DoctorCommands(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_test: DoctorStatusDetail
    case_test_suggest: DoctorStatusDetail
    case_create: DoctorStatusDetail


class DoctorPlatformResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    platform: Literal["android", "web", "windows", "macos"]
    status: SummaryStatus
    checks: DoctorChecks
    commands: DoctorCommands


class DoctorWorkspaceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    root: Path
    status: Literal["ready"] = "ready"


class DoctorResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: SummaryStatus
    workspace: DoctorWorkspaceSummary
    platforms: tuple[DoctorPlatformResult, ...]
    actions: tuple[str, ...]
