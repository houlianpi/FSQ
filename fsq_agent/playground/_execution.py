from __future__ import annotations

import asyncio
import os
import json
from pathlib import Path
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import ValidationError

from fsq_agent._capability_bootstrap import build_capability_registry
from fsq_agent.agent import FsqAgent
from fsq_agent.config import Settings, validate_runtime_settings, validate_strict_core_settings
from fsq_agent.core import (
	AndroidHarness,
	AppiumMac2Driver,
	ArtifactStore,
	EvidenceRecorder,
	MacOSHarness,
	PlaywrightWebDriver,
	PywinautoWindowsDriver,
	StepRunner,
	StepSequenceRunner,
	UiAutomator2AndroidDriver,
	WebHarness,
	WindowsHarness,
)
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import CapabilityRegistrySnapshot, ExecutableStep, PostActionDelaySettings, ReportArtifact, RunEvent, RunnerEvent, RuntimeSecretRef, Task, TaskResult, VerificationResult
from fsq_agent.playground._recording import record_dynamic_result
from fsq_agent.playground._state import PlaygroundState
from fsq_agent.providers import build_ai_assertion_evaluator
from fsq_agent.report import CoreEvidenceReportGenerator


class PlaygroundTaskCancelled(RuntimeError):
	pass


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
	slug_source = source_path.stem or "case-yaml"
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
	candidates = []
	if requested.is_absolute():
		candidates.append(requested)
	else:
		candidates.append(settings.cases.dir / requested)
		candidates.append(Path.cwd() / requested)
	for candidate in candidates:
		if candidate.exists() and candidate.is_file():
			resolved = candidate.resolve()
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
		if goal:
			validate_runtime_settings(run_settings)
			task = task_from_goal(goal)
			result = await _run_agent_task_async(run_settings, state, request_id, task, handle)
		elif case_yaml_path:
			validate_runtime_settings(run_settings)
			task = task_from_case_yaml(case_yaml_path, run_settings)
			result = await _run_agent_task_async(run_settings, state, request_id, task, handle)
		elif strict_case_yaml_path:
			if handle is None:
				result = await asyncio.to_thread(_run_strict_case_yaml, run_settings, state, request_id, strict_case_yaml_path)
			else:
				result = await asyncio.to_thread(_run_strict_case_yaml, run_settings, state, request_id, strict_case_yaml_path, handle)
		else:
			raise ValueError("goal, case_yaml_path, or strict_case_yaml_path is required")
		if state.is_cancel_requested(request_id):
			return
		recording = None
		if not strict_case_yaml_path and record:
			recording = record_dynamic_result(run_settings, task, result, allow_failure=record_on_failure)
		state.finish_task(request_id, result, recording=recording)
	except asyncio.CancelledError:
		state.request_cancel(request_id)
		raise
	except PlaygroundTaskCancelled:
		state.request_cancel(request_id)
	except BaseException as exc:  # noqa: BLE001 - background failures must be visible through progress state.
		state.fail_task(request_id, exc)
	finally:
		if handle is not None:
			handle.clear_harness()


def _run_agent_task(settings: Settings, state: PlaygroundState, request_id: str, task: Task) -> TaskResult:
	return asyncio.run(
		_run_agent_task_async(settings, state, request_id, task)
	)


async def _run_agent_task_async(
	settings: Settings,
	state: PlaygroundState,
	request_id: str,
	task: Task,
	handle: PlaygroundExecutionHandle | None = None,
) -> TaskResult:
	harness_factory = _preview_harness_factory(settings, handle) if handle is not None and settings.harness.platform in {"web", "windows", "macos"} else None
	agent = FsqAgent.from_settings(settings, harness_factory=harness_factory) if harness_factory is not None else FsqAgent.from_settings(settings)
	return await agent.run(
		task,
		event_sink=_event_sink(state, request_id),
	)


def _raise_if_cancelled(state: PlaygroundState, request_id: str) -> None:
	if state.is_cancel_requested(request_id):
		raise PlaygroundTaskCancelled("Cancelled by user.")


