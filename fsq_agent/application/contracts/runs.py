# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.execution import RunArtifactIndex, RunMetadata, RunResultSummary, RunRuntime, RunSource, RunStepCounts

Platform = Literal["android", "web", "windows", "macos"]
RunMode = Literal["strict", "explore"]
RunStatus = Literal["preparing", "running", "finalizing", "success", "failed", "inconclusive", "cancelled", "error", "interrupted"]


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    platform: Platform
    mode: RunMode | None = None
    status: RunStatus
    started_at: datetime | None = None
    duration_ms: int | None = None
    source: RunSource | None = None
    warnings: tuple[str, ...] = ()


class ListRunsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    platform: Platform | None = None
    statuses: tuple[RunStatus, ...] = ()
    mode: RunMode | None = None
    since: str | None = None
    case_id: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class ListRunsResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    workspace: str
    platforms: tuple[Platform, ...]
    filters: dict[str, Any]
    matched_count: int
    returned_count: int
    truncated: bool
    runs: tuple[RunSummary, ...]
    warnings: tuple[str, ...] = ()


class ShowRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    run_id: str
    platform: Platform | None = None


class GenerateRunHtmlRequest(ShowRunRequest):
    pass


class RunDetail(RunMetadata):
    status: RunStatus


class ShowRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    workspace: str
    run: RunDetail
    html_path: str | None = None
    warnings: tuple[str, ...] = ()


class RunLogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sequence: int | None = None
    time: str | None = Field(default=None, max_length=100)
    level: str | None = Field(default=None, max_length=50)
    phase: str | None = Field(default=None, max_length=100)
    tool: str | None = Field(default=None, max_length=200)
    label: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=100)
    message: str | None = Field(default=None, max_length=4000)


class ReadRunLogsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    run_id: str
    platform: Platform | None = None
    levels: tuple[str, ...] = ()
    phases: tuple[str, ...] = ()
    limit: int = Field(default=200, ge=1, le=5000)


class ReadRunLogsResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    platform: Platform
    filters: dict[str, Any]
    matched_count: int
    returned_count: int
    truncated: bool
    events: tuple[RunLogEvent, ...]
    warnings: tuple[str, ...] = ()


class GenerateRunHtmlResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    platform: Platform
    html_path: str


__all__ = [
    "GenerateRunHtmlRequest",
    "GenerateRunHtmlResult",
    "ListRunsRequest",
    "ListRunsResult",
    "ReadRunLogsRequest",
    "ReadRunLogsResult",
    "RunArtifactIndex",
    "RunDetail",
    "RunLogEvent",
    "RunMetadata",
    "RunResultSummary",
    "RunRuntime",
    "RunSource",
    "RunStepCounts",
    "RunSummary",
    "ShowRunRequest",
    "ShowRunResult",
]
