# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models import RunEventSink


class ApplicationErrorCode(StrEnum):
    WORKSPACE_NOT_INITIALIZED = "workspace.not_initialized"
    CASE_GOAL_INVALID = "case.goal_invalid"
    CASE_NOT_FOUND = "case.not_found"
    CASE_INVALID = "case.invalid"
    CONFIGURATION_INVALID = "configuration.invalid"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    ENVIRONMENT_UNAVAILABLE = "environment.unavailable"
    INTERNAL_ERROR = "internal.error"


class ApplicationErrorCategory(StrEnum):
    WORKSPACE_CONFIGURATION = "workspace_configuration"
    REQUEST_VALIDATION = "request_validation"
    CONFIGURATION = "configuration"
    UNAVAILABLE = "unavailable"
    INTERNAL = "internal"


class ApplicationRecordType(StrEnum):
    EVENT = "event"
    RESULT = "result"
    ERROR = "error"


APPLICATION_PROTOCOL_VERSION = "fsq.machine/v1"


def _record_metadata(*, operation: str, status: str) -> dict[str, object]:
    return {
        "schema_version": APPLICATION_PROTOCOL_VERSION,
        "operation": operation,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
    }


class ApplicationError(Exception):
    def __init__(
        self,
        *,
        code: ApplicationErrorCode,
        category: ApplicationErrorCategory,
        message: str,
        action: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.category = category
        self.message = message
        self.action = action
        self.details = details or {}

    def to_record(self, *, operation: str = "unknown") -> dict[str, object]:
        return {
            **_record_metadata(operation=operation, status="error"),
            "type": ApplicationRecordType.ERROR.value,
            "error": {
                "code": self.code.value,
                "category": self.category.value,
                "message": self.message,
                "action": self.action,
                "details": self.details,
            },
        }


def result_record(
    result: object,
    *,
    operation: str = "unknown",
    status: str = "success",
    warnings: list[str] | None = None,
) -> dict[str, object]:
    return {
        **_record_metadata(operation=operation, status=status),
        "type": ApplicationRecordType.RESULT.value,
        "warnings": warnings or [],
        "result": result,
    }


def event_record(event: object, *, operation: str = "unknown") -> dict[str, object]:
    return {
        **_record_metadata(operation=operation, status="running"),
        "type": ApplicationRecordType.EVENT.value,
        "event": event,
    }


class WorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current_directory: Path = Field(description="Current directory selected by the calling adapter.")


class WorkspaceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current_directory: Path
    workspace: Path


class WorkspaceInitializeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    current_directory: Path
    platform: Literal["android", "web", "windows", "macos"]
    name: str | None = None
    app_id: str | None = None
    browser_channel: Literal["chromium", "chrome", "chrome-beta", "chrome-dev", "chrome-canary", "msedge", "msedge-beta", "msedge-dev", "msedge-canary"] | None = None
    browser_executable_path: Path | None = None
    app_path: Path | None = None
    window_title_re: str | None = None
    launch_args: str | None = None
    bundle_id: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    install_driver: bool = False
    update_existing: bool = False
    user_config_root: Path | None = None


class WorkspaceInitializeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["initialized", "platform_added", "unchanged", "updated"]
    name: str
    root_path: Path
    platform: Literal["android", "web", "windows", "macos"]
    driver_status: Literal["ready", "installed"]
    browser_executable_path: Path | None = None


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


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    path: Path


class ProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    configured: bool
    selected: bool


class EnvironmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    platform: str
    ready: bool
    message: str | None = None