def _run_strict_case_yaml(
	settings: Settings,
	state: PlaygroundState,
	request_id: str,
	path_text: str,
	handle: PlaygroundExecutionHandle | None = None,
) -> TaskResult:
	case_path = _resolve_case_yaml_path(path_text, settings)
	case = FsqCaseLoader().load_case(case_path)
	_validate_strict_case_platform(settings, case)
	registry = build_capability_registry(platform=settings.harness.platform)
	registry_snapshot = registry.snapshot()
	requires_ai_assertion = _case_requires_ai_assertion(case, registry_snapshot)
	validate_strict_core_settings(settings, requires_ai_assertion=requires_ai_assertion)
	run_id = case.id
	run_dir = Path(settings.output.runs_dir) / run_id
	state.add_event(
		request_id,
		RunEvent(run_id=run_id, task_id=case.id, type="run_started", title="Strict YAML started", message=str(case_path)),
	)
	steps = _resolve_strict_replay_steps(
		FsqExecutableStepAdapter(registry_snapshot=registry_snapshot).to_executable_steps(case),
		settings,
		registry_snapshot,
	)
	harness = _build_strict_harness(settings, case, run_dir, requires_ai_assertion)
	if handle is not None and settings.harness.platform in {"web", "windows", "macos"}:
		handle.bind_harness(harness)
	cancellable_harness = _CancellableHarness(harness, state, request_id)
	artifact = _run_strict_core_steps(
		case_path=case_path,
		harness=cancellable_harness,
		output_dir=run_dir,
		run_id=run_id,
		steps=steps,
		registry=registry,
		post_action_delay_seconds=settings.execution.post_action_delay_seconds,
		state=state,
		request_id=request_id,
	)
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
	candidates = [requested] if requested.is_absolute() else [settings.cases.dir / requested, Path.cwd() / requested]
	for candidate in candidates:
		if candidate.exists() and candidate.is_file():
			return candidate.resolve()
	raise FileNotFoundError(f"Case YAML not found: {path_text}")


def _run_strict_core_steps(
	*,
	case_path: Path,
	harness: Any,
	output_dir: Path,
	run_id: str,
	steps: list[ExecutableStep],
	registry,
	post_action_delay_seconds: PostActionDelaySettings,
	state: PlaygroundState,
	request_id: str,
) -> ReportArtifact:
	normal_steps, teardown_steps = _split_trailing_teardown_steps(steps)
	recorder = _PlaygroundEvidenceRecorder(run_id=run_id, output_dir=output_dir, state=state, request_id=request_id)
	StepSequenceRunner(
		step_runner=StepRunner(
			harness=harness,
			capability_registry=registry,
			post_action_delay_seconds=post_action_delay_seconds,
		),
		evidence_recorder=recorder,
	).run_steps(run_id=run_id, steps=normal_steps, teardown_steps=teardown_steps)
	manifest_path = recorder.write_manifest()
	return CoreEvidenceReportGenerator().generate_from_manifest(manifest_path)


class _PlaygroundEvidenceRecorder(EvidenceRecorder):
	def __init__(self, *, run_id: str, output_dir: Path, state: PlaygroundState, request_id: str) -> None:
		super().__init__(run_id=run_id, output_dir=output_dir)
		self.state = state
		self.request_id = request_id

	def record_event(self, event: RunnerEvent) -> None:
		super().record_event(event)
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


def _split_trailing_teardown_steps(steps: list[ExecutableStep]) -> tuple[list[ExecutableStep], list[ExecutableStep]]:
	split_at = len(steps)
	while split_at > 0 and steps[split_at - 1].kind == "teardown":
		split_at -= 1
	return steps[:split_at], steps[split_at:]


def _strict_report_status(artifact: ReportArtifact) -> tuple[str, str]:
	json_path = artifact.path.with_suffix(".json")
	try:
		payload = json.loads(json_path.read_text(encoding="utf-8"))
		status = str(payload.get("summary", {}).get("status") or "failed")
		failed_steps = payload.get("summary", {}).get("failed_steps")
		return status, f"Strict YAML {status}; failed_steps={failed_steps}"
	except Exception:
		return "failed", "Strict YAML run completed but report status could not be read."


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
		resolved_params = _resolve_replay_value(step.params, allowed_names, step.step_id)
		_validate_resolved_params(step, resolved_params, snapshot)
		resolved_steps.append(step.model_copy(update={"params": resolved_params}))
	return resolved_steps


