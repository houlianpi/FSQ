# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

DetailStatus = Literal["ready", "unavailable", "error", "not_applicable"]
SummaryStatus = Literal["ready", "partial", "unavailable"]


class DoctorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path


class RegisteredPlatformDoctorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    workspace_name: str = Field(min_length=1, max_length=200)
    platform: Literal["android", "web", "windows", "macos"]
    user_config_root: Path | None = None


class DoctorStatusDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: DetailStatus
    code: str | None = None
    message: str | None = None
    action: str | None = None


class DoctorPrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identifier: str
    status: DetailStatus
    message: str
    action: str | None = None
    commands: tuple[Annotated[str, Field(min_length=1, max_length=2000)], ...] = Field(default=(), max_length=5)


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
    prerequisites: tuple[DoctorPrerequisite, ...] = ()
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
