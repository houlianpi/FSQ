# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


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


def _record_metadata(*, operation: str, status: str) -> dict[str, object]:
    return {"schema_version": "fsq.machine/v1", "operation": operation, "status": status, "timestamp": datetime.now(UTC).isoformat()}


class ApplicationError(Exception):
    def __init__(self, *, code: ApplicationErrorCode, category: ApplicationErrorCategory, message: str, action: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code, self.category, self.message, self.action, self.details = code, category, message, action, details or {}

    def to_record(self, *, operation: str = "unknown") -> dict[str, object]:
        return {
            **_record_metadata(operation=operation, status="error"),
            "type": ApplicationRecordType.ERROR.value,
            "error": {"code": self.code.value, "category": self.category.value, "message": self.message, "action": self.action, "details": self.details},
        }


def result_record(result: object, *, operation: str = "unknown", status: str = "success", warnings: list[str] | None = None) -> dict[str, object]:
    return {**_record_metadata(operation=operation, status=status), "type": ApplicationRecordType.RESULT.value, "warnings": warnings or [], "result": result}


def event_record(event: object, *, operation: str = "unknown") -> dict[str, object]:
    return {**_record_metadata(operation=operation, status="running"), "type": ApplicationRecordType.EVENT.value, "event": event}