def _resolve_replay_value(value: Any, allowed_names: set[str], step_id: str) -> Any:
	ref = _as_runtime_secret_ref(value)
	if ref is not None:
		if ref.env_name not in allowed_names:
			raise ValueError(f"Runtime secret name is not allowed for strict replay: {ref.env_name}")
		secret_value = os.getenv(ref.env_name)
		if not secret_value:
			raise ValueError(f"Runtime secret is not set for strict replay: {ref.env_name}")
		return secret_value
	if isinstance(value, dict):
		return {key: _resolve_replay_value(item, allowed_names, step_id) for key, item in value.items()}
	if isinstance(value, list):
		return [_resolve_replay_value(item, allowed_names, step_id) for item in value]
	return value


def _as_runtime_secret_ref(value: Any) -> RuntimeSecretRef | None:
	if isinstance(value, RuntimeSecretRef):
		return value
	if isinstance(value, dict) and set(value) == {"runtimeSecret"}:
		try:
			return RuntimeSecretRef.model_validate(value)
		except ValidationError as exc:
			raise ValueError("Invalid runtimeSecret replay reference.") from exc
	return None


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
	raise ValueError(
		f"Strict case platform {case.config.platform!r} does not match configured harness platform {settings.harness.platform!r}."
	)


def _build_strict_harness(settings: Settings, case, run_dir: Path, requires_ai_assertion: bool) -> Any:
	if settings.harness.platform == "android":
		app_id = settings.harness.android.app_id or case.config.app_id or ""
		if not app_id:
			raise ValueError("Android app id is required for strict YAML runs.")
		return AndroidHarness(
			driver=UiAutomator2AndroidDriver(app_id=app_id, serial=settings.harness.android.serial),
			artifact_store=ArtifactStore(run_dir=run_dir),
			ai_assertion_evaluator=build_ai_assertion_evaluator(settings) if requires_ai_assertion else None,
			runtime_secret_settings=settings.runtime_secrets,
		)
	if settings.harness.platform == "web":
		return _build_web_harness(settings, run_dir, requires_ai_assertion=requires_ai_assertion)
	if settings.harness.platform == "windows":
		return _build_windows_harness(settings, run_dir, requires_ai_assertion=requires_ai_assertion)
	if settings.harness.platform == "macos":
		return _build_macos_harness(settings, run_dir, requires_ai_assertion=requires_ai_assertion)
	raise ValueError(f"Unsupported harness platform: {settings.harness.platform}")


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


def _build_web_harness(settings: Settings, run_dir: Path, *, requires_ai_assertion: bool) -> WebHarness:
	web = settings.harness.web
	viewport = (web.viewport_width, web.viewport_height) if web.viewport_width is not None and web.viewport_height is not None else None
	return WebHarness(
		driver=PlaywrightWebDriver(
			channel=web.channel,
			executable_path=web.browser_executable_path,
			headless=web.headless,
			base_url=web.base_url,
			viewport=viewport,
		),
		artifact_store=ArtifactStore(run_dir=run_dir),
		ai_assertion_evaluator=build_ai_assertion_evaluator(settings) if requires_ai_assertion else None,
		runtime_secret_settings=settings.runtime_secrets,
	)


def _build_windows_harness(settings: Settings, run_dir: Path, *, requires_ai_assertion: bool) -> WindowsHarness:
	windows = settings.harness.windows
	return WindowsHarness(
		driver=PywinautoWindowsDriver(
			app_path=windows.app_path,
			backend_kind=windows.backend_kind,
			window_title_re=windows.window_title_re,
			launch_args=windows.launch_args,
		),
		artifact_store=ArtifactStore(run_dir=run_dir),
		ai_assertion_evaluator=build_ai_assertion_evaluator(settings) if requires_ai_assertion else None,
		runtime_secret_settings=settings.runtime_secrets,
	)


def _build_macos_harness(settings: Settings, run_dir: Path, *, requires_ai_assertion: bool) -> MacOSHarness:
	macos = settings.harness.macos
	return MacOSHarness(
		driver=AppiumMac2Driver(
			server_url=macos.appium_server_url or "",
			bundle_id=macos.bundle_id,
			app_path=macos.app_path,
			page_source_max_depth=macos.page_source_max_depth,
			action_timeout_seconds=macos.action_timeout_seconds,
		),
		artifact_store=ArtifactStore(run_dir=run_dir),
		ai_assertion_evaluator=build_ai_assertion_evaluator(settings) if requires_ai_assertion else None,
		runtime_secret_settings=settings.runtime_secrets,
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


