# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

import pytest

from fsq_agent.application import (
    ApplicationError,
    ApplicationErrorCode,
    WorkspaceInitializeRequest,
    WorkspaceRequest,
    WorkspaceResult,
    initialize_workspace,
    require_initialized_workspace,
)
from fsq_agent.core import PlatformRuntimeService
from fsq_agent.models import PlatformRuntimeCheck


def test_require_initialized_workspace_returns_exact_registered_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fsq_agent.application._workspace.list_workspace_registry", lambda: [type("Entry", (), {"name": "project", "root_path": tmp_path})()])
    monkeypatch.setattr("fsq_agent.application._workspace.inspect_registered_workspace", lambda _name: type("Status", (), {"status": "available"})())

    result = require_initialized_workspace(WorkspaceRequest(current_directory=tmp_path))

    assert result == WorkspaceResult(current_directory=tmp_path.resolve(), workspace=tmp_path.resolve())


def test_require_initialized_workspace_does_not_search_parent_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fsq_agent.application._workspace.list_workspace_registry", lambda: [type("Entry", (), {"name": "project", "root_path": tmp_path})()])
    child = tmp_path / "project"
    child.mkdir()

    with pytest.raises(ApplicationError) as error:
        require_initialized_workspace(WorkspaceRequest(current_directory=child))

    assert error.value.code == ApplicationErrorCode.WORKSPACE_NOT_INITIALIZED
    assert error.value.details["current_directory"] == str(child.resolve())
    assert error.value.details["workspace"] == str(child.resolve())
    assert error.value.action == "Run 'fsq init' here or change to an initialized FSQ Workspace."


def test_require_initialized_workspace_rejects_legacy_marker_only(tmp_path: Path) -> None:
    workspace = tmp_path / ".fsq-agent-workspace"
    workspace.mkdir()
    (workspace / ".fsq-agent-workspace").write_text("legacy", encoding="utf-8")
    with pytest.raises(ApplicationError) as error:
        require_initialized_workspace(WorkspaceRequest(current_directory=tmp_path))

    assert error.value.code.value == "workspace.not_initialized"
    assert error.value.category.value == "workspace_configuration"


def test_workspace_contracts_are_transport_neutral_and_json_serializable(tmp_path: Path) -> None:
    request = WorkspaceRequest(current_directory=tmp_path)
    result = WorkspaceResult(current_directory=tmp_path.resolve(), workspace=tmp_path.resolve())

    assert request.model_dump(mode="json") == {"current_directory": str(tmp_path)}
    assert result.model_dump(mode="json") == {
        "current_directory": str(tmp_path.resolve()),
        "workspace": str(tmp_path.resolve()),
    }


def test_initialize_workspace_resolves_web_browser_before_config_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    browser = tmp_path / "Google Chrome" / "chrome.exe"
    browser.parent.mkdir(parents=True)
    browser.write_text("", encoding="utf-8")
    browser.chmod(0o755)
    calls: list[object] = []
    monkeypatch.setattr(PlatformRuntimeService, "check", lambda self, platform: PlatformRuntimeCheck(platform=platform, status="ready", ready=True, message="ready"))
    monkeypatch.setattr(PlatformRuntimeService, "discover_web_executables", lambda self, channel: [browser])
    monkeypatch.setattr(
        "fsq_agent.application._workspace_init.initialize_workspace_root",
        lambda **kwargs: calls.append(kwargs) or type("Result", (), {"status": "initialized", "name": "project", "root_path": tmp_path.resolve(), "platform": "web"})(),
    )

    result = initialize_workspace(WorkspaceInitializeRequest(current_directory=tmp_path, platform="web", browser_channel="chrome"))

    assert result.root_path == tmp_path.resolve()
    assert calls[0]["config"].target.browser_executable_path == browser.resolve()


def test_initialize_workspace_does_not_mutate_when_driver_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformRuntimeService, "check", lambda self, platform: PlatformRuntimeCheck(platform=platform, status="missing", ready=False, message="missing", action="pip install fsq-agent[web]"))
    monkeypatch.setattr("fsq_agent.application._workspace_init.initialize_workspace_root", lambda **kwargs: pytest.fail("config mutation must not run"))

    with pytest.raises(ApplicationError, match="missing"):
        initialize_workspace(WorkspaceInitializeRequest(current_directory=tmp_path, platform="web", browser_channel="chrome"))


def test_initialize_workspace_validates_target_before_driver_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PlatformRuntimeService, "check", lambda self, platform: PlatformRuntimeCheck(platform=platform, status="missing", ready=False, message="missing"))
    monkeypatch.setattr(PlatformRuntimeService, "install", lambda self, platform: pytest.fail("invalid target must not install"))

    with pytest.raises(ApplicationError) as error:
        initialize_workspace(WorkspaceInitializeRequest(current_directory=tmp_path, platform="android", app_id="example", browser_channel="chrome", install_driver=True))

    assert error.value.code == ApplicationErrorCode.CONFIGURATION_INVALID


def test_initialize_workspace_does_not_install_unsupported_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "app.exe"
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setattr(
        PlatformRuntimeService,
        "check",
        lambda self, platform: PlatformRuntimeCheck(platform=platform, status="unsupported", ready=False, message="unsupported"),
    )
    monkeypatch.setattr(PlatformRuntimeService, "install", lambda self, platform: pytest.fail("unsupported runtime must not install"))

    with pytest.raises(ApplicationError, match="unsupported"):
        initialize_workspace(WorkspaceInitializeRequest(current_directory=tmp_path, platform="windows", app_path=executable, install_driver=True))


def test_initialize_workspace_persists_normalized_windows_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "bin" / "app.exe"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setattr(PlatformRuntimeService, "check", lambda self, platform: PlatformRuntimeCheck(platform=platform, status="ready", ready=True, message="ready"))
    monkeypatch.chdir(tmp_path)

    target, _ = __import__("fsq_agent.application", fromlist=["resolve_workspace_target"]).resolve_workspace_target(
        WorkspaceInitializeRequest(current_directory=tmp_path, platform="windows", app_path=Path("bin/app.exe"))
    )

    assert target.app_path == executable.resolve()
