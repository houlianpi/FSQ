# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from fsq_agent.core.evidence import EvidenceRecorder
from fsq_agent.models import ConfigurationError, DynamicAgentOutcome, EvidenceBundle, ReportArtifact, RunExecutionContext, RunnerEvent, RunRuntime, RunSource, TaskResult, ToolExecutionError
from fsq_agent.report import ReportGenerator

from .recording import RecordingResult, RecordingService
from .runs import RunLifecycleService, allocate_run, transition_run

if TYPE_CHECKING:
    from collections.abc import Callable

    from fsq_agent.config import Settings
    from fsq_agent.models import RunEventSink, Task


class DynamicAgent(Protocol):
    async def run_in_context(self, task: Task, context: RunExecutionContext, event_sink: RunEventSink | None = None, *, evidence_sink, cancellation_check=None) -> DynamicAgentOutcome: ...


@dataclass(frozen=True)
class DynamicExecutionRequest:
    task: Task
    settings: Settings
    event_sink: RunEventSink | None = None
    record: bool = False
    case_name: str | None = None
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
        if not callable(getattr(self._agent, "run_in_context", None)):
            raise ConfigurationError("Dynamic execution requires a run_in_context collaborator before actions.")
        settings = request.settings
        started = time.perf_counter()
        lifecycle = RunLifecycleService()
        secret_values = tuple(settings.runtime_secrets.private_values().values())
        safe_task = request.task.model_copy(update={key: lifecycle.safe_text(value, secret_values) for key, value in request.task.model_dump().items() if isinstance(value, str)})
        root = Path(settings.workspace.root_dir or Path(settings.output.runs_dir).parent.parent.parent)
        from fsq_agent.config import list_workspace_registry

        workspace_name = next((item.name for item in list_workspace_registry() if item.root_path.resolve() == root.resolve()), root.name)  # noqa: ASYNC240 - bounded local identity resolution before execution.
        metadata = allocate_run(
            workspace=root,
            workspace_name=workspace_name,
            platform=settings.harness.platform,
            source_id=safe_task.id,
            mode="explore",
            source=RunSource(kind="goal", goal_summary=safe_task.name[:500]),
            platform_runs_dir=Path(settings.output.runs_dir),
        )
        run_dir = Path(settings.output.runs_dir) / metadata.run_id
        processing = {}
        active_processing = None
        recording = None
        heartbeat = None
        try:
            metadata = lifecycle.snapshot_sources(
                run_dir, metadata, sources={"goal": request.task.planning_reference_text or request.task.description}, secret_values=secret_values, configuration=lifecycle.safe_configuration(settings)
            )
            metadata = transition_run(run_dir, metadata, "running")
            lifecycle.heartbeat(run_dir)
            heartbeat = asyncio.create_task(self._heartbeat(run_dir))
            recorder = EvidenceRecorder(run_id=metadata.run_id, output_dir=run_dir, secret_values=secret_values)
            outcome = await self._agent.run_in_context(safe_task, lifecycle.context(run_dir, metadata), request.event_sink, evidence_sink=recorder, cancellation_check=request.cancellation_check)
            if request.cancellation_check is not None:
                request.cancellation_check()
            try:
                bundle = lifecycle.read_evidence(run_dir)
            except FileNotFoundError:
                bundle = recorder.build_bundle()
                if not bundle.steps and not bundle.events and not bundle.planned_steps:
                    recorder.record_event(RunnerEvent(run_id=metadata.run_id, event_type="session_finish", payload={"capability_execution": "not_requested"}))
                    recorder.write_manifest()
                    bundle = lifecycle.read_evidence(run_dir)
            frozen = lifecycle.freeze(
                run_dir,
                metadata,
                bundle=bundle,
                verification=outcome.verification,
                summary=outcome.verification.summary,
                fatal_errors=outcome.errors,
                secret_values=secret_values,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            active_processing = "report"
            processing[active_processing] = {"status": "pending"}
            try:
                report = ReportGenerator(settings.output.runs_dir, secret_values=secret_values).generate(metadata.run_id, outcome.task, outcome.steps, outcome.verification)
                processing["report"] = {"status": "success"}
            except Exception as exc:  # noqa: BLE001 - isolate derived processing failures from frozen execution.
                report = ReportArtifact(run_id=metadata.run_id, path=run_dir / "execution-result.json", evidence_manifest_path=bundle.manifest_path)
                processing["report"] = {"status": "failed", "error_type": type(exc).__name__}
            result = TaskResult(
                task_id=request.task.id,
                status=frozen.outcome,
                steps=outcome.steps,
                verification=outcome.verification,
                report=report,
                duration_ms=frozen.duration_ms,
            )
            active_processing = None
            if request.report_coordinator is not None:
                active_processing = "report"
                try:
                    request.report_coordinator(result)
                except Exception as exc:  # noqa: BLE001 - isolate derived processing failures from frozen execution.
                    processing["report"] = {"status": "failed", "error_type": type(exc).__name__}
            active_processing = None
            if request.record:
                active_processing = "recording"
                processing[active_processing] = {"status": "pending"}
                try:
                    recording = self._recording_service.record(
                        run_dir=run_dir,
                        task=outcome.task,
                        result=result,
                        settings=settings,
                        allow_failure=request.allow_recording_failure,
                        publication_directory=request.publication_directory,
                        case_name=request.case_name,
                    )
                    processing["recording"] = {"status": "success" if recording.status == "recorded" else "failed"}
                    processing["publication"] = {"status": recording.publication_status, "errors": list(recording.publication_errors)}
                    if recording.published_case_path is not None:
                        processing["publication"]["published_case_path"] = recording.published_case_path.name
                except Exception as exc:  # noqa: BLE001 - isolate derived processing failures from frozen execution.
                    processing["recording"] = {"status": "failed", "error_type": type(exc).__name__}
                    if request.recording_error_sink is not None:
                        request.recording_error_sink(exc)
            active_processing = None
            lifecycle.finalize(run_dir, metadata, execution_result=frozen, processing=processing, runtime=RunRuntime(provider=settings.openai_agents.provider, model=settings.openai_agents.model))
            return DynamicExecutionResult(task_result=result, recording=recording)
        except BaseException as exc:
            if active_processing is not None:
                processing[active_processing] = {"status": "cancelled" if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)) else "failed", "error_type": type(exc).__name__}
            try:
                try:
                    bundle = lifecycle.read_evidence(run_dir)
                except (OSError, ValueError):
                    bundle = EvidenceBundle(bundle_id=f"{metadata.run_id}-evidence", run_id=metadata.run_id)
                if (run_dir / "execution-result.json").is_file():
                    from fsq_agent.models import RunExecutionResult

                    frozen = RunExecutionResult.model_validate_json((run_dir / "execution-result.json").read_text())
                else:
                    cancelled = isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)) or type(exc).__name__ in {"ExecutionCancelled", "RunCancelled", "TaskCancelledError"}
                    frozen = lifecycle.freeze(
                        run_dir, metadata, bundle=bundle, status="cancelled" if cancelled else "error", summary="Execution cancelled." if cancelled else f"Execution stopped ({type(exc).__name__})."
                    )
                lifecycle.finalize(run_dir, metadata, execution_result=frozen, processing=processing)
            except Exception as persistence_error:  # noqa: BLE001 - preserve the original failure.
                logging.getLogger(__name__).warning("Run finalization failed (%s)", type(persistence_error).__name__)
            cancelled = isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)) or type(exc).__name__ in {"ExecutionCancelled", "RunCancelled", "TaskCancelledError"}
            if cancelled:
                exc.run_id = metadata.run_id
                exc.platform = metadata.platform
                raise
            raise ToolExecutionError("Run execution failed.", context={"run_id": metadata.run_id, "platform": metadata.platform, "exception_type": type(exc).__name__}) from exc
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat

    @staticmethod
    async def _heartbeat(run_dir: Path) -> None:
        while True:
            await asyncio.sleep(5)
            RunLifecycleService.heartbeat(run_dir)
