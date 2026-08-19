# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.application._contracts import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
    WorkspaceRequest,
    WorkspaceResult,
)
from fsq_agent.config import inspect_registered_workspace, list_workspace_registry


def require_initialized_workspace(request: WorkspaceRequest) -> WorkspaceResult:
    current_directory = request.current_directory.expanduser().resolve()
    entry = next((item for item in list_workspace_registry() if item.root_path.resolve() == current_directory), None)
    if entry is None:
        raise ApplicationError(
            code=ApplicationErrorCode.WORKSPACE_NOT_INITIALIZED,
            category=ApplicationErrorCategory.WORKSPACE_CONFIGURATION,
            message="The current directory is not an initialized FSQ Workspace.",
            action="Run 'fsq init' here or change to an initialized FSQ Workspace.",
            details={
                "current_directory": str(current_directory),
                "workspace": str(current_directory),
            },
        )
    try:
        status = inspect_registered_workspace(entry.name)
    except Exception as exc:
        raise ApplicationError(
            code=ApplicationErrorCode.WORKSPACE_NOT_INITIALIZED,
            category=ApplicationErrorCategory.WORKSPACE_CONFIGURATION,
            message="The registered FSQ Workspace is unavailable.",
            action="Repair it in Control Plane or initialize a valid workspace root.",
            details={"workspace": str(current_directory)},
        ) from exc
    if status.status == "unavailable":
        raise ApplicationError(
            code=ApplicationErrorCode.WORKSPACE_NOT_INITIALIZED,
            category=ApplicationErrorCategory.WORKSPACE_CONFIGURATION,
            message="The registered FSQ Workspace has no valid platform configuration.",
            action="Add or repair a platform configuration.",
            details={"workspace": str(current_directory)},
        )
    return WorkspaceResult(current_directory=current_directory, workspace=current_directory)
