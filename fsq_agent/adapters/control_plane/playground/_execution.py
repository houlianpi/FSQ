# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Never

from pydantic import ValidationError

from fsq_agent._capability_bootstrap import build_capability_registry
from fsq_agent._run_ids import new_run_id
from fsq_agent._workspace_paths import resolve_workspace_cases_path
from fsq_agent.adapters.control_plane.playground import _recording as playground_recording
from fsq_agent.agent import FsqAgent
from fsq_agent.config import refresh_provider_settings, validate_runtime_settings, validate_strict_core_settings
from fsq_agent.core import (
    ArtifactStore,
    EvidenceRecorder,
    HarnessFactory,
    HarnessInterface,
    RuntimeSecretStore,
)
from fsq_agent.execution import (
    DynamicExecutionRequest,
    DynamicExecutionService,
    LifecycleExecutionRequest,
    LifecycleExecutionService,
    RecordingService,
    collect_strict_lifecycle_cases,
    run_strict_lifecycle_case,
)
from fsq_agent.fsq import FSQ_CASE_SUFFIX, FsqCaseLoader, FsqExecutableStepAdapter, is_fsq_case_file
from fsq_agent.models import CapabilityRegistrySnapshot, ConfigurationError, ExecutableStep, ReportArtifact, RunEvent, RunnerEvent, Task, TaskResult, VerificationResult
from fsq_agent.providers import build_ai_assertion_evaluator

if TYPE_CHECKING:
    from collections.abc import Callable

    from fsq_agent.adapters.control_plane.playground._state import PlaygroundState
    from fsq_agent.config import Settings


class PlaygroundTaskCancelledError(RuntimeError):
    pass


def refresh_execution_settings(settings: Settings) -> Settings:
    snapshot = settings.model_copy(deep=True)
    user_config_root = settings.openai_agents.user_config_root
    if user_config_root is None:
        return snapshot
    return refresh_provider_settings(snapshot, user_config_root)


@dataclass
class PlaygroundExecutionHandle:
    request_id: str
    thread: threading.Thread | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _loop: asyncio.AbstractEventLoop | None = None
    _task: asyncio.Task[None] | None = None
    _harness: Any | None = None
    _cancel_requested: bool = False

    def attach(self, loop: asyncio.AbstractEventLoop, task: asyncio.Task[None]) -> None:
        with self._lock:
            self._loop = loop
            self._task = task
            cancel_requested = self._cancel_requested
        if cancel_requested:
            loop.call_soon_threadsafe(task.cancel)

    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True
            loop = self._loop
            task = self._task
        if loop is not None and task is not None and not task.done():
            loop.call_soon_threadsafe(task.cancel)

    def bind_harness(self, harness: Any) -> None:
        with self._lock:
            self._harness = harness

    def clear_harness(self) -> None:
        with self._lock:
            self._harness = None

    def current_harness(self) -> Any | None:
        with self._lock:
            return self._harness


def start_dynamic_goal_execution(
    *,
    settings: Settings,
    state: PlaygroundState,
    request_id: str,
    goal: str | None = None,
    case_yaml_path: str | None = None,
    strict_case_yaml_path: str | None = None,
    device_id: str | None,
    record: bool = True,
    record_on_failure: bool = True,
) -> PlaygroundExecutionHandle:
    handle = PlaygroundExecutionHandle(request_id=request_id)
    thread = threading.Thread(
        target=_run_dynamic_task_thread,
        kwargs={
            "settings": settings,
            "state": state,
            "request_id": request_id,
            "goal": goal,
            "case_yaml_path": case_yaml_path,
            "strict_case_yaml_path": strict_case_yaml_path,
            "device_id": device_id,
            "record": record,
            "record_on_failure": record_on_failure,
            "handle": handle,
        },
        name=f"fsq-playground-{request_id}",
        daemon=True,
    )
    handle.thread = thread
    thread.start()
    return handle


def task_from_goal(goal: str) -> Task:
    normalized = " ".join(goal.split())
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "playground-goal"
    return Task(
        id=slug[:80],
        name=normalized,
        description=normalized,
        planning_reference_kind="goal",
        planning_reference_text=normalized,
    )


