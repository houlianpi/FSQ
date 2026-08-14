# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from fsq_agent._strict_case_recording import record_dynamic_run_as_strict_case
from fsq_agent.agent import FsqAgent
from fsq_agent.application._contracts import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
    CaseCreateEventSink,
    CaseCreateRequest,
    CaseCreateResult,
    WorkspaceRequest,
)
from fsq_agent.application._workspace import require_initialized_workspace
from fsq_agent.config import Settings, load_platform_settings
from fsq_agent.models import Task, TaskResult


class _Agent(Protocol):
    async def run(self, task: Task, event_sink: CaseCreateEventSink | None = None) -> TaskResult: ...


SettingsLoader = Callable[[str, Path], Settings]
AgentFactory = Callable[[Settings], _Agent]


async def create_case(
    request: CaseCreateRequest,
    *,
    event_sink: CaseCreateEventSink | None = None,
    settings_loader: SettingsLoader = load_platform_settings,
    agent_factory: AgentFactory = FsqAgent.from_settings,
) -> CaseCreateResult:
    normalized_goal = " ".join(request.goal.split())
    if not normalized_goal:
        raise ApplicationError(
            code=ApplicationErrorCode.CASE_GOAL_INVALID,
            category=ApplicationErrorCategory.REQUEST_VALIDATION,
            message="Goal cannot be empty.",
            action="Provide a non-empty natural-language Goal.",
        )

    workspace = require_initialized_workspace(WorkspaceRequest(current_directory=request.current_directory))
    settings = settings_loader(request.platform, workspace.workspace)
    task = _task_from_goal(normalized_goal)
    result = await agent_factory(settings).run(task, event_sink=event_sink)
    candidate_case_path = None
    try:
        recording = record_dynamic_run_as_strict_case(
            run_dir=Path(settings.output.runs_dir) / result.report.run_id,
            task=task,
            result=result,
            settings=settings,
        )
        if recording.status == "recorded":
            candidate_case_path = recording.recorded_case_path
    except (AttributeError, OSError, ValueError):
        candidate_case_path = None
    return CaseCreateResult(
        run_id=result.report.run_id,
        task_id=result.task_id,
        status=result.status,
        summary=result.verification.summary,
        report_path=result.report.path,
        candidate_case_path=candidate_case_path,
    )


def _task_from_goal(goal: str) -> Task:
    return Task(
        id=_goal_task_id(goal),
        name=goal,
        description=(
            "Run this natural-language goal as a goal-driven automation task. "
            "First derive ordered key actions from page knowledge, then execute them while adapting to live UI state. "
            "Final verification should judge whether the goal is complete.\n\n"
            f"Goal: {goal}"
        ),
        planning_reference_kind="goal",
        planning_reference_text=goal,
    )


def _goal_task_id(goal: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", goal.casefold()).strip("-")
    return slug[:80] or "goal-task"
