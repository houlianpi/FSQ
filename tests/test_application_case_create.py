# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
from typing import Any

import pytest

from fsq_agent.application import ApplicationError, ApplicationErrorCode, CaseCreateRequest, create_case
from fsq_agent.models import ReportArtifact, Task, TaskResult, VerificationResult


class _FakeAgent:
    def __init__(self, result: TaskResult) -> None:
        self.result = result
        self.task: Task | None = None
        self.event_sink: Any = None

    async def run(self, task: Task, event_sink=None) -> TaskResult:
        self.task = task
        self.event_sink = event_sink
        return self.result


def _task_result(tmp_path: Path) -> TaskResult:
    return TaskResult(
        task_id="verify-product-search",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="Search works."),
        report=ReportArtifact(run_id="run-1", path=tmp_path / "runs" / "run-1" / "report.md"),
    )


@pytest.mark.asyncio
async def test_create_case_builds_goal_task_and_delegates_to_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path
    monkeypatch.setattr("fsq_agent.application._case.require_initialized_workspace", lambda _request: type("Workspace", (), {"workspace": workspace})())
    settings = object()
    loaded: list[tuple[str, Path]] = []
    agent = _FakeAgent(_task_result(tmp_path))

    result = await create_case(
        CaseCreateRequest(current_directory=tmp_path, platform="web", goal="  Verify   product search  "),
        settings_loader=lambda platform, path: loaded.append((platform, path)) or settings,
        agent_factory=lambda value: agent if value is settings else None,
    )

    assert loaded == [("web", workspace.resolve())]
    assert agent.task is not None
    assert agent.task.id == "verify-product-search"
    assert agent.task.name == "Verify product search"
    assert agent.task.planning_reference_kind == "goal"
    assert agent.task.planning_reference_text == "Verify product search"
    assert result.run_id == "run-1"
    assert result.status == "success"
    assert result.report_path == tmp_path / "runs" / "run-1" / "report.md"
    assert result.candidate_case_path is None


@pytest.mark.asyncio
async def test_create_case_forwards_transport_neutral_event_sink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fsq_agent.application._case.require_initialized_workspace", lambda _request: type("Workspace", (), {"workspace": tmp_path.resolve()})())
    agent = _FakeAgent(_task_result(tmp_path))
    events: list[object] = []
    sink = events.append

    await create_case(
        CaseCreateRequest(current_directory=tmp_path, platform="web", goal="Verify product search"),
        event_sink=sink,
        settings_loader=lambda _platform, _path: object(),
        agent_factory=lambda _settings: agent,
    )

    assert agent.event_sink == sink


@pytest.mark.asyncio
async def test_create_case_rejects_blank_goal_before_loading_settings(tmp_path: Path) -> None:
    workspace = tmp_path / ".fsq-agent-workspace"
    workspace.mkdir()
    (workspace / ".fsq-agent-workspace").write_text("fsq-agent workspace\n", encoding="utf-8")
    called = False

    def load_settings(_platform: str, _path: Path) -> object:
        nonlocal called
        called = True
        return object()

    with pytest.raises(ApplicationError, match="Goal cannot be empty") as error:
        await create_case(
            CaseCreateRequest(current_directory=tmp_path, platform="web", goal="   "),
            settings_loader=load_settings,
        )

    assert called is False
    assert error.value.code == ApplicationErrorCode.CASE_GOAL_INVALID