def task_from_case_yaml(path_text: str, settings: Settings) -> Task:
    source_path, content = _read_case_yaml_text(path_text, settings)
    display_path = str(source_path)
    name = f"Case reference: {source_path.name}"
    description = (
        "Run this raw FSQ YAML reference through dynamic LLM execution.\n\n"
        "The playground has not parsed this YAML into strict executable steps. "
        "Treat the full file content as advisory planning reference material.\n\n"
        f"Source path: {display_path}\n\n"
        "Raw file content:\n"
        f"{content}"
    )
    reference_text = f"Source path: {display_path}\n\nRaw file content:\n{content}"
    slug_source = source_path.name.removesuffix(FSQ_CASE_SUFFIX) or "case-yaml"
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-") or "case-yaml"
    return Task(
        id=slug[:80],
        name=name,
        description=description,
        planning_reference_kind="raw_case",
        planning_reference_text=reference_text,
    )


def _read_case_yaml_text(path_text: str, settings: Settings) -> tuple[Path, str]:
    requested = Path(path_text.strip())
    if not is_fsq_case_file(requested):
        raise ConfigurationError(f"FSQ case files must use the {FSQ_CASE_SUFFIX} suffix.")
    resolved = resolve_workspace_cases_path(requested, settings.cases.dir)
    if resolved.exists() and resolved.is_file():
        return resolved, resolved.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Case YAML not found: {path_text}")


def _run_dynamic_task(
    *,
    settings: Settings,
    state: PlaygroundState,
    request_id: str,
    goal: str | None,
    case_yaml_path: str | None,
    strict_case_yaml_path: str | None,
    device_id: str | None,
    record: bool,
    record_on_failure: bool,
    handle: PlaygroundExecutionHandle | None = None,
) -> None:
    asyncio.run(
        _run_dynamic_task_async(
            settings=settings,
            state=state,
            request_id=request_id,
            goal=goal,
            case_yaml_path=case_yaml_path,
            strict_case_yaml_path=strict_case_yaml_path,
            device_id=device_id,
            record=record,
            record_on_failure=record_on_failure,
            handle=handle,
        )
    )


def _run_dynamic_task_thread(
    *,
    handle: PlaygroundExecutionHandle,
    settings: Settings,
    state: PlaygroundState,
    request_id: str,
    goal: str | None,
    case_yaml_path: str | None,
    strict_case_yaml_path: str | None,
    device_id: str | None,
    record: bool,
    record_on_failure: bool,
) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task = loop.create_task(
        _run_dynamic_task_async(
            settings=settings,
            state=state,
            request_id=request_id,
            goal=goal,
            case_yaml_path=case_yaml_path,
            strict_case_yaml_path=strict_case_yaml_path,
            device_id=device_id,
            record=record,
            record_on_failure=record_on_failure,
            handle=handle,
        )
    )
    handle.attach(loop, task)
    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        state.request_cancel(request_id)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _run_dynamic_task_async(
    *,
    settings: Settings,
    state: PlaygroundState,
    request_id: str,
    goal: str | None,
    case_yaml_path: str | None,
    strict_case_yaml_path: str | None,
    device_id: str | None,
    record: bool,
    record_on_failure: bool,
    handle: PlaygroundExecutionHandle | None,
) -> None:
    run_settings = settings.model_copy(deep=True)
    if device_id and run_settings.harness.platform == "android":
        run_settings.harness.android.serial = device_id
    try:
        _raise_if_cancelled(state, request_id)
        execution_recordings: list[object] = []
        if goal:
            validate_runtime_settings(run_settings)
            task = task_from_goal(goal)
            result = await _run_agent_task_async(
                run_settings, state, request_id, task, handle, record=record, allow_recording_failure=record_on_failure,
                recording_sink=execution_recordings,
            )
        elif case_yaml_path:
            validate_runtime_settings(run_settings)
            task = task_from_case_yaml(case_yaml_path, run_settings)
            result = await _run_agent_task_async(
                run_settings, state, request_id, task, handle, record=record, allow_recording_failure=record_on_failure,
                recording_sink=execution_recordings,
            )
        elif strict_case_yaml_path:
            if handle is None:
                result = await asyncio.to_thread(_run_strict_case_yaml, run_settings, state, request_id, strict_case_yaml_path)
            else:
                result = await asyncio.to_thread(_run_strict_case_yaml, run_settings, state, request_id, strict_case_yaml_path, handle)
        else:
            _raise_missing_execution_source()
        if state.is_cancel_requested(request_id):
            return
        recording = None
        if execution_recordings:
            value = execution_recordings[0]
            recording = {
                "status": value.status, "recording_path": str(value.recording_path),
                "recorded_case_path": str(value.recorded_case_path) if value.recorded_case_path else None,
                "published_case_path": str(value.published_case_path) if value.published_case_path else None,
                "command_count": value.command_count, "required_runtime_secret_names": list(value.required_runtime_secret_names),
                "warnings": list(value.warnings), "skipped_tool_calls": list(value.skipped_tool_calls),
                "errors": list(value.errors), "validation_status": value.validation_status, "draft": value.draft,
            }
        state.finish_task(request_id, result, recording=recording)
    except asyncio.CancelledError:
        state.request_cancel(request_id)
        raise
    except PlaygroundTaskCancelledError:
        state.request_cancel(request_id)
    # Background task failures must be reflected in playground progress state.
    except Exception as exc:  # noqa: BLE001
        state.fail_task(request_id, exc)
    finally:
        if handle is not None:
            handle.clear_harness()


