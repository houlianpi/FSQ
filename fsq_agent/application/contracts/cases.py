# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models import RunEventSink


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    platform: Literal["android", "web", "windows", "macos"]
    goal: str

class CaseCreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    task_id: str
    status: str
    summary: str
    report_path: Path
    candidate_case_path: Path | None = None

CaseCreateEventSink = RunEventSink

class CaseTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    platform: Literal["android", "web", "windows", "macos"]
    case_path: Path
    suggest: bool = False

class CaseTestResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    status: Literal["success", "failed"]
    summary: str
    report_path: Path
    evidence_manifest_path: Path | None = None
    suggestion_path: Path | None = None
    candidate_case_path: Path | None = None
    warnings: list[str] = Field(default_factory=list)
