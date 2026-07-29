# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

class FsqAgentError(Exception):
    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class ConfigurationError(FsqAgentError):
    pass


class PlanningError(FsqAgentError):
    pass


class ToolExecutionError(FsqAgentError):
    pass


class VerificationError(FsqAgentError):
    pass


class ReportGenerationError(FsqAgentError):
    pass