def _run_agent_task(settings: Settings, state: PlaygroundState, request_id: str, task: Task) -> TaskResult:
    return asyncio.run(_run_agent_task_async(settings, state, request_id, task))


async def _run_agent_task_async(
    settings: Settings,
    state: PlaygroundState,
    request_id: str,
    task: Task,
    handle: PlaygroundExecutionHandle | None = None,
    *,
    record: bool = False,
    allow_recording_failure: bool = False,
    recording_sink: list[object] | None = None,
) -> TaskResult:
    harness_factory = _preview_harness_factory(settings, handle) if handle is not None and settings.harness.platform in {"web", "windows", "macos"} else None
    agent = FsqAgent.from_settings(settings, harness_factory=harness_factory) if harness_factory is not None else FsqAgent.from_settings(settings)
    execution = await DynamicExecutionService(
        agent=agent, recording_service=RecordingService(recorder=playground_recording._record_dynamic_run_as_strict_case)
    ).execute(
        DynamicExecutionRequest(
            task=task, settings=settings, event_sink=_event_sink(state, request_id), record=record,
            allow_recording_failure=allow_recording_failure, publication_directory=settings.cases.dir,
            cancellation_check=lambda: _raise_if_cancelled(state, request_id),
        )
    )
    if recording_sink is not None and execution.recording is not None:
        recording_sink.append(execution.recording)
    return execution.task_result


def _raise_if_cancelled(state: PlaygroundState, request_id: str) -> None:
    if state.is_cancel_requested(request_id):
        raise PlaygroundTaskCancelledError("Cancelled by user.")


def _raise_missing_execution_source() -> Never:
    raise ValueError("goal, case_yaml_path, or strict_case_yaml_path is required")


