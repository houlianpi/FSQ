# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

import pytest

from fsq_agent.application import (
    ApplicationError,
    ApplicationErrorCode,
    WorkspaceRequest,
    WorkspaceResult,
    require_initialized_workspace,
)


def test_require_initialized_workspace_returns_current_directory_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / ".fsq-agent-workspace"
    workspace.mkdir()
    (workspace / ".fsq-agent-workspace").write_text("fsq-agent workspace\n", encoding="utf-8")

    result = require_initialized_workspace(WorkspaceRequest(current_directory=tmp_path))

    assert result == WorkspaceResult(current_directory=tmp_path.resolve(), workspace=workspace.resolve())


def test_require_initialized_workspace_does_not_search_parent_directories(tmp_path: Path) -> None:
    workspace = tmp_path / ".fsq-agent-workspace"
    workspace.mkdir()
    (workspace / ".fsq-agent-workspace").write_text("fsq-agent workspace\n", encoding="utf-8")
    child = tmp_path / "project"
    child.mkdir()

    with pytest.raises(ApplicationError) as error:
        require_initialized_workspace(WorkspaceRequest(current_directory=child))

    assert error.value.code == ApplicationErrorCode.WORKSPACE_NOT_INITIALIZED
    assert error.value.details["current_directory"] == str(child.resolve())
    assert error.value.details["workspace"] == str(child.resolve() / ".fsq-agent-workspace")
    assert error.value.action == "Run 'fsq init' here or change to an initialized FSQ Workspace."


@pytest.mark.parametrize("workspace_shape", ["missing", "file", "unmarked_directory"])
def test_require_initialized_workspace_uses_stable_error_for_invalid_workspace(tmp_path: Path, workspace_shape: str) -> None:
    workspace = tmp_path / ".fsq-agent-workspace"
    if workspace_shape == "file":
        workspace.write_text("not a directory", encoding="utf-8")
    elif workspace_shape == "unmarked_directory":
        workspace.mkdir()

    with pytest.raises(ApplicationError) as error:
        require_initialized_workspace(WorkspaceRequest(current_directory=tmp_path))

    assert error.value.code.value == "workspace.not_initialized"
    assert error.value.category.value == "workspace_configuration"


def test_workspace_contracts_are_transport_neutral_and_json_serializable(tmp_path: Path) -> None:
    request = WorkspaceRequest(current_directory=tmp_path)
    result = WorkspaceResult(current_directory=tmp_path.resolve(), workspace=tmp_path / ".fsq-agent-workspace")

    assert request.model_dump(mode="json") == {"current_directory": str(tmp_path)}
    assert result.model_dump(mode="json") == {
        "current_directory": str(tmp_path.resolve()),
        "workspace": str(tmp_path / ".fsq-agent-workspace"),
    }
