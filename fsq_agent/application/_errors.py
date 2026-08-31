# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.application.contracts import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
)
from fsq_agent.models import ConfigurationError, FsqAgentError


def normalize_application_error(error: Exception) -> ApplicationError:
    if isinstance(error, ApplicationError):
        return error
    if isinstance(error, ConfigurationError):
        return ApplicationError(
            code=ApplicationErrorCode.CONFIGURATION_INVALID,
            category=ApplicationErrorCategory.CONFIGURATION,
            message=str(error),
            action="Review the FSQ Workspace and platform configuration.",
            details=error.context,
        )
    if isinstance(error, FsqAgentError):
        return ApplicationError(
            code=ApplicationErrorCode.INTERNAL_ERROR,
            category=ApplicationErrorCategory.INTERNAL,
            message=str(error),
            action="Inspect the Run artifacts and retry.",
            details=error.context,
        )
    if isinstance(error, (ConnectionError, TimeoutError)):
        return ApplicationError(
            code=ApplicationErrorCode.PROVIDER_UNAVAILABLE,
            category=ApplicationErrorCategory.UNAVAILABLE,
            message=str(error) or "Provider or environment is unavailable.",
            action="Check provider credentials, network access, and environment readiness.",
        )
    return ApplicationError(
        code=ApplicationErrorCode.INTERNAL_ERROR,
        category=ApplicationErrorCategory.INTERNAL,
        message="FSQ encountered an internal error.",
        action="Inspect diagnostics and retry.",
        details={"exception_type": error.__class__.__name__},
    )