def _run_strict_case_yaml(
    settings: Settings,
    state: PlaygroundState,
    request_id: str,
    path_text: str,
    handle: PlaygroundExecutionHandle | None = None,
) -> TaskResult:
    case_path = _resolve_case_yaml_path(path_text, settings)
    case = FsqCaseLoader().load_case(case_path)
    registry = build_capability_registry(platform=settings.harness.platform)
    registry_snapshot = registry.snapshot()
    lifecycle_cases = collect_strict_lifecycle_cases(case_path=case_path, case=case, settings=settings)
    for _lifecycle_path, lifecycle_case in lifecycle_cases:
        _validate_strict_case_platform(settings, lifecycle_case)
    requires_ai_assertion = any(_case_requires_ai_assertion(lifecycle_case, registry_snapshot) for _lifecycle_path, lifecycle_case in lifecycle_cases)
    resolved_steps_by_path = {
        lifecycle_path.resolve(): _resolve_strict_replay_steps(
            FsqExecutableStepAdapter(registry_snapshot=registry_snapshot).to_executable_steps(lifecycle_case),
            settings,
            registry_snapshot,
        )
        for lifecycle_path, lifecycle_case in lifecycle_cases
    }
    validate_strict_core_settings(settings, requires_ai_assertion=requires_ai_assertion)
    run_id = new_run_id(case.id)
    run_dir = Path(settings.output.runs_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    state.add_event(
        request_id,
        RunEvent(run_id=run_id, task_id=case.id, type="run_started", title="Strict YAML started", message=str(case_path)),
    )
    harness = _build_strict_harness(settings, case, run_dir, requires_ai_assertion)
    if handle is not None and settings.harness.platform in {"web", "windows", "macos"}:
        handle.bind_harness(harness)
    cancellable_harness = _CancellableHarness(harness, state, request_id)
    recorder = _PlaygroundEvidenceRecorder(run_id=run_id, output_dir=run_dir, state=state, request_id=request_id)
    artifact = LifecycleExecutionService(runner=run_strict_lifecycle_case).execute(
        LifecycleExecutionRequest(
            case_path=case_path, case=case, settings=settings, harness=cancellable_harness, output_dir=run_dir,
            run_id=run_id, registry=registry, registry_snapshot=registry_snapshot,
            post_action_delay_seconds=settings.execution.post_action_delay_seconds,
            runtime_secret_store=RuntimeSecretStore.from_settings(settings.runtime_secrets), recorder=recorder,
            resolve_steps=lambda steps, _case: _resolve_strict_replay_steps(steps, settings, registry_snapshot),
            resolved_steps_by_path=resolved_steps_by_path,
            cases_by_path={lifecycle_path.resolve(): lifecycle_case for lifecycle_path, lifecycle_case in lifecycle_cases},
            cancellation_check=lambda: _raise_if_cancelled(state, request_id),
        )
    ).report
    status, summary = _strict_report_status(artifact)
    state.add_event(
        request_id,
        RunEvent(
            run_id=run_id,
            task_id=case.id,
            type="run_completed",
            title="Strict YAML completed",
            message=summary,
            payload={"status": status, "report_path": str(artifact.path)},
        ),
    )
    return TaskResult(
        task_id=case.id,
        status="success" if status == "passed" else "failed",
        steps=[],
        verification=VerificationResult(status="success" if status == "passed" else "failed", summary=summary),
        report=ReportArtifact(run_id=run_id, path=artifact.path, evidence_manifest_path=artifact.evidence_manifest_path),
    )


class _CancellableHarness:
    def __init__(self, harness: Any, state: PlaygroundState, request_id: str) -> None:
        self._harness = harness
        self._state = state
        self._request_id = request_id

    def _check_cancelled(self) -> None:
        _raise_if_cancelled(self._state, self._request_id)

    def get_context(self):
        self._check_cancelled()
        return self._harness.get_context()

    def action_space(self):
        return self._harness.action_space()

    def before_action(self, step: ExecutableStep, context) -> None:
        self._check_cancelled()
        return self._harness.before_action(step, context)

    def invoke_action(self, step: ExecutableStep, context):
        self._check_cancelled()
        return self._harness.invoke_action(step, context)

    def after_action(self, step: ExecutableStep, context, action_result) -> None:
        self._check_cancelled()
        return self._harness.after_action(step, context, action_result)

    def capture_artifact(self, *args, **kwargs):
        self._check_cancelled()
        return self._harness.capture_artifact(*args, **kwargs)

    def classify_error(self, error: BaseException, phase, step: ExecutableStep):
        return self._harness.classify_error(error, phase, step)


def _resolve_case_yaml_path(path_text: str, settings: Settings) -> Path:
    requested = Path(path_text.strip())
    if not is_fsq_case_file(requested):
        raise ConfigurationError(f"FSQ case files must use the {FSQ_CASE_SUFFIX} suffix.")
    resolved = resolve_workspace_cases_path(requested, settings.cases.dir)
    if resolved.exists() and resolved.is_file():
        return resolved
    raise FileNotFoundError(f"Case YAML not found: {path_text}")


class _PlaygroundEvidenceRecorder(EvidenceRecorder):
    def __init__(self, *, run_id: str, output_dir: Path, state: PlaygroundState, request_id: str) -> None:
        super().__init__(run_id=run_id, output_dir=output_dir)
        self.state = state
        self.request_id = request_id

    def record_event(self, event: RunnerEvent) -> None:
        super().record_event(event)
        self._record_active_step(event)
        payload = event.payload or {}
        if event.event_type != "artifact_captured" or payload.get("kind") != "screenshot":
            return
        path = payload.get("path")
        if not isinstance(path, str):
            return
        self.state.set_preview(
            self.request_id,
            {
                "runId": event.run_id,
                "path": path,
                "timestamp": event.timestamp.isoformat(),
                "token": f"{event.run_id}:{path}:{event.timestamp.isoformat()}",
            },
        )

    def _record_active_step(self, event: RunnerEvent) -> None:
        if event.event_type != "step_start" or not event.step_id:
            return
        self.state.set_active_step(
            self.request_id,
            {
                "stepId": event.step_id,
                "stepIndex": _step_index_from_step_id(event.step_id),
            },
        )


def _step_index_from_step_id(step_id: str) -> int | None:
    match = re.search(r"-step-(\d+)$", step_id)
    if match is None:
        return None
    return int(match.group(1))


def _strict_report_status(artifact: ReportArtifact) -> tuple[str, str]:
    json_path = artifact.path.with_suffix(".json")
    # Any unreadable or malformed persisted report intentionally maps to the stable failed summary.
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        status = str(payload.get("summary", {}).get("status") or "failed")
        failed_steps = payload.get("summary", {}).get("failed_steps")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return "failed", "Strict YAML run completed but report status could not be read."
    else:
        return status, f"Strict YAML {status}; failed_steps={failed_steps}"


def _case_requires_ai_assertion(case, registry_snapshot: CapabilityRegistrySnapshot | None = None) -> bool:
    snapshot = registry_snapshot or build_capability_registry(platform=case.config.platform).snapshot()
    return any(step.action_name == "assert_with_ai" for step in FsqExecutableStepAdapter(registry_snapshot=snapshot).to_executable_steps(case))


def _resolve_strict_replay_steps(
    steps: list[ExecutableStep],
    settings: Settings,
    registry_snapshot: CapabilityRegistrySnapshot | None = None,
) -> list[ExecutableStep]:
    allowed_names = set(settings.runtime_secrets.allowed_env_names)
    snapshot = registry_snapshot or build_capability_registry(platform=settings.harness.platform).snapshot()
    resolved_steps = []
    for step in steps:
        _validate_runtime_secret_refs(step.params, allowed_names, step.step_id)
        _validate_resolved_params(step, step.params, snapshot)
        resolved_steps.append(step)
    return resolved_steps


def _validate_runtime_secret_refs(value: Any, allowed_names: set[str], step_id: str) -> None:
    for name in _collect_runtime_secret_refs(value):
        if name not in allowed_names:
            raise ValueError(f"Runtime secret name is not allowed for strict replay: {name}")


def _collect_runtime_secret_refs(value: Any) -> set[str]:
    names: set[str] = set()
    _collect_runtime_secret_refs_into(value, names)
    return names


def _collect_runtime_secret_refs_into(value: Any, names: set[str]) -> None:
    if isinstance(value, dict):
        text_type = value.get("textType")
        text = value.get("text")
        if text_type == "runtimeSecret" and isinstance(text, str) and text.strip():
            names.add(text.strip())
            return
        for item in value.values():
            _collect_runtime_secret_refs_into(item, names)
        return
    if isinstance(value, list):
        for item in value:
            _collect_runtime_secret_refs_into(item, names)


def _validate_resolved_params(step: ExecutableStep, params: dict[str, Any], registry_snapshot: CapabilityRegistrySnapshot) -> None:
    capability = registry_snapshot.resolve(step.action_name)
    if capability is None:
        return
    try:
        capability.params_model.model_validate(params)
    except ValidationError as exc:
        raise ValueError(f"Invalid strict replay command after runtime secret resolution: {step.step_id}") from exc


def _validate_strict_case_platform(settings: Settings, case) -> None:
    if case.config.platform == settings.harness.platform:
        return
    raise ValueError(f"Strict case platform {case.config.platform!r} does not match configured harness platform {settings.harness.platform!r}.")


def _build_strict_harness(settings: Settings, case, run_dir: Path, requires_ai_assertion: bool) -> Any:
    app_id = None
    if settings.harness.platform == "android":
        app_id = settings.harness.android.app_id or case.config.app_id or ""
        if not app_id:
            raise ValueError("Android app id is required for strict YAML runs.")
    return HarnessFactory().create_harness(
        platform=settings.harness.platform,
        harness_settings=settings.harness,
        artifact_store=ArtifactStore(run_dir=run_dir),
        ai_assertion_evaluator=build_ai_assertion_evaluator(settings) if requires_ai_assertion else None,
        runtime_secret_settings=settings.runtime_secrets,
        app_id=app_id,
    )


def _preview_harness_factory(settings: Settings, handle: PlaygroundExecutionHandle):
    def factory(run_id: str):
        if settings.harness.platform == "macos":
            harness = _build_macos_harness(
                settings,
                Path(settings.output.runs_dir) / run_id,
                requires_ai_assertion=True,
            )
        elif settings.harness.platform == "windows":
            harness = _build_windows_harness(
                settings,
                Path(settings.output.runs_dir) / run_id,
                requires_ai_assertion=True,
            )
        else:
            harness = _build_web_harness(
                settings,
                Path(settings.output.runs_dir) / run_id,
                requires_ai_assertion=True,
            )
        handle.bind_harness(harness)
        return harness

    return factory


def _build_web_harness(settings: Settings, run_dir: Path, *, requires_ai_assertion: bool) -> HarnessInterface:
    return _build_factory_harness(settings, run_dir, requires_ai_assertion=requires_ai_assertion)


def _build_windows_harness(settings: Settings, run_dir: Path, *, requires_ai_assertion: bool) -> HarnessInterface:
    return _build_factory_harness(settings, run_dir, requires_ai_assertion=requires_ai_assertion)


def _build_macos_harness(settings: Settings, run_dir: Path, *, requires_ai_assertion: bool) -> HarnessInterface:
    return _build_factory_harness(settings, run_dir, requires_ai_assertion=requires_ai_assertion)


def _build_factory_harness(settings: Settings, run_dir: Path, *, requires_ai_assertion: bool) -> HarnessInterface:
    return HarnessFactory().create_harness(
        platform=settings.harness.platform,
        harness_settings=settings.harness,
        artifact_store=ArtifactStore(run_dir=run_dir),
        ai_assertion_evaluator=build_ai_assertion_evaluator(settings) if requires_ai_assertion else None,
        runtime_secret_settings=settings.runtime_secrets,
        app_id=settings.harness.android.app_id,
    )


def _event_sink(state: PlaygroundState, request_id: str) -> Callable[[RunEvent], None]:
    def sink(event: RunEvent) -> None:
        if state.is_cancel_requested(request_id):
            return
        state.add_event(request_id, event)
        _preview = _preview_from_dynamic_event(event)
        if _preview is not None:
            state.set_preview(request_id, _preview)

    return sink


def _preview_from_dynamic_event(event: RunEvent) -> dict[str, object] | None:
    if event.type != "tool_call_completed":
        return None
    path = _latest_screenshot_artifact_path(event.payload)
    if path is None:
        return None
    timestamp = event.timestamp.isoformat()
    return {
        "runId": event.run_id,
        "path": path,
        "timestamp": timestamp,
        "token": f"{event.run_id}:{path}:{timestamp}",
    }


def _latest_screenshot_artifact_path(payload: dict[str, Any]) -> str | None:
    artifact_refs = payload.get("artifact_refs")
    if isinstance(artifact_refs, list):
        for artifact_ref in reversed(artifact_refs):
            if not isinstance(artifact_ref, dict) or artifact_ref.get("kind") != "screenshot":
                continue
            path = artifact_ref.get("path")
            if isinstance(path, str) and path:
                return path
    artifact_path = payload.get("artifact_path")
    if isinstance(artifact_path, str) and _looks_like_screenshot_path(artifact_path):
        return artifact_path
    return None


def _looks_like_screenshot_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return "/screenshots/" in normalized and normalized.endswith((".png", ".jpg", ".jpeg", ".webp"))
