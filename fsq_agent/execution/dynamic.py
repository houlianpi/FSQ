# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .recording import RecordingResult, RecordingService

if TYPE_CHECKING:
    from collections.abc import Callable

    from fsq_agent.config import Settings
    from fsq_agent.models import RunEventSink, Task, TaskResult


class DynamicAgent(Protocol):
    async def run(self, task: Task, event_sink: RunEventSink | None = None) -> TaskResult: ...


@dataclass(frozen=True)
class DynamicExecutionRequest:
    task: Task
    settings: Settings
    event_sink: RunEventSink | None = None
    record: bool = False
    allow_recording_failure: bool = False
    publication_directory: Path | None = None
    cancellation_check: Callable[[], None] | None = None
    report_coordinator: Callable[[TaskResult], None] | None = None
    recording_error_sink: Callable[[Exception], None] | None = None


@dataclass(frozen=True)
class DynamicExecutionResult:
    task_result: TaskResult
    recording: RecordingResult | None = None


class DynamicExecutionService:
    def __init__(self, *, agent: DynamicAgent, recording_service: RecordingService | None = None) -> None:
        self._agent = agent
        self._recording_service = recording_service or RecordingService()

    async def execute(self, request: DynamicExecutionRequest) -> DynamicExecutionResult:
        if request.cancellation_check is not None:
            request.cancellation_check()
        result = await self._agent.run(request.task, event_sink=request.event_sink)
        if request.cancellation_check is not None:
            request.cancellation_check()
        if request.report_coordinator is not None:
            request.report_coordinator(result)
        recording = None
        if request.record:
            try:
                recording = self._recording_service.record(
                    run_dir=Path(request.settings.output.runs_dir) / result.report.run_id,
                    task=request.task,
                    result=result,
                    settings=request.settings,
                    allow_failure=request.allow_recording_failure,
                    publication_directory=request.publication_directory,
                )
            except Exception as exc:  # noqa: BLE001 - recording never changes completed execution status.
                if request.recording_error_sink is not None:
                    request.recording_error_sink(exc)
                recording = None
        return DynamicExecutionResult(task_result=result, recording=recording)
