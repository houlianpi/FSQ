# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from fsq_agent.application._contracts import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
    WorkspaceRequest,
    WorkspaceResult,
)

WORKSPACE_DIRECTORY = ".fsq-agent-workspace"
WORKSPACE_MARKER = ".fsq-agent-workspace"


def require_initialized_workspace(request: WorkspaceRequest) -> WorkspaceResult:
    current_directory = request.current_directory.expanduser().resolve()
    workspace = current_directory / WORKSPACE_DIRECTORY
    marker = workspace / WORKSPACE_MARKER
    if not workspace.is_dir() or not marker.is_file():
        raise ApplicationError(
            code=ApplicationErrorCode.WORKSPACE_NOT_INITIALIZED,
            category=ApplicationErrorCategory.WORKSPACE_CONFIGURATION,
            message="The current directory is not an initialized FSQ Workspace.",
            action="Run 'fsq init' here or change to an initialized FSQ Workspace.",
            details={
                "current_directory": str(current_directory),
                "workspace": str(workspace),
            },
        )
    return WorkspaceResult(current_directory=current_directory, workspace=workspace.resolve())